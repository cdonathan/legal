# AI NDA Redlining System --- Design Recap

This document summarizes the design discussion for building an
**AI-assisted NDA redlining system** using GPT‑4o‑mini. The goal is to
automatically review and redline NDAs while maintaining **minimal edits,
legal balance, and high acceptance by opposing counsel**.

------------------------------------------------------------------------

# 1. Source Analysis

Six NDA examples were analyzed:

-   6 **pre‑redline NDAs**
-   6 **post‑attorney‑redline NDAs**

The attorney edits showed **consistent patterns and legal intent**.

## Common Structural Pattern

Across the redlined examples, attorneys consistently converged toward
the following structure:

1.  Parties / Introduction
2.  Purpose of disclosure
3.  Definition of Confidential Information
4.  Confidentiality obligations
5.  Exceptions to confidentiality
6.  Permitted recipients (advisors, lenders, investors)
7.  Return or destruction of materials
8.  Compelled disclosure
9.  Term of agreement
10. Remedies / injunctive relief
11. No obligation to transact
12. No representation or warranty
13. Governing law
14. Notices
15. Miscellaneous / entire agreement
16. Counterparts
17. Signatures

This structure became the **Golden NDA Template**.

------------------------------------------------------------------------

# 2. Golden NDA

A **Golden NDA Markdown document** was created to represent the
institutional drafting standard.

Characteristics:

-   Structured with **Clause IDs**
-   Includes **purpose of each clause**
-   Contains **standard language patterns**
-   Provides a consistent legal structure

Example structure:

    CLAUSE_ID: NDA_001
    Clause Name: Purpose

    Purpose:
    Defines the business reason for disclosure.

    Standard Language:
    Disclosing Party may disclose confidential information
    to evaluate a potential transaction involving certain property.

This template is used as a **reference standard**, not copied verbatim
into documents.

------------------------------------------------------------------------

# 3. Clause Library

A **Clause Library** was created from the redline patterns.

It contains **20 standardized clauses**, each including:

-   Clause ID
-   Clause Name
-   Purpose
-   Standard Language Pattern
-   When to Apply
-   When Not to Apply

Example:

    CLAUSE_006
    Permitted Recipients

    Allows disclosure to advisors needed for transaction evaluation.
    Examples include:
    - attorneys
    - accountants
    - lenders
    - investors

The clause library acts as the **AI's editing vocabulary**, preventing
hallucinated legal language.

------------------------------------------------------------------------

# 4. Redlining Philosophy

The AI must behave like a **transactional deal lawyer**, not a document
generator.

Key rules:

-   Preserve original wording whenever possible
-   Prefer inserting phrases instead of rewriting paragraphs
-   Avoid aggressive language that triggers negotiation
-   Maintain balance between both parties
-   Do not rewrite clauses that already accomplish the legal goal
-   Do not expand document length more than \~20%
-   Only add clauses if a critical protection is missing

------------------------------------------------------------------------

# 5. System Architecture

The recommended architecture combines **code parsing + AI clause
editing**.

    Upload NDA
          ↓
    Lambda parses document into clauses
          ↓
    API Call #1 — Full document review
          ↓
    Extract document context
          ↓
    Loop through clauses
          ↓
    API Call per clause (redline)
          ↓
    Merge edits
          ↓
    Generate DOCX with tracked changes

------------------------------------------------------------------------

# 6. Document Context Step

Because OpenAI API calls are **stateless**, context must be extracted
once and reused.

## Step 1 --- Document Review

Send the **full NDA** to GPT‑4o‑mini and request structured context.

Example output:

``` json
{
  "transaction_type": "Commercial real estate acquisition",
  "purpose": "Evaluation of property purchase",
  "tone": "Balanced institutional NDA",
  "governing_law": "Texas",
  "special_clauses": ["Broker protection"]
}
```

This **document_context** is reused in clause calls.

------------------------------------------------------------------------

# 7. Clause Parsing (Code Layer)

The document should be split into clauses **before sending to AI**.

Reasons:

-   faster processing
-   smaller prompts
-   deterministic behavior
-   easier debugging
-   fits API Gateway 29‑second limit

Example parsed output:

``` json
[
  {
    "clause_number": "1",
    "title": "Purpose",
    "text": "..."
  },
  {
    "clause_number": "2",
    "title": "Confidential Information",
    "text": "..."
  }
]
```

Rules:

-   Never change clause numbering
-   Never merge clauses
-   Never split clauses

------------------------------------------------------------------------

# 8. Clause Redline Calls

Each clause request includes:

    DOCUMENT_CONTEXT
    CLAUSE_TEXT
    GOLD_STANDARD_NDA
    CLAUSE_LIBRARY

Example prompt:

    You are redlining a clause from a commercial real estate NDA.

    DOCUMENT CONTEXT:
    Transaction Type: Real estate acquisition
    Purpose: Property evaluation
    Tone: Balanced NDA

    CLAUSE TEXT:
    Confidential Information means information relating to the property.

    REFERENCE:
    Golden NDA
    Clause Library

    TASK:
    Apply minimal edits to align with institutional NDA standards.

------------------------------------------------------------------------

# 9. Expected AI Output

AI returns structured edits.

Example JSON:

``` json
{
  "document_name": "Example_NDA_redlined.docx",
  "changes": [
    {
      "change_type": "Insert",
      "location": "Confidential Information means...",
      "original_text": "",
      "revised_text": "Confidential Information shall include analyses, summaries, or notes derived from such information.",
      "clause_reference": "CLAUSE_004",
      "reason": "Protects derivative materials."
    }
  ]
}
```

------------------------------------------------------------------------

# 10. Word Document Generation

The code layer converts structured edits into a **Word document with
Track Changes**.

Process:

    Original NDA
    ↓
    Apply edits
    ↓
    python-docx track changes
    ↓
    Save

Output filename:

    name_redlined.docx

------------------------------------------------------------------------

# 11. API Gateway Timing

API Gateway limit:

    29 seconds

Estimated runtime:

  Step                   Time
  ---------------------- ----------------
  Document review        \~2 seconds
  Clause redline calls   \~10 seconds
  Document assembly      \~1--2 seconds

Total:

    ~13–15 seconds

Safe within limits.

Parallel clause processing can reduce runtime to **3--5 seconds**.

------------------------------------------------------------------------

# 12. Additional Optimization

Add rule:

    If clause already satisfies legal purpose
    return "NO_CHANGE"

Example:

``` json
{
  "clause_number": "Section 5",
  "status": "NO_CHANGE"
}
```

This reduces unnecessary edits.

------------------------------------------------------------------------

# 13. File Structure

Recommended project layout:

    nda-redline-system/

    golden_nda.md
    nda_clause_library.md
    prompt_redline.txt

    input/
        nda.docx

    output/
        nda_redlined.docx

------------------------------------------------------------------------

# 14. Key Design Principles

The system succeeds because it:

-   mimics real legal review workflows
-   performs clause-level analysis
-   enforces minimal edits
-   maintains legal balance
-   avoids AI hallucinated language

------------------------------------------------------------------------

# 15. Final Workflow Summary

    1 Upload NDA
    2 Parse clauses in code
    3 Send full document for context summary
    4 Loop through clauses
    5 Redline clauses using clause library
    6 Reassemble document
    7 Export tracked Word document

This architecture is:

-   fast
-   deterministic
-   API‑safe
-   legally reliable
