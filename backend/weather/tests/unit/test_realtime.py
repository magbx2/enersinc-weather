import pytest
from channels.layers import BaseChannelLayer

from weather.realtime import channel_group


@pytest.mark.parametrize(
    "city_key",
    ["santiago", "new york", "o'brien", "sao paulo", "a.b-c_d", "x" * 80],
)
def test_group_name_is_valid_for_channels(city_key):
    name = channel_group(city_key)

    # BaseChannelLayer.valid_group_name raises TypeError for invalid names.
    assert BaseChannelLayer().valid_group_name(name) is True
    assert len(name) < 100


def test_group_names_are_stable_and_distinct():
    assert channel_group("new york") == channel_group("new york")
    assert channel_group("new york") != channel_group("new_york")
    assert channel_group("new york") != channel_group("new  york")
