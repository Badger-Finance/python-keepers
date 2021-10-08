import json
import logging
import os
import pytest
from decimal import Decimal
from hexbytes import HexBytes

from src.data_classes.emissions_schedule import EmissionsSchedule
from tests.utils import schedule_json

logger = logging.getLogger()

SECONDS_IN_A_DAY = 60 * 60 * 24


def test_days_in_schedule(schedule_json):
    last_harvest = 1631008800  # 9/7/21 at 10AM
    current_time = 1633687200  # 10/8/21 at 10AM

    emissions = EmissionsSchedule(schedule_json)
    schedule = emissions.get_schedule()

    days_elapsed = (current_time - last_harvest) // SECONDS_IN_A_DAY

    schedules_to_use = []
    for start_time in schedule.keys():
        start_time = int(start_time)
        if start_time > last_harvest and start_time <= current_time:
            schedules_to_use.append(str(start_time))

    assert schedules_to_use == [
        "1631206800",
        "1631811600",
        "1632416400",
        "1633021200",
        "1633626000",
    ]

    days_in_prev = (int(schedules_to_use[0]) - last_harvest) // SECONDS_IN_A_DAY
    assert days_in_prev == 2

    if days_in_prev > 0: