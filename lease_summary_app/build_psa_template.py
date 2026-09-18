"""
PSA Template Build Script
==========================
One-time (re-runnable) build tool that creates SeedJura_PSA_Summary_FORM.docx
from scratch, using the same 4-column table layout as the lease template:

    No. | Categories | Interpretation | Raw Data

For every field, the Interpretation column carries the [!@Field_Int]
placeholder and the Raw Data column carries the [!@Field_Raw] placeholder
(matching the suffix convention consumed by field_variants.py /
populate_template()). Reuses the row/table-building helpers from
build_template.py rather than duplicating them.

Run:
    python build_psa_template.py

Creates (or overwrites) SeedJura_PSA_Summary_FORM.docx in this directory.
A timestamped backup is kept alongside it if a previous version exists.
"""

import os
import shutil
from datetime import datetime

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT

from build_template import (
    _row, _divider, _build_table,
    HEADER_FILL_MAIN, HEADER_FILL_SUB, COL_WIDTHS,
    FONT_NAME, FONT_SIZE,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(HERE, "SeedJura_PSA_Summary_FORM.docx")

# =============================================================================
# TABLE A - Main summary table (parties, property, dates, price/deposit,
# financing/diligence, title/closing)
# =============================================================================

TABLE_A_ROWS = [
    _row("Property Name", ["Property_Name"]),
    _row("Property Address", ["Property_Address_1", "Property_Address_2", "Property_Address_City",
                               "Property_Address_State", "Property_Address_Zip"]),
    _row("Property Type", ["Property_Type"]),
    _row("Legal Description", ["Property_Legal_Description"]),
    _row("Seller", ["Seller_Name", "Seller_StReg", "Seller_Type"]),
    _row("Seller Notice Address", ["Seller_Address", "Seller_Attn", "Seller_Email"]),
    _row("Buyer", ["Buyer_Name", "Buyer_StReg", "Buyer_Type"]),
    _row("Buyer Notice Address", ["Buyer_Address", "Buyer_Attn", "Buyer_Email"]),
    _row("Agreement Name", ["Agreement_Name"]),
    _row("Amendments", ["Agreement_Amendments"]),
    _row("Effective Date", ["Date_Effective"]),
    _row("Amendment Effective Date", ["Amendment_Effective_Date"]),
    _row("Closing Date", ["Closing_Date"]),
    _row("Termination Date", ["Date_Termination"]),
    _row("Deposit Disposition on Termination", ["Termination_Deposit_Disposition"]),
    _divider("Purchase Price & Deposit"),
    _row("Purchase Price", ["Purchase_Price"]),
    _row("Price Allocation", ["Purchase_Price_Allocation"]),
    _row("Earnest Money Deposit", ["Earnest_Money_Amount"]),
    _row("Deposit Deadline", ["Earnest_Money_Deposit_Deadline"]),
    _row("Deposit Refundability", ["Earnest_Money_Refundability"]),
    _row("Additional Deposit", ["Additional_Deposit_Amount"]),
    _row("Escrow Agent", ["Escrow_Agent_Name"]),
    _row("Title Company", ["Title_Company_Name"]),
    _divider("Financing & Due Diligence"),
    _row("Financing Contingency", ["Financing_Contingency"]),
    _row("Due Diligence Period", ["Due_Diligence_Period_Length"]),
    _row("Due Diligence Termination Rights", ["Due_Diligence_Termination_Rights"]),
    _divider("Title & Survey"),
    _row("Title Requirements", ["Title_Requirements"]),
    _row("Title Review Period", ["Title_Review_Period"]),
    _row("Survey Requirements", ["Survey_Requirements"]),
    _row("Permitted Title Exceptions", ["Permitted_Title_Exceptions"]),
    _divider("Closing"),
    _row("Closing Extension Rights", ["Closing_Extension_Rights"]),
    _row("Buyer's Closing Conditions", ["Closing_Conditions_Buyer"]),
    _row("Seller's Closing Conditions", ["Closing_Conditions_Seller"]),
    _row("Closing Costs Allocation", ["Closing_Costs_Allocation"]),
    _row("Prorations", ["Proration_Items"]),
]

# =============================================================================
# TABLE B - Representations, Warranties & Risk
# =============================================================================

TABLE_B_ROWS = [
    _row("Seller's Representations:", ["Seller_Representations"]),
    _row("Buyer's Representations:", ["Buyer_Representations"]),
    _row("As-Is Disclaimer:", ["AsIs_Disclaimer"]),
    _row("Survival Period:", ["Reps_Survival_Period"]),
    _row("Holdback Escrow:", ["Holdback_Escrow_Amount"]),
    _row("Risk of Loss:", ["Risk_of_Loss"]),
    _row("Condemnation:", ["Condemnation_Provision"]),
]

# =============================================================================
# TABLE C - Default, Remedies & Other Provisions
# =============================================================================

TABLE_C_ROWS = [
    _divider("Default & Remedies:"),
    _row("Remedy for Seller's Default:", ["Default_Seller_Remedy"]),
    _row("Remedy for Buyer's Default:", ["Default_Buyer_Remedy"]),
    _divider("Other Provisions:"),
    _row("Broker:", ["Broker_Name"]),
    _row("Commission Responsibility:", ["Broker_Commission_Responsibility"]),
    _row("Assignment Rights:", ["Assignment_Rights"]),
    _row("1031 Exchange:", ["Section_1031_Exchange"]),
    _row("Confidentiality:", ["Confidentiality_Provision"]),
    _row("Governing Law:", ["Governing_Law"]),
    _row("Prohibited Persons:", ["Prohibited_Persons_Provision"]),
    _row("Jury Trial Waiver:", ["Waiver_Jury_Trial"]),
    _row("Notice Method:", ["Notices_Method"]),
]


def _add_title_block(doc):
    """Add the title/header paragraphs above Table A, matching the lease
    template's look (title line, then DATE/Prepared by/Purpose lines)."""
    title = doc.add_paragraph()
    run = title.add_run("SeedJura Purchase & Sale Agreement Summary")
    run.font.name = FONT_NAME
    run.font.size = Pt(14)
    run.bold = True

    for label, field in (
        ("DATE:", "PSA_Summary_Date"),
        ("Prepared by:", "PSA_Summary_Preparer"),
        ("Summary Purposes:", "PSA_Summary_Purpose"),
    ):
        p = doc.add_paragraph()
        run = p.add_run(f"{label} [!@{field}_Int]")
        run.font.name = FONT_NAME
        run.font.size = FONT_SIZE

    doc.add_paragraph()
    doc.add_paragraph()


def _add_section_heading(doc, text):
    doc.add_paragraph()
    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = FONT_NAME
    run.font.size = Pt(12)
    run.bold = True


def main():
    if os.path.exists(OUTPUT_PATH):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(HERE, f"SeedJura_PSA_Summary_FORM.backup_{stamp}.docx")
        shutil.copy2(OUTPUT_PATH, backup_path)
        print(f"Backed up previous template to {backup_path}")

    doc = Document()

    # Match the lease template's page setup exactly: landscape letter
    # (11" x 8.5") with 1" margins all around, giving 9" of usable width -
    # this is what COL_WIDTHS (imported from build_template.py) was tuned
    # for. A brand-new Document() defaults to portrait letter with 1.25"
    # margins (only 6" usable), which is why the 4-column table previously
    # ran off the right edge of the page.
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    # A minimal placeholder paragraph is required as an anchor for
    # _build_table() to insert "before" - add one, build the table, then
    # let the natural document flow continue with normal add_paragraph().
    _add_title_block(doc)
    anchor_a = doc.add_paragraph()
    table_a, _ = _build_table(doc, anchor_a._p, HEADER_FILL_MAIN, TABLE_A_ROWS, no_start=1)
    anchor_a._p.getparent().remove(anchor_a._p)

    _add_section_heading(doc, "B. Representations, Warranties & Risk")
    anchor_b = doc.add_paragraph()
    table_b, _ = _build_table(doc, anchor_b._p, HEADER_FILL_SUB, TABLE_B_ROWS, no_start=1)
    anchor_b._p.getparent().remove(anchor_b._p)

    _add_section_heading(doc, "C. Default, Remedies & Other Provisions")
    anchor_c = doc.add_paragraph()
    table_c, _ = _build_table(doc, anchor_c._p, HEADER_FILL_SUB, TABLE_C_ROWS, no_start=1)
    anchor_c._p.getparent().remove(anchor_c._p)

    doc.add_paragraph()
    doc.add_paragraph()

    doc.save(OUTPUT_PATH)
    print(f"PSA template saved to {OUTPUT_PATH}")
    print(f"Table A: {len(TABLE_A_ROWS)} data rows")
    print(f"Table B: {len(TABLE_B_ROWS)} data rows")
    print(f"Table C: {len(TABLE_C_ROWS)} data rows")


if __name__ == "__main__":
    main()
