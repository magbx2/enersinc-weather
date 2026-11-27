"""Bounded LiteLLM tool-calling loop with server-side persistence."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction

from weather.chat.prompts import SYSTEM_PROMPT
from weather.chat.sanitize import sanitize
from weather.chat.tools import TOOL_DEFINITIONS, execute_tool_call
from weather.models import ChatMessage, ChatSession, ToolRun

logger = logging.getLogger("weather.chat")

MAX_CONTEXT_MESSAGES = 20
MAX_CONTENT_LENGTH = 8000
PROVIDER_ENV_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AZURE_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    "COHERE_API_KEY",
    "OPENROUTER_API_KEY",
)


class LlmError(Exception):
    """A safe, classified LLM failure; never carries provider payloads."""

    code = "llm_unavailable"


class LlmNotConfigured(LlmError):
    code = "llm_not_configured"


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: Any


def llm_configured() -> bool:
    """A model plus a usable credential source, without exposing the key."""
    if not getattr(settings, "LLM_MODEL", ""):
        return False
    if getattr(settings, "LLM_API_KEY", ""):
        return True
    return any(os.environ.get(name) for name in PROVIDER_ENV_KEYS)


def llm_status() -> dict[str, Any]:
    return {
        "configured": llm_configured(),
        "model": getattr(settings, "LLM_MODEL", "") or None,
    }


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _message_from_response(response: Any) -> tuple[str, list[ToolCall]]:
    choices = _get(response, "choices") or []
    if not choices:
        raise LlmError("The model returned no choices.")
    message = _get(choices[0], "message")
    content = _get(message, "content") or ""
    calls: list[ToolCall] = []
    for index, raw in enumerate(_get(message, "tool_calls") or []):
        function = _get(raw, "function")
        name = _get(function, "name") or ""
        if not name:
            continue
        calls.append(
            ToolCall(
                id=str(_get(raw, "id") or f"call_{index}"),
                name=str(name),
                arguments=_get(function, "arguments"),
            )
        )
    return str(content), calls


def _load_litellm() -> Any:
    """Import LiteLLM lazily so module import never needs provider credentials."""
    import litellm

    return litellm


def _completion(messages: list[dict[str, Any]]) -> tuple[str, list[ToolCall]]:
    if not llm_configured():
        raise LlmNotConfigured("No LLM model or credential is configured.")
    try:
        litellm = _load_litellm()
    except ImportError as exc:  # pragma: no cover - the image always installs it
        raise LlmError("The LiteLLM SDK is not installed.") from exc

    kwargs: dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "tools": TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "temperature": 0,
        "timeout": getattr(settings, "LLM_TIMEOUT_SECONDS", 30),
    }
    if getattr(settings, "LLM_API_KEY", ""):
        kwargs["api_key"] = settings.LLM_API_KEY
    if getattr(settings, "LLM_API_BASE", ""):
        kwargs["api_base"] = settings.LLM_API_BASE
    response = litellm.completion(**kwargs)
    return _message_from_response(response)


def _context_messages(session: ChatSession) -> list[dict[str, Any]]:
    history = list(
        session.messages.order_by("-created_at", "-id")[:MAX_CONTEXT_MESSAGES]
    )
    history.reverse()
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for message in history:
        if message.role == ChatMessage.ROLE_USER:
            messages.append({"role": "user", "content": message.content})
        elif message.content:
            messages.append({"role": "assistant", "content": message.content})
    return messages


def _arguments_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return sanitize(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": sanitize(raw)}
        return sanitize(parsed) if isinstance(parsed, dict) else {"value": sanitize(parsed)}
    return {}


def _assistant_tool_message(content: str, calls: list[ToolCall]) -> dict[str, Any]:
    payload_calls = []
    for call in calls:
        arguments = (
            call.arguments
            if isinstance(call.arguments, str)
            else json.dumps(sanitize(call.arguments), default=str)
        )
        payload_calls.append(
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": arguments},
            }
        )
    return {"role": "assistant", "content": content or None, "tool_calls": payload_calls}


def run_chat_turn(session: ChatSession, text: str) -> ChatMessage:
    """Persist the user message, run the tool loop, persist the assistant turn."""
    ChatMessage.objects.create(
        session=session, role=ChatMessage.ROLE_USER, content=text, status="completed"
    )
    session.save(update_fields=["updated_at"])

    messages = _context_messages(session)
    tool_runs: list[dict[str, Any]] = []
    status = ChatMessage.STATUS_COMPLETED
    error_code: str | None = None
    content = ""
    max_rounds = max(1, int(getattr(settings, "LLM_MAX_TOOL_ROUNDS", 4)))

    try:
        for _round in range(max_rounds):
            content, calls = _completion(messages)
            if not calls:
                break
            messages.append(_assistant_tool_message(content, calls))
            for call in calls:
                result = execute_tool_call(call.name, call.arguments)
                sanitized_result = sanitize(result)
                tool_runs.append(
                    {
                        "name": call.name,
                        "arguments": _arguments_payload(call.arguments),
                        "output": sanitized_result,
                        "status": ToolRun.STATUS_OK if result.get("ok") else ToolRun.STATUS_ERROR,
                        "error_code": (result.get("error") or {}).get("code"),
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": json.dumps(sanitized_result, default=str),
                    }
                )
        else:
            status = ChatMessage.STATUS_FAILED
            error_code = "tool_round_limit"
    except LlmNotConfigured:
        status = ChatMessage.STATUS_FAILED
        error_code = LlmNotConfigured.code
    except LlmError:
        status = ChatMessage.STATUS_FAILED
        error_code = LlmError.code
    except Exception as exc:  # noqa: BLE001 - classify provider failures safely
        logger.warning(
            "LLM call failed",
            extra={"event": "llm_error", "error_type": type(exc).__name__},
        )
        status = ChatMessage.STATUS_FAILED
        error_code = "llm_unavailable"

    if status == ChatMessage.STATUS_COMPLETED and not content.strip():
        status = ChatMessage.STATUS_FAILED
        error_code = "llm_empty_response"

    safe_content = sanitize(content)[:MAX_CONTENT_LENGTH] if content else ""

    with transaction.atomic():
        assistant = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            content=safe_content,
            status=status,
            error_code=error_code,
        )
        ToolRun.objects.bulk_create(
            [
                ToolRun(message=assistant, **run)
                for run in tool_runs
            ]
        )
    session.save(update_fields=["updated_at"])

    logger.info(
        "chat turn completed",
        extra={
            "event": "chat_turn",
            "session_id": str(session.id),
            "status": status,
            "error_code": error_code,
            "tool_count": len(tool_runs),
        },
    )
    return assistant
