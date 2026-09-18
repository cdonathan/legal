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


def field_data_to_xml(
    field_data: Dict[str, str],
    normalized_dates: Dict[str, str] = None,
    xml_fields: list = None,
) -> str:
    """
    Convert extracted field data dict to the GlobalFormVars XML format.
    Returns XML string.
    normalized_dates: optional dict of {field_name: "mm/dd/yyyy"}

    xml_fields: the ordered list of base field names to emit as top-level
    XML elements. Defaults to XML_FIELDS (the lease schema) for backward
    compatibility. Pass an agreement type's own field list (e.g.
    list(agr.fields.keys())) for non-lease types (like PSA) so their real
    field names appear in the output instead of silently being dropped
    because they don't match the lease's fixed schema, or mixed in with
    lease-only fields that don't apply.

    Every base field in xml_fields is emitted along with its two companion
    variables:
      <FieldName>       -- base value
      <FieldName_Int>   -- Interpretation (precise/latest value + section ref)
      <FieldName_Raw>   -- Raw Data (verbatim copy/paste, all historical
                            versions with document + section references)
    """
    if normalized_dates is None:
        normalized_dates = {}
    if xml_fields is None:
        xml_fields = XML_FIELDS

    # FIELD_TO_XML_MAP and the Early_Termination split below are quirks of
    # the lease schema specifically (renaming a couple of internal field
    # names, and splitting one combined field into two). They only apply
    # when emitting the default lease schema - a non-lease type (e.g. PSA)
    # has its own field names already and none of this remapping is
    # meaningful for it.
    using_lease_schema = xml_fields is XML_FIELDS

    # Build a lookup that maps XML field names to values
    xml_values = {}
    xml_dates = {}  # Normalized dates keyed by XML field name

    for internal_name, value in field_data.items():
        if not value:
            continue

        # Split off any _Int/_Raw suffix so we can remap the base name and
        # re-attach the same suffix afterward.
        suffix = ""
        base_internal = internal_name
        for s in ("_Int", "_Raw"):
            if internal_name.endswith(s):
                suffix = s
                base_internal = internal_name[: -len(s)]
                break

        # Check if this field needs name mapping (lease schema only)
        if using_lease_schema and base_internal in FIELD_TO_XML_MAP:
            xml_base = FIELD_TO_XML_MAP[base_internal]
            if xml_base is None:
                continue
        else:
            xml_base = base_internal

        xml_name = f"{xml_base}{suffix}"
        xml_values[xml_name] = value
        if not suffix and base_internal in normalized_dates:
            xml_dates[xml_name] = normalized_dates[base_internal]

    if using_lease_schema:
        # Handle Early_Termination split (base value only; _Int/_Raw pass
        # through under their own already-mapped names since
        # Early_Termination_Description isn't in XML_FIELDS as a bare field)
        et_value = field_data.get("Early_Termination_Description", "")
        if et_value:
            ll_text, tn_text = _split_early_termination(et_value)
            xml_values["Early_Termination_LL_Description"] = ll_text
            xml_values["Early_Termination_Tenant_Description"] = tn_text
        for suffix in ("_Int", "_Raw"):
            et_variant = field_data.get(f"Early_Termination_Description{suffix}", "")
            if et_variant:
                ll_text, tn_text = _split_early_termination(et_variant)
                xml_values[f"Early_Termination_LL_Description{suffix}"] = ll_text
                xml_values[f"Early_Termination_Tenant_Description{suffix}"] = tn_text

    # Build XML
    root = ET.Element("GlobalFormVars")

    def _clean(val):
        if val.strip().lower() in ('none', 'none.', 'n/a', 'not applicable'):
            return ""
        return val

    for xml_field in xml_fields:
        for suffix in ("", "_Int", "_Raw"):
            name = f"{xml_field}{suffix}"
            elem = ET.SubElement(root, name)
            val = _clean(xml_values.get(name, ""))
            elem.text = val if val else None
            # Add normalized date as attribute if available (base field only)
            if not suffix and xml_field in xml_dates:
                elem.set("normalized_date", xml_dates[xml_field])

    # Generate XML string with declaration
    rough_string = ET.tostring(root, encoding="unicode", xml_declaration=False)
    xml_string = '<?xml version="1.0" encoding="utf-8"?>' + rough_string

    return xml_string


def field_data_to_xml_pretty(
    field_data: Dict[str, str],
    normalized_dates: Dict[str, str] = None,
    xml_fields: list = None,
) -> str:
    """
    Same as field_data_to_xml but with pretty-printing for readability.
    """
    xml_str = field_data_to_xml(field_data, normalized_dates, xml_fields=xml_fields)
    # Parse and pretty-print
    dom = minidom.parseString(xml_str)
    pretty = dom.toprettyxml(indent="  ", encoding=None)
    # Remove the extra declaration minidom adds
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="utf-8"?>'
    return "\n".join(lines)
