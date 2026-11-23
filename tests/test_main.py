"""Run main.py for several simulated days and check when the sunrise starts."""

import pytest
from fake_board import Board

NIGHT = "2026-11-16 20:00"  # Monday evening


def test_normal_week():
    board = Board(NIGHT, days=7).run()
    board.assert_alarms_on_time()
    assert board.resets == 0


@pytest.mark.parametrize("outage", [(14, 80), (14, 999)], ids=["returns on day 4", "never returns"])
def test_wifi_outage_after_boot_does_not_block_alarms(outage):
    board = Board(NIGHT, days=7, wifi_outages=[outage]).run()
    board.assert_alarms_on_time()
    assert board.failed_connects > 0


def test_ntp_outage_after_boot_does_not_block_alarms():
    Board(NIGHT, days=7, ntp_outages=[(1, 999)]).run().assert_alarms_on_time()


@pytest.mark.parametrize("router_hours", [5 / 60, 2], ids=["5 minutes", "2 hours"])
def test_power_outage_waits_for_router(router_hours):
    board = Board("2026-11-17 01:00", days=4, wifi_outages=[(0, router_hours)]).run()
    board.assert_alarms_on_time()


def test_power_outage_waits_for_ntp():
    Board("2026-11-17 01:00", days=4, ntp_outages=[(0, 1)]).run().assert_alarms_on_time()


@pytest.mark.parametrize("start", ["2026-11-17 04:15", "2026-11-17 05:15", "2026-11-17 05:44"])
def test_powered_on_shortly_before_the_alarm(start):
    Board(start, days=4).run().assert_alarms_on_time()


@pytest.mark.parametrize("start", ["2027-03-11 20:00", "2027-11-04 20:00"], ids=["spring", "fall"])
@pytest.mark.parametrize("outages", [[], [(10, 999)]], ids=["wifi up", "wifi down"])
def test_dst_weekend(start, outages):
    Board(start, days=5, wifi_outages=outages).run().assert_alarms_on_time()


@pytest.mark.parametrize("drift_ppm", [50, -50])
@pytest.mark.parametrize("outages", [[], [(14, 999)]], ids=["wifi up", "wifi down"])
def test_clock_drift(drift_ppm, outages):
    Board(NIGHT, days=7, drift_ppm=drift_ppm, wifi_outages=outages).run().assert_alarms_on_time()


def test_unexpected_error_resets_and_recovers():
    board = Board(NIGHT, days=5, sync_error_at=25).run()
    board.assert_alarms_on_time()
    assert board.resets == 1


@pytest.mark.parametrize(
    "hours",
    [2 / 3600, 1, 9, 9.8],
    ids=["startup delay", "first sleep", "second sleep", "sunrise"],
)
def test_interrupt_stops_the_program_with_lights_off(hours):
    board = Board(NIGHT, days=2, interrupt_at=hours)
    with pytest.raises(KeyboardInterrupt):
        board.run()
    assert board.hours() == pytest.approx(hours, abs=1 / 3600)
    assert not board._lit
    assert board.resets == 0
