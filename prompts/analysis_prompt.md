# NDA Analysis Prompt (Single Call)

You are an experienced real estate attorney reviewing this NDA from the **Recipient's perspective** (the party being asked to sign).

Read the NDA carefully. For each category below, quote the relevant language and score it.

## STEP 1: IDENTIFY DOCUMENT TERMINOLOGY

What does this NDA call:
- The confidential information? (e.g., "Information", "Confidential Information", "Evaluation Material")
- The recipient/buyer? (e.g., "Buyer", "Prospective Purchaser", "you", "Receiving Party")
- The provider/discloser? (e.g., "Owner", "Seller", "us", "Disclosing Party")
- The recipient's representatives? (e.g., "Representatives", "Related Parties", "Advisors")

## STEP 2: ANALYZE AND SCORE EACH CATEGORY

For each category, you MUST either:
- Quote the exact language from the NDA that addresses it, OR
- State "NOT FOUND"

Then assign a score using the rubric provided.

### Category 1: Carve-outs of "Confidential Information"
Three required concepts:
- (a) Information already in Recipient's or Representatives' possession prior to disclosure
- (b) Information available to the public generally (not through breach)
- (c) Information independently developed by Recipient or Representatives without reliance on Confidential Information

**Search for:** "shall not include", "does not include", "notwithstanding", "excludes", "exception"

QUOTE the language, or state NOT FOUND.

Scoring:
- 10 = No carve-outs exist at all
- 8 = Only 1 of 3 concepts present
- 6 = 2 of 3 concepts present
- 3 = All 3 present but weak/ambiguous wording
- 0 = All 3 present with clear language

### Category 2: Sharing — Representatives Breadth
Who can the Recipient share information with?

Required roles: affiliates, directors, officers, employees, members, partners, investors, agents, attorneys, accountants, brokers, consultants, advisors

QUOTE the language, or state NOT FOUND. List every role mentioned.

Scoring:
- 10 = No sharing rights at all
- 8 = Very narrow (3 or fewer roles)
- 7 = Moderate list but missing financial players (investors, partners, members)
- 5 = Has some financial players but missing 2+ key ones
- 3 = Broad list missing only 1 minor role
- 0 = Broad list with financial players or catch-all language

### Category 3: Sub-Agreement / Binding Requirements
What must Representatives do? Sign a separate agreement? Be "bound by"? Be "informed of"?

QUOTE the language, or state NOT FOUND.

Scoring:
- 9 = Must sign separate confidentiality agreement
- 7 = Must "agree to be bound by" this agreement
- 3 = Must be "directed to keep confidential" / "abide by terms" / "act in accordance with"
- 0 = Must be "informed of confidential nature" OR no mention

### Category 4: Return / Destroy
Is return/destroy automatic or upon request? Does it include a destroy option?

QUOTE the language, or state NOT FOUND.

Scoring:
- 8 = Automatic return/destroy, no request trigger
- 6 = Dual trigger (automatic AND upon request)
- 4 = Upon request only, but no destroy option
- 0 = Upon request with destroy option, OR no clause

### Category 5: Non-Circumvention
Are there restrictions on contacting third parties introduced by the provider?

QUOTE the language, or state NOT FOUND.

Scoring:
- 9 = Broad: cannot contact ANY third party, no time limit
- 6 = Moderate: limited to property/transaction, no time limit
- 5 = Any non-circumvention with time limit >2 years
- 2 = Narrowly scoped, time limit 1-2 years
- 0 = No non-circumvention clause

### Category 6: Term / Duration
How long does the agreement last?

QUOTE the language, or state NOT FOUND.

Scoring:
- 9 = No term/expiration/termination clause at all
- 9 = Indefinite or perpetual
- 7 = Term >2 years
- 0 = Term 1-2 years
- 0 = Term <1 year

### Category 7: Effective Date
Is there a date in the preamble?

QUOTE the language, or state NOT FOUND.

Scoring:
- 8 = Blank date field in preamble
- 7 = No date anywhere
- 4 = Date exists but no "Effective Date" label
- 2 = Date on signature page only
- 0 = Effective Date properly defined

### Category 8: Legal Compliance Exceptions
Can the Recipient disclose if required by court order, subpoena, or legal process?

**Search for:** "court order", "subpoena", "legally required", "compelled by law", "regulatory requirement"

QUOTE the language, or state NOT FOUND.

Scoring:
- 8 = No legal compliance exception at all
- 6 = Exception exists but no notice requirement to provider
- 3 = Exception with notice but no cooperation/protective order language
- 0 = Full exception with notice and cooperation provisions

### Category 9: Remedies Balance
Is the remedies/damages section disproportionately punitive against the Recipient?

**Red flags:** "any and all forms and types of remuneration", "consequential and incidental damages", "all expenses incurred in enforcing", open-ended liability, no injunctive relief, injunctive relief requiring bond.

QUOTE the language, or state NOT FOUND.

Scoring:
- 9 = Highly punitive: open-ended damages + no injunctive relief + no bond waiver
- 7 = Punitive damages present without injunctive relief
- 5 = Injunctive relief requires bond, OR punitive damages with some limits
- 2 = Injunctive relief without bond, but damages still broad
- 0 = Balanced: injunctive relief without bond, damages limited to breach

### Circumstantial Categories (score 0 if no relevant clause exists)

- C1 Electronic Signatures: Mentions "facsimile" without "electronic"? Score 4 if yes, 0 otherwise.
- C2 Reasonable Fees: Attorney's fees clause without "reasonable"? Score 4 if yes, 0 otherwise.
- C3 Narrow Indemnification: Indemnification covers "any disclosure" (not limited to breach)? Score 5 if yes, 0 otherwise.
- C4 No Obligation to Proceed: NDA implies obligation to transact? Score 5 if yes, 0 otherwise.
- C5 Personal Financial Disclosure: Requires personal financial statements? Score 5 if yes, 0 otherwise.
- C6 Signature Page Notation: Signature block without notation/page break? Score 3 if yes, 0 otherwise.
- C7 Commercial Reasonableness: Absolute language like "take all steps", "shall ensure", "best efforts" without reasonableness qualifier? Score 4 if yes, 0 otherwise.
- C8 Defined Term Consistency: Mixed capitalization of defined terms? Score 3 if yes, 0 otherwise.
- C9 Business Purpose Expansion: Purpose narrowly worded without "purchasing" or acquisition language? Score 4 if yes, 0 otherwise.

## OUTPUT FORMAT

Respond with valid JSON only — no markdown fencing, no commentary.

```json
{
  "terminology": {
    "conf_info_term": "term used",
    "receiver_term": "term used",
    "provider_term": "term used",
    "reps_term": "term used or null"
  },
  "analysis": {
    "1_carveouts": {
      "quoted_language": "exact quote or NOT FOUND",
      "concepts_found": ["public", "prior_possession", "independent_dev"],
      "score": 8,
      "reason": "brief explanation"
    },
    "2_representatives": {
      "quoted_language": "exact quote or NOT FOUND",
      "roles_found": ["directors", "officers", "employees"],
      "score": 7,
      "reason": "brief explanation"
    },
    "3_sub_agreement": {
      "quoted_language": "exact quote or NOT FOUND",
      "requirement_type": "sign|bound|directed|informed|none",
      "score": 0,
      "reason": "brief explanation"
    },
    "4_return_destroy": {
      "quoted_language": "exact quote or NOT FOUND",
      "trigger": "automatic|upon_request|both|none",
      "has_destroy_option": false,
      "score": 0,
      "reason": "brief explanation"
    },
    "5_non_circumvention": {
      "quoted_language": "exact quote or NOT FOUND",
      "scope": "broad|moderate|narrow|none",
      "time_limit_years": null,
      "score": 0,
      "reason": "brief explanation"
    },
    "6_term": {
      "quoted_language": "exact quote or NOT FOUND",
      "duration_years": null,
      "score": 0,
      "reason": "brief explanation"
    },
    "7_effective_date": {
      "quoted_language": "exact quote or NOT FOUND",
      "preamble_date_blank": false,
      "has_effective_date_label": false,
      "has_dated_as_of": false,
      "signature_page_date_only": false,
      "score": 0,
      "reason": "brief explanation"
    },
    "8_legal_compliance": {
      "quoted_language": "exact quote or NOT FOUND",
      "has_notice_requirement": false,
      "has_cooperation_provision": false,
      "score": 0,
      "reason": "brief explanation"
    },
    "9_remedies": {
      "quoted_language": "exact quote or NOT FOUND",
      "has_punitive_language": false,
      "has_injunctive_relief": false,
      "has_bond_waiver": false,
      "score": 0,
      "reason": "brief explanation"
    },
    "c1_electronic_sig": { "found": false, "score": 0, "reason": "brief explanation" },
    "c2_reasonable_fees": { "found": false, "score": 0, "reason": "brief explanation" },
    "c3_indemnification": { "found": false, "score": 0, "reason": "brief explanation" },
    "c4_obligation_to_proceed": { "found": false, "score": 0, "reason": "brief explanation" },
    "c5_personal_financial": { "found": false, "score": 0, "reason": "brief explanation" },
    "c6_signature_notation": { "found": false, "score": 0, "reason": "brief explanation" },
    "c7_commercial_reasonableness": { "found": false, "score": 0, "reason": "brief explanation" },
    "c8_defined_term_consistency": { "found": false, "score": 0, "reason": "brief explanation" },
    "c9_business_purpose": { "found": false, "score": 0, "reason": "brief explanation" }
  },
  "total_score": 0
}
```
