from __future__ import annotations
import json
import re
from typing import Optional, Dict, Any

def one_sentence(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    x = re.sub(r"\s+", " ", text).strip()
    if not x:
        return None
    parts = re.split(r"(?<=[.!?])\s+", x)
    x = parts[0].strip()
    if not x.endswith((".", "!", "?")):
        x += "."
    return x

def one_question(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    x = re.sub(r"\s+", " ", text).strip()
    if not x:
        return None
    m = re.search(r"(.+?\?)", x)
    if m:
        return m.group(1).strip()
    if not x.endswith("?"):
        x += "?"
    return x

def safe_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    s = text.strip()
    m = re.search(r"\{.*\}", s, flags=re.S)
    if m:
        s = m.group(0)
    try:
        return json.loads(s)
    except Exception:
        return None
