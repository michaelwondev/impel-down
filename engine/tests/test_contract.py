import json
import os
from datetime import datetime

from impel.rules import Rules

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "fixtures")


def _load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


def test_contract_cases():
    rules = Rules.from_json(_load("rules.json"))
    by_id = {g.id: g for g in rules.groups}
    cases = json.loads(_load("expectations.json"))["cases"]
    assert cases, "expectations.json has no cases"
    for c in cases:
        g = by_id[c["group"]]
        at = datetime.fromisoformat(c["at"])
        closed = not g.is_open(at)
        assert closed == c["closed"], c
        expected_next = datetime.fromisoformat(c["next_open"]) if c["next_open"] else None
        actual_next = g.next_open(at) if closed else None
        assert actual_next == expected_next, c


def test_contract_decide():
    rules = Rules.from_json(_load("rules.json"))
    cases = json.loads(_load("expectations.json"))["decide"]
    assert cases, "expectations.json has no decide cases"
    for c in cases:
        g = rules.decide(c["host"], c["path"], datetime.fromisoformat(c["at"]))
        assert (g.id if g else None) == c["blocked_by"], c
