import sys
sys.path.insert(0, "/home/cliff/redact/ai_attorney_v3")
from docx_to_html import convert_docx_to_html

r = convert_docx_to_html("/home/cliff/redact/ai_attorney/jobs/70fe68c1-3d61-4905-b9fe-e36ca6a2c23d/PSA_Form2 (1).docx")
lines = r["html"].split("\n")

print("Paragraphs 68-75 HTML:")
for i, l in enumerate(lines[68:75], 68):
    print(f"  [{i}] {l[:250]}")
