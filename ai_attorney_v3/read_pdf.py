import pdfplumber

pdf_path = "/mnt/c/Users/cliff/Downloads/OneDrive_1_7-9-2026/PSA_Form2.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"Pages: {len(pdf.pages)}")
    
    # Check first few pages for text and font info
    for i, page in enumerate(pdf.pages[:5]):
        text = page.extract_text()
        if text:
            print(f"\n--- PAGE {i+1} ---")
            print(text[:2000])
        
        # Check chars for bold info (font names containing 'Bold')
        if i < 2:
            chars = page.chars[:50]
            fonts_seen = set()
            for ch in chars:
                fonts_seen.add(ch.get("fontname", ""))
            print(f"\nFonts on page {i+1}: {fonts_seen}")
