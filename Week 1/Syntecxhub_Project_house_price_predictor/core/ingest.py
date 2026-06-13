"""Data loading and column-role auto-detection."""

import io
import json
import re
from typing import Optional

import numpy as np
import pandas as pd

# ── Column role hints ─────────────────────────────────────────────────────────
_ID_PATTERNS   = re.compile(r'\bid\b|_id$|^id_|index|uuid|key', re.I)
_LAT_PATTERNS  = re.compile(r'^lat(itude)?$', re.I)
_LON_PATTERNS  = re.compile(r'^lon(gitude)?$|^lng$', re.I)
_PRICE_PATTERNS= re.compile(r'price|value|cost|sale|amount|sold', re.I)


def load_file(file) -> pd.DataFrame:
    name = file.name.lower()
    raw  = file.read()
    if name.endswith('.csv'):
        return pd.read_csv(io.BytesIO(raw))
    if name.endswith(('.xls', '.xlsx')):
        return pd.read_excel(io.BytesIO(raw))
    if name.endswith('.json'):
        data = json.loads(raw)
        return pd.json_normalize(data) if isinstance(data, list) else pd.DataFrame([data])
    raise ValueError(f"Unsupported file type: {file.name}")


def auto_detect_roles(df: pd.DataFrame) -> dict[str, str]:
    """
    Returns a dict mapping column → role.
    Roles: 'target', 'numeric', 'categorical', 'id', 'lat', 'lon', 'exclude'
    """
    roles: dict[str, str] = {}
    target_assigned = False

    for col in df.columns:
        if _LAT_PATTERNS.match(col):
            roles[col] = 'lat'; continue
        if _LON_PATTERNS.match(col):
            roles[col] = 'lon'; continue
        if _ID_PATTERNS.search(col):
            roles[col] = 'id'; continue

        dtype = df[col].dtype
        n_unique = df[col].nunique()

        if _PRICE_PATTERNS.search(col) and pd.api.types.is_numeric_dtype(dtype):
            if not target_assigned:
                roles[col] = 'target'
                target_assigned = True
                continue

        if pd.api.types.is_numeric_dtype(dtype):
            roles[col] = 'numeric'
        elif n_unique <= 30 or pd.api.types.is_bool_dtype(dtype):
            roles[col] = 'categorical'
        else:
            roles[col] = 'exclude'   # high-cardinality text

    # If no target found yet, suggest the last numeric column
    if not target_assigned:
        for col in reversed(df.columns):
            if roles.get(col) == 'numeric':
                roles[col] = 'target'
                break

    return roles


def apply_roles(df: pd.DataFrame, roles: dict[str, str]) -> dict:
    """Split columns into typed buckets based on role assignments."""
    return {
        'target':      [c for c, r in roles.items() if r == 'target'],
        'numeric':     [c for c, r in roles.items() if r == 'numeric'],
        'categorical': [c for c, r in roles.items() if r == 'categorical'],
        'lat':         [c for c, r in roles.items() if r == 'lat'],
        'lon':         [c for c, r in roles.items() if r == 'lon'],
        'excluded':    [c for c, r in roles.items() if r in ('id', 'exclude')],
    }
