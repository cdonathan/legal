#!/usr/bin/env python3
"""Rules engine: generates surgical edits based on analysis and scores."""

from datetime import datetime


class RulesEngine:
    """Generates a list of surgical edit operations from analysis + applied categories."""

    def __init__(self, config_loader):
        self.config = config_loader.config
        self.templates = config_loader.templates
        self.required_roles = self.config.get('required_roles', [])

    def generate_edits(self, analysis, applied_items):
        """Returns list of edit operations: {type, find, replace, anchor, content, category}."""
        edits = []
        term = analysis.get('terminology', {})
        a = analysis.get('analysis', {})

        for item in applied_items:
            rule_cfg = self.config.get('rules', {}).get(item, {})
            if isinstance(rule_cfg, dict) and not rule_cfg.get('enabled', True):
                continue
            circ_cfg = self.config.get('circumstantial_rules', {})
            if item.startswith('c') and not circ_cfg.get(item, True):
                continue

            method = getattr(self, f'_rule_{item}', None)
            if method:
                new_edits = method(term, a, rule_cfg)
                edits.extend(new_edits)

        return edits

    def _fmt(self, template, term, **kwargs):
        """Fill template with terminology."""
        return template.format(
            conf_info_term=term.get('conf_info_term', 'Confidential Information'),
            receiver_term=term.get('receiver_term', 'Recipient'),
            provider_term=term.get('provider_term', 'Discloser'),
            reps_term=term.get('reps_term', 'Representatives'),
            current_date=datetime.now().strftime('%B %d, %Y'),
            duration='1 year',
            letter='c',
            **kwargs
        )

    # === CATEGORY 1: CARVE-OUTS ===
    def _rule_1_carveouts(self, term, a, cfg):
        edits = []
        data = a.get('1_carveouts', {})
        concepts = set(data.get('concepts_found', []))
        all_concepts = {'public', 'prior_possession', 'independent_dev'}
        missing = all_concepts - concepts
        quoted = data.get('quoted_language', '')

        if len(missing) == 3 or quoted == 'NOT FOUND':
            # Insert full carve-out block after conf info definition
            # Try to anchor using other category quotes that are near the definition
            anchor = quoted if quoted != 'NOT FOUND' else ''
            if not anchor:
                for key in ['2_representatives', '3_sub_agreement', '4_return_destroy']:
                    q = a.get(key, {}).get('quoted_language', '')
                    if q and q != 'NOT FOUND':
                        anchor = q
                        break
            edits.append({
                'type': 'insert_block',
                'anchor_quote': anchor,
                'anchor_description': 'after confidential info definition',
                'content': self._fmt(self.templates['carveout_block'], term),
                'category': '1_carveouts'
            })
        else:
            # Find the end of existing carve-out text and append missing concepts
            # Use last portion of quoted language as anchor, avoiding ligature issues
            if quoted and len(quoted) > 20:
                # Take last 40 chars, strip trailing punctuation, clean up
                anchor = quoted.rstrip('.').strip()
                # Try progressively shorter anchors if needed
                anchors = [anchor[-50:], anchor[-40:], anchor[-30:], anchor[-20:]]
                for concept in sorted(missing):
                    key = f'carveout_{concept}'
                    if key in self.templates:
                        letter = chr(ord('a') + len(concepts))
                        text = self.templates[key].format(
                            letter=letter,
                            conf_info_term=term.get('conf_info_term', 'Confidential Information'),
                            receiver_term=term.get('receiver_term', 'Recipient'),
                            reps_term=term.get('reps_term', 'Representatives')
                        )
                        edits.append({
                            'type': 'insert_after',
                            'find_candidates': anchors,
                            'content': text,
                            'category': '1_carveouts'
                        })
                        concepts.add(concept)
        return edits

    # === CATEGORY 2: REPRESENTATIVES ===
    def _rule_2_representatives(self, term, a, cfg):
        edits = []
        data = a.get('2_representatives', {})
        found = set(r.lower() for r in data.get('roles_found', []))
        required = set(r.lower() for r in self.required_roles)
        missing = sorted(required - found)
        quoted = data.get('quoted_language', '')

        if missing and quoted and quoted != 'NOT FOUND':
            # Find the last role in the quoted text to anchor insertion
            roles_in_doc = data.get('roles_found', [])
            if roles_in_doc:
                last_role = roles_in_doc[-1]
                insert_text = ', ' + ', '.join(missing) + ','
                edits.append({
                    'type': 'insert_after',
                    'find': last_role,
                    'content': insert_text,
                    'category': '2_representatives'
                })
        elif missing and (not quoted or quoted == 'NOT FOUND'):
            # No representatives clause — need to insert one
            insert_text = ', '.join(self.required_roles)
            edits.append({
                'type': 'insert_block',
                'anchor_description': 'after confidentiality obligation',
                'content': f'{term.get("receiver_term", "Recipient")} may share the {term.get("conf_info_term", "Confidential Information")} with its {insert_text} ("Representatives").',
                'category': '2_representatives'
            })

        if not term.get('reps_term') or term.get('reps_term') == 'null':
            edits.append({
                'type': 'insert_after',
                'find': (data.get('roles_found', [''])[-1] if data.get('roles_found') else ''),
                'content': ' ("Representatives")',
                'category': '2_representatives'
            })
        return edits

    # === CATEGORY 3: SUB-AGREEMENT ===
    def _rule_3_sub_agreement(self, term, a, cfg):
        edits = []
        data = a.get('3_sub_agreement', {})
        req_type = data.get('requirement_type', 'none')

        swap_map = {
            'sign': {
                'patterns': ['sign a copy of this Agreement', 'sign a confidentiality agreement',
                             'obtain the written agreement of', 'sign a separate'],
                'replace': 'are informed of the confidential nature of the ' + term.get('conf_info_term', 'Confidential Information')
            },
            'bound': {
                'patterns': ['agree to be bound by', 'bound by its terms', 'bound by the provisions',
                             'bound by the terms'],
                'replace': 'informed of the confidential nature of the ' + term.get('conf_info_term', 'Confidential Information')
            }
        }

        if req_type in swap_map:
            for pattern in swap_map[req_type]['patterns']:
                edits.append({
                    'type': 'swap_phrase',
                    'find': pattern,
                    'replace': swap_map[req_type]['replace'],
                    'category': '3_sub_agreement'
                })
        return edits

    # === CATEGORY 4: RETURN/DESTROY ===
    def _rule_4_return_destroy(self, term, a, cfg):
        edits = []
        data = a.get('4_return_destroy', {})
        trigger = data.get('trigger', 'none')
        has_destroy = data.get('has_destroy_option', False)

        if trigger == 'automatic':
            for phrase in ['upon termination', 'upon expiration', 'upon completion',
                           'upon the termination', 'upon the expiration']:
                edits.append({
                    'type': 'swap_phrase',
                    'find': phrase,
                    'replace': f"Upon {term.get('provider_term', 'Discloser')}'s request",
                    'category': '4_return_destroy'
                })

        if not has_destroy:
            edits.append({
                'type': 'insert_after',
                'find': 'return the',
                'content': ' or destroy/delete the',
                'category': '4_return_destroy'
            })
        return edits

    # === CATEGORY 5: NON-CIRCUMVENTION ===
    def _rule_5_non_circumvention(self, term, a, cfg):
        edits = []
        data = a.get('5_non_circumvention', {})
        if data.get('scope', 'none') == 'none':
            return edits

        action = cfg.get('action', 'delete') if isinstance(cfg, dict) else 'delete'
        if action == 'delete':
            edits.append({
                'type': 'delete_block',
                'anchor_description': 'non-circumvention paragraph',
                'quoted': data.get('quoted_language', ''),
                'category': '5_non_circumvention'
            })
        else:
            edits.append({
                'type': 'insert_words',
                'anchor_description': 'end of non-circumvention clause',
                'content': ' for one (1) year',
                'category': '5_non_circumvention'
            })
        return edits

    # === CATEGORY 6: TERM ===
    def _rule_6_term(self, term, a, cfg):
        edits = []
        data = a.get('6_term', {})
        dur = data.get('duration_years')
        ladder = cfg.get('reduction_ladder', {}) if isinstance(cfg, dict) else {}

        if dur is None or data.get('quoted_language') == 'NOT FOUND':
            add_dur = ladder.get('none', '1 year')
            content = self.templates['term_clause'].format(duration=add_dur)
            # Anchor after the last clause we can find
            anchor = ''
            for key in ['8_legal_compliance', '4_return_destroy', '5_non_circumvention',
                        '3_sub_agreement', '2_representatives', '1_carveouts']:
                q = a.get(key, {}).get('quoted_language', '')
                if q and q != 'NOT FOUND':
                    anchor = q
                    break
            edits.append({
                'type': 'insert_block',
                'anchor_quote': anchor,
                'anchor_description': 'after last clause',
                'content': content,
                'category': '6_term'
            })
        elif dur >= 5:
            target = ladder.get('5+', 'three (3) years')
            edits.append({
                'type': 'swap_phrase',
                'find_patterns': [f'five (5) years', '5 years', f'five years'],
                'replace': target,
                'category': '6_term'
            })
        elif dur >= 3:
            target = ladder.get('3-4', 'two (2) years')
            for n, w in [(4, 'four'), (3, 'three')]:
                edits.append({
                    'type': 'swap_phrase',
                    'find_patterns': [f'{w} ({n}) years', f'{n} years', f'{w} years'],
                    'replace': target,
                    'category': '6_term'
                })
        # 1-2 years: leave alone
        return edits

    # === CATEGORY 7: EFFECTIVE DATE ===
    def _rule_7_effective_date(self, term, a, cfg):
        edits = []
        data = a.get('7_effective_date', {})
        today = datetime.now().strftime('%B %d, %Y')
        use_as_of = cfg.get('use_dated_as_of', True) if isinstance(cfg, dict) else True
        quoted = data.get('quoted_language', '')

        if data.get('preamble_date_blank'):
            # Fill blank date — use quoted text to find the blank
            if quoted and quoted != 'NOT FOUND':
                # Try to find blank patterns within the quoted text
                for pattern in ['_____ day of _____', '________________,', '____day of ____',
                                '_____ day of _______________,', '______ day of',
                                '_________,', '_____________, ___', '_____________,  ___']:
                    if pattern in quoted or '_' in quoted:
                        edits.append({
                            'type': 'swap_phrase',
                            'find': pattern,
                            'replace': f'{today} ("Effective Date")',
                            'category': '7_effective_date'
                        })
                # Also try the raw quoted text with underscores
                blank_match = None
                for seg in quoted.split():
                    if '_' in seg:
                        blank_match = seg
                        break
                if blank_match and not edits:
                    edits.append({
                        'type': 'swap_phrase',
                        'find': blank_match,
                        'replace': today,
                        'category': '7_effective_date'
                    })
        elif data.get('signature_page_date_only'):
            # Date on signature page only — that's fine per attorney rules
            pass
        elif not data.get('has_effective_date_label') and quoted and quoted != 'NOT FOUND':
            # Date exists but no label — find the date and add label after
            # Use first 30 chars of quoted as anchor
            anchor = quoted[:40].strip()
            if anchor:
                edits.append({
                    'type': 'insert_after',
                    'find': anchor,
                    'content': ' ("Effective Date")',
                    'category': '7_effective_date'
                })
        return edits

    # === CATEGORY 8: LEGAL COMPLIANCE ===
    def _rule_8_legal_compliance(self, term, a, cfg):
        edits = []
        data = a.get('8_legal_compliance', {})
        if data.get('quoted_language') == 'NOT FOUND':
            # Anchor after the confidentiality obligation or return/destroy clause
            # Use quoted text from nearby categories as anchor
            anchor = ''
            for key in ['4_return_destroy', '3_sub_agreement', '2_representatives', '1_carveouts']:
                q = a.get(key, {}).get('quoted_language', '')
                if q and q != 'NOT FOUND':
                    anchor = q
                    break
            edits.append({
                'type': 'insert_block',
                'anchor_quote': anchor,
                'anchor_description': 'after confidentiality obligation paragraph',
                'content': self._fmt(self.templates['legal_compliance_block'], term),
                'category': '8_legal_compliance'
            })
        return edits

    # === CATEGORY 9: REMEDIES ===
    def _rule_9_remedies(self, term, a, cfg):
        edits = []
        data = a.get('9_remedies', {})

        if data.get('has_punitive_language'):
            for phrase in ['any and all forms and types of remuneration',
                           'all expenses incurred in enforcing',
                           'consequential and incidental damages']:
                edits.append({
                    'type': 'delete_phrase',
                    'find': phrase,
                    'category': '9_remedies'
                })

        if data.get('has_injunctive_relief') and not data.get('has_bond_waiver'):
            edits.append({
                'type': 'insert_after',
                'find': 'injunctive relief',
                'content': ' without necessity of posting any bond',
                'category': '9_remedies'
            })
        return edits

    # === CIRCUMSTANTIAL RULES ===
    def _rule_c1_electronic_sig(self, term, a, cfg):
        if not a.get('c1_electronic_sig', {}).get('found'):
            return []
        return [{'type': 'insert_after', 'find': 'facsimile', 'content': ' or electronic', 'category': 'c1'}]

    def _rule_c2_reasonable_fees(self, term, a, cfg):
        if not a.get('c2_reasonable_fees', {}).get('found'):
            return []
        edits = []
        for phrase in ["attorney's fees", "attorneys' fees", "attorneys fees"]:
            edits.append({'type': 'add_qualifier', 'find': phrase, 'qualifier': 'reasonable ', 'category': 'c2'})
        return edits

    def _rule_c3_indemnification(self, term, a, cfg):
        if not a.get('c3_indemnification', {}).get('found'):
            return []
        return [{'type': 'insert_after', 'find': 'any disclosure', 'content': ' that is in breach of this Agreement', 'category': 'c3'}]

    def _rule_c4_obligation_to_proceed(self, term, a, cfg):
        if not a.get('c4_obligation_to_proceed', {}).get('found'):
            return []
        return [{'type': 'append_sentence', 'anchor_description': 'before signature block',
                 'content': self._fmt(self.templates['no_obligation'], term), 'category': 'c4'}]

    def _rule_c5_personal_financial(self, term, a, cfg):
        if not a.get('c5_personal_financial', {}).get('found'):
            return []
        return [{'type': 'swap_word', 'find': 'personal', 'replace': 'business', 'category': 'c5'}]

    def _rule_c6_signature_notation(self, term, a, cfg):
        if not a.get('c6_signature_notation', {}).get('found'):
            return []
        return [{'type': 'insert_before_signature', 'content': self.templates['signature_notation'], 'category': 'c6'}]

    def _rule_c7_commercial_reasonableness(self, term, a, cfg):
        if not a.get('c7_commercial_reasonableness', {}).get('found'):
            return []
        edits = []
        for find, repl in [('take all steps', 'take all commercially reasonable steps'),
                           ('shall ensure', 'shall use commercially reasonable efforts to ensure'),
                           ('best efforts', 'commercially reasonable efforts')]:
            edits.append({'type': 'swap_phrase', 'find': find, 'replace': repl, 'category': 'c7'})
        return edits

    def _rule_c8_defined_term_consistency(self, term, a, cfg):
        # Code-driven normalization — handled in document editor
        return []

    def _rule_c9_business_purpose(self, term, a, cfg):
        if not a.get('c9_business_purpose', {}).get('found'):
            return []
        return [{'type': 'insert_words', 'anchor_description': 'in purpose clause',
                 'content': ', purchasing', 'category': 'c9'}]
