from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

import timesheet_nag


def _mock_worklogs_response(worklogs: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"results": worklogs, "metadata": {}}
    resp.raise_for_status = MagicMock()
    return resp


def _mock_approval_response(status_key: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"status": {"key": status_key}}
    resp.raise_for_status = MagicMock()
    return resp


class TestGetLastWeekRange:
    def test_monday(self) -> None:
        monday, sunday = timesheet_nag.get_last_week_range(date(2026, 3, 30))
        assert monday == "2026-03-23"
        assert sunday == "2026-03-29"

    def test_friday(self) -> None:
        monday, sunday = timesheet_nag.get_last_week_range(date(2026, 4, 3))
        assert monday == "2026-03-23"
        assert sunday == "2026-03-29"

    def test_sunday(self) -> None:
        monday, sunday = timesheet_nag.get_last_week_range(date(2026, 4, 5))
        assert monday == "2026-03-23"
        assert sunday == "2026-03-29"


class TestGetCurrentWeekRange:
    def test_monday(self) -> None:
        monday, sunday = timesheet_nag.get_current_week_range(date(2026, 3, 30))
        assert monday == "2026-03-30"
        assert sunday == "2026-04-05"

    def test_wednesday(self) -> None:
        monday, sunday = timesheet_nag.get_current_week_range(date(2026, 4, 1))
        assert monday == "2026-03-30"
        assert sunday == "2026-04-05"

    def test_saturday(self) -> None:
        monday, sunday = timesheet_nag.get_current_week_range(date(2026, 4, 4))
        assert monday == "2026-03-30"
        assert sunday == "2026-04-05"

    def test_sunday(self) -> None:
        monday, sunday = timesheet_nag.get_current_week_range(date(2026, 4, 5))
        assert monday == "2026-03-30"
        assert sunday == "2026-04-05"


class TestFetchLoggedHours:
    @patch("timesheet_nag.requests.get")
    def test_sums_worklogs(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _mock_worklogs_response([
            {"timeSpentSeconds": 3600 * 8},
            {"timeSpentSeconds": 3600 * 4},
        ])
        hours = timesheet_nag.fetch_logged_hours("tok", "acc", "2026-03-23", "2026-03-29")
        assert hours == 12.0

    @patch("timesheet_nag.requests.get")
    def test_empty_worklogs(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _mock_worklogs_response([])
        hours = timesheet_nag.fetch_logged_hours("tok", "acc", "2026-03-23", "2026-03-29")
        assert hours == 0.0

    @patch("timesheet_nag.requests.get")
    def test_pagination(self, mock_get: MagicMock) -> None:
        page1 = MagicMock()
        page1.json.return_value = {
            "results": [{"timeSpentSeconds": 3600 * 20}],
            "metadata": {"next": "https://api.tempo.io/4/worklogs?offset=1"},
        }
        page1.raise_for_status = MagicMock()

        page2 = _mock_worklogs_response([{"timeSpentSeconds": 3600 * 20}])
        mock_get.side_effect = [page1, page2]

        hours = timesheet_nag.fetch_logged_hours("tok", "acc", "2026-03-23", "2026-03-29")
        assert hours == 40.0
        assert mock_get.call_count == 2


class TestFetchApprovalStatus:
    @patch("timesheet_nag.requests.get")
    def test_returns_status_key(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _mock_approval_response("WAITING_FOR_APPROVAL")
        status = timesheet_nag.fetch_approval_status("tok", "acc", "2026-03-23", "2026-03-29")
        assert status == "WAITING_FOR_APPROVAL"

    @patch("timesheet_nag.requests.get")
    def test_open_status(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _mock_approval_response("OPEN")
        status = timesheet_nag.fetch_approval_status("tok", "acc", "2026-03-23", "2026-03-29")
        assert status == "OPEN"


class TestIsTimesheetComplete:
    def test_complete(self) -> None:
        assert timesheet_nag.is_timesheet_complete(40.0, "APPROVED") is True

    def test_submitted_enough_hours(self) -> None:
        assert timesheet_nag.is_timesheet_complete(42.0, "WAITING_FOR_APPROVAL") is True

    def test_low_hours(self) -> None:
        assert timesheet_nag.is_timesheet_complete(39.5, "APPROVED") is False

    def test_not_submitted(self) -> None:
        assert timesheet_nag.is_timesheet_complete(40.0, "OPEN") is False

    def test_both_incomplete(self) -> None:
        assert timesheet_nag.is_timesheet_complete(20.0, "OPEN") is False


class TestWriteNagFile:
    def test_writes_file(self, tmp_path: Path) -> None:
        nag_file = tmp_path / "nag.txt"
        with patch.object(timesheet_nag, "NAG_FILE", nag_file):
            timesheet_nag.write_nag_file(32.5, "OPEN", "2026-03-23", "2026-03-29")
        content = nag_file.read_text()
        assert "32.5" in content
        assert "40.0" in content
        assert "OPEN" in content
        assert "2026-03-23" in content


class TestMain:
    @patch("timesheet_nag.time.sleep")
    @patch("timesheet_nag.open_nag_file")
    @patch("timesheet_nag.write_nag_file")
    @patch("timesheet_nag.fetch_approval_status", return_value="APPROVED")
    @patch("timesheet_nag.fetch_logged_hours", return_value=40.0)
    @patch("timesheet_nag.load_config", return_value=("tok", "acc"))
    def test_stops_when_complete(
        self, _cfg: MagicMock, _hours: MagicMock, _status: MagicMock,
        mock_write: MagicMock, mock_open: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        timesheet_nag.main([])
        mock_write.assert_not_called()
        mock_open.assert_not_called()
        mock_sleep.assert_not_called()

    @patch("timesheet_nag.time.sleep")
    @patch("timesheet_nag.open_nag_file")
    @patch("timesheet_nag.write_nag_file")
    @patch("timesheet_nag.fetch_approval_status", side_effect=["OPEN", "APPROVED"])
    @patch("timesheet_nag.fetch_logged_hours", side_effect=[30.0, 40.0])
    @patch("timesheet_nag.load_config", return_value=("tok", "acc"))
    def test_stops_when_filled_on_second_check(
        self, _cfg: MagicMock, _hours: MagicMock, _status: MagicMock,
        mock_write: MagicMock, mock_open: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        timesheet_nag.main([])
        assert mock_write.call_count == 1
        assert mock_open.call_count == 1
        assert mock_sleep.call_count == 1

    @patch("timesheet_nag.time.sleep")
    @patch("timesheet_nag.open_nag_file")
    @patch("timesheet_nag.write_nag_file")
    @patch("timesheet_nag.fetch_approval_status", return_value="APPROVED")
    @patch("timesheet_nag.fetch_logged_hours", side_effect=[
        requests.RequestException("network"),
        requests.RequestException("network"),
        40.0,
    ])
    @patch("timesheet_nag.load_config", return_value=("tok", "acc"))
    def test_api_error_skips_and_retries(
        self, _cfg: MagicMock, _hours: MagicMock, _status: MagicMock,
        mock_write: MagicMock, mock_open: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        timesheet_nag.main([])
        mock_write.assert_not_called()
        mock_open.assert_not_called()
        assert mock_sleep.call_count == 2


class TestLoadConfig:
    def test_happy_path(self, tmp_path: Path) -> None:
        token_file = tmp_path / ".tempo_token"
        token_file.write_text("my-token\nmy-account-id\n")
        with patch.object(timesheet_nag, "TOKEN_FILE", token_file):
            token, account_id = timesheet_nag.load_config()
        assert token == "my-token"
        assert account_id == "my-account-id"

    def test_missing_file(self, tmp_path: Path) -> None:
        token_file = tmp_path / ".tempo_token"
        with patch.object(timesheet_nag, "TOKEN_FILE", token_file):
            with pytest.raises(SystemExit):
                timesheet_nag.load_config()

    def test_single_line(self, tmp_path: Path) -> None:
        token_file = tmp_path / ".tempo_token"
        token_file.write_text("my-token\n")
        with patch.object(timesheet_nag, "TOKEN_FILE", token_file):
            with pytest.raises(SystemExit):
                timesheet_nag.load_config()

    def test_empty_token(self, tmp_path: Path) -> None:
        token_file = tmp_path / ".tempo_token"
        token_file.write_text("\nmy-account-id\n")
        with patch.object(timesheet_nag, "TOKEN_FILE", token_file):
            with pytest.raises(SystemExit):
                timesheet_nag.load_config()

    def test_empty_account_id(self, tmp_path: Path) -> None:
        token_file = tmp_path / ".tempo_token"
        token_file.write_text("my-token\n  \n")
        with patch.object(timesheet_nag, "TOKEN_FILE", token_file):
            with pytest.raises(SystemExit):
                timesheet_nag.load_config()


class TestParseArgs:
    def test_defaults(self) -> None:
        args = timesheet_nag.parse_args([])
        assert args.dry_run is False
        assert args.week == "last"

    def test_dry_run(self) -> None:
        args = timesheet_nag.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_week_current(self) -> None:
        args = timesheet_nag.parse_args(["--week", "current"])
        assert args.week == "current"

    def test_week_last(self) -> None:
        args = timesheet_nag.parse_args(["--week", "last"])
        assert args.week == "last"


class TestDryRun:
    @patch("timesheet_nag.open_nag_file")
    @patch("timesheet_nag.write_nag_file")
    @patch("timesheet_nag.fetch_approval_status")
    @patch("timesheet_nag.fetch_logged_hours")
    @patch("timesheet_nag.load_config", return_value=("tok", "account123"))
    def test_dry_run_skips_api_and_nag(
        self, _cfg: MagicMock, mock_hours: MagicMock, mock_status: MagicMock,
        mock_write: MagicMock, mock_open: MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        timesheet_nag.main(["--dry-run"])
        mock_hours.assert_not_called()
        mock_status.assert_not_called()
        mock_write.assert_not_called()
        mock_open.assert_not_called()
        output = capsys.readouterr().out
        assert "[dry-run]" in output
        assert "acc***" in output
        assert "Would fetch worklogs" in output

    @patch("timesheet_nag.time.sleep")
    @patch("timesheet_nag.open_nag_file")
    @patch("timesheet_nag.write_nag_file")
    @patch("timesheet_nag.fetch_approval_status", return_value="APPROVED")
    @patch("timesheet_nag.fetch_logged_hours", return_value=40.0)
    @patch("timesheet_nag.load_config", return_value=("tok", "acc"))
    def test_no_flag_still_works(
        self, _cfg: MagicMock, _hours: MagicMock, _status: MagicMock,
        mock_write: MagicMock, mock_open: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        timesheet_nag.main([])
        mock_write.assert_not_called()
        mock_open.assert_not_called()
