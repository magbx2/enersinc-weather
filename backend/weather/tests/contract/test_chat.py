"""Contract tests for the chat endpoint, persistence and safe failures."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from tests.fixtures import llm_text, llm_tool_call
from weather.models import ChatMessage, ChatSession, ToolRun

pytestmark = pytest.mark.django_db

CHAT_URL = "/chat/messages/"
SAME_ORIGIN = {"HTTP_ORIGIN": "http://testserver"}


def _post(api_client, session_id, message):
    return api_client.post(
        CHAT_URL,
        {"session_id": str(session_id), "message": message},
        format="json",
        **SAME_ORIGIN,
    )


def test_a_turn_runs_a_tool_and_persists_sanitized_evidence(api_client, make_observation, fake_llm):
    now = timezone.now()
    make_observation("Santiago", timestamp=now - timedelta(days=1), temperature=10.0)
    make_observation("Santiago", timestamp=now - timedelta(days=2), temperature=20.0)
    session_id = uuid.uuid4()
    fake = fake_llm(
        [
            llm_tool_call(
                "calcular_estadistica",
                {"city": "Santiago", "metric": "temperature", "statistic": "average"},
            ),
            llm_text(
                "El promedio de temperatura en Santiago fue 15 °C, calculado sobre 2 observaciones."
            ),
        ]
    )

    response = _post(api_client, session_id, "¿Cuál fue la temperatura promedio en Santiago?")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(session_id)
    message = body["message"]
    assert message["role"] == "assistant"
    assert message["status"] == "completed"
    assert "15" in message["content"]
    assert len(message["tool_runs"]) == 1
    run = message["tool_runs"][0]
    assert run["name"] == "calcular_estadistica"
    assert run["status"] == "ok"
    assert run["output"]["value"] == 15.0
    assert run["output"]["evidence"]["sample_count"] == 2

    # The wrapper received the configured model and key and the typed tool schemas.
    assert fake.calls[0]["model"] == "gpt-4o-mini"
    assert fake.calls[0]["api_key"] == "test-llm-key"
    assert {tool["function"]["name"] for tool in fake.calls[0]["tools"]} == {
        "consultar_clima",
        "calcular_estadistica",
    }
    assert ChatSession.objects.count() == 1
    assert ChatMessage.objects.count() == 2
    assert ToolRun.objects.count() == 1


def test_history_survives_reload_and_keeps_order(api_client, make_observation, fake_llm):
    make_observation("Santiago", temperature=18.0)
    session_id = uuid.uuid4()
    fake_llm([llm_text("Primera respuesta.")])
    _post(api_client, session_id, "Primera pregunta")
    fake_llm([llm_text("Segunda respuesta.")])
    _post(api_client, session_id, "Segunda pregunta")

    response = api_client.get(f"{CHAT_URL}?session_id={session_id}")

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [message["role"] for message in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[0]["content"] == "Primera pregunta"
    assert messages[-1]["content"] == "Segunda respuesta."


def test_a_fresh_session_returns_empty_history(api_client):
    response = api_client.get(f"{CHAT_URL}?session_id={uuid.uuid4()}")
    assert response.status_code == 200
    assert response.json()["messages"] == []


def test_missing_city_becomes_a_clarification_tool_error(api_client, fake_llm):
    fake_llm(
        [
            llm_tool_call("consultar_clima", {}),
            llm_text("¿De qué ciudad quieres consultar el clima?"),
        ]
    )

    response = _post(api_client, uuid.uuid4(), "¿Cuál fue la temperatura?")

    assert response.status_code == 200
    run = response.json()["message"]["tool_runs"][0]
    assert run["status"] == "error"
    assert run["error_code"] == "missing_parameter"
    assert response.json()["message"]["content"].startswith("¿De qué ciudad")


def test_sensitive_tool_arguments_are_redacted_before_storage(api_client, fake_llm):
    fake_llm(
        [
            llm_tool_call(
                "consultar_clima", {"city": "Santiago", "api_key": "sk-supersecretvalue123456"}
            ),
            llm_text("No necesito esa clave para responder."),
        ]
    )
    session_id = uuid.uuid4()

    response = _post(api_client, session_id, "Consulta Santiago")

    assert response.status_code == 200
    run = response.json()["message"]["tool_runs"][0]
    assert run["arguments"]["api_key"] == "[redacted]"
    stored = ToolRun.objects.get(message__session_id=session_id)
    assert "supersecret" not in str(stored.arguments)


def test_missing_credentials_produce_a_safe_failed_status(api_client, settings, monkeypatch):
    settings.LLM_API_KEY = ""
    monkeypatch.setattr("weather.chat.agent.llm_configured", lambda: False)

    response = _post(api_client, uuid.uuid4(), "¿Cuál fue la temperatura promedio?")

    assert response.status_code == 200
    message = response.json()["message"]
    assert message["status"] == "failed"
    assert message["error_code"] == "llm_not_configured"
    assert message["content"] == ""


def test_provider_failure_is_classified_without_leaking_details(api_client, fake_llm):
    fake_llm([RuntimeError("provider said: key sk-leakedsecret123456")])

    response = _post(api_client, uuid.uuid4(), "¿Cuál fue la temperatura promedio?")

    assert response.status_code == 200
    body = response.json()["message"]
    assert body["status"] == "failed"
    assert body["error_code"] == "llm_unavailable"
    assert "sk-leaked" not in str(response.json())


def test_model_change_is_configuration_only(api_client, settings, fake_llm):
    settings.LLM_MODEL = "anthropic/claude-3-5-sonnet"
    fake = fake_llm([llm_text("Respuesta con otro proveedor.")])

    response = _post(api_client, uuid.uuid4(), "Hola")

    assert response.status_code == 200
    assert fake.calls[0]["model"] == "anthropic/claude-3-5-sonnet"


def test_empty_model_response_is_a_visible_failure(api_client, fake_llm):
    fake_llm([llm_text("   ")])

    response = _post(api_client, uuid.uuid4(), "Hola")

    assert response.json()["message"]["error_code"] == "llm_empty_response"


def test_request_validation(api_client):
    missing = api_client.get(CHAT_URL)
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "invalid_chat"

    bad_uuid = api_client.get(f"{CHAT_URL}?session_id=not-a-uuid")
    assert bad_uuid.status_code == 400

    unknown_field = api_client.post(
        CHAT_URL,
        {"session_id": str(uuid.uuid4()), "message": "Hola", "extra": True},
        format="json",
        **SAME_ORIGIN,
    )
    assert unknown_field.status_code == 400
    assert unknown_field.json()["error"]["code"] == "invalid_chat"

    blank = api_client.post(
        CHAT_URL,
        {"session_id": str(uuid.uuid4()), "message": "   "},
        format="json",
        **SAME_ORIGIN,
    )
    assert blank.status_code == 400

    wrong_type = api_client.post(
        CHAT_URL,
        data='{"message":"Hola"}',
        content_type="text/plain",
        **SAME_ORIGIN,
    )
    assert wrong_type.status_code == 400

    cross_origin = api_client.post(
        CHAT_URL,
        {"session_id": str(uuid.uuid4()), "message": "Hola"},
        format="json",
        HTTP_ORIGIN="http://evil.test",
    )
    assert cross_origin.status_code == 403
    assert cross_origin.json()["error"]["code"] == "cross_origin_rejected"


def test_invalid_session_id_in_post_is_rejected(api_client):
    response = api_client.post(
        CHAT_URL,
        {"session_id": "not-a-uuid", "message": "Hola"},
        format="json",
        **SAME_ORIGIN,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_chat"
