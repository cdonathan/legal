from docx import Document
from docx.oxml.ns import qn

doc = Document("/home/cliff/redact/ai_attorney/jobs/70fe68c1-3d61-4905-b9fe-e36ca6a2c23d/PSA_Form2 (1).docx")

# Check paragraphs 70-120 (body text area)
print("=== BODY PARAGRAPHS — ALL RUNS ===")
for i, para in enumerate(doc.paragraphs[69:100], 69):
    if not para.text.strip():
        continue
    bold_runs = []
    normal_runs = []
    for run in para.runs:
        if not run.text.strip():
            continue
        # Check XML directly
        rpr = run._r.find(qn('w:rPr'))
        has_bold_xml = False
        if rpr is not None:
            b = rpr.find(qn('w:b'))
            if b is not None:
                val = b.get(qn('w:val'))
                has_bold_xml = (val is None or (val != '0' and val != 'false'))
        if has_bold_xml:
            bold_runs.append(run.text[:30])
        else:
            normal_runs.append(run.text[:30])
    
    if bold_runs or normal_runs:
        total = len(bold_runs) + len(normal_runs)
        pct = len(bold_runs) / total * 100 if total else 0
        print(f"Para {i} [{para.style.name[:25]}]: {len(bold_runs)} bold / {len(normal_runs)} normal ({pct:.0f}% bold)")
        if bold_runs:
            print(f"  BOLD: {bold_runs[:3]}")
        if normal_runs:
            print(f"  NORMAL: {normal_runs[:3]}")
