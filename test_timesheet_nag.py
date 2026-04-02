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

    @patch("timesheet_nag.requests.get")
    def test_rejects_spoofed_subdomain(self, mock_get: MagicMock) -> None:
        page1 = MagicMock()
        page1.json.return_value = {
            "results": [{"timeSpentSeconds": 3600 * 20}],
            "metadata": {"next": "https://api.tempo.io.evil.com/4/worklogs?offset=1"},
        }
        page1.raise_for_status = MagicMock()
        mock_get.return_value = page1

        hours = timesheet_nag.fetch_logged_hours("tok", "acc", "2026-03-23", "2026-03-29")
        assert hours == 20.0
        assert mock_get.call_count == 1

    @patch("timesheet_nag.requests.get")
    def test_rejects_http_downgrade(self, mock_get: MagicMock) -> None:
        page1 = MagicMock()
        page1.json.return_value = {
            "results": [{"timeSpentSeconds": 3600 * 20}],
            "metadata": {"next": "http://api.tempo.io/4/worklogs?offset=1"},
        }
        page1.raise_for_status = MagicMock()
        mock_get.return_value = page1

        hours = timesheet_nag.fetch_logged_hours("tok", "acc", "2026-03-23", "2026-03-29")
        assert hours == 20.0
        assert mock_get.call_count == 1


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


class TestShowNagPopup:
    def test_shows_custom_window(self) -> None:
        mock_tk = MagicMock()
        mock_root = MagicMock()
        mock_tk.Tk.return_value = mock_root

        with patch.dict("sys.modules", {"tkinter": mock_tk}):
            timesheet_nag.show_nag_popup(32.5, "OPEN", "2026-03-23", "2026-03-29")

        mock_root.overrideredirect.assert_called_once_with(True)
        mock_root.attributes.assert_called_once_with("-topmost", True)
        mock_root.configure.assert_called_once_with(bg="#FFFFFF")
        label_calls = mock_tk.Label.call_args_list
        assert len(label_calls) == 2
        title_call = label_calls[0]
        assert "FILL YOUR TIMESHEET!" in title_call[1]["text"]
        assert title_call[1]["font"] == ("Consolas", 28, "bold")
        assert title_call[1]["fg"] == "#FFFF55"
        assert title_call[1]["bg"] == "#0000AA"
        message_call = label_calls[1]
        assert "32.5" in message_call[1]["text"]
        assert "2026-03-23" in message_call[1]["text"]
        assert message_call[1]["font"] == ("Consolas", 14)
        assert message_call[1]["fg"] == "#FFFFFF"
        assert message_call[1]["bg"] == "#0000AA"
        mock_tk.Button.assert_called_once()
        btn_call = mock_tk.Button.call_args[1]
        assert btn_call["text"] == "[ OK ]"
        assert btn_call["relief"] == "flat"
        mock_root.mainloop.assert_called_once()

    def test_notify_send_fallback(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch.dict("sys.modules", {"tkinter": None}):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                timesheet_nag.show_nag_popup(32.5, "OPEN", "2026-03-23", "2026-03-29")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "notify-send"
        assert "--urgency=critical" in args
        assert "FILL YOUR TIMESHEET!" in args

    def test_notify_send_failure_falls_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.dict("sys.modules", {"tkinter": None}):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with patch("timesheet_nag.sys") as mock_sys:
                    mock_sys.platform = "linux"
                    mock_sys.stderr = __import__("sys").stderr
                    timesheet_nag.show_nag_popup(32.5, "OPEN", "2026-03-23", "2026-03-29")
        err = capsys.readouterr().err
        assert "falling back to stderr" in err
        assert "32.5" in err
        assert "2026-03-23" in err

    def test_notify_send_nonzero_falls_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch.dict("sys.modules", {"tkinter": None}):
            with patch("subprocess.run", return_value=mock_result):
                with patch("timesheet_nag.sys") as mock_sys:
                    mock_sys.platform = "linux"
                    mock_sys.stderr = __import__("sys").stderr
                    timesheet_nag.show_nag_popup(32.5, "OPEN", "2026-03-23", "2026-03-29")
        err = capsys.readouterr().err
        assert "falling back to stderr" in err
        assert "32.5" in err

    def test_osascript_fallback_on_macos(self) -> None:
        def run_side_effect(cmd, **kwargs):
            if cmd[0] == "notify-send":
                raise FileNotFoundError
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        with patch.dict("sys.modules", {"tkinter": None}):
            with patch("subprocess.run", side_effect=run_side_effect) as mock_run:
                with patch("timesheet_nag.sys") as mock_sys:
                    mock_sys.platform = "darwin"
                    mock_sys.stderr = __import__("sys").stderr
                    timesheet_nag.show_nag_popup(32.5, "OPEN", "2026-03-23", "2026-03-29")
        osascript_calls = [c for c in mock_run.call_args_list if c[0][0][0] == "osascript"]
        assert len(osascript_calls) == 1
        assert "FILL YOUR TIMESHEET!" in osascript_calls[0][0][0][2]

    def test_osascript_skipped_on_linux(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.dict("sys.modules", {"tkinter": None}):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with patch("timesheet_nag.sys") as mock_sys:
                    mock_sys.platform = "linux"
                    mock_sys.stderr = __import__("sys").stderr
                    timesheet_nag.show_nag_popup(32.5, "OPEN", "2026-03-23", "2026-03-29")
        err = capsys.readouterr().err
        assert "falling back to stderr" in err

    def test_window_configured_topmost(self) -> None:
        mock_tk = MagicMock()
        mock_root = MagicMock()
        mock_tk.Tk.return_value = mock_root

        with patch.dict("sys.modules", {"tkinter": mock_tk}):
            timesheet_nag.show_nag_popup(40.0, "APPROVED", "2026-03-23", "2026-03-29")

        mock_root.overrideredirect.assert_called_once_with(True)
        mock_root.attributes.assert_called_once_with("-topmost", True)
        mock_root.mainloop.assert_called_once()


class TestMain:
    @patch("timesheet_nag.time.sleep")
    @patch("timesheet_nag.show_nag_popup")
    @patch("timesheet_nag.fetch_approval_status", return_value="APPROVED")
    @patch("timesheet_nag.fetch_logged_hours", return_value=40.0)
    @patch("timesheet_nag.load_config", return_value=("tok", "acc"))
    def test_stops_when_complete(
        self, _cfg: MagicMock, _hours: MagicMock, _status: MagicMock,
        mock_popup: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        timesheet_nag.main([])
        mock_popup.assert_not_called()
        mock_sleep.assert_not_called()

    @patch("timesheet_nag.time.sleep")
    @patch("timesheet_nag.show_nag_popup")
    @patch("timesheet_nag.fetch_approval_status", side_effect=["OPEN", "APPROVED"])
    @patch("timesheet_nag.fetch_logged_hours", side_effect=[30.0, 40.0])
    @patch("timesheet_nag.load_config", return_value=("tok", "acc"))
    def test_stops_when_filled_on_second_check(
        self, _cfg: MagicMock, _hours: MagicMock, _status: MagicMock,
        mock_popup: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        timesheet_nag.main([])
        assert mock_popup.call_count == 1
        assert mock_sleep.call_count == 1

    @patch("timesheet_nag.time.sleep")
    @patch("timesheet_nag.show_nag_popup")
    @patch("timesheet_nag.fetch_approval_status", return_value="APPROVED")
    @patch("timesheet_nag.fetch_logged_hours", side_effect=[
        requests.RequestException("network"),
        requests.RequestException("network"),
        40.0,
    ])
    @patch("timesheet_nag.load_config", return_value=("tok", "acc"))
    def test_api_error_skips_and_retries(
        self, _cfg: MagicMock, _hours: MagicMock, _status: MagicMock,
        mock_popup: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        timesheet_nag.main([])
        mock_popup.assert_not_called()
        assert mock_sleep.call_count == 2

    @patch("timesheet_nag.time.sleep")
    @patch("timesheet_nag.show_nag_popup")
    @patch("timesheet_nag.fetch_approval_status", return_value="APPROVED")
    @patch("timesheet_nag.load_config", return_value=("tok", "acc"))
    def test_4xx_error_exits_immediately(
        self, _cfg: MagicMock, _status: MagicMock,
        mock_popup: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        resp = MagicMock()
        resp.status_code = 401
        with patch("timesheet_nag.fetch_logged_hours", side_effect=requests.HTTPError(response=resp)):
            with pytest.raises(SystemExit):
                timesheet_nag.main([])
        mock_popup.assert_not_called()
        mock_sleep.assert_not_called()


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
    @patch("timesheet_nag.show_nag_popup")
    @patch("timesheet_nag.fetch_approval_status")
    @patch("timesheet_nag.fetch_logged_hours")
    @patch("timesheet_nag.load_config", return_value=("tok", "account123"))
    def test_dry_run_skips_api_and_nag(
        self, _cfg: MagicMock, mock_hours: MagicMock, mock_status: MagicMock,
        mock_popup: MagicMock, capsys: pytest.CaptureFixture[str],
    ) -> None:
        timesheet_nag.main(["--dry-run"])
        mock_hours.assert_not_called()
        mock_status.assert_not_called()
        mock_popup.assert_called_once()
        output = capsys.readouterr().out
        assert "[dry-run]" in output
        assert "acc***" in output

    @patch("timesheet_nag.time.sleep")
    @patch("timesheet_nag.show_nag_popup")
    @patch("timesheet_nag.fetch_approval_status", return_value="APPROVED")
    @patch("timesheet_nag.fetch_logged_hours", return_value=40.0)
    @patch("timesheet_nag.load_config", return_value=("tok", "acc"))
    def test_no_flag_still_works(
        self, _cfg: MagicMock, _hours: MagicMock, _status: MagicMock,
        mock_popup: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        timesheet_nag.main([])
        mock_popup.assert_not_called()
