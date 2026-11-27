"""Unit tests for recursive secret redaction in chat payloads."""

from weather.chat.sanitize import REDACTED, sanitize


def test_sensitive_keys_are_redacted_at_any_depth():
    payload = {
        "city": "Santiago",
        "nested": {"api_key": "abc", "list": [{"password": "hunter2"}, {"token": "x"}]},
        "Authorization": "Bearer abc",
        "safe": 3,
    }

    cleaned = sanitize(payload)

    assert cleaned["city"] == "Santiago"
    assert cleaned["nested"]["api_key"] == REDACTED
    assert cleaned["nested"]["list"][0]["password"] == REDACTED
    assert cleaned["nested"]["list"][1]["token"] == REDACTED
    assert cleaned["Authorization"] == REDACTED
    assert cleaned["safe"] == 3


def test_secret_looking_values_inside_strings_are_redacted():
    cleaned = sanitize({"note": "use sk-abcdefghijklmnop1234567890 here"})
    assert "sk-abcdefghijklmnop" not in cleaned["note"]
    assert REDACTED in cleaned["note"]


def test_non_json_values_become_strings():
    from decimal import Decimal

    cleaned = sanitize({"temperature": Decimal("18.40")})
    assert cleaned["temperature"] == "18.40"
