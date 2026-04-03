#!/usr/bin/env python3
"""AI analysis call and dual scoring system."""

import os
import re
import json
from datetime import datetime


class AIAnalyzer:
    """Single AI call: analyze document, identify terminology, score categories."""

    def __init__(self, config_loader):
        self.config = config_loader
        self.client = self._setup_openai()

    def _setup_openai(self):
        try:
            import openai
            key_file = "/home/cliff/redact/openai_api_key.txt"
            if os.path.exists(key_file):
                with open(key_file, 'r') as f:
                    key = f.read().strip()
                client = openai.OpenAI(api_key=key)
                print("✅ OpenAI client initialized")
                return client
        except Exception as e:
            print(f"❌ OpenAI setup failed: {e}")
        return None

    def analyze(self, redacted_text, base_name, output_dir):
        """Run single AI call. Returns parsed JSON analysis."""
        if not self.client:
            print("   ❌ No OpenAI client")
            return None

        # Line-number the text
        lines = redacted_text.split('\n')
        numbered = '\n'.join(f"LINE {i:03d}: {line}" for i, line in enumerate(lines, 1) if line.strip())

        prompt = f"""{self.config.prompt}

LINE-NUMBERED NDA:
{numbered}

Respond with valid JSON only — no markdown fencing, no commentary."""

        print("   🔄 AI analysis call...")
        start = datetime.now()

        resp = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert real estate attorney reviewing NDAs from the Recipient's perspective. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=5000
        )

        raw = resp.choices[0].message.content.strip()
        dur = (datetime.now() - start).total_seconds()
        print(f"   ✅ AI call done in {dur:.1f}s")

        # Save raw output
        with open(os.path.join(output_dir, f"{base_name}_ai_raw.txt"), 'w') as f:
            f.write(raw)

        # Parse JSON
        clean = raw
        if clean.startswith('```'):
            clean = re.sub(r'^```(?:json)?\s*', '', clean)
            clean = re.sub(r'\s*```$', '', clean)
        clean = clean.replace('\t', '\\t').replace('\r', '\\r')

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parse error: {e}")
            with open(os.path.join(output_dir, f"{base_name}_parse_error.txt"), 'w') as f:
                f.write(f"Error: {e}\n\n{raw}")
            return None


class CodeScorer:
    """Independent code-based scoring using AI's factual findings."""

    def __init__(self, config_loader):
        self.config = config_loader
        self.required_roles = set(config_loader.config.get('required_roles', []))

    def score(self, analysis):
        """Score each category from AI's factual data. Returns dict of scores."""
        scores = {}
        a = analysis.get('analysis', {})

        # Cat 1: Carve-outs — count concepts
        c1 = a.get('1_carveouts', {})
        concepts = c1.get('concepts_found', [])
        n = len(concepts)
        if n == 0:
            scores['1_carveouts'] = 10
        elif n == 1:
            scores['1_carveouts'] = 8
        elif n == 2:
            scores['1_carveouts'] = 6
        else:
            scores['1_carveouts'] = 0

        # Cat 2: Representatives — count missing roles
        c2 = a.get('2_representatives', {})
        found = set(r.lower() for r in c2.get('roles_found', []))
        missing = self.required_roles - found
        if c2.get('quoted_language') == 'NOT FOUND' or not found:
            scores['2_representatives'] = 10
        elif len(found) <= 3:
            scores['2_representatives'] = 8
        elif len(missing) > 4:
            scores['2_representatives'] = 7
        elif len(missing) >= 2:
            scores['2_representatives'] = 5
        elif len(missing) == 1:
            scores['2_representatives'] = 3
        else:
            scores['2_representatives'] = 0

        # Cat 3: Sub-agreement — by type
        c3 = a.get('3_sub_agreement', {})
        req_type = c3.get('requirement_type', 'none')
        type_scores = {'sign': 9, 'bound': 7, 'directed': 3, 'informed': 0, 'none': 0}
        scores['3_sub_agreement'] = type_scores.get(req_type, 0)

        # Cat 4: Return/destroy
        c4 = a.get('4_return_destroy', {})
        trigger = c4.get('trigger', 'none')
        has_destroy = c4.get('has_destroy_option', False)
        if trigger == 'automatic':
            scores['4_return_destroy'] = 8
        elif trigger == 'both':
            scores['4_return_destroy'] = 6
        elif trigger == 'upon_request' and not has_destroy:
            scores['4_return_destroy'] = 4
        else:
            scores['4_return_destroy'] = 0

        # Cat 5: Non-circumvention
        c5 = a.get('5_non_circumvention', {})
        scope = c5.get('scope', 'none')
        time_limit = c5.get('time_limit_years')
        if scope == 'none':
            scores['5_non_circumvention'] = 0
        elif scope == 'broad' and not time_limit:
            scores['5_non_circumvention'] = 9
        elif scope == 'moderate' and not time_limit:
            scores['5_non_circumvention'] = 6
        elif scope == 'narrow' and not time_limit:
            scores['5_non_circumvention'] = 2
        elif time_limit and time_limit > 2:
            scores['5_non_circumvention'] = 5
        elif time_limit and time_limit <= 2:
            scores['5_non_circumvention'] = 2
        else:
            scores['5_non_circumvention'] = 2

        # Cat 6: Term
        c6 = a.get('6_term', {})
        dur = c6.get('duration_years')
        if dur is None and c6.get('quoted_language') == 'NOT FOUND':
            scores['6_term'] = 9
        elif dur is None:
            scores['6_term'] = 9  # indefinite/perpetual
        elif dur > 2:
            scores['6_term'] = 7
        else:
            scores['6_term'] = 0

        # Cat 7: Effective date
        c7 = a.get('7_effective_date', {})
        if c7.get('preamble_date_blank'):
            scores['7_effective_date'] = 8
        elif c7.get('quoted_language') == 'NOT FOUND':
            scores['7_effective_date'] = 7
        elif not c7.get('has_effective_date_label'):
            scores['7_effective_date'] = 4
        elif c7.get('signature_page_date_only'):
            scores['7_effective_date'] = 2
        else:
            scores['7_effective_date'] = 0

        # Cat 8: Legal compliance
        c8 = a.get('8_legal_compliance', {})
        if c8.get('quoted_language') == 'NOT FOUND':
            scores['8_legal_compliance'] = 8
        elif not c8.get('has_notice_requirement'):
            scores['8_legal_compliance'] = 6
        elif not c8.get('has_cooperation_provision'):
            scores['8_legal_compliance'] = 3
        else:
            scores['8_legal_compliance'] = 0

        # Cat 9: Remedies
        c9 = a.get('9_remedies', {})
        punitive = c9.get('has_punitive_language', False)
        injunctive = c9.get('has_injunctive_relief', False)
        bond = c9.get('has_bond_waiver', False)
        if punitive and not injunctive:
            scores['9_remedies'] = 9 if not bond else 7
        elif injunctive and not bond:
            scores['9_remedies'] = 5
        elif injunctive and bond and punitive:
            scores['9_remedies'] = 2
        else:
            scores['9_remedies'] = 0

        # Circumstantial — pass through AI scores (binary checks)
        for key in ['c1_electronic_sig', 'c2_reasonable_fees', 'c3_indemnification',
                     'c4_obligation_to_proceed', 'c5_personal_financial', 'c6_signature_notation',
                     'c7_commercial_reasonableness', 'c8_defined_term_consistency', 'c9_business_purpose']:
            entry = a.get(key, {})
            scores[key] = entry.get('score', 0)

        return scores


def resolve_scores(ai_analysis, code_scores):
    """Dual scoring: take max(ai_score, code_score) per category."""
    ai_scores = {}
    for key, val in ai_analysis.get('analysis', {}).items():
        if isinstance(val, dict):
            ai_scores[key] = val.get('score', 0)

    final = {}
    all_keys = set(list(ai_scores.keys()) + list(code_scores.keys()))
    for key in all_keys:
        ai_s = ai_scores.get(key, 0)
        code_s = code_scores.get(key, 0)
        final[key] = max(ai_s, code_s)

    return final, ai_scores, code_scores


def apply_thresholds(final_scores, config):
    """Determine which categories to act on based on threshold rules."""
    thresholds = config.get('thresholds', {})
    auto = thresholds.get('auto_apply', 8)
    should_total = thresholds.get('should_apply_total', 15)
    should_count = thresholds.get('should_apply_count', 3)
    nice_total = thresholds.get('nice_to_have_total', 20)
    nice_high = thresholds.get('nice_to_have_high_count', 2)

    total = sum(final_scores.values())
    items_8_plus = [k for k, s in final_scores.items() if s >= auto]
    items_5_7 = [k for k, s in final_scores.items() if 5 <= s <= 7]
    items_1_4 = [k for k, s in final_scores.items() if 1 <= s <= 4]

    applied = list(items_8_plus)

    if items_5_7 and (total >= should_total or len(items_5_7) >= should_count or len(items_8_plus) > 0):
        applied.extend(items_5_7)

    if items_1_4 and (total >= nice_total or len(items_8_plus) >= nice_high):
        applied.extend(items_1_4)

    return applied, total
