from docx import Document
from docx.oxml.ns import qn
from lxml import etree

doc = Document("/home/cliff/redact/ai_attorney/jobs/70fe68c1-3d61-4905-b9fe-e36ca6a2c23d/PSA_Form2 (1).docx")

# Look at paragraph 69 (first body paragraph) - show raw XML of first few runs
para = doc.paragraphs[69]
print(f"Paragraph 69: style='{para.style.name}'")
print(f"Text: {para.text[:100]}")
print()

for j, run in enumerate(para.runs[:5]):
    print(f"  Run {j}: text='{run.text[:40]}' bold={run.bold}")
    rpr = run._r.find(qn('w:rPr'))
    if rpr is not None:
        print(f"    rPr XML: {etree.tostring(rpr, pretty_print=True).decode()[:300]}")
    else:
        print(f"    rPr: None")
    print()

# Also check the style definition
print("\n=== Style 'Body Text First Indent' definition ===")
for style in doc.styles:
    if style.name == "Body Text First Indent":
        print(f"  base_style: {style.base_style.name if style.base_style else None}")
        print(f"  font.bold: {style.font.bold}")
        rpr = style.element.find(qn('w:rPr'))
        if rpr is not None:
            print(f"  rPr XML: {etree.tostring(rpr, pretty_print=True).decode()[:300]}")
        # Check parent style chain
        base = style.base_style
        while base:
            print(f"  -> parent '{base.name}': font.bold={base.font.bold}")
            base = base.base_style
        break
