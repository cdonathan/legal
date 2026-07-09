"""Check what the docx_to_html converter is producing for the PSA."""
import sys
sys.path.insert(0, '/home/cliff/redact/ai_attorney_v3')
from docx_to_html import convert_docx_to_html

result = convert_docx_to_html("/home/cliff/redact/ai_attorney/jobs/70fe68c1-3d61-4905-b9fe-e36ca6a2c23d/PSA_Form2 (1).docx")

html = result["html"]

# Count bold vs non-bold
import re
strong_count = len(re.findall(r'<strong>', html))
p_count = len(re.findall(r'<[ph]\d?', html))
total_text_len = len(re.sub(r'<[^>]+>', '', html))
bold_text = ''.join(re.findall(r'<strong>(.*?)</strong>', html))
bold_pct = len(bold_text) / total_text_len * 100 if total_text_len else 0

print(f"Total paragraphs/headings: {p_count}")
print(f"Strong tags: {strong_count}")
print(f"Total text: {total_text_len} chars")
print(f"Bold text: {len(bold_text)} chars ({bold_pct:.1f}%)")
print()

# Show first 30 paragraphs with their bold status
lines = html.split('\n')
print("First 30 elements:")
for i, line in enumerate(lines[:30]):
    has_strong = '<strong>' in line
    plain = re.sub(r'<[^>]+>', '', line)[:60]
    marker = "**BOLD**" if has_strong else "        "
    if plain.strip():
        print(f"  {marker} {plain}")
print()
print("Body paragraphs (skip TOC, index 70-90):")
for i, line in enumerate(lines[70:90], 70):
    has_strong = '<strong>' in line
    plain = re.sub(r'<[^>]+>', '', line)[:60]
    marker = "**BOLD**" if has_strong else "        "
    if plain.strip():
        print(f"  {marker} {plain}")
