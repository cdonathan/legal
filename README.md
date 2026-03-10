# Contract Redaction System

A comprehensive 4-phase document redaction system that combines pattern-based redaction with AI-powered redaction using OpenAI GPT-4o-mini.

## Overview

This system processes legal contracts through four distinct phases to ensure comprehensive redaction of personally identifiable information (PII) and sensitive data while preserving document structure and legal terminology.

## System Architecture

```
Phase 1: Pattern Redaction → Phase 2: Chunking → Phase 3: AI Redaction → Phase 4: Reassembly
```

## Phase Breakdown

### Phase 1: Pattern-Based Redaction
- **Purpose**: Identify and redact structured PII using regex patterns
- **Input**: Original contract files (.mhtml, .txt)
- **Output**: Pattern-redacted document with summary
- **Location**: `C:\seedJura\contracts\phase1\`

**What gets redacted:**
- Addresses (street numbers + suffixes)
- City, State, ZIP codes
- Dollar amounts and financial figures
- Email addresses
- Phone numbers
- Dates in specific contexts

**What gets flagged:**
- Non-whitelisted words for manual review
- Potential entity names and proper nouns

### Phase 2: Chunking
- **Purpose**: Break documents into manageable chunks with random hash IDs
- **Input**: Phase 1 redacted documents
- **Output**: Random hash-named chunks + mapping file
- **Location**: `C:\seedJura\contracts\phase2\`

**Features:**
- 1000-word chunks (configurable)
- Random 12-character hash IDs for security
- JSON mapping file for reassembly
- Preserves word boundaries

### Phase 3: AI Redaction
- **Purpose**: Advanced redaction using OpenAI GPT-4o-mini
- **Input**: Phase 2 chunks
- **Output**: AI-redacted chunks
- **Location**: `C:\seedJura\contracts\phase3\`

**Features:**
- Parallel processing (5 concurrent workers)
- GPT-4o-mini model enforcement
- Comprehensive PII detection
- Rate limiting and error handling

### Phase 4: Reassembly
- **Purpose**: Reconstruct final document in original format
- **Input**: Phase 3 AI-redacted chunks + mapping
- **Output**: Final redacted document
- **Location**: `C:\seedJura\contracts\phase4\`

## Installation & Setup

### Prerequisites
- Python 3.12+
- OpenAI API key
- Linux/WSL environment

### Required Python Packages
```bash
pip install openai --break-system-packages
```

### Setup
1. Clone/download the redaction system files
2. Create OpenAI API key file:
   ```bash
   echo "your-api-key-here" > openai_api_key.txt
   ```
3. Ensure directory structure exists:
   ```
   C:\seedJura\contracts\
   ├── phase1\
   ├── phase2\
   ├── phase3\
   └── phase4\
   ```

## Usage

### Complete Pipeline (Recommended)
Process a contract through all 4 phases:
```bash
cd ~/redact
python3 pipeline.py /path/to/contract.mhtml
```

### Individual Phases
Run phases separately if needed:

**Phase 1 - Pattern Redaction:**
```bash
python3 redact_and_save.py
```

**Phase 2 - Chunking:**
```bash
python3 chunk_file.py
```

**Phase 3 - AI Redaction:**
```bash
python3 phase3_openai.py
```

**Phase 4 - Reassembly:**
```bash
python3 phase4_reassemble.py
```

## File Structure

```
~/redact/
├── README.md                          # This file
├── pipeline.py                        # Complete 4-phase pipeline
├── redactor.py                        # Phase 1 redaction engine
├── redaction_whitelist.txt            # Safe words whitelist
├── chunk_file.py                      # Phase 2 chunking
├── phase3_openai.py                   # Phase 3 AI processing
├── phase4_reassemble.py               # Phase 4 reassembly
├── openai_prompt.txt                  # AI redaction instructions
├── openai_api_key.txt                 # OpenAI API key (create this)
└── contracts/                         # Local contract storage
```

## Configuration Files

### Whitelist (`redaction_whitelist.txt`)
Contains ~800 safe words that should NOT be redacted:
- Legal terminology
- Common business terms
- Function words (articles, prepositions)
- Generic location terms

### OpenAI Prompt (`openai_prompt.txt`)
Instructions for GPT-4o-mini redaction:
- What to redact vs. preserve
- Output format requirements
- Comprehensive PII categories

## Output Examples

### Phase 1 Output
```
Original: "John Smith, 123 Main Street, Anytown, CA 90210"
Redacted: "[REDACTED], [REDACTED], [REDACTED]"
```

### Phase 3 AI Enhancement
```
Original: "The buyer, John Smith, agrees to purchase..."
AI Redacted: "The buyer, [REDACT], agrees to purchase..."
```

### Final Document
- All PII replaced with `[REDACT]`
- Legal structure preserved
- Original formatting maintained
- Comprehensive redaction summary

## Security Features

- **Random hash chunk IDs** prevent identification without mapping
- **Parallel processing** with isolated failures
- **API key file storage** (not environment variables)
- **Comprehensive logging** for audit trails
- **Mapping files** required for reassembly

## Performance

- **Phase 1**: ~2-3 seconds per document
- **Phase 2**: ~1 second per document
- **Phase 3**: ~30-60 seconds (depends on chunk count and API response)
- **Phase 4**: ~1-2 seconds per document

**Total processing time**: ~1-2 minutes per contract

## Supported File Types

- **Primary**: .mhtml files (web-saved contracts)
- **Secondary**: .txt files
- **Future**: .pdf support (requires additional libraries)

## Error Handling

- Individual chunk failures don't stop processing
- Failed chunks are logged and reported
- Original content preserved on API failures
- Comprehensive error messages and debugging info

## Customization

### Adjust Chunk Size
Edit `chunk_size=1000` in chunking functions

### Modify Redaction Patterns
Edit patterns in `redactor.py`:
```python
self.patterns = [
    (r'pattern_regex', 'LABEL'),
    # Add custom patterns here
]
```

### Update Whitelist
Add safe words to `redaction_whitelist.txt`

### Customize AI Prompt
Modify `openai_prompt.txt` for different redaction requirements

## Troubleshooting

### Common Issues

**"No OpenAI API key found"**
- Ensure `openai_api_key.txt` exists with valid key

**"No chunks found"**
- Check that previous phases completed successfully
- Verify directory permissions

**"Rate limit exceeded"**
- Reduce parallel workers in Phase 3
- Add delays between API calls

**"Permission denied"**
- Ensure WSL has access to Windows directories
- Check file permissions

### Debug Mode
Add print statements or logging to individual phase scripts for detailed debugging.

## License

This system is designed for document redaction and PII protection. Use responsibly and in compliance with applicable privacy laws.

## Support

For issues or questions:
1. Check error messages and logs
2. Verify file permissions and API keys
3. Test individual phases separately
4. Review configuration files

---

**Note**: This system processes sensitive legal documents. Always verify redaction quality and completeness before using redacted documents in production environments.
