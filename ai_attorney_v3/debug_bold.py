from docx import Document
from docx.oxml.ns import qn

doc = Document("/home/cliff/redact/ai_attorney/jobs/70fe68c1-3d61-4905-b9fe-e36ca6a2c23d/PSA_Form2 (1).docx")

# Check styles for bold
print("=== STYLE DEFINITIONS ===")
for style in doc.styles:
    if style.name in ['Body Text', 'Body Text First Indent', 'Body Text First Indent 2', 'Body Text Center', 'Title Page', 'Normal']:
        rpr = style.element.find(qn('w:rPr'))
        if rpr is not None:
            bold_elem = rpr.find(qn('w:b'))
            if bold_elem is not None:
                val = bold_elem.get(qn('w:val'))
                print(f'  Style "{style.name}": BOLD defined (val={val})')
            else:
                print(f'  Style "{style.name}": rPr exists but no bold')
        else:
            print(f'  Style "{style.name}": no rPr')

# Check body paragraphs (skip first 50 to get past TOC)
print("\n=== BODY PARAGRAPHS (50-70) ===")
for i, para in enumerate(doc.paragraphs[50:70], 50):
    if not para.text.strip():
        continue
    for run in para.runs[:2]:
        if not run.text.strip():
            continue
        # Check raw XML for bold
        rpr = run._r.find(qn('w:rPr'))
        bold_in_xml = False
        if rpr is not None:
            b = rpr.find(qn('w:b'))
            if b is not None:
                val = b.get(qn('w:val'))
                bold_in_xml = val != '0' and val != 'false'
        print(f'  Para {i} [{para.style.name[:20]}]: run.bold={run.bold} | xml_bold={bold_in_xml} | "{run.text[:40]}"')
        break
