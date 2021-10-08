import json
import logging
import os
import pytest
from decimal import Decimal
from hexbytes import HexBytes

from src.data_classes.emissions_schedule import EmissionsSchedule

logger = logging.getLogger()


@pytest.fixture
def mock_sett_formatted():
    return {
        "0x6dEf55d2e18486B9dDfaA075bc4e4EE0B28c1545": {
            "name": "renBTC",
            "badger_allocation": 3429,
            "digg_allocation": 0,
        },
        "0xd04c48A53c111300aD41190D63681ed3dAd998eC": {
            "name": "sBTC",
            "badger_allocation": 1715,
            "digg_allocation": 0,
        },
    }


@pytest.fixture
def mock_sett_list():
    return [
        {
            "name": "renBTC",
            "address": "0x6dEf55d2e18486B9dDfaA075bc4e4EE0B28c1545",
            "badger_allocation": 3429,
            "digg_allocation": 0,
        },
        {
            "name": "sBTC",
            "address": "0xd04c48A53c111300aD41190D63681ed3dAd998eC",
            "badger_allocation": 1715,
            "digg_allocation": 0,
        },
    ]


@pytest.fixture
def schedule_json():
    with open("./tests/data_classes/mock_emissions_schedule.json") as f:
        mock_schedule_json = json.load(f)
        return mock_schedule_json


@pytest.fixture
def formatted_schedule():
    with open("./tests/data_classes/mock_formatted_schedule.json") as f:
        mock_formatted_schedule = json.load(f)
        return mock_formatted_schedule


@pytest.fixture
def emissions_schedule(schedule_json):
    return EmissionsSchedule(schedule_json)


def test_get_start_times(emissions_schedule):
    start_times = emissions_schedule.get_start_times()
    assert start_times == [
        "1629997200",
        "1630602000",
        "1631206800",
        "1631811600",
        "1632416400",
        "1633021200",
        "1633626000",
        "1634230800",
        "1634835600",
        "1635440400",
        "1636045200",
        "1636650000",
        "1637254800",
        "1637859600",
        "1638464400",
        "1639069200",
        "1639674000",
        "1640278800",
    ]


def test_get_end_times(emissions_schedule):
    start_times = emissions_schedule.get_end_times()
    assert start_times == [
        "1630602000",
        "1631206800",
        "1631811600",
        "1632416400",
        "1633021200",
        "1633626000",
        "1634230800",
        "1634835600",
        "1635440400",
        "1636045200",
        "1636650000",
        "1637254800",
        "1637859600",
        "1638464400",
        "1639069200",
        "1639674000",
        "1640278800",
        "1640883600",
    ]


def test_format_setts(emissions_schedule, mock_sett_list, mock_sett_formatted):
    assert emissions_schedule.format_setts(mock_sett_list) == mock_sett_formatted


def test_get_schedule(emissions_schedule, formatted_schedule):
    calc_schedule = emissions_schedule.get_schedule()
    for key in formatted_schedule.keys():
        assert key in calc_schedule.keys()
        assert calc_schedule[key] == formatted_schedule[key]


def test_schedule_keys_ascending_order(emissions_schedule):
    schedule = emissions_schedule.get_schedule()
    prev = 0
    for key in schedule.keys():
        cur = int(key)
        assert cur > prev
        prev = cur
