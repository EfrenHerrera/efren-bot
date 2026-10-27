import copy

import pytest

from efren_bot.review.model import DIMENSIONS, sanitize, validate


def snapshot():
    return {
        "refs": {"head_sha": "a" * 40, "base_sha": "b" * 40, "start_sha": "b" * 40},
        "diffs": [{"path": "core/example.py", "old_path": "core/example.py", "added_lines": [2]}],
        "notes": [{"discussion_id": "old"}],
        "sources": [
            {
                "id": "s1",
                "kind": "diff",
                "path": "core/example.py",
                "sha": "a" * 40,
                "text": "@@ -1 +1,2 @@\n original\n+dangerous_call()",
            }
        ],
        "limitations": [],
    }


def report():
    citation = {"source_id": "s1", "quote": "dangerous_call()"}
    return {
        "summary": "Static review only",
        "checks": [
            {
                "dimension": d,
                "status": "reviewed",
                "conclusion": "Inspected this path",
                "evidence": [citation],
            }
            for d in sorted(DIMENSIONS)
        ],
        "findings": [
            {
                "dimension": "business",
                "path": "core/example.py",
                "line": 2,
                "severity": "medium",
                "confidence": 90,
                "problem": "Unconditional call",
                "scenario": "Missing input",
                "impact": "Failure",
                "alternative": "Guard before call",
                "comment": "Can we guard this call?",
                "evidence": [citation],
            }
        ],
        "previous": [],
        "pending": [],
    }


def test_review_evidence_and_changed_line_are_required():
    payload = {"snapshot": snapshot()}
    assert validate("analyze", payload, report())["findings"][0]["line"] == 2
    for field, value in [("line", 1), ("path", "core/untouched.py")]:
        result = report()
        result["findings"][0][field] = value
        with pytest.raises(ValueError):
            validate("analyze", payload, result)
    result = report()
    result["findings"][0]["evidence"][0]["quote"] = "fabricated evidence"
    with pytest.raises(ValueError):
        validate("analyze", payload, result)


def test_review_cannot_claim_code_correction_from_comment_alone():
    data = snapshot()
    data["sources"].append({"id": "s2", "kind": "discussion", "text": "The author said fixed"})
    result = report()
    result["previous"] = [
        {
            "discussion_id": "old",
            "assessment": "Fixed",
            "status": "addressed_in_code",
            "evidence": [{"source_id": "s2", "quote": "The author said fixed"}],
        }
    ]
    with pytest.raises(ValueError):
        validate("analyze", {"snapshot": data}, result)
    result["previous"][0]["status"] = "needs_validation"
    assert (
        validate("analyze", {"snapshot": data}, result)["previous"][0]["status"]
        == "needs_validation"
    )


def test_previous_correction_must_reference_current_code_not_only_base():
    data = snapshot()
    data["sources"].append(
        {
            "id": "s2",
            "kind": "file",
            "path": "core/example.py",
            "sha": data["refs"]["base_sha"],
            "text": "Old version returned the default",
        }
    )
    result = report()
    result["previous"] = [
        {
            "discussion_id": "old",
            "assessment": "Fixed",
            "status": "addressed_in_code",
            "evidence": [{"source_id": "s2", "quote": "Old version returned the default"}],
        }
    ]
    with pytest.raises(ValueError, match="review_correction_not_verified"):
        validate("analyze", {"snapshot": data}, result)


def test_plan_is_limited_to_immutable_mrs_in_the_same_request():
    payload = {"related": [{"item_id": "own", "refs": snapshot()["refs"]}]}
    raw = {
        "objective": "Trace calls",
        "reads": [{"item_id": "other", "path": "core/example.py", "reason": "dependency"}],
        "hypotheses": [],
    }
    with pytest.raises(ValueError):
        validate("plan", payload, raw)
    raw["reads"][0]["item_id"] = "own"
    assert validate("plan", payload, raw)["reads"][0]["side"] == "head"
    raw["reads"][0]["path"] = ".env"
    with pytest.raises(ValueError):
        validate("plan", payload, raw)


def test_checks_are_not_a_fake_complete_checklist():
    result = report()
    result["checks"][-1] = copy.deepcopy(result["checks"][0])
    with pytest.raises(ValueError):
        validate("analyze", {"snapshot": snapshot()}, result)
    result = report()
    result["checks"][0]["evidence"] = []
    with pytest.raises(ValueError):
        validate("analyze", {"snapshot": snapshot()}, result)


def test_sanitizing_prose_does_not_rewrite_opaque_reference_values():
    raw = {
        "refs": {"head_sha": "1234567890" + "a" * 30},
        "iid": "123456789012",
        "text": "Reach person@example.test or token=secret_value",
        "context_urls": ["https://gitlab.com/approved/path/-/merge_requests/123456789012"],
    }
    clean = sanitize(raw)
    assert clean["refs"] == raw["refs"] and clean["iid"] == raw["iid"]
    assert clean["context_urls"] == raw["context_urls"]
    assert "person@example" not in clean["text"] and "secret_value" not in clean["text"]


def test_prompt_compacts_metadata_without_changing_sources_or_snapshot():
    import json

    from efren_bot.review.model import input_text

    data = snapshot()
    data["diffs"][0]["added_lines"] = [2, 3, 4, 9, 10]
    original = copy.deepcopy(data)
    value = json.loads(input_text({"snapshot": data}))
    assert value["snapshot"]["diffs"][0]["added_ranges"] == [[2, 4], [9, 10]]
    assert value["snapshot"]["sources"] == data["sources"]
    assert data == original


def test_dependencies_fit_total_serialized_context_budget_not_only_raw_text():
    from efren_bot.review.model import MAX_CONTEXT, input_text
    from efren_bot.review.runner import read_context

    data = snapshot()
    data["sources"][0]["text"] = "x" * 160000
    payload = {
        "item_id": "own",
        "snapshot": data,
        "request_context": {"text": "x" * 10000},
        "related": [{"item_id": "own", "project": "allowed", "iid": "1", "refs": data["refs"]}],
        "plan": {
            "reads": [
                {
                    "item_id": "own",
                    "path": "core/example.py",
                    "side": "head",
                    "start": 1,
                    "end": 500,
                    "reason": "Trace behavior",
                }
            ]
        },
    }
    calls = []

    class Client:
        def __init__(self, project, iid):
            pass

        def file(self, *args, **kwargs):
            calls.append(args)
            return "line_of_code\n" * 5000

    result = read_context({"payload": payload}, Client)
    assert len(input_text({**payload, "snapshot": result})) <= MAX_CONTEXT
    assert any("Presupuesto total" in text for text in result["limitations"])
    assert len(calls) == 1 and data["sources"][0]["text"] == "x" * 160000
