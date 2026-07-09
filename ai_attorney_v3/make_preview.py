#!/usr/bin/env python3
"""Generate a preview HTML example from a DOCX file using mammoth."""
import sys
import mammoth

input_file = sys.argv[1] if len(sys.argv) > 1 else "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA_Sample_4_pre_redline.docx"
output_file = sys.argv[2] if len(sys.argv) > 2 else "/home/cliff/redact/ai_attorney_v3/static/preview_example.html"

with open(input_file, "rb") as f:
    result = mammoth.convert_to_html(f)

html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Document Preview — Option A Example</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: Georgia, 'Times New Roman', serif;
    max-width: 860px;
    margin: 0 auto;
    padding: 40px 60px;
    line-height: 1.8;
    color: #1a1a1a;
    background: white;
    font-size: 11pt;
  }}
  h1 {{ font-size: 14pt; text-align: center; font-weight: bold; margin: 24px 0 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
  h2 {{ font-size: 12pt; font-weight: bold; margin: 20px 0 8px; }}
  h3 {{ font-size: 11pt; font-weight: bold; margin: 16px 0 6px; }}
  p {{ margin: 6px 0; text-align: justify; }}
  strong {{ font-weight: bold; }}
  em {{ font-style: italic; }}
  u {{ text-decoration: underline; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 10pt; }}
  td, th {{ border: 1px solid #555; padding: 6px 10px; vertical-align: top; }}
  th {{ background: #f0f0f0; font-weight: bold; }}
  ol {{ margin: 8px 0 8px 28px; }}
  ul {{ margin: 8px 0 8px 28px; list-style-type: disc; }}
  li {{ margin: 4px 0; }}
  .note {{
    background: #fffbeb;
    border: 1px solid #f59e0b;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 24px;
    font-family: -apple-system, sans-serif;
    font-size: 0.85rem;
    color: #78350f;
  }}
  .note strong {{ color: #92400e; }}
</style>
</head>
<body>
<div class="note">
  <strong>Option A Preview Example</strong> — This shows how the document looks after DOCX → HTML conversion using mammoth.
  Bold, italic, headings, lists, and tables are preserved. Exact margins and page layout are not.
  Edits made here would be saved back to the original DOCX preserving all formatting.
</div>

{result.value}

</body>
</html>"""

with open(output_file, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Preview written to: {output_file}")
print(f"HTML body size: {len(result.value):,} chars")
if result.messages:
    print(f"Conversion notes ({len(result.messages)}):")
    for m in result.messages[:10]:
        print(f"  {m.type}: {m.message}")
