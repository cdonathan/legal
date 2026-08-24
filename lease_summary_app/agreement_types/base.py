"""
AgreementType Base Class
=========================
Defines the interface and data model for an agreement type.
All agreement-specific knowledge is encapsulated here.
"""

import os
import json
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field


@dataclass
class AgreementType:
    """Represents a single agreement type configuration."""

    # Identity
    type_id: str
    name: str
    description: str
    base_path: str  # Filesystem path to this type's directory

    # Fields to extract: {field_name: description}
    fields: Dict[str, str] = field(default_factory=dict)

    # UI preview sections: [{title, fields: [(key, label), ...]}]
    sections: List[dict] = field(default_factory=list)

    # Verification config
    short_fields: Set[str] = field(default_factory=set)
    none_fields: Set[str] = field(default_factory=set)
    expected_fields: Set[str] = field(default_factory=set)

    # Document type detection signals
    doc_type_signals: Dict[str, List[str]] = field(default_factory=dict)

    # Sub-type detection (e.g., amendment vs full lease)
    sub_types: Dict[str, dict] = field(default_factory=dict)

    # Template path
    template_path: str = ""

    # AI prompt configuration
    system_prompt: str = ""
    extraction_rules: str = ""
    retry_hints: Dict[str, str] = field(default_factory=dict)

    # Field anchors for source verification (loaded from field_anchors.json)
    field_anchors: Dict[str, List[str]] = field(default_factory=dict)

    @classmethod
    def from_config(cls, type_id: str, base_path: str, config: dict) -> "AgreementType":
        """Build an AgreementType from a config.json dict."""
        # Load fields - support grouped field dicts
        fields = {}
        if "fields" in config:
            for group in config["fields"]:
                if isinstance(group, dict) and "fields" in group:
                    fields.update(group["fields"])
                elif isinstance(group, dict):
                    fields.update(group)
            # If fields is a flat dict directly
            if isinstance(config["fields"], dict):
                fields = config["fields"]

        # Load sections for UI preview
        sections = config.get("sections", [])

        # Load verification sets
        short_fields = set(config.get("short_fields", []))
        none_fields = set(config.get("none_fields", []))
        expected_fields = set(config.get("expected_fields", []))

        # Load field anchors from separate file if exists
        field_anchors = {}
        anchors_path = os.path.join(base_path, "field_anchors.json")
        if os.path.exists(anchors_path):
            try:
                with open(anchors_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                field_anchors = {k: v for k, v in data.items() if not k.startswith("_")}
            except (json.JSONDecodeError, IOError):
                pass

        return cls(
            type_id=type_id,
            name=config.get("name", type_id),
            description=config.get("description", ""),
            base_path=base_path,
            fields=fields,
            sections=sections,
            short_fields=short_fields,
            none_fields=none_fields,
            expected_fields=expected_fields,
            doc_type_signals=config.get("doc_type_signals", {}),
            sub_types=config.get("sub_types", {}),
            template_path=config.get("template_path", ""),
            system_prompt=config.get("system_prompt", ""),
            extraction_rules=config.get("extraction_rules", ""),
            retry_hints=config.get("retry_hints", {}),
            field_anchors=field_anchors,
        )

    def detect_sub_type(self, text: str, filename: str) -> str:
        """
        Detect document sub-type (e.g., 'amendment' vs 'lease').
        Returns the sub-type key or the base type_id.
        """
        if not self.sub_types:
            return self.type_id

        fname_lower = filename.lower()
        header = text[:2000].lower()

        for sub_id, sub_config in self.sub_types.items():
            # Check filename signals
            for signal in sub_config.get("filename_signals", []):
                if signal in fname_lower:
                    return sub_id
            # Check header signals
            for signal in sub_config.get("header_signals", []):
                if signal in header:
                    return sub_id

        return self.type_id

    def get_sub_type_instruction(self, sub_type: str) -> str:
        """Get AI instruction text for a specific sub-type."""
        if sub_type in self.sub_types:
            return self.sub_types[sub_type].get("ai_instruction", "")
        return ""

    def get_full_lease_only_fields(self) -> Set[str]:
        """Fields only applicable to full agreements, not amendments."""
        result = set()
        for sub_id, sub_config in self.sub_types.items():
            if sub_config.get("skip_fields"):
                result.update(sub_config["skip_fields"])
        return result
