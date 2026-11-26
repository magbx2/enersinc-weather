"""Shared error envelope, typed API errors and the DRF exception handler.

Envelope: ``{"error": {"code", "message", "details", "request_id"}}``.
Unexpected failures never leak internals or credentials.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from django.db import DatabaseError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from weather.context import current_request_id

logger = logging.getLogger("weather.errors")

CODES = frozenset(
    {
        "invalid_city",
        "duplicate_city",
        "unknown_city",
        "invalid_pagination",
        "invalid_window",
        "invalid_range",
        "provider_unavailable",
        "credential_invalid",
        "rate_limited",
        "no_data_available",
        "cross_origin_rejected",
        "internal_error",
    }
)


class ApiError(exceptions.APIException):
    """An error the client can act on, expressed in the contract's vocabulary."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(detail=message, code=code)


def envelope(
    code: str, message: str, details: dict[str, Any] | None = None, request_id: str | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id or current_request_id(),
        }
    }


def _field_code(detail: dict[str, Any]) -> str:
    fields = set(detail)
    if fields & {"page", "page_size"}:
        return "invalid_pagination"
    if "window" in fields:
        return "invalid_window"
    if fields & {"start", "end"}:
        return "invalid_range"
    if fields & {"cities", "city"}:
        return "invalid_city"
    return "invalid_city"


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    request = context.get("request")
    request_id = getattr(request, "request_id", None)
    headers: dict[str, str] = {}

    if isinstance(exc, ApiError):
        return Response(
            envelope(exc.code, exc.message, exc.details, request_id),
            status=exc.status_code,
        )

    if isinstance(exc, exceptions.Throttled):
        wait = getattr(exc, "wait", None)
        if wait is not None:
            headers["Retry-After"] = str(max(1, math.ceil(float(wait))))
        return Response(
            envelope("rate_limited", "Too many requests. Please retry later.", None, request_id),
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers=headers,
        )

    if isinstance(exc, exceptions.ValidationError):
        detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
        return Response(
            envelope(_field_code(detail), "Invalid request.", detail, request_id),
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, Http404):
        return Response(
            envelope("internal_error", "Resource not found.", None, request_id),
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, exceptions.PermissionDenied):
        return Response(
            envelope("cross_origin_rejected", "Request origin is not allowed.", None, request_id),
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, exceptions.NotAcceptable | exceptions.UnsupportedMediaType):
        return Response(
            envelope("invalid_city", "Unsupported request content type.", None, request_id),
            status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    if isinstance(exc, exceptions.ParseError):
        return Response(
            envelope("invalid_city", "Request body is not valid JSON.", None, request_id),
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, DatabaseError):
        logger.exception("database operation failed", extra={"event": "database_error"})
        return Response(
            envelope("internal_error", "Storage is unavailable.", None, request_id),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    logger.exception("unhandled API error", extra={"event": "internal_error"})
    return Response(
        envelope("internal_error", "An unexpected error occurred.", None, request_id),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
