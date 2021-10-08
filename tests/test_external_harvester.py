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

    # if days_in_prev > 0:
    previous = schedules_to_use[0]
    for start_time in schedule.keys():
        if start_time == schedules_to_use[0]:
            break
        previous = str(start_time)
    previous_schedule_time = previous
    assert previous_schedule_time == "1630602000"

    distribution = []
    schedule_start_and_time_elapsed = (previous_schedule_time, days_in_prev)

    distribution.append(schedule_start_and_time_elapsed)
    for week in schedules_to_use:
        duration = (int(current_time) - int(week)) // SECONDS_IN_A_DAY
        weekly_rewards = (week, min(7, duration))
        distribution.append(weekly_rewards)

    assert distribution == [
        ("1630602000", 2),
        ("1631206800", 7),
        ("1631811600", 7),
        ("1632416400", 7),
        ("1633021200", 7),
        ("1633626000", 0),
    ]

    sum_of_days = sum([x[1] for x in distribution])
    assert sum_of_days == days_elapsed - 1


def test_alt(schedule_json):
    last_harvest = 1631008800  # 9/7/21 at 10AM
    current_time = 1631095200  # 10/8/21 at 10AM

    emissions = EmissionsSchedule(schedule_json)
    schedule = emissions.get_schedule()

    days_elapsed = (current_time - last_harvest) // SECONDS_IN_A_DAY

    schedules_to_use = []
    for start_time in schedule.keys():
        start_time = int(start_time)
        if start_time > last_harvest and start_time <= current_time:
            schedules_to_use.append(str(start_time))

    assert schedules_to_use == []

    previous = 0
    for start_time in schedule.keys():
        if int(start_time) > current_time and current_time >= previous:
            break
        previous = int(start_time)
    previous_schedule_time = str(previous)
    assert previous_schedule_time == "1630602000"

    if schedules_to_use == []:
        assert days_elapsed == 1
        days_in_prev = days_elapsed

    distribution = []
    schedule_start_and_time_elapsed = (previous_schedule_time, days_in_prev)

    distribution.append(schedule_start_and_time_elapsed)
    for week in schedules_to_use:
        duration = (int(current_time) - int(week)) // SECONDS_IN_A_DAY
        weekly_rewards = (week, min(7, duration))
        distribution.append(weekly_rewards)

    assert distribution == [
        ("1630602000", 1),
    ]

    sum_of_days = sum([x[1] for x in distribution])
    assert sum_of_days == days_elapsed - 1
