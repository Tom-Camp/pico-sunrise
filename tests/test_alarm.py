from datetime import datetime, timedelta

import pytest
from fake_board import EASTERN, Board, eastern

HOUR = 3600
DAY = 24 * HOUR


@pytest.fixture
def alarm():
    return Board("2026-11-17 01:00").load("lib.alarm")


def utc(text: str) -> int:
    return int(eastern(text).timestamp())


@pytest.mark.parametrize(
    "year, month, weekday, n, day",
    [
        (2026, 3, 6, 2, 8),  # DST start
        (2027, 3, 6, 2, 14),
        (2026, 11, 6, 1, 1),  # DST end, month starts on the target day
        (2027, 11, 6, 1, 7),
        (2026, 2, 0, 1, 2),
    ],
)
def test_nth_weekday(alarm, year, month, weekday, n, day):
    assert alarm.nth_weekday(year, month, weekday, n) == day


def test_utc_to_eastern_matches_timezone_database(alarm):
    start = utc("2026-01-01 00:00")
    for now in range(start, start + 5 * 365 * DAY, HOUR):
        offset = datetime.fromtimestamp(now, EASTERN).utcoffset() // timedelta(seconds=1)
        assert alarm.utc_to_eastern(now) == now + offset


@pytest.mark.parametrize(
    "now, expected",
    [
        ("2026-11-17 01:00", "2026-11-17 05:45"),  # before today's alarm
        ("2026-11-17 05:45", "2026-11-18 05:45"),  # exactly at the alarm
        ("2026-11-17 06:24", "2026-11-18 05:45"),  # after the sunrise ends
        ("2026-11-17 20:00", "2026-11-18 05:45"),  # already tomorrow in UTC
        ("2026-11-20 12:00", "2026-11-21 06:00"),  # Friday to Saturday
        ("2026-11-22 12:00", "2026-11-23 05:45"),  # Sunday to Monday
        ("2026-11-30 12:00", "2026-12-01 05:45"),  # month end
        ("2026-12-31 22:00", "2027-01-01 05:45"),  # year end
        ("2028-02-28 12:00", "2028-02-29 05:45"),  # leap day
        ("2027-07-01 01:00", "2027-07-01 05:45"),  # during DST
    ],
)
def test_next_alarm(alarm, now, expected):
    assert alarm.next_alarm(utc(now)) == utc(expected) - utc(now)


def test_next_alarm_is_an_hour_off_across_a_dst_change(alarm):
    """A known limit: main.py resyncs two hours early to absorb this."""
    spring, sunday = utc("2027-03-13 12:00"), utc("2027-03-14 06:00")
    assert alarm.next_alarm(spring) == sunday - spring + HOUR

    fall, sunday = utc("2027-11-06 12:00"), utc("2027-11-07 06:00")
    assert alarm.next_alarm(fall) == sunday - fall - HOUR
