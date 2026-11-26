"""Channels consumer for the live weather subscription protocol."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from weather.errors import ApiError
from weather.realtime import channel_group
from weather.services.cities import NormalizedCity, is_known_name, parse_cities_query
from weather.services.dashboard import snapshot_for_socket

logger = logging.getLogger("weather.consumer")

HEARTBEAT_SECONDS = 25
INVALID_SUBSCRIPTION_CODES = {"invalid_subscription", "unknown_city", "duplicate_city"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def frame(message_type: str, payload: dict) -> dict:
    return {"type": message_type, "sent_at": _now(), "payload": payload}


class WeatherConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.cities: list[NormalizedCity] = []
        self.group_names: list[str] = []
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self) -> None:
        try:
            cities = self._parse_cities()
            await self._ensure_known(cities)
        except ApiError as exc:
            await self.accept()
            code = exc.code if exc.code in INVALID_SUBSCRIPTION_CODES else "invalid_subscription"
            await self.send_json(frame("error", {"code": code, "message": exc.message}))
            await self.close(code=4001)
            return

        self.cities = cities
        self.group_names = [channel_group(city.key) for city in cities]
        for group_name in self.group_names:
            await self.channel_layer.group_add(group_name, self.channel_name)
        await self.accept()

        snapshot = await database_sync_to_async(snapshot_for_socket)(cities)
        await self.send_json(frame("snapshot", snapshot))
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, code: int) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        for group_name in self.group_names:
            await self.channel_layer.group_discard(group_name, self.channel_name)
        self.group_names = []

    async def receive_json(self, content: dict, **kwargs: object) -> None:
        # The socket is server-authored: clients may only keep it alive.
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json(frame("heartbeat", {"cities": [city.key for city in self.cities]}))
            return
        await self.send_json(
            frame(
                "error",
                {"code": "invalid_subscription", "message": "Clients may only send ping frames."},
            )
        )

    async def weather_observation(self, event: dict) -> None:
        await self.send_json(frame("observation", event["observation"]))

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_SECONDS)
                await self.send_json(
                    frame("heartbeat", {"cities": [city.key for city in self.cities]})
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("heartbeat loop failed", extra={"event": "realtime_error"})

    def _parse_cities(self):
        raw_query = self.scope.get("query_string", b"").decode()
        raw_cities = parse_qs(raw_query).get("cities", [None])[0]
        return parse_cities_query(raw_cities)

    async def _ensure_known(self, cities) -> None:
        for city in cities:
            known = await database_sync_to_async(is_known_name)(city.name)
            if not known:
                raise ApiError("unknown_city", f"No weather source found for '{city.name}'.")
