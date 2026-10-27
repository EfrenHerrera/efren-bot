import json

import pytest
from bridge_helpers import URL, result_data, synthetic_profile

from efren_bot.bridge.stream import StreamFailure, StreamProjection


def events():
    profile = synthetic_profile()
    return [
        {"type": "system", "subtype": "init"},
        {
            "type": "assistant",
            "message": {
                "id": "a1",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": profile.connector.tool_name,
                        "input": profile.arguments(URL),
                    }
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "is_error": False,
                    }
                ]
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps(result_data()),
        },
    ]


def projection(data):
    parser = StreamProjection(synthetic_profile(), URL)
    raw = ("\n".join(json.dumps(e) for e in data) + "\n").encode()
    # Exercise arbitrary read boundaries, not just one JSON per read.
    for start in range(0, len(raw), 17):
        parser.feed(raw[start : start + 17])
    return parser


def test_success_requires_matching_hook_budget_and_no_violation():
    parser = projection(events())
    good = {"used": True, "violation": False, "tool_use_id": "t1"}
    assert parser.finish(good).evidence_refs == [URL]
    for changes in ({"used": False}, {"violation": True}, {"tool_use_id": "different"}):
        with pytest.raises(StreamFailure):
            parser.finish({**good, **changes})


@pytest.mark.parametrize(
    "mode", ["duplicate_read", "wrong_result_id", "failed_hook", "stream_error"]
)
def test_no_failed_or_uncorrelated_stream(mode):
    data = events()
    if mode == "duplicate_read":
        data.insert(2, data[1])
    elif mode == "wrong_result_id":
        data[2]["message"]["content"][0]["tool_use_id"] = "other"
    elif mode == "failed_hook":
        data.insert(2, {"type": "system", "subtype": "hook_response", "outcome": "error"})
    else:
        data.insert(2, {"type": "system", "subtype": "error", "error": "not-persisted"})
    with pytest.raises(StreamFailure):
        projection(data)


def test_incomplete_stream_and_no_final_result_fail():
    parser = projection(events()[:-1])
    with pytest.raises(StreamFailure):
        parser.finish({"used": True, "violation": False, "tool_use_id": "t1"})
    parser.feed(b'{"type":')
    with pytest.raises(StreamFailure):
        parser.finish({"used": True, "violation": False, "tool_use_id": "t1"})
