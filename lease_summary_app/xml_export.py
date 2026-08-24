"""
XML Export for SeedJura Agreement Summary
==========================================
Exports extracted field data into the GlobalFormVars XML format
compatible with the existing form system.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict


# Mapping from internal field names to XML element names.
# Where names differ between the tool and the XML schema, this handles the translation.
# Fields not in this map are passed through as-is if they exist in the XML schema.
FIELD_TO_XML_MAP = {
    "OPEX_Inclusion": "OPEX_Inclusions",
    "OPEX_Exclusion": "OPEX_Exclusions",
    "Date_Commencment": "Date_Commencement",
    "Early_Termination_Description": None,  # Split into two fields below
}

# The canonical list of XML element names in the GlobalFormVars schema,
# in alphabetical order matching the target format.
XML_FIELDS = [
    "Amt_Security_Deposit",
    "Assignment_3rd_Parties",
    "Assignment_Affiliates",
    "Assignment_Change_Control",
    "Assignment_LL_Decision",
    "Assignment_Other_Terms",
    "Assignment_Process_Fee",
    "Assignment_Recapture_Space",
    "Assignment_Rent_Profit",
    "Base_Year",
    "Broker_Landlord_Name",
    "Broker_Tenant_Name",
    "Date_Commencement",
    "Date_EarlyAccess",
    "Date_Expiration",
    "Date_Lease",
    "Early_Termination_LL_Description",
    "Early_Termination_Tenant_Description",
    "Estoppel_Details",
    "Estoppel_Return_Period",
    "Expansion_Description",
    "Expansion_Space",
    "Fees_Management",
    "Gross_Up_Percent_Language",
    "Guarantor_Name",
    "Guarantor_StReg",
    "Guarantor_Type",
    "Guaranty_Term",
    "Holdover_Rent",
    "Landlord_Repair_Obligations",
    "Lease_Summary_Date",
    "Lease_Summary_Preparer",
    "Lease_Summary_Purpose",
    "LeaseAgr_Amendments",
    "LeaseAgr_Name",
    "OPEX_Exclusions",
    "OPEX_Inclusions",
    "Other_Rights",
    "Parking_Reserved_Amt_Fees",
    "Parking_Reserved_Spaces",
    "Parking_Unreserved_Amt_Fees",
    "Parking_Unreserved_Spaces",
    "Permitted_Use_Description",
    "Premises_SqFt",
    "Premises_UnitNumber_Description",
    "Purchase_Option_Description",
    "Purchase_Option_Space",
    "Reduction_Description",
    "Relocation_Cost",
    "Relocation_Language",
    "Relocation_Notice_Period",
    "Relocation_Rights",
    "Relocation_Termination_Rights",
    "Renewal_Option_Numbers",
    "Renewal_Option_Period_PerOption",
    "Rent_Abatement_Additional_Rent",
    "Rent_Abatement_Base_Rent",
    "Rent_Abatement_Commencement",
    "Rent_Abatement_Duration",
    "Rent_Abatement_Expiration",
    "Rent_Abatement_Qualifier",
    "Rent_AnnualIncrease_Percentage",
    "Rent_BaseRent_Amt",
    "Rent_BaseRent_Monthly",
    "Rent_PercentageRent_Percent",
    "Rent_PercentageRent_ThresholdAmt",
    "ROFO_Description",
    "ROFO_Space",
    "ROFR_Description",
    "ROFR_Space",
    "Signage_Allowed",
    "Signage_Approval_Required",
    "Signage_Location",
    "Signage_Removal",
    "Signage_Renovation_Replacement",
    "Signage_Type",
    "SNDA_Required_by_Lender_Provision",
    "SNDA_Subject_Existing_GroundLease",
    "SNDA_Subject_Existing_Mortgages",
    "SNDA_Subject_Future_GroundLease",
    "SNDA_Subject_Future_Mortgages",
    "Sublease_Terms",
    "Tenant_Address_1",
    "Tenant_Address_2",
    "Tenant_Address_City",
    "Tenant_Address_State",
    "Tenant_Address_Zip",
    "Tenant_Allowance_PSF",
    "Tenant_Allowance_Total",
    "Tenant_Attn",
    "Tenant_DBA",
    "Tenant_Email",
    "Tenant_Improvements_Description",
    "Tenant_Insurance",
    "Tenant_Name",
    "Tenant_Repair_Obligations",
    "Tenant_Share_Percentage",
    "Tenant_StReg",
    "Tenant_Type",
    "Utilities",
]


def _split_early_termination(value: str) -> tuple:
    """
    Split the combined Early_Termination_Description into landlord and tenant parts.
    Looks for patterns like "Landlord:" / "Tenant:" or "Landlord may" / "Tenant may".
    If it can't split, puts the full text in both fields.
    """
    if not value or value.strip().lower() in ('none', 'none.', 'n/a'):
        return ("", "")

    val_lower = value.lower()

    # Try to find a landlord/tenant split point
    # Common patterns: "Landlord:" "Tenant:", or "Landlord may" / "Tenant may"
    ll_markers = ["landlord:", "landlord may", "landlord has", "landlord shall have the right"]
    tn_markers = ["tenant:", "tenant may", "tenant has", "tenant shall have the right"]

    ll_pos = -1
    tn_pos = -1

    for marker in ll_markers:
        pos = val_lower.find(marker)
        if pos >= 0:
            ll_pos = pos
            break

    for marker in tn_markers:
        pos = val_lower.find(marker)
        if pos >= 0:
            tn_pos = pos
            break

    if ll_pos >= 0 and tn_pos >= 0:
        if ll_pos < tn_pos:
            ll_text = value[ll_pos:tn_pos].strip().rstrip(";.,")
            tn_text = value[tn_pos:].strip()
        else:
            tn_text = value[tn_pos:ll_pos].strip().rstrip(";.,")
            ll_text = value[ll_pos:].strip()
        return (ll_text, tn_text)

    # Can't split — put in both
    return (value, value)


def field_data_to_xml(field_data: Dict[str, str], normalized_dates: Dict[str, str] = None) -> str:
    """
    Convert extracted field data dict to the GlobalFormVars XML format.
    Returns XML string.
    normalized_dates: optional dict of {field_name: "mm/dd/yyyy"}
    """
    if normalized_dates is None:
        normalized_dates = {}

    # Build a lookup that maps XML field names to values
    xml_values = {}
    xml_dates = {}  # Normalized dates keyed by XML field name

    for internal_name, value in field_data.items():
        if not value:
            continue

        # Check if this field needs name mapping
        if internal_name in FIELD_TO_XML_MAP:
            xml_name = FIELD_TO_XML_MAP[internal_name]
            if xml_name is None:
                continue
            xml_values[xml_name] = value
            if internal_name in normalized_dates:
                xml_dates[xml_name] = normalized_dates[internal_name]
        else:
            xml_values[internal_name] = value
            if internal_name in normalized_dates:
                xml_dates[internal_name] = normalized_dates[internal_name]

    # Handle Early_Termination split
    et_value = field_data.get("Early_Termination_Description", "")
    if et_value:
        ll_text, tn_text = _split_early_termination(et_value)
        xml_values["Early_Termination_LL_Description"] = ll_text
        xml_values["Early_Termination_Tenant_Description"] = tn_text

    # Build XML
    root = ET.Element("GlobalFormVars")

    for xml_field in XML_FIELDS:
        elem = ET.SubElement(root, xml_field)
        val = xml_values.get(xml_field, "")
        # Clean "None." values — leave empty in XML
        if val.strip().lower() in ('none', 'none.', 'n/a', 'not applicable'):
            val = ""
        elem.text = val if val else None
        # Add normalized date as attribute if available
        if xml_field in xml_dates:
            elem.set("normalized_date", xml_dates[xml_field])

    # Generate XML string with declaration
    rough_string = ET.tostring(root, encoding="unicode", xml_declaration=False)
    xml_string = '<?xml version="1.0" encoding="utf-8"?>' + rough_string

    return xml_string


def field_data_to_xml_pretty(field_data: Dict[str, str], normalized_dates: Dict[str, str] = None) -> str:
    """
    Same as field_data_to_xml but with pretty-printing for readability.
    """
    xml_str = field_data_to_xml(field_data, normalized_dates)
    # Parse and pretty-print
    dom = minidom.parseString(xml_str)
    pretty = dom.toprettyxml(indent="  ", encoding=None)
    # Remove the extra declaration minidom adds
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="utf-8"?>'
    return "\n".join(lines)
