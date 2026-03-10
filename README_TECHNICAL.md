# Contract Redaction System - Technical Documentation

A multi-phase document redaction system that combines pattern-based redaction with AI verification for comprehensive PII removal from legal contracts.

## System Architecture

The system operates in 4 phases with an optional AI verification step:

```
Phase 1: Pattern Redaction → Phase 2: Chunking → Phase 3: AI Verification → Phase 4: Reassembly
```

## Phase 1: Pattern-Based Redaction

**Purpose**: Identify and redact structured PII using regex patterns and whitelist filtering

**Implementation**: `redactor.py` - `ContractRedactor` class

### Pattern Detection
The system uses 15+ regex patterns to identify:
- **Title + Name combinations**: `Dr Smith`, `CEO Johnson`, `Vice President Williams`
- **Entity names**: Between contract parties using phrases like "between X and Y"
- **Addresses**: Street numbers + suffixes within 10 words, full address patterns
- **Geographic data**: City/State/ZIP combinations, state codes
- **Financial data**: Dollar amounts, account numbers, routing numbers
- **Personal identifiers**: SSN, driver's license, credit cards, tax IDs
- **Contact info**: Phone numbers, email addresses
- **Dates**: Contract-specific date patterns

### Whitelist Filtering
- **Whitelist size**: 16,576 approved terms
- **Content**: Legal terminology, business terms, function words, generic locations
- **Logic**: Any word NOT in whitelist gets flagged for redaction
- **Threshold**: Words must be >2 characters

### Redaction Process
1. Apply pattern-based redaction (replaces with `[REDACT]` or specific labels)
2. Apply whitelist filtering (flags non-whitelisted words)
3. Generate redaction summary with counts

**Output**: Pattern-redacted document saved to `phase1/` directory

## Phase 2: Chunking

**Purpose**: Break documents into manageable chunks with randomized identifiers for security

**Implementation**: `chunk_file.py` and chunking logic in `pipeline.py`

### Chunking Strategy
- **Chunk size**: 1000 characters (not words as stated in original README)
- **Identifier**: 12-character random hash IDs for security
- **Mapping**: JSON file tracks chunk order and metadata

### Security Features
- Random hash prevents identification without mapping file
- Chunks are unordered by filename
- Mapping required for reassembly

**Output**: Random-named chunk files + mapping JSON in `phase2/` directory

## Phase 3: AI Verification (Two Options)

### Option A: Local AI Review (Default in pipeline.py)
**Model**: qwen2.5:3b via Ollama
**Implementation**: `phi35_reviewer.py`

**Process**:
1. Each chunk reviewed by local AI model
2. AI identifies potential PII missed by patterns
3. Returns binary flag: PII found/clean
4. **No automatic redaction** - flagging only
5. Original chunks copied unchanged to phase3/

### Option B: OpenAI Redaction (Alternative)
**Model**: GPT-4o-mini
**Implementation**: `phase3_openai.py`

**Process**:
1. Parallel processing (5 concurrent workers)
2. AI performs additional redaction
3. Returns redacted content
4. Handles rate limiting and errors

### AI Prompt Strategy
The AI is instructed to:
- **Redact**: Names, companies, addresses, financial data, contact info
- **Preserve**: Legal terminology, document structure, generic business terms
- **Output**: Clean redacted text with `[REDACT]` replacements

## Phase 4: Reassembly

**Purpose**: Reconstruct final document from processed chunks

**Implementation**: `phase4_reassemble.py`

### Reassembly Process
1. Load mapping file from phase3
2. Sort chunks by original order
3. Join chunks with single space
4. Create final redacted document

**Output**: Complete redacted document in `phase4/` directory

## File Structure

```
~/redact/
├── pipeline.py                    # Complete 4-phase pipeline
├── redactor.py                    # Phase 1 pattern redaction engine
├── redaction_whitelist.txt        # 16,576 approved terms
├── chunk_file.py                  # Phase 2 chunking utilities
├── phi35_reviewer.py              # Phase 3 local AI reviewer
├── phase3_openai.py               # Phase 3 OpenAI redaction (alternative)
├── phase4_reassemble.py           # Phase 4 reassembly
├── openai_prompt.txt              # AI redaction instructions
└── openai_api_key.txt             # OpenAI API key (create this)
```

## Usage

### Complete Pipeline
```bash
python3 pipeline.py /path/to/contract.mhtml
```

### Individual Phases
```bash
# Phase 1 only
python3 redactor.py

# Phase 3 with OpenAI (alternative)
python3 phase3_openai.py

# Phase 4 only
python3 phase4_reassemble.py
```

## Technical Implementation Details

### Pattern Redaction Engine
- **Regex patterns**: 15+ comprehensive patterns for PII detection
- **Whitelist lookup**: O(1) hash table lookup for 16K+ terms
- **Multi-pass processing**: Pattern redaction followed by whitelist filtering

### AI Integration
- **Local model**: qwen2.5:3b for PII flagging (verification only)
- **Cloud model**: GPT-4o-mini for comprehensive redaction
- **Parallel processing**: ThreadPoolExecutor with 5 workers
- **Error handling**: Individual chunk failures don't stop processing

### Security Features
- **Random chunk IDs**: 12-character hashes prevent identification
- **Mapping separation**: Chunks meaningless without mapping file
- **API key file storage**: Not environment variables
- **Comprehensive logging**: Full audit trail

### File Format Support
- **Primary**: .mhtml files (web-saved contracts)
- **Secondary**: .txt files
- **MHTML processing**: Extracts text, skips base64/binary sections

## Performance Characteristics

- **Phase 1**: ~2-3 seconds (pattern + whitelist processing)
- **Phase 2**: ~1 second (chunking + mapping)
- **Phase 3**: 
  - Local AI: ~30-60 seconds (depends on chunk count)
  - OpenAI: ~30-60 seconds (parallel processing)
- **Phase 4**: ~1-2 seconds (reassembly)

**Total**: ~1-2 minutes per contract

## Configuration

### Adjust Chunk Size
```python
chunk_size = 1000  # characters in pipeline.py
```

### Modify Redaction Patterns
```python
# In redactor.py
self.patterns = [
    (r'pattern_regex', 'LABEL'),
    # Add custom patterns
]
```

### Update Whitelist
Add approved terms to `redaction_whitelist.txt`

### AI Model Selection
- Edit `pipeline.py` to use `phase3_openai.py` instead of local reviewer
- Modify model names in respective files

## Key Differences from Original README

1. **Phase 3 is verification, not redaction** (in default pipeline)
2. **Chunking uses characters, not words**
3. **Whitelist has 16K+ terms, not 800**
4. **AI flagging vs. AI redaction** (two different approaches)
5. **Local AI model is qwen2.5:3b, not phi3.5**
6. **Pattern redaction is more comprehensive** (15+ patterns)

## Error Handling

- Individual chunk processing failures logged but don't stop pipeline
- Missing chunks reported during reassembly
- API failures preserve original content
- Comprehensive error messages for debugging

## Security Considerations

- Random chunk naming prevents content identification
- Mapping files required for reassembly
- API keys stored in files, not environment
- Comprehensive audit logging
- Original documents preserved through pipeline

This system provides robust PII redaction through multiple complementary approaches: pattern matching, whitelist filtering, and AI verification/redaction.
