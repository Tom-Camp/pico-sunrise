from fake_board import Board


def sync(board):
    return board.load("lib.time_sync").sync_and_set_rtc()


def clock_error(board):
    return abs(board.clock() - board.now)


def test_sets_the_clock():
    board = Board("2026-11-17 01:00")
    assert sync(board) is True
    assert clock_error(board) <= 1


def test_wifi_down():
    board = Board("2026-11-17 01:00", wifi_outages=[(0, 5)])
    assert sync(board) is False
    assert clock_error(board) > 86400


def test_ntp_down():
    board = Board("2026-11-17 01:00", ntp_outages=[(0, 5)])
    assert sync(board) is False
    assert clock_error(board) > 86400


def test_failed_sync_keeps_the_existing_clock():
    board = Board("2026-11-17 01:00", wifi_outages=[(1, 5)])
    assert sync(board) is True
    board._sleep(2 * 3600)
    assert sync(board) is False
    assert clock_error(board) <= 1


def test_reconnects_after_the_link_drops():
    board = Board("2026-11-17 01:00", wifi_outages=[(1, 2)])
    assert sync(board) is True
    board._sleep(3 * 3600)
    assert not board.connected()
    assert sync(board) is True
