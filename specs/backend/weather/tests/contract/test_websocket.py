import asyncio
from datetime import timedelta

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.utils import timezone

from weather.routing import websocket_urlpatterns

pytestmark = pytest.mark.django_db(transaction=True)

APPLICATION = URLRouter(websocket_urlpatterns)


@pytest.fixture(autouse=True)
def close_async_connections():
    """Close the shared sync-to-async thread's DB connection after each test."""
    yield
    from django.db import connections

    asyncio.run(database_sync_to_async(connections.close_all)())


def _path(*cities: str) -> str:
    return f"/ws/weather/?cities={','.join(cities)}"


def _seed(make_observation) -> None:
    now = timezone.now()
    make_observation("Santiago", timestamp=now)
    make_observation("Valparaiso", timestamp=now - timedelta(minutes=1))


def test_snapshot_on_connect(make_observation):
    _seed(make_observation)

    async def scenario():
        communicator = WebsocketCommunicator(APPLICATION, _path("Santiago", "Valparaiso"))
        connected, _ = await communicator.connect()
        assert connected is True
        message = await communicator.receive_json_from(timeout=5)
        assert message["type"] == "snapshot"
        assert message["sent_at"].endswith("Z")
        payload = message["payload"]
        assert [city["city"] for city in payload["cities"]] == ["Santiago", "Valparaiso"]
        assert payload["comparison"]["temperature_delta"] is not None
        await communicator.disconnect()

    asyncio.run(scenario())


def test_observation_frame_shape(make_observation):
    _seed(make_observation)
    observation = {
        "id": 1043,
        "city": "Santiago",
        "city_key": "santiago",
        "country_code": "CL",
        "temperature": 18.6,
        "humidity": 61,
        "wind_speed": 3.4,
        "timestamp": "2026-11-25T14:00:00Z",
        "source": "live",
    }

    async def scenario():
        communicator = WebsocketCommunicator(APPLICATION, _path("Santiago", "Valparaiso"))
        await communicator.connect()
        await communicator.receive_json_from(timeout=5)

        layer = get_channel_layer()
        await layer.group_send(
            "weather.santiago", {"type": "weather.observation", "observation": observation}
        )
        message = await communicator.receive_json_from(timeout=5)
        assert message["type"] == "observation"
        assert message["payload"] == observation
        await communicator.disconnect()

    asyncio.run(scenario())


def test_ping_answers_with_a_heartbeat(make_observation):
    _seed(make_observation)

    async def scenario():
        communicator = WebsocketCommunicator(APPLICATION, _path("Santiago", "Valparaiso"))
        await communicator.connect()
        await communicator.receive_json_from(timeout=5)
        await communicator.send_json_to({"type": "ping"})
        message = await communicator.receive_json_from(timeout=5)
        assert message["type"] == "heartbeat"
        assert message["payload"]["cities"] == ["santiago", "valparaiso"]
        await communicator.disconnect()

    asyncio.run(scenario())


def test_duplicate_cities_close_with_4001():
    async def scenario():
        communicator = WebsocketCommunicator(APPLICATION, _path("Santiago", "santiago"))
        connected, _ = await communicator.connect()
        assert connected is True
        error = await communicator.receive_json_from(timeout=5)
        assert error["type"] == "error"
        assert error["payload"]["code"] == "duplicate_city"
        await communicator.wait(timeout=5)

    asyncio.run(scenario())


def test_missing_cities_close_with_4001():
    async def scenario():
        communicator = WebsocketCommunicator(APPLICATION, "/ws/weather/")
        connected, _ = await communicator.connect()
        assert connected is True
        error = await communicator.receive_json_from(timeout=5)
        assert error["type"] == "error"
        assert error["payload"]["code"] == "invalid_subscription"
        await communicator.wait(timeout=5)

    asyncio.run(scenario())


def test_unknown_city_closes_with_4001(settings):
    settings.OPENWEATHER_API_KEY = ""

    async def scenario():
        communicator = WebsocketCommunicator(APPLICATION, _path("Atlantis", "Nowhere"))
        connected, _ = await communicator.connect()
        assert connected is True
        error = await communicator.receive_json_from(timeout=5)
        assert error["payload"]["code"] == "unknown_city"
        await communicator.wait(timeout=5)

    asyncio.run(scenario())


def test_client_messages_other_than_ping_are_rejected(make_observation):
    _seed(make_observation)

    async def scenario():
        communicator = WebsocketCommunicator(APPLICATION, _path("Santiago", "Valparaiso"))
        await communicator.connect()
        await communicator.receive_json_from(timeout=5)
        await communicator.send_json_to({"type": "subscribe", "cities": ["Lima", "Quito"]})
        message = await communicator.receive_json_from(timeout=5)
        assert message["type"] == "error"
        assert message["payload"]["code"] == "invalid_subscription"
        await communicator.disconnect()

    asyncio.run(scenario())
