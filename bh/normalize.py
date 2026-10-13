"""Normalization and similarity helpers used by the matcher."""
import re
from difflib import SequenceMatcher

_STREET_ABBR = {
    "street": "st", "avenue": "ave", "av": "ave", "road": "rd", "drive": "dr", "lane": "ln",
    "boulevard": "blvd", "court": "ct", "place": "pl", "parkway": "pkwy", "highway": "hwy",
    "circle": "cir", "terrace": "ter", "trail": "trl", "square": "sq", "pike": "pk",
    "north": "n", "south": "s", "east": "e", "west": "w",
    "northeast": "ne", "northwest": "nw", "southeast": "se", "southwest": "sw",
    "first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th", "fifth": "5th",
}

_NAME_STOP = {"bellhaven", "of", "the", "at", "and", "senior", "living", "community",
              "communities", "llc", "inc", "a"}


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def norm_street(s):
    s = clean(s).lower()
    s = re.sub(r"\b(suite|ste|unit|apt|bldg|building|#)\s*[\w-]+", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    toks = [_STREET_ABBR.get(t, t) for t in s.split()]
    return " ".join(toks)


def street_number(s):
    m = re.match(r"\s*(\d+[a-z]?)\b", norm_street(s))
    return m.group(1) if m else ""


def norm_name(s):
    s = clean(s).lower().replace("&", " and ").replace("centre", "center")
    s = s.replace("(parent account)", " ")
    s = re.sub(r"\brehab\b", "rehabilitation", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(s.split())


def name_core(s):
    return [t for t in norm_name(s).split() if t not in _NAME_STOP]


def norm_city(s):
    s = clean(s).lower().replace(".", "")
    s = re.sub(r"\bsaint\b", "st", s)
    return " ".join(s.split())


def norm_state(s):
    return clean(s).upper()[:2]


def zip5(s):
    d = re.sub(r"\D", "", str(s or ""))
    return d[:5] if len(d) >= 5 else ""


def phone10(s):
    d = re.sub(r"\D", "", str(s or ""))
    return d[-10:] if len(d) >= 10 else ""


def ratio(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def name_similarity(a, b):
    """Best of full-string ratio and core-token overlap (ignores 'Bellhaven', 'of', ...)."""
    full = ratio(norm_name(a), norm_name(b))
    ca, cb = set(name_core(a)), set(name_core(b))
    jac = len(ca & cb) / len(ca | cb) if ca and cb else 0.0
    return max(full, jac)


def street_similarity(a, b):
    na, nb = norm_street(a), norm_street(b)
    if not na or not nb:
        return None  # unknown, not a mismatch
    if na == nb:
        return 1.0
    if street_number(a) and street_number(a) != street_number(b):
        return min(0.4, ratio(na, nb))  # different house number = different building
    return ratio(na, nb)


def to_number(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(re.sub(r"[^\d.\-]", "", str(v)) or 0)
    except ValueError:
        return 0.0


CARE_SYNONYMS = {  # website wording -> CRM-style wording
    "short term rehabilitation and nursing": "skilled nursing",
    "short term rehabilitation": "skilled nursing",
    "rehabilitation and nursing": "skilled nursing",
    "nursing": "skilled nursing",
    "memory support": "memory care",
}


def care_canon(s):
    n = norm_name(s)
    return CARE_SYNONYMS.get(n, n)


def care_set(v):
    if v is None or v == "":
        return set()
    if isinstance(v, str):
        parts = re.split(r"[;,|/]\s*", v)
    else:
        parts = list(v)
    return {care_canon(p) for p in parts if clean(p)}
