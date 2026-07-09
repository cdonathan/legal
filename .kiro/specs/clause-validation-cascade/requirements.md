# Requirements Document

## Introduction

The Clause Validation Cascade Engine is a replacement architecture for the AI Attorney legal document redlining system (SeedJura). The current system allows AI (GPT-4o) to both identify deficiencies and generate replacement legal language — which is legally impermissible because AI is not a licensed attorney. This feature separates concerns: AI evaluates documents and identifies which attorney-approved clause addresses each deficiency, while deterministic code handles the actual text replacement using ONLY verified clause language from the SQL Server database (1,500+ clauses). A four-tier validation cascade ensures replacement text is always provably sourced from the clause database.

## Glossary

- **Cascade_Engine**: The four-tier validation system that resolves AI-identified deficiencies into verified replacement text from the clause database
- **Evaluation_Module**: The AI (GPT-4o) component responsible for scoring documents, identifying deficiencies, and referencing which approved clause addresses each gap — without generating any legal language
- **Clause_Database**: The SQL Server (SeedJuraTech) database containing 1,500+ attorney-approved clauses with fields PROV_DESC, HTML_DATA, HTML_DATA_TEXT, RISK_LEVEL, form_type, and category_id
- **Rules_Engine**: The deterministic pattern-matching module that handles simple exact-match replacements (e.g., "attorney's fees" → "reasonable attorney's fees") without invoking AI or the cascade
- **Change_Presenter**: The UI component that shows each proposed change with 150 words of context before and after, allowing users to accept or reject individual changes, displayed in a split-panel layout with a full document preview
- **Redaction_System**: The existing PII hex-mapping system that redacts personally identifiable information before AI sees document text and reconstructs it afterward
- **Document_Processor**: The module responsible for file conversion, text extraction, and final document output (redlined DOCX, clean DOCX, PDF)
- **Approved_Clause**: A clause record in the Clause_Database that has been reviewed and approved by a licensed attorney for use in legal documents
- **Cascade_Tier**: One of the four sequential validation levels (exact substring, fuzzy match, full clause replacement, human review flag)
- **Form_Type**: The document classification (NDA, PSA, LEASE, OA, MANA, JV, SUBS, GRNTY, EA, BRKR, SRVC) that determines which clauses from the Clause_Database are applicable

## Requirements

### Requirement 1: AI Evaluation Boundary Enforcement

**User Story:** As a system operator, I want the AI to only identify deficiencies and reference approved clauses, so that no AI-generated legal language can enter the document pipeline.

#### Acceptance Criteria

1. WHEN the Evaluation_Module receives redacted document text, THE Evaluation_Module SHALL return a structured response containing: a deficiency score per category, the exact quoted document text that is deficient, a description of the gap, and the clause_id from the Clause_Database that addresses the deficiency.
2. THE Evaluation_Module SHALL produce output that contains zero tokens of replacement legal language.
3. IF the Evaluation_Module response contains text not traceable to either the input document or a clause_id reference, THEN THE Cascade_Engine SHALL reject that response item and log the violation.
4. WHEN the Evaluation_Module identifies a deficiency, THE Evaluation_Module SHALL provide a verbatim quote of 30 to 150 characters from the document text identifying the deficient section.

### Requirement 2: Clause Database Integration

**User Story:** As a system operator, I want clause lookups to use the existing SQL Server database with local SQLite fallback, so that the system retrieves approved clauses reliably across deployment environments.

#### Acceptance Criteria

1. WHEN the Cascade_Engine receives a clause_id from the Evaluation_Module, THE Cascade_Engine SHALL query the Clause_Database for the matching record filtered by the document Form_Type.
2. IF the SQL Server connection fails, THEN THE Cascade_Engine SHALL fall back to the local SQLite provisions.db containing the same clause data.
3. THE Cascade_Engine SHALL retrieve the full Approved_Clause text from the HTML_DATA_TEXT field, stripping all HTML tags and template placeholders before use.
4. IF a clause_id returned by the Evaluation_Module does not exist in the Clause_Database for the given Form_Type, THEN THE Cascade_Engine SHALL flag the item for human review and log the missing clause reference.

### Requirement 3: Cascade Tier 1 — Exact Substring Match

**User Story:** As a system operator, I want the system to verify whether the AI's suggested clause portion is a verbatim substring of the approved clause, so that replacements are applied with the highest confidence level.

#### Acceptance Criteria

1. WHEN the Evaluation_Module suggests a specific portion of an Approved_Clause as the relevant replacement text, THE Cascade_Engine SHALL check whether that portion is a verbatim substring of the full Approved_Clause text retrieved from the Clause_Database.
2. WHEN an exact substring match is confirmed, THE Cascade_Engine SHALL use the matched substring as the replacement text and mark the change with confidence level "exact".
3. IF no exact substring match is found, THEN THE Cascade_Engine SHALL proceed to Cascade Tier 2.

### Requirement 4: Cascade Tier 2 — Fuzzy Match

**User Story:** As a system operator, I want the system to find the closest matching substring in the approved clause when exact match fails, so that minor AI paraphrasing does not block valid replacements.

#### Acceptance Criteria

1. WHEN Cascade Tier 1 fails, THE Cascade_Engine SHALL compute similarity between the AI-suggested portion and all substrings of the Approved_Clause text using a character-level similarity metric.
2. WHEN a substring of the Approved_Clause achieves a similarity score of 90% or higher against the AI-suggested portion, THE Cascade_Engine SHALL use that actual Approved_Clause substring as the replacement text and mark the change with confidence level "fuzzy".
3. IF no substring achieves 90% or higher similarity, THEN THE Cascade_Engine SHALL proceed to Cascade Tier 3.
4. WHEN multiple substrings exceed the 90% threshold, THE Cascade_Engine SHALL select the substring with the highest similarity score.

### Requirement 5: Cascade Tier 3 — Full Clause Replacement

**User Story:** As a system operator, I want the system to use the full approved clause text when partial matching fails, so that the document still receives the correct legal protection.

#### Acceptance Criteria

1. WHEN Cascade Tiers 1 and 2 fail, THE Cascade_Engine SHALL identify the relevant section in the document by locating the deficient text quoted by the Evaluation_Module.
2. WHEN the Cascade_Engine can locate the quoted deficient text within the document with a match confidence of 85% or higher using normalized text comparison, THE Cascade_Engine SHALL propose replacing the deficient section with the full Approved_Clause text and mark the change with confidence level "full_clause".
3. IF the Cascade_Engine cannot locate the deficient section in the document with 85% or higher confidence, THEN THE Cascade_Engine SHALL proceed to Cascade Tier 4.

### Requirement 6: Cascade Tier 4 — Human Review Flag

**User Story:** As a system operator, I want unresolvable changes flagged for manual handling, so that no incorrect replacement is silently applied.

#### Acceptance Criteria

1. WHEN Cascade Tiers 1, 2, and 3 all fail, THE Cascade_Engine SHALL flag the item for human review and mark it with confidence level "manual".
2. WHEN an item is flagged for human review, THE Change_Presenter SHALL display the full Approved_Clause text, the document section the Evaluation_Module identified as deficient, and the Evaluation_Module's gap description.
3. THE Cascade_Engine SHALL record all cascade tier attempts and their failure reasons in a structured audit log for each flagged item.

### Requirement 7: Rules Engine Deterministic Replacements

**User Story:** As a system operator, I want simple exact-match text patterns handled deterministically without AI or cascade processing, so that known corrections are applied instantly and reliably.

#### Acceptance Criteria

1. THE Rules_Engine SHALL execute before the Cascade_Engine processes AI-identified changes, applying all deterministic pattern replacements to the document text.
2. WHEN a document contains text matching a Rules_Engine pattern, THE Rules_Engine SHALL replace it with the predefined replacement text without invoking the Evaluation_Module or Cascade_Engine.
3. THE Rules_Engine SHALL support the following minimum pattern set: "attorney's fees" → "reasonable attorney's fees", "best efforts" → "commercially reasonable efforts", "take all steps" → "take commercially reasonable steps".
4. WHEN the Rules_Engine applies a replacement, THE Rules_Engine SHALL record the change with source attribution "rules_engine" and include 150 words of context before and after the match.

### Requirement 8: Change Presentation and User Approval

**User Story:** As a user reviewing proposed changes, I want to see each change with surrounding context and approve or reject it individually, so that I maintain full control over document modifications.

#### Acceptance Criteria

1. WHEN the Cascade_Engine produces a proposed change, THE Change_Presenter SHALL display 150 words before the change location, the old text (deficient) and new text (from Approved_Clause), and 150 words after the change location.
2. THE Change_Presenter SHALL display the confidence level (exact, fuzzy, full_clause, or manual) and the source Approved_Clause reference for each proposed change.
3. WHEN a user accepts a change, THE Document_Processor SHALL apply that change to the document. WHEN a user rejects a change, THE Document_Processor SHALL leave the original text unmodified.
4. THE Change_Presenter SHALL group changes by cascade confidence level, presenting "exact" matches first, followed by "fuzzy", "full_clause", and "manual" items.

### Requirement 13: Document Preview Panel with Navigation

**User Story:** As a user reviewing proposed changes, I want to see the full document alongside the change suggestions, so that I can read the complete context and understand exactly where each change applies.

#### Acceptance Criteria

1. THE Change_Presenter SHALL display a split-panel layout with change suggestions on the left side and a full document preview on the right side.
2. WHEN the Change_Presenter renders the document preview, THE Change_Presenter SHALL display the complete document text with each suggested change location highlighted in the preview.
3. WHEN a user selects a change suggestion on the left panel, THE Change_Presenter SHALL scroll the document preview on the right panel to the corresponding section and visually emphasize the affected text.
4. THE Change_Presenter SHALL render navigation markers in the document preview at each change location, allowing the user to click a marker to jump to the corresponding suggestion in the left panel.
5. WHILE the user scrolls through the document preview, THE Change_Presenter SHALL indicate which change suggestions correspond to the currently visible document section.

### Requirement 9: Replacement Text Provenance Verification

**User Story:** As a compliance officer, I want every replacement text verified as originating from the clause database, so that the system can prove no AI-generated language was used.

#### Acceptance Criteria

1. THE Cascade_Engine SHALL verify that every replacement text proposed to the user is a verbatim substring of an Approved_Clause record retrieved from the Clause_Database.
2. WHEN a replacement text passes provenance verification, THE Cascade_Engine SHALL record the clause_id, the character offset within the clause text, and the match tier in an audit record.
3. IF any replacement text cannot be verified as a substring of its referenced Approved_Clause, THEN THE Cascade_Engine SHALL reject the replacement and escalate the item to Cascade Tier 4 (human review).
4. THE Cascade_Engine SHALL generate a provenance report for each processed document listing every applied change with its source clause_id and verification method.

### Requirement 10: Document Processing Pipeline Integration

**User Story:** As a system operator, I want the cascade engine to integrate with the existing PII redaction, file conversion, and output generation pipeline, so that the system produces the same output formats with the new architecture.

#### Acceptance Criteria

1. THE Document_Processor SHALL preserve the existing Redaction_System behavior: redact PII with hex mapping before sending text to the Evaluation_Module, and reconstruct PII in output documents after changes are applied.
2. WHEN processing is complete, THE Document_Processor SHALL produce redlined DOCX output with strikethrough on removed text and green underline on inserted text from Approved_Clauses.
3. WHEN processing is complete, THE Document_Processor SHALL produce clean DOCX output with all accepted changes applied and no track-change markup.
4. THE Document_Processor SHALL support input files in .docx, .pdf, .txt, and .mhtml formats.
5. WHILE the Cascade_Engine processes a document, THE Document_Processor SHALL maintain an association between each change and its position in the original document to ensure changes do not overlap or conflict.

### Requirement 11: Document Type Classification and Clause Filtering

**User Story:** As a system operator, I want clauses filtered by document type so that only relevant approved language is considered for each document.

#### Acceptance Criteria

1. WHEN a document is uploaded, THE Evaluation_Module SHALL classify it into one of the supported Form_Types (NDA, PSA, LEASE, OA, MANA, JV, SUBS, GRNTY, EA, BRKR, SRVC).
2. WHEN querying the Clause_Database, THE Cascade_Engine SHALL filter clauses by the detected Form_Type to retrieve only applicable Approved_Clauses.
3. IF the Evaluation_Module classification confidence is below 70%, THEN THE Document_Processor SHALL prompt the user to confirm or select the correct Form_Type before proceeding.

### Requirement 12: Audit Trail and Compliance Logging

**User Story:** As a compliance officer, I want a complete audit trail of every decision the system makes, so that the legal provenance of each change can be demonstrated.

#### Acceptance Criteria

1. THE Cascade_Engine SHALL log each cascade tier attempted for every deficiency, including the tier name, the input data, the result (pass or fail), and the reason for failure at each tier.
2. THE Cascade_Engine SHALL log the final resolution for each deficiency: the applied replacement text, the source clause_id, the confidence level, and whether the user accepted or rejected the change.
3. WHEN a document completes processing, THE Cascade_Engine SHALL produce a JSON audit file containing all logged decisions, timestamps, the document identifier, and the Form_Type classification.
4. THE Cascade_Engine SHALL include in the audit log the exact AI response received from the Evaluation_Module to enable post-hoc review of AI behavior.
