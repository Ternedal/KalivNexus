"""Deterministic, read-only capability matching. Never executes discovered URLs."""
import re

STOP = {'the','and','for','with','from','that','this','have','into','find','use','api','apis','get','data','en','et','der','med','til','kan','jeg','vil','skal','finde'}

def tokens(value: str) -> set[str]:
    return {word for word in re.findall(r'[^\W_]{3,}', value.casefold()) if word not in STOP}

def rank(query: str, records: list[dict], limit: int = 10) -> list[dict]:
    terms = tokens(query)
    if not terms:
        return []
    results = []
    for record in records:
        name = tokens(record['name'])
        category = tokens(record['category'])
        description = tokens(record['description'])
        score = 5 * len(terms & name) + 3 * len(terms & category) + len(terms & description)
        if score:
            results.append({**record, 'score': score, 'matched_terms': sorted(terms & (name | category | description))})
    return sorted(results, key=lambda r: (-r['score'], r['name'].casefold(), r['id']))[:limit]
