# SeedJura Call 1: Analysis & Scoring

You are an experienced real estate attorney. Read this NDA carefully and analyze it against the scoring criteria below.

## STEP 1: IDENTIFY DOCUMENT TERMINOLOGY

What does this NDA call:
- The confidential information?
- The recipient?
- The discloser?
- The recipient's people/representatives?

## STEP 2: FOR EACH CATEGORY, QUOTE THE RELEVANT LANGUAGE AND SCORE

For each category, you MUST either:
- Quote the exact language from the NDA that addresses it, OR
- State "NOT FOUND — no language in the document addresses this"

Then assign a score.

### Category 1: Confidential Information Carve-outs
Look for exclusions from the definition of confidential information. Three required concepts:
- (a) Information already in Recipient's possession prior to disclosure
- (b) Information publicly available (not through breach)
- (c) Information independently developed

**Search for phrases like:** "shall not include", "does not include", "notwithstanding", "excludes", "exception"

QUOTE the exclusion language you find, or state NOT FOUND.

Scoring:
- 10 = No carve-outs exist at all
- 8 = Only 1 of 3 concepts present
- 6 = 2 of 3 concepts present
- 3 = All 3 present but weak/ambiguous
- 0 = All 3 present with clear language

### Category 2: Representatives Breadth
Look for who the Recipient can share information with.

QUOTE the sharing/representatives language, or state NOT FOUND.

Scoring:
- 10 = No sharing rights at all
- 8 = Very narrow (3 or fewer roles)
- 6 = Moderate (4-7 roles), missing key ones like investors/partners
- 3 = Broad but missing 1-2 minor roles
- 0 = Broad list or catch-all language

### Category 3: Sub-Agreement Requirements
Look for what Representatives must do — sign a separate agreement? Be "bound by"? Be "informed of"?

QUOTE the relevant language, or state NOT FOUND.

Scoring:
- 9 = Must sign separate confidentiality agreement
- 7 = Must "agree to be bound by" this agreement
- 3 = Must be "directed to keep confidential" / "abide by terms"
- 0 = Must be "informed of confidential nature" OR no mention

### Category 4: Return/Destroy
Look for obligations to return or destroy confidential information. Is it automatic or upon request?

QUOTE the relevant language, or state NOT FOUND.

Scoring:
- 8 = Automatic return/destroy, no request trigger
- 6 = Dual trigger (automatic AND upon request)
- 4 = Upon request only, but no destroy/delete option
- 0 = Upon request with destroy option, OR no clause

### Category 5: Non-Circumvention
Look for restrictions on contacting third parties introduced by the Discloser.

QUOTE the relevant language, or state NOT FOUND.

Scoring:
- 9 = Broad: cannot contact ANY third party, no time limit
- 6 = Moderate: limited to property/transaction, no time limit
- 5 = Any non-circumvention with time limit >2 years
- 2 = Narrowly scoped, time limit 1-2 years
- 0 = No non-circumvention clause

### Category 6: Term/Duration
Look for how long the agreement lasts.

QUOTE the relevant language, or state NOT FOUND.

Scoring:
- 9 = No term/expiration/termination clause at all
- 9 = Indefinite or perpetual
- 7 = Term >2 years
- 0 = Term 1-2 years
- 0 = Term <1 year

### Category 7: Effective Date
Look for a date in the preamble.

QUOTE the relevant language, or state NOT FOUND.

Scoring:
- 8 = Blank date field in preamble
- 7 = No date anywhere
- 4 = Date exists but no "Effective Date" label
- 2 = Date on signature page only
- 0 = Effective Date properly defined

### Category 8: Legal Compliance Exceptions
Look for carve-outs allowing disclosure when required by court order, subpoena, or legal requirement.

**Search for phrases like:** "court order", "subpoena", "legally required", "compelled by law", "regulatory requirement"

QUOTE the relevant language, or state NOT FOUND.

Scoring:
- 8 = No legal compliance exception at all
- 6 = Exception exists but no notice requirement to Discloser
- 3 = Exception with notice but no cooperation/protective order language
- 0 = Full exception with notice and cooperation provisions

### Circumstantial Categories (score 0 if no relevant clause exists)

- C1 Electronic Signatures: Does it mention facsimile/counterparts? Score 4 if facsimile only, 0 if already electronic or no clause.
- C2 Reasonable Fees: Is there an attorney's fees clause without "reasonable"? Score 4 if yes, 0 otherwise.
- C3 Narrow Indemnification: Does indemnification cover "any disclosure" (not limited to breach)? Score 5 if yes, 0 otherwise.
- C4 No Obligation to Proceed: Does the NDA imply obligation to transact? Score 5 if yes, 0 otherwise.
- C5 Personal Financial Disclosure: Requires personal financial statements? Score 5 if yes, 0 otherwise.
- C6 Signature Page Notation: Has signature block without notation? Score 3 if yes, 0 otherwise.
- C7 Commercial Reasonableness: Does the NDA use absolute obligation language like "take all steps", "shall ensure", or "best efforts" without a reasonableness qualifier? Score 4 if yes, 0 otherwise.
- C8 Injunctive Relief Balance: Is injunctive relief missing, or does the clause require bond posting? Score 4 if yes, 0 otherwise.
- C9 Defined Term Consistency: Are defined terms used with mixed capitalization (e.g., "Confidential Information" vs "confidential information" for the same concept)? Score 3 if yes, 0 otherwise.
- C10 Business Purpose Expansion: Is the stated purpose narrowly worded (e.g., "participation, financing") without including "purchasing" or equivalent acquisition language? Score 4 if yes, 0 otherwise.

## OUTPUT FORMAT

Respond with valid JSON only:

```json
{
  "terminology": {
    "confidential_info_term": "term used",
    "recipient_term": "term used",
    "discloser_term": "term used",
    "representatives_term": "term used or null"
  },
  "analysis": {
    "1_carveouts": {
      "quoted_language": "exact quote from NDA or NOT FOUND",
      "concepts_found": ["possession", "public", "independent"],
      "score": 10,
      "reason": "No carve-out language found in document"
    },
    "2_representatives": {
      "quoted_language": "exact quote or NOT FOUND",
      "roles_found": ["employees", "attorneys"],
      "score": 6,
      "reason": "Missing investors, partners"
    },
    "3_sub_agreements": {
      "quoted_language": "exact quote or NOT FOUND",
      "score": 0,
      "reason": "explanation"
    },
    "4_return_destroy": {
      "quoted_language": "exact quote or NOT FOUND",
      "score": 0,
      "reason": "explanation"
    },
    "5_non_circumvention": {
      "quoted_language": "exact quote or NOT FOUND",
      "score": 0,
      "reason": "explanation"
    },
    "6_term": {
      "quoted_language": "exact quote or NOT FOUND",
      "score": 0,
      "reason": "explanation"
    },
    "7_effective_date": {
      "quoted_language": "exact quote or NOT FOUND",
      "score": 8,
      "reason": "explanation"
    },
    "8_legal_compliance": {
      "quoted_language": "exact quote or NOT FOUND",
      "score": 0,
      "reason": "explanation"
    },
    "c1_electronic_sig": {"score": 0, "reason": "explanation"},
    "c2_reasonable_fees": {"score": 0, "reason": "explanation"},
    "c3_narrow_indemnification": {"score": 0, "reason": "explanation"},
    "c4_no_obligation": {"score": 0, "reason": "explanation"},
    "c5_personal_financial": {"score": 0, "reason": "explanation"},
    "c6_signature_notation": {"score": 0, "reason": "explanation"},
    "c7_commercial_reasonableness": {"score": 0, "reason": "explanation"},
    "c8_injunctive_relief": {"score": 0, "reason": "explanation"},
    "c9_defined_term_consistency": {"score": 0, "reason": "explanation"},
    "c10_business_purpose": {"score": 0, "reason": "explanation"}
  },
  "total_score": 17,
  "sophistication": "simple|moderate|complex"
}
```
