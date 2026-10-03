"""
PB HERO Database Serialization & Normalization Helpers.

Provides safe central JSON encoding and decoding for SQLite fields,
preventing sqlite3 list/dict parameter binding errors.
"""

import json
from typing import Any, List, Optional


def normalize_domain(domain: str) -> str:
    """
    Normalize domain string:
    - lowercase
    - strip protocol (http://, https://)
    - remove leading www.
    - trim whitespace
    - remove trailing slash, path, query parameters, port
    """
    if not domain:
        return ""
    d = domain.strip().lower()
    if d.startswith("http://"):
        d = d[7:]
    elif d.startswith("https://"):
        d = d[8:]
    if d.startswith("www."):
        d = d[4:]
    # Strip path, query params, port
    d = d.split("/")[0].split("?")[0].split(":")[0].strip()
    return d


def normalize_domain_list(domains: Any) -> List[str]:
    """Normalize a list or comma-separated string of domains."""
    if not domains:
        return []
    if isinstance(domains, str):
        # Could be JSON string or comma-separated
        try:
            parsed = json.loads(domains)
            if isinstance(parsed, list):
                return [normalize_domain(d) for d in parsed if normalize_domain(d)]
        except Exception:
            pass
        return [normalize_domain(d) for d in domains.split(",") if normalize_domain(d)]
    elif isinstance(domains, (list, tuple, set)):
        result = []
        for d in domains:
            if not d:
                continue
            norm = normalize_domain(str(d))
            if norm and norm not in result:
                result.append(norm)
        return result
    return []


def serialize_json_field(val: Any) -> str:
    """
    Safely serialize a Python list, dict, set, or string to a JSON string.
    Ensures SQLite cursor.execute() NEVER receives a raw Python list.
    Empty values serialize to '[]'.
    """
    if val is None:
        return json.dumps([])
    if isinstance(val, (list, tuple, set)):
        return json.dumps(list(val))
    if isinstance(val, dict):
        return json.dumps(val)
    if isinstance(val, str):
        val_clean = val.strip()
        if not val_clean:
            return json.dumps([])
        try:
            # Check if already valid JSON
            parsed = json.loads(val_clean)
            if isinstance(parsed, (list, dict)):
                return json.dumps(parsed)
        except Exception:
            # Maybe comma-separated list of items
            items = [item.strip() for item in val_clean.split(",") if item.strip()]
            return json.dumps(items)
    return json.dumps(val)


def deserialize_json_field(val: Any, default: Any = None) -> Any:
    """
    Safely deserialize a JSON string from SQLite into Python data structure.
    If already a list/dict, returns it directly.
    Defaults to empty list [] if default is not provided.
    """
    if default is None:
        default = []
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        val_clean = val.strip()
        if not val_clean:
            return default
        try:
            return json.loads(val_clean)
        except Exception:
            # Fallback for comma-separated legacy data if default is list
            if isinstance(default, list) and "," in val_clean:
                return [x.strip() for x in val_clean.split(",") if x.strip()]
            return default
    return default
