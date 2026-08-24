"""
Agreement Type Registry
========================
Discovers and loads agreement type configurations from subdirectories.
Each agreement type is a folder containing a config.json and optional overrides.
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional

from .base import AgreementType

# Registry of loaded agreement types
_registry: Dict[str, AgreementType] = {}

TYPES_DIR = os.path.dirname(os.path.abspath(__file__))


def discover_types() -> Dict[str, AgreementType]:
    """Scan agreement_types/ subdirectories and load each valid type."""
    global _registry
    _registry = {}

    for entry in os.scandir(TYPES_DIR):
        if not entry.is_dir():
            continue
        if entry.name.startswith(("_", ".")):
            continue

        config_path = os.path.join(entry.path, "config.json")
        if not os.path.exists(config_path):
            continue

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            agreement = AgreementType.from_config(entry.name, entry.path, config)
            _registry[entry.name] = agreement
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Warning: Failed to load agreement type '{entry.name}': {e}")
            continue

    return _registry


def get_type(type_id: str) -> Optional[AgreementType]:
    """Get a loaded agreement type by ID."""
    if not _registry:
        discover_types()
    return _registry.get(type_id)


def list_types() -> Dict[str, dict]:
    """List all available agreement types with their metadata."""
    if not _registry:
        discover_types()
    return {
        type_id: {
            "id": type_id,
            "name": agr.name,
            "description": agr.description,
            "doc_type_signals": agr.doc_type_signals,
        }
        for type_id, agr in _registry.items()
    }


def detect_agreement_type(text: str, filename: str) -> Optional[str]:
    """
    Auto-detect which agreement type a document belongs to.
    Checks filename and header text against each type's signals.
    Returns the type_id or None if no match.
    """
    if not _registry:
        discover_types()

    fname_lower = filename.lower()
    header = text[:3000].lower()

    # Score each type
    best_type = None
    best_score = 0

    for type_id, agr in _registry.items():
        score = 0
        signals = agr.doc_type_signals

        # Check filename signals
        for signal in signals.get("filename", []):
            if signal.lower() in fname_lower:
                score += 10

        # Check header text signals
        for signal in signals.get("header", []):
            if signal.lower() in header:
                score += 5

        if score > best_score:
            best_score = score
            best_type = type_id

    return best_type if best_score > 0 else None
