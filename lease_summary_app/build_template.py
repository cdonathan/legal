"""
Template Rebuild Script
==========================
One-time (re-runnable) build tool that regenerates
SeedJura_Lease_Summary_FORM.docx with the new 4-column table layout:

    No. | Categories | Interpretation | Raw Data

For every field, the Interpretation column carries the [!@Field_Int]
placeholder and the Raw Data column carries the [!@Field_Raw] placeholder
(matching the suffix convention consumed by field_variants.py /
populate_template()). The "No." column is now populated with a literal,
sequential row number per table (the app never wrote to it before).

Run:
    python build_template.py

This overwrites SeedJura_Lease_Summary_FORM.docx in this directory.
A timestamped backup of the previous file is kept alongside it.
"""

import os
import re
import shutil
from datetime import datetime

import docx
from docx import Document
from docx.shared import Pt, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(HERE, "SeedJura_Lease_Summary_FORM.docx")

FONT_NAME = "Arial"
FONT_SIZE = Pt(10)

HEADER_FILL_MAIN = "F1A983"   # Table 0 header (No./Categories/Interpretation/Raw Data)
HEADER_FILL_SUB = "FAE2D5"    # Table 1 (OPEX) / Table 2 (Other Provisions) headers

COL_WIDTHS = [Emu(450000), Emu(1950000), Emu(2900000), Emu(2900000)]

# Authoring-hint paragraphs that leaked into real output as literal text
# in the old template (they matched no placeholder so were never replaced).
# These are dropped when rebuilding rows - "None" is the correct way to
# express "no data" everywhere now.
_HINT_PATTERN = re.compile(r"^\(\s*e\.?g\.?,?.*\)$", re.IGNORECASE)


def _is_hint_paragraph(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if _HINT_PATTERN.match(t):
        return True
    if t.lower() in ("(yes or no)",):
        return True
    return False


def _placeholder_variant(text: str, suffix: str) -> str:
    """Rewrite every [!@Field] / [*Field] token in text to [!@Field_Int] etc."""
    def repl(m):
        prefix, name = m.group(1), m.group(2)
        return f"[{prefix}{name}{suffix}]"
    return re.sub(r"\[(!@|\*)([A-Za-z0-9_]+)\]", repl, text)


def _set_cell_shading(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _write_cell(cell, paragraphs, bold=False, header=False):
    """Replace a cell's contents with the given list of paragraph strings."""
    # Clear existing paragraphs except the first (python-docx requires >=1)
    cell.text = ""
    first = True
    paras = paragraphs if paragraphs else [""]
    for i, text in enumerate(paras):
        p = cell.paragraphs[0] if first else cell.add_paragraph()
        first = False
        if header:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.font.name = FONT_NAME
        run.font.size = FONT_SIZE
        run.bold = bold


def _set_col_widths(table, widths):
    table.autofit = False
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            cell.width = widths[idx]
    for idx, col in enumerate(table.columns):
        col.width = widths[idx]


def _build_table(doc, insert_before_element, header_fill, rows_spec, no_start=1):
    """
    Build a brand-new 4-column table and insert it into the document body
    immediately before insert_before_element. rows_spec is a list of
    (category_paragraphs, interpretation_paragraphs, raw_paragraphs, is_divider).
    Returns the new table.
    """
    table = doc.add_table(rows=1 + len(rows_spec), cols=4)
    table.style = doc.tables[0].style if doc.tables else None
    # python-docx add_table appends to the end of the body; move it into place.
    tbl_element = table._tbl
    insert_before_element.addprevious(tbl_element)

    # Header row
    header_cells = table.rows[0].cells
    headers = ["No.", "Categories", "Interpretation", "Raw Data"]
    for i, htext in enumerate(headers):
        _write_cell(header_cells[i], [htext], bold=True, header=True)
        _set_cell_shading(header_cells[i], header_fill)
    for cell in table.rows[0].cells:
        cell.vertical_alignment = 1  # center-ish; harmless if unsupported

    # Data rows
    row_num = no_start
    for cat_paras, int_paras, raw_paras, is_divider in rows_spec:
        r = table.rows[row_num - no_start + 1]
        _write_cell(r.cells[0], [str(row_num) + "."], bold=True)
        _write_cell(r.cells[1], cat_paras, bold=True)
        _write_cell(r.cells[2], int_paras)
        _write_cell(r.cells[3], raw_paras)
        row_num += 1

    _set_col_widths(table, COL_WIDTHS)
    return table, row_num


def _row(category, fields, wrap=None):
    """
    Build a (category_paragraphs, interpretation_paragraphs, raw_paragraphs,
    is_divider) tuple for a normal data row.

    category: str or list[str] -- the Categories column label(s)
    fields: list[str] -- bare field names; one placeholder paragraph per field,
            OR if wrap is given, fields are substituted into the wrap template(s).
    wrap: optional list[str] template strings containing {F0}, {F1}, ... tokens
          that get replaced with the [!@Field_Int]/[!@Field_Raw] placeholder
          for fields[0], fields[1], etc. Any hint-only lines are dropped.
    """
    cat_paras = category if isinstance(category, list) else [category]

    if wrap:
        int_paras, raw_paras = [], []
        for line in wrap:
            if _is_hint_paragraph(line):
                continue
            int_line = line
            raw_line = line
            for i, f in enumerate(fields):
                int_line = int_line.replace(f"{{F{i}}}", f"[!@{f}_Int]")
                raw_line = raw_line.replace(f"{{F{i}}}", f"[!@{f}_Raw]")
            int_paras.append(int_line)
            raw_paras.append(raw_line)
    else:
        int_paras = [f"[!@{f}_Int]" for f in fields]
        raw_paras = [f"[!@{f}_Raw]" for f in fields]

    return (cat_paras, int_paras, raw_paras, False)


def _divider(category):
    cat_paras = category if isinstance(category, list) else [category]
    return (cat_paras, [], [], True)


# =============================================================================
# TABLE A - Main summary table
# =============================================================================

TABLE_A_ROWS = [
    _row("Property/Project Name", ["Property_Name"]),
    _row("Property/Project Address", ["Property_Address_1", "Property_Address_2", "Property_Address_City",
                                       "Property_Address_State", "Property_Address_Zip"]),
    _row("Owner Name", ["Owner_Name", "Owner_StReg", "Owner_Type"]),
    _row("Tenant Name", ["Tenant_Name", "Tenant_StReg", "Tenant_Type", "Tenant_DBA"]),
    _row("Tenant Address", ["Tenant_Address_1", "Tenant_Address_2", "Tenant_Address_City",
                             "Tenant_Address_State", "Tenant_Address_Zip", "Tenant_Attn", "Tenant_Email"]),
    _row("Tenant Notice Copy To", ["Tenant_CopyTo_Address_1", "Tenant_CopyTo_Address_2",
                                    "Tenant_CopyTo_Address_City", "Tenant_CopyTo_Address_State",
                                    "Tenant_CopyTo_Address_Zip", "Tenant_CopyTo_Attn", "Tenant_CopyTo_Email"]),
    _row("Suite Number", ["Premises_UnitNumber_Description"]),
    _row("Premises", ["Premises_SqFt"]),
    _row("Leases and Amendments References", ["LeaseAgr_Name", "LeaseAgr_Amendments"]),
    _row("Commencement Date", ["Date_Lease"]),
    _row("Effective Date", ["Amendment_Effective_Date"]),
    _row("Termination Date", ["Date_Termination"]),
    _row("Opening Date", ["Date_Opening"]),
    _row(["Lease Term and", "Expiration Date"], ["Lease_Term", "Date_Expiration"]),
    _row("Early Access", ["Date_EarlyAccess"]),
    _row("Renewal Options", ["Renewal_Option_Numbers", "Renewal_Option_Period_PerOption"],
         wrap=["{F0}, {F1}"]),
    _row("Security Deposit", ["Amt_Security_Deposit"]),
    _divider("Base Rent"),
    _row("Base Rent \u2013 Per Sq. Ft. and Annual:", ["Rent_BaseRent_PSF", "Rent_BaseRent_Amt"],
         wrap=["{F0} per sq. ft.", "{F1} annually"]),
    _row("Base Rent \u2013 Monthly:", ["Rent_BaseRent_Monthly"]),
    _row("Base Rent \u2013 Increase:", ["Rent_AnnualIncrease_Percentage"]),
    _row("Base Year", ["Base_Year"]),
    _divider("Rent Abatement"),
    _row("Rent - Abatement Commencement:", ["Rent_Abatement_Commencement"]),
    _row("Rent - Abatement Expiration:", ["Rent_Abatement_Expiration"]),
    _row("Rent - Abatement Term:", ["Rent_Abatement_Duration"]),
    _row("Rent Abatement Included or Amt:", ["Rent_Abatement_Base_Rent", "Rent_Abatement_Additional_Rent"],
         wrap=["Base Rent = {F0}", "Additional Rent = {F1}"]),
    _row("Rent Abatement Qualifier:", ["Rent_Abatement_Qualifier"]),
    _row("Tenant's Percentage Share", ["Tenant_Share_Percentage"]),
    _row("Tenant's Share Amount ($)", ["Tenant_Share_Amount"]),
    _row("Percentage Rent", ["Rent_PercentageRent_ThresholdAmt", "Rent_PercentageRent_Percent"]),
    _row("Tenant Allowance", ["Tenant_Allowance_PSF", "Tenant_Allowance_Total"],
         wrap=["Per Sq. Ft. = {F0}", "Total = {F1}"]),
    _row("Additional TI Funds", ["Tenant_Allowance_Additional"]),
    _row("Permitted Use", ["Permitted_Use_Description"]),
    _row("Parking", ["Parking_Reserved_Spaces", "Parking_Unreserved_Spaces"],
         wrap=["Reserved = {F0}", "Unreserved = {F1}"]),
    _row("Parking Charges", ["Parking_Reserved_Amt_Fees", "Parking_Unreserved_Amt_Fees"],
         wrap=["Reserved = {F0}", "Unreserved = {F1}"]),
    _row("Guarantor", ["Guarantor_Name", "Guarantor_StReg", "Guarantor_Type"]),
    _row("Guarantor Term", ["Guaranty_Term"]),
    _row("Broker", ["Broker_Landlord_Name", "Broker_Tenant_Name"]),
    _row("Landlord\u2019s Work / Tenant Improvement", ["Tenant_Improvements_Description"]),
    _row("ROFR Option", ["ROFR_Space", "ROFR_Description"]),
    _row("ROFO Option", ["ROFO_Space", "ROFO_Description"]),
    _row("Expansion Option", ["Expansion_Space", "Expansion_Description"]),
    _row("Early Termination Option", ["Early_Termination_Description"]),
    _row("Reduction Option", ["Reduction_Description"]),
    _row("Purchase Option", ["Purchase_Option_Space", "Purchase_Option_Description"]),
]

# =============================================================================
# TABLE B - OPEX Items
# =============================================================================

TABLE_B_ROWS = [
    _row("OPEX Inclusions:", ["OPEX_Inclusion"]),
    _row("OPEX Exclusions:", ["OPEX_Exclusion"]),
    _row("Utilities:", ["Utilities"]),
    _row("Admin / Management / Accounting Fees:", ["Fees_Management"]),
    _row("Gross Up %:", ["Gross_Up_Percent_Language"]),
]

# =============================================================================
# TABLE C - Other Major Concepts and Provisions
# =============================================================================

TABLE_C_ROWS = [
    _row("Insurance:", ["Tenant_Insurance"]),
    _row("Landlord Repair and Maintenance Obligations:", ["Landlord_Repair_Obligations"]),
    _row("Tenant Repair and Maintenance Obligations:", ["Tenant_Repair_Obligations"]),
    _divider("Assignment:"),
    _row("Assignment Languages:", ["Assignment_3rd_Parties", "Assignment_Affiliates", "Assignment_Change_Control"],
         wrap=["3rd Parties: {F0}", "Affiliates: {F1}", "Change of Control: {F2}"]),
    _row("Landlord Decision re Assignment:", ["Assignment_LL_Decision"]),
    _row("Rent Profits re Assignment:", ["Assignment_Rent_Profit"]),
    _row("LL Recapture of Space:", ["Assignment_Recapture_Space"]),
    _row("Processing Fee:", ["Assignment_Process_Fee"]),
    _row("Other:", ["Assignment_Other_Terms"]),
    _row("Sublease:", ["Sublease_Terms"]),
    _row("Holdover:", ["Holdover_Rent"]),
    _divider("Estoppel:"),
    _row("Estoppel Return Period:", ["Estoppel_Return_Period"]),
    _row("Details to be included:", ["Estoppel_Details"]),
    _divider("SNDA:"),
    _row("Lease is subject to existing mortgages:", ["SNDA_Subject_Existing_Mortgages"]),
    _row("Lease is subject to Future Mortgages:", ["SNDA_Subject_Future_Mortgages"]),
    _row("Lease is subject to existing Ground Leases:", ["SNDA_Subject_Existing_GroundLease"]),
    _row("Lease is subject to Future Ground Leases:", ["SNDA_Subject_Future_GroundLease"]),
    _row("Language re if requested by Lender:", ["SNDA_Required_by_Lender_Provision"]),
    _divider("Relocation Rights:"),
    _row("Relocation Allowed?", ["Relocation_Rights"]),
    _row("Notice Days:", ["Relocation_Notice_Period"]),
    _row("Language:", ["Relocation_Language"]),
    _row("Relocation Costs:", ["Relocation_Cost"]),
    _row("Termination Rights:", ["Relocation_Termination_Rights"]),
    _row("Signage:", ["Signage_Allowed"]),
    _row("Location:", ["Signage_Location"]),
    _row("Approval Required:", ["Signage_Approval_Required"]),
    _row("Type of Signage:", ["Signage_Type"]),
    _row("Renovation Repair and Replacement:", ["Signage_Renovation_Replacement"]),
    _row("Removal", ["Signage_Removal"]),
    _row("Other Rights:", ["Other_Rights"]),
]


def _set_paragraph_text(p, new_text):
    """Replace a paragraph's full text, preserving the first run's formatting."""
    if not p.runs:
        p.add_run(new_text)
        return
    p.runs[0].text = new_text
    for r in p.runs[1:]:
        r.text = ""


def _fix_header_paragraphs(doc):
    """
    Fix the header block above Table A:
    - "DATE:" / "Prepared by:" fields were swapped (Lease_Summary_Preparer
      shown next to "DATE:" and vice versa) - swap the labels back, and
      point them at the new _Int variables.
    - Remove the "Project Name:" / "Project Address:" / "Owner Name:" lines
      since that data now lives in Table A with full Interpretation/Raw
      Data treatment.
    """
    paras = doc.paragraphs
    to_delete = []
    for p in paras:
        full_text = "".join(run.text for run in p.runs)
        t = full_text.strip()
        if t.startswith("DATE:"):
            _set_paragraph_text(p, "DATE: [!@Lease_Summary_Date_Int]")
        elif t.startswith("Prepared by:"):
            _set_paragraph_text(p, "Prepared by: [!@Lease_Summary_Preparer_Int]")
        elif t.startswith("Summary Purposes:"):
            _set_paragraph_text(p, "Summary Purposes: [!@Lease_Summary_Purpose_Int]")
        elif t.startswith("Project Name:") or t.startswith("Project Address:") or t.startswith("Owner Name:"):
            to_delete.append(p)

    for p in to_delete:
        p._p.getparent().remove(p._p)


def main():
    if not os.path.exists(TEMPLATE_PATH):
        raise SystemExit(f"Template not found: {TEMPLATE_PATH}")

    # Backup existing template
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(HERE, f"SeedJura_Lease_Summary_FORM.backup_{stamp}.docx")
    shutil.copy2(TEMPLATE_PATH, backup_path)
    print(f"Backed up previous template to {backup_path}")

    doc = Document(TEMPLATE_PATH)

    if len(doc.tables) != 3:
        raise SystemExit(f"Expected 3 tables in template, found {len(doc.tables)}")

    _fix_header_paragraphs(doc)

    old_tables = list(doc.tables)
    # Anchor elements: insert new tables right before each old table, then
    # remove the old tables.
    anchors = [t._tbl for t in old_tables]

    new_table_a, _ = _build_table(doc, anchors[0], HEADER_FILL_MAIN, TABLE_A_ROWS, no_start=1)
    new_table_b, _ = _build_table(doc, anchors[1], HEADER_FILL_SUB, TABLE_B_ROWS, no_start=1)
    new_table_c, _ = _build_table(doc, anchors[2], HEADER_FILL_SUB, TABLE_C_ROWS, no_start=1)

    # Remove old tables now that replacements are in place
    for tbl_element in anchors:
        tbl_element.getparent().remove(tbl_element)

    doc.save(TEMPLATE_PATH)
    print(f"Rebuilt template saved to {TEMPLATE_PATH}")
    print(f"Table A: {len(TABLE_A_ROWS)} data rows")
    print(f"Table B: {len(TABLE_B_ROWS)} data rows")
    print(f"Table C: {len(TABLE_C_ROWS)} data rows")


if __name__ == "__main__":
    main()
