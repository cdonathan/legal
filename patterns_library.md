# Patterns Library - Attorney Decision-Making Patterns for NDA Redlining

## 🧠 COMPLETE PATTERN DEFINITIONS FOR AI IMPLEMENTATION

### **UNIVERSAL PATTERNS (Always Applied)**

#### **Pattern 1: Confidential Information Exclusions**
**Trigger:** Any NDA without standard exclusions
**Detection:**
```
MISSING (needs fixing): No exclusions defined for confidential information
PRESENT (good): Contains exclusions for publicly available, already possessed, or independently developed information
```
**AI Instruction:** IF no exclusions present, ADD standard 3-part exclusions:
- Information already in possession prior to disclosure
- Information available to public generally  
- Information independently developed without reliance on confidential information

#### **Pattern 2: Expanded Disclosure Recipients**
**Trigger:** Limited disclosure lists
**Detection:**
```
LIMITED (needs fixing): Only "employees, legal counsel"
EXPANDED (good): Includes "investors, members, managers, officers, directors, partners, advisors"
```
**AI Instruction:** IF disclosure list is limited, ADD business-necessary recipients: "investors, members, managers, officers, directors, partners, advisors"

#### **Pattern 3: Effective Date Definition**
**Trigger:** Any agreement without clear date definition
**Detection:**
```
MISSING (needs fixing): No "Effective Date" defined
PRESENT (good): "Effective Date" clearly defined in document
```
**AI Instruction:** IF no Effective Date definition, ADD definition in signature section or preamble

---

### **CONDITIONAL PATTERNS (Trigger-Based)**

#### **Pattern 4: Return/Destruction Flexibility**
**Trigger:** Rigid return-only requirements
**Detection:**
```
RIGID (needs fixing): "must be returned to Disclosing Party"
RIGID (needs fixing): "shall return all materials"
FLEXIBLE (good): "returned to Disclosing Party OR destroyed/deleted"
FLEXIBLE (good): "if hard copies: return; if electronic: destroy/delete"
```
**AI Instruction:** IF you see only "return" or "must return" without destroy option, ADD "or destroy/delete" alternative

#### **Pattern 5: Sophistication-Based Approach**
**Trigger:** Document complexity level
**Detection:**
```
SIMPLE NDA (needs major changes):
- No confidential information exclusions
- Basic disclosure language (under 3 recipients listed)
- Missing standard protections (no injunctive relief, no legal exceptions)
- Short document (under 2 pages)

SOPHISTICATED NDA (needs targeted changes):
- Already has exclusions defined
- Detailed confidentiality provisions
- Professional legal language
- Longer document (2+ pages with multiple sections)
```
**AI Instruction:** IF NDA is missing 3+ standard protections, apply comprehensive overhaul. IF NDA has most protections, make targeted enhancements only.

#### **Pattern 6: Commercial Reasonableness Standards**
**Trigger:** Absolute obligations on purchaser
**Detection:**
```
ABSOLUTE (needs fixing): "take all steps to ensure"
ABSOLUTE (needs fixing): "shall ensure" or "must guarantee"
REASONABLE (good): "take commercially reasonable steps"
REASONABLE (good): "use reasonable efforts"
```
**AI Instruction:** IF you see "all steps" or "ensure" or "guarantee", REPLACE with "commercially reasonable steps"

#### **Pattern 7: Legal Compliance Exceptions**
**Trigger:** NDAs without legal disclosure provisions
**Detection:**
```
MISSING (needs fixing): No mention of legal requirements, court orders, or legal process
PRESENT (good): "required by law" or "court order" or "legal process"
PRESENT (good): "compelled by legal process" or "pursuant to court order"
```
**AI Instruction:** IF no legal disclosure exception exists, ADD "may disclose if required by court order or applicable law, provided prompt notice is given to Disclosing Party"

#### **Pattern 8: Fee Protection**
**Trigger:** Unqualified attorney fee obligations
**Detection:**
```
UNQUALIFIED (needs fixing): "attorney's fees"
UNQUALIFIED (needs fixing): "legal fees and costs"
QUALIFIED (good): "reasonable attorney's fees"
QUALIFIED (good): "actual attorney's fees incurred"
```
**AI Instruction:** IF you see "attorney's fees" without qualifier, ADD "reasonable" before "attorney's fees"

#### **Pattern 9: Injunctive Relief Balance**
**Trigger:** Missing or unbalanced injunctive relief provisions
**Detection:**
```
MISSING (needs fixing): No injunctive relief clause
UNBALANCED (needs fixing): "entitled to injunction and must post bond"
UNBALANCED (needs fixing): "shall post security for injunctive relief"
BALANCED (good): "entitled to injunctive relief without posting bond"
BALANCED (good): "equitable remedies available without bond"
```
**AI Instruction:** IF no injunctive relief clause, ADD "entitled to equitable relief without necessity of posting bond"

#### **Pattern 10: Term Limitation**
**Trigger:** Perpetual or unclear duration
**Detection:**
```
PROBLEMATIC (needs fixing): "obligations shall continue indefinitely"
PROBLEMATIC (needs fixing): "in perpetuity" or no termination clause
REASONABLE (good): "expire one (1) year after Effective Date"
REASONABLE (good): "terminate two (2) years from execution"
```
**AI Instruction:** IF no termination date OR perpetual language, ADD "expire one (1) year after Effective Date"

#### **Pattern 11: Defined Term Consistency**
**Trigger:** Inconsistent term usage
**Detection:**
```
INCONSISTENT (needs fixing): "confidential information" and "Confidential Information" mixed usage
INCONSISTENT (needs fixing): "the agreement" instead of "this Agreement"
INCONSISTENT (needs fixing): "subject business" and "Subject Business" mixed
CONSISTENT (good): "Confidential Information" capitalized throughout
CONSISTENT (good): "Subject Business" defined and capitalized consistently
```
**AI Instruction:** IF key terms are used inconsistently (mixed capitalization), standardize to capitalized defined terms throughout document

#### **Pattern 12: Execution Flexibility**
**Trigger:** Rigid execution requirements
**Detection:**
```
RIGID (needs fixing): "original signatures required"
RIGID (needs fixing): "wet signatures only"
RIGID (needs fixing): No mention of counterparts or electronic signatures
FLEXIBLE (good): "may be executed in counterparts"
FLEXIBLE (good): "facsimile or electronic signatures acceptable"
```
**AI Instruction:** IF no counterpart language, ADD "This Agreement may be executed in counterparts and electronic signatures are acceptable"

---

## 🤖 AI IMPLEMENTATION DECISION TREE

```
FOR EACH NDA:

1. ASSESS SOPHISTICATION (Pattern 5)
   ├─ Count missing standard protections
   ├─ IF missing 3+ → Apply comprehensive approach
   └─ IF missing <3 → Apply targeted approach

2. CHECK UNIVERSAL PATTERNS (1-3)
   ├─ Pattern 1: Confidential info exclusions present? → If NO, add standard exclusions
   ├─ Pattern 2: Disclosure recipients expanded? → If NO, add business recipients  
   └─ Pattern 3: Effective Date defined? → If NO, add definition

3. CHECK CONDITIONAL PATTERNS (4,6-12)
   ├─ Pattern 4: Return flexibility? → If rigid, add destroy option
   ├─ Pattern 6: Reasonable standards? → If absolute, add reasonableness
   ├─ Pattern 7: Legal exceptions? → If missing, add court order exception
   ├─ Pattern 8: Fee qualification? → If unqualified, add "reasonable"
   ├─ Pattern 9: Injunctive relief? → If missing/unbalanced, add balanced clause
   ├─ Pattern 10: Term limitation? → If perpetual, add 1-year limit
   ├─ Pattern 11: Term consistency? → If inconsistent, standardize capitalization
   └─ Pattern 12: Execution flexibility? → If rigid, add counterpart provision

4. APPLY ONLY TRIGGERED PATTERNS
   └─ Do not add patterns where conditions are not met
```

## 🎯 PATTERN PRIORITY ORDER

**High Priority (Always Check):**
1. Pattern 1: Confidential Information Exclusions
2. Pattern 2: Expanded Disclosure Recipients  
3. Pattern 7: Legal Compliance Exceptions

**Medium Priority (Common Triggers):**
4. Pattern 6: Commercial Reasonableness
5. Pattern 8: Fee Protection
6. Pattern 10: Term Limitation

**Low Priority (Context Dependent):**
7. Pattern 4: Return/Destruction Flexibility
8. Pattern 9: Injunctive Relief Balance
9. Pattern 11: Defined Term Consistency
10. Pattern 12: Execution Flexibility

**Meta Priority:**
11. Pattern 5: Sophistication Assessment (determines approach level)

---

## 📋 USAGE NOTES

- **Patterns are conditional** - only apply when trigger conditions are met
- **Attorney is surgical** - makes precise changes, not blanket additions
- **Purchaser protection focus** - all patterns bias toward protecting the buyer
- **Consistency across samples** - patterns validated across 5 different NDAs
- **Scalable to thousands** - designed for automated application to large document sets
