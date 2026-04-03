#!/usr/bin/env python3
"""Document editor: applies surgical edits to DOCX with track changes via LibreOffice."""

import os
import re
import subprocess
import shutil
import time
import uno
from com.sun.star.beans import PropertyValue


class DocumentEditor:
    """Applies edit operations to a DOCX using LibreOffice UNO API with track changes."""

    def __init__(self, output_dir):
        self.output_dir = output_dir

    def apply_edits(self, edits, docx_path, base_name, mapping_path, pii_redactor):
        """Apply all edits to document, produce output files."""
        if not edits:
            print("   ⚠️ No edits to apply — document is adequate")
            return {}

        try:
            print("   🔄 Starting LibreOffice...")
            os.system("pkill -f 'soffice'")
            time.sleep(2)

            document = self._open_document(docx_path)
            if not document:
                return {}

            document.setPropertyValue("RecordChanges", True)
            print("   ✓ Track changes enabled")

            applied = 0
            for edit in edits:
                if self._apply_edit(document, edit):
                    applied += 1

            print(f"   📊 Applied {applied}/{len(edits)} edits")

            outputs = self._save_outputs(document, base_name, mapping_path, pii_redactor)
            document.close(True)
            return outputs

        except Exception as e:
            print(f"   ❌ Document editing failed: {e}")
            return {}
        finally:
            time.sleep(1)
            os.system("pkill -f 'soffice'")

    def _open_document(self, docx_path):
        """Connect to LibreOffice and open document."""
        try:
            local_ctx = uno.getComponentContext()
            resolver = local_ctx.ServiceManager.createInstanceWithContext(
                "com.sun.star.bridge.UnoUrlResolver", local_ctx)

            try:
                ctx = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
            except:
                subprocess.Popen([
                    'libreoffice', '--headless', '--invisible', '--nocrashreport',
                    '--nodefault', '--nolockcheck', '--nologo', '--norestore',
                    '--accept=socket,host=localhost,port=2002;urp;'
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(3)
                ctx = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")

            desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
            file_url = uno.systemPathToFileUrl(os.path.abspath(docx_path))
            props = (PropertyValue("Hidden", 0, True, 0),)
            return desktop.loadComponentFromURL(file_url, "_blank", 0, props)
        except Exception as e:
            print(f"   ❌ LibreOffice connection failed: {e}")
            return None

    def _apply_edit(self, document, edit):
        """Apply a single edit operation."""
        edit_type = edit.get('type', '')
        try:
            if edit_type == 'swap_phrase':
                return self._do_swap(document, edit)
            elif edit_type == 'swap_word':
                return self._do_swap(document, edit)
            elif edit_type == 'add_qualifier':
                return self._do_qualifier(document, edit)
            elif edit_type == 'insert_after':
                return self._do_insert_after(document, edit)
            elif edit_type == 'delete_phrase':
                return self._do_delete(document, edit)
            elif edit_type == 'insert_block':
                return self._do_insert_block(document, edit)
            elif edit_type in ('append_sentence', 'insert_before_signature'):
                return self._do_append(document, edit)
            elif edit_type == 'insert_words':
                print(f"   ⚠️ Manual anchor needed: {edit.get('category')} — {edit.get('content', '')[:60]}")
                return False
            elif edit_type == 'delete_block':
                return self._do_delete_block(document, edit)
            else:
                print(f"   ⚠️ Unknown edit type: {edit_type}")
                return False
        except Exception as e:
            print(f"   ❌ Edit failed ({edit.get('category')}): {e}")
            return False

    def _search(self, document, text, regex=False, case_sensitive=False):
        """Search for text in document. Returns found range or None."""
        search = document.createSearchDescriptor()
        search.setPropertyValue("SearchRegularExpression", regex)
        search.setPropertyValue("SearchCaseSensitive", case_sensitive)

        # Try exact, then normalized whitespace
        for search_str in [text, re.sub(r'[\t]+', ' ', text).strip()]:
            search.setSearchString(search_str)
            found = document.findFirst(search)
            if found:
                return found

        # Try regex whitespace fallback
        if not regex:
            normalized = re.sub(r'[\t]+', ' ', text).strip()
            regex_pat = re.sub(r'\s+', '\\\\s+', re.escape(normalized))
            search.setPropertyValue("SearchRegularExpression", True)
            search.setSearchString(regex_pat)
            found = document.findFirst(search)
            search.setPropertyValue("SearchRegularExpression", False)
            if found:
                return found
        return None

    def _do_swap(self, document, edit):
        """Swap a phrase or word."""
        patterns = edit.get('find_patterns', [edit.get('find', '')])
        replace = edit.get('replace', '')
        for pattern in patterns:
            if not pattern:
                continue
            found = self._search(document, pattern)
            if found:
                found.setString(replace)
                print(f"   ✓ [{edit.get('category')}] Swapped: '{pattern[:40]}' → '{replace[:40]}'")
                return True
        print(f"   ❌ [{edit.get('category')}] Not found: '{patterns[0][:50] if patterns else '?'}'")
        return False

    def _do_qualifier(self, document, edit):
        """Add a qualifier word before a found phrase."""
        find = edit.get('find', '')
        qualifier = edit.get('qualifier', '')
        found = self._search(document, find)
        if found:
            current = found.getString()
            if qualifier.strip().lower() not in current.lower():
                found.setString(qualifier + current)
                print(f"   ✓ [{edit.get('category')}] Added '{qualifier.strip()}' before '{find[:40]}'")
                return True
            else:
                print(f"   ✓ [{edit.get('category')}] Already has '{qualifier.strip()}'")
                return True
        print(f"   ❌ [{edit.get('category')}] Not found: '{find[:50]}'")
        return False

    def _do_insert_after(self, document, edit):
        """Insert text after a found phrase."""
        candidates = edit.get('find_candidates', [edit.get('find', '')])
        if isinstance(candidates, str):
            candidates = [candidates]
        content = edit.get('content', '')

        for find in candidates:
            if not find:
                continue
            found = self._search(document, find)
            if found:
                current = found.getString()
                if content.strip() not in current:
                    found.setString(current + content)
                    print(f"   ✓ [{edit.get('category')}] Inserted after '{find[:40]}'")
                    return True
        print(f"   ❌ [{edit.get('category')}] Not found: '{candidates[0][:50] if candidates else '?'}'")
        return False

    def _do_delete(self, document, edit):
        """Delete a phrase from the document."""
        find = edit.get('find', '')
        found = self._search(document, find)
        if found:
            found.setString('')
            print(f"   ✓ [{edit.get('category')}] Deleted: '{find[:50]}'")
            return True
        print(f"   ❌ [{edit.get('category')}] Not found for deletion: '{find[:50]}'")
        return False

    def _do_delete_block(self, document, edit):
        """Delete a block/paragraph. Uses quoted text to find it."""
        quoted = edit.get('quoted', '')
        if not quoted or quoted == 'NOT FOUND':
            return False
        # Try first 80 chars of quoted text
        search_text = quoted[:80].strip()
        found = self._search(document, search_text)
        if found:
            # Extend to paragraph
            cursor = found.getText().createTextCursorByRange(found)
            cursor.gotoStartOfParagraph(False)
            cursor.gotoEndOfParagraph(True)
            cursor.setString('')
            print(f"   ✓ [{edit.get('category')}] Deleted block: '{search_text[:50]}...'")
            return True
        print(f"   ❌ [{edit.get('category')}] Block not found: '{search_text[:50]}'")
        return False

    def _do_insert_block(self, document, edit):
        """Insert a block of text after a specific anchor paragraph found via anchor_quote."""
        content = edit.get('content', '')
        anchor_quote = edit.get('anchor_quote', '')

        # Try to find the anchor paragraph using quoted text
        if anchor_quote and anchor_quote != 'NOT FOUND':
            # Try progressively shorter portions of the anchor
            for length in [60, 40, 25]:
                snippet = anchor_quote[:length].strip()
                if not snippet:
                    continue
                found = self._search(document, snippet)
                if found:
                    # Insert new paragraph after the found text's paragraph
                    cursor = found.getText().createTextCursorByRange(found)
                    cursor.gotoEndOfParagraph(False)
                    found.getText().insertControlCharacter(cursor, 0, False)  # PARAGRAPH_BREAK
                    cursor.setString(content)
                    print(f"   ✓ [{edit.get('category')}] Inserted block after '{snippet[:40]}...'")
                    return True

        # Fallback: append before signature
        return self._do_append(document, edit)

    def _do_append(self, document, edit):
        """Append text as a new numbered clause before the signature block."""
        content = edit.get('content', '')
        text_obj = document.getText()

        # Find signature area markers
        for sig_marker in ['Signed this', 'Sincerely', 'ACCEPTED AND AGREED', 'IN WITNESS',
                           'AGREED TO AND ACCEPTED', 'By:', 'Prospective']:
            found = self._search(document, sig_marker)
            if found:
                cursor = text_obj.createTextCursorByRange(found)
                cursor.gotoStartOfParagraph(False)
                text_obj.insertControlCharacter(cursor, 0, False)  # PARAGRAPH_BREAK
                text_obj.insertControlCharacter(cursor, 0, False)  # Extra blank line
                cursor.gotoPreviousParagraph(False)
                cursor.setString(content)
                print(f"   ✓ [{edit.get('category')}] Appended as new clause before '{sig_marker}'")
                return True

        # Last resort: append at end
        cursor = text_obj.createTextCursor()
        cursor.gotoEnd(False)
        text_obj.insertControlCharacter(cursor, 0, False)
        cursor.setString(content)
        print(f"   ✓ [{edit.get('category')}] Appended at end of document")
        return True

    def _save_outputs(self, document, base_name, mapping_path, pii_redactor):
        """Save all output variants."""
        save_props = (PropertyValue("FilterName", 0, "MS Word 2007 XML", 0),)
        outputs = {}

        # 1. Redacted + Redlined
        p1 = os.path.join(self.output_dir, f"{base_name}_Redacted_Redlined.docx")
        document.storeAsURL(uno.systemPathToFileUrl(os.path.abspath(p1)), save_props)
        outputs['redacted_redlined'] = p1
        print(f"   ✅ Redacted+Redlined: {os.path.basename(p1)}")

        # 2. Reconstructed + Redlined (restore PII)
        p2 = os.path.join(self.output_dir, f"{base_name}_Reconstructed_Redlined.docx")
        shutil.copy2(p1, p2)
        pii_redactor.restore_docx(p2, mapping_path)
        outputs['reconstructed_redlined'] = p2
        print(f"   ✅ Reconstructed+Redlined: {os.path.basename(p2)}")

        # Accept all changes for clean versions
        try:
            # Method 1: UNO dispatch
            dispatcher = ctx_sm = document.getCurrentController()
            frame = dispatcher.getFrame()
            from com.sun.star.beans import PropertyValue as PV
            import uno as _uno
            dispatch = _uno.getComponentContext().ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.DispatchHelper", _uno.getComponentContext())
            dispatch.executeDispatch(frame, ".uno:AcceptAllTrackedChanges", "", 0, ())
            document.setPropertyValue("RecordChanges", False)
            print("   ✓ Accepted all changes via dispatch")
        except Exception as e1:
            print(f"   ⚠️ Dispatch accept failed: {e1}")
            try:
                # Method 2: iterate redlines
                redlines = document.getRedlines()
                for i in range(redlines.getCount()):
                    redlines.getByIndex(0).accept()
            except Exception as e2:
                print(f"   ⚠️ Redlines accept also failed: {e2}")

        # 3. Redacted + Clean
        p3 = os.path.join(self.output_dir, f"{base_name}_Redacted_Clean.docx")
        document.storeAsURL(uno.systemPathToFileUrl(os.path.abspath(p3)), save_props)
        outputs['redacted_clean'] = p3
        print(f"   ✅ Redacted+Clean: {os.path.basename(p3)}")

        # 4. Reconstructed + Clean
        p4 = os.path.join(self.output_dir, f"{base_name}_Reconstructed_Clean.docx")
        shutil.copy2(p3, p4)
        pii_redactor.restore_docx(p4, mapping_path)
        outputs['reconstructed_clean'] = p4
        print(f"   ✅ Reconstructed+Clean: {os.path.basename(p4)}")

        return outputs
