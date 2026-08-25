import email.message
import logging
import os

import pytest
from datetime import date, timedelta
from unittest.mock import patch
from urllib.error import HTTPError


@pytest.fixture
def download_dir(download_mod, tmp_path, monkeypatch):
    """
    Points the download script at an empty temporary folder and removes the
    polite pause between files, so tests are isolated and fast.
    """
    monkeypatch.setattr(download_mod, 'DOWNLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(download_mod, 'PAUSE_BETWEEN_FILES', 0)
    monkeypatch.setattr(download_mod, 'FORCE_REDOWNLOAD', False)
    return tmp_path


# --- URL construction -------------------------------------------------------

def test_download_yearly_data_urls(download_mod, download_dir):
    downloaded_urls = []

    def fake_download_file(url, filepath):
        downloaded_urls.append((url, filepath))
        return True

    with patch.object(download_mod, 'download_file', side_effect=fake_download_file):
        download_mod.download_yearly_data(2020, 2024)

    assert len(downloaded_urls) == 4
    assert downloaded_urls[0][0] == "https://www.valuergeneral.nsw.gov.au/__psi/yearly/2020.zip"
    assert downloaded_urls[3][0] == "https://www.valuergeneral.nsw.gov.au/__psi/yearly/2023.zip"


def test_download_weekly_data_urls(download_mod, download_dir):
    downloaded_urls = []

    def fake_download_file(url, filepath):
        downloaded_urls.append((url, filepath))
        return True

    start_date = date(2024, 1, 1)
    # End date + 28 days -> after excluding RECENT_WEEKS_TO_EXCLUDE (14 days), should download 2 weeks (day 0 and day 7)
    end_date = start_date + timedelta(days=28)

    with patch.object(download_mod, 'download_file', side_effect=fake_download_file):
        download_mod.download_weekly_data(start_date, end_date)

    assert len(downloaded_urls) == 2
    assert downloaded_urls[0][0] == "https://www.valuergeneral.nsw.gov.au/__psi/weekly/20240101.zip"
    assert downloaded_urls[1][0] == "https://www.valuergeneral.nsw.gov.au/__psi/weekly/20240108.zip"


def test_yearly_download_starts_at_1990(download_mod, download_dir):
    """The earliest year must be fetched, not skipped by an off-by-one."""
    downloaded_urls = []

    def fake_download_file(url, filepath):
        downloaded_urls.append(url)
        return True

    with patch.object(download_mod, 'download_file', side_effect=fake_download_file):
        download_mod.download_yearly_data(download_mod.EARLIEST_YEAR, 2026)

    assert downloaded_urls[0] == "https://www.valuergeneral.nsw.gov.au/__psi/yearly/1990.zip"
    assert len(downloaded_urls) == 2026 - 1990


def test_earliest_year_matches_extract_earliest_date(download_mod, extract_mod):
    """
    1-download.py decides how far back to FETCH; 2-extract.py decides which dates
    are junk. They are separate controls but must refer to the same year.
    """
    earliest_date_year = int(extract_mod.EARLIEST_DATE.split('-')[0])
    assert download_mod.EARLIEST_YEAR == earliest_date_year


# --- Caching ----------------------------------------------------------------

def test_existing_yearly_file_is_skipped(download_mod, download_dir):
    (download_dir / "2020.zip").write_bytes(b"already here")

    downloaded_urls = []

    def fake_download_file(url, filepath):
        downloaded_urls.append(url)
        return True

    with patch.object(download_mod, 'download_file', side_effect=fake_download_file):
        download_mod.download_yearly_data(2020, 2023)

    assert len(downloaded_urls) == 2
    assert all("2020.zip" not in url for url in downloaded_urls)
    # And the cached file was left alone
    assert (download_dir / "2020.zip").read_bytes() == b"already here"


def test_existing_weekly_file_is_skipped(download_mod, download_dir):
    (download_dir / "20240101.zip").write_bytes(b"already here")

    downloaded_urls = []

    def fake_download_file(url, filepath):
        downloaded_urls.append(url)
        return True

    start_date = date(2024, 1, 1)
    with patch.object(download_mod, 'download_file', side_effect=fake_download_file):
        download_mod.download_weekly_data(start_date, start_date + timedelta(days=28))

    assert downloaded_urls == ["https://www.valuergeneral.nsw.gov.au/__psi/weekly/20240108.zip"]


def test_force_redownload_ignores_the_cache(download_mod, download_dir, monkeypatch):
    (download_dir / "2020.zip").write_bytes(b"already here")
    monkeypatch.setattr(download_mod, 'FORCE_REDOWNLOAD', True)

    downloaded_urls = []

    def fake_download_file(url, filepath):
        downloaded_urls.append(url)
        return True

    with patch.object(download_mod, 'download_file', side_effect=fake_download_file):
        download_mod.download_yearly_data(2020, 2021)

    assert len(downloaded_urls) == 1


# --- Failure reporting ------------------------------------------------------

def test_failed_downloads_are_returned(download_mod, download_dir):
    def fake_download_file(url, filepath):
        return "2021.zip" not in url  # 2021 fails, others succeed

    with patch.object(download_mod, 'download_file', side_effect=fake_download_file):
        failures = download_mod.download_yearly_data(2020, 2023)

    assert failures == ["2021.zip"]


def test_main_exits_non_zero_when_a_yearly_file_fails(download_mod, download_dir):
    with patch.object(download_mod, 'download_weekly_data', return_value=([], 10)), \
         patch.object(download_mod, 'download_yearly_data', return_value=["1995.zip"]):
        with pytest.raises(SystemExit) as excinfo:
            download_mod.main()

    assert excinfo.value.code != 0


def test_main_tolerates_some_weekly_failures(download_mod, download_dir):
    """Recent weekly files may not be published yet - that must not fail the run."""
    with patch.object(download_mod, 'download_weekly_data', return_value=(["20260810.zip"], 10)), \
         patch.object(download_mod, 'download_yearly_data', return_value=[]):
        download_mod.main()  # must not raise SystemExit


def test_main_exits_non_zero_when_every_weekly_download_fails(download_mod, download_dir):
    """
    A handful of weekly failures is normal; all of them failing is a broken
    connection, and publishing would drop the whole current year.
    """
    all_failed = ([f"2026010{n}.zip" for n in range(1, 6)], 5)
    with patch.object(download_mod, 'download_weekly_data', return_value=all_failed), \
         patch.object(download_mod, 'download_yearly_data', return_value=[]):
        with pytest.raises(SystemExit) as excinfo:
            download_mod.main()

    assert excinfo.value.code != 0


def test_main_succeeds_when_everything_is_cached(download_mod, download_dir):
    """Nothing attempted, nothing failed - a normal no-op day must not error."""
    with patch.object(download_mod, 'download_weekly_data', return_value=([], 0)), \
         patch.object(download_mod, 'download_yearly_data', return_value=[]):
        download_mod.main()  # must not raise SystemExit


def test_weekly_download_reports_attempt_count(download_mod, download_dir):
    """Cached files must not be counted as attempts, or the all-failed check misfires."""
    (download_dir / "20240101.zip").write_bytes(b"cached")

    with patch.object(download_mod, 'download_file', return_value=True):
        failures, attempted = download_mod.download_weekly_data(
            date(2024, 1, 1), date(2024, 1, 1) + timedelta(days=28))

    assert failures == []
    assert attempted == 1  # 20240108 only; 20240101 was cached


# --- Download mechanics -----------------------------------------------------

def _http_error(code, content_type):
    headers = email.message.Message()
    headers['Content-Type'] = content_type
    headers['Cf-Mitigated'] = 'challenge'
    return HTTPError('http://example.test/x.zip', code, 'Forbidden', headers, None)


def test_cloudflare_block_is_reported_as_such(download_mod, download_dir, caplog):
    """A 403 with an HTML body is bot protection, not a missing file."""
    monkey_target = 'urllib.request.urlopen'
    with patch(monkey_target, side_effect=_http_error(403, 'text/html; charset=UTF-8')), \
         patch.object(download_mod, 'RETRY_ATTEMPTS', 1), \
         caplog.at_level(logging.ERROR):
        result = download_mod.download_file('http://example.test/x.zip',
                                            str(download_dir / "x.zip"))

    assert result is False
    assert "bot protection" in caplog.text


def test_ordinary_http_error_is_not_mislabelled(download_mod, download_dir, caplog):
    with patch('urllib.request.urlopen', side_effect=_http_error(404, 'text/plain')), \
         patch.object(download_mod, 'RETRY_ATTEMPTS', 1), \
         caplog.at_level(logging.ERROR):
        result = download_mod.download_file('http://example.test/x.zip',
                                            str(download_dir / "x.zip"))

    assert result is False
    assert "bot protection" not in caplog.text


def test_interrupted_download_leaves_no_partial_zip(download_mod, download_dir):
    """
    A failed transfer must not leave a truncated .zip that 2-extract.py would
    treat as a real file.
    """
    class FailingResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, *args):
            raise ConnectionResetError("connection dropped mid-transfer")

    target = str(download_dir / "2020.zip")
    with patch('urllib.request.urlopen', return_value=FailingResponse()), \
         patch.object(download_mod, 'RETRY_ATTEMPTS', 1):
        result = download_mod.download_file('http://example.test/2020.zip', target)

    assert result is False
    assert not os.path.exists(target), "a partial download must not land at the final path"


def test_successful_download_writes_the_file(download_mod, download_dir):
    class OkResponse:
        def __init__(self):
            self._data = [b"PK\x03\x04payload"]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            return self._data.pop(0) if self._data else b""

    target = str(download_dir / "2020.zip")
    with patch('urllib.request.urlopen', return_value=OkResponse()):
        result = download_mod.download_file('http://example.test/2020.zip', target)

    assert result is True
    assert open(target, 'rb').read() == b"PK\x03\x04payload"
    assert not os.path.exists(target + '.part')


# --- Manual download fallback -----------------------------------------------

def test_non_zip_response_is_rejected(download_mod, download_dir):
    """A 200 response containing an error page must not land in data/ as a .zip."""
    class HtmlResponse:
        def __init__(self):
            self._data = [b"<!doctype html><html>Just a moment...</html>"]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            return self._data.pop(0) if self._data else b""

    target = str(download_dir / "2020.zip")
    with patch('urllib.request.urlopen', return_value=HtmlResponse()), \
         patch.object(download_mod, 'RETRY_ATTEMPTS', 1):
        result = download_mod.download_file('http://example.test/2020.zip', target)

    assert result is False
    assert not os.path.exists(target)
    assert not os.path.exists(target + '.part')


def test_manual_download_page_lists_missing_files(download_mod, tmp_path):
    page = tmp_path / "manual.html"
    download_mod.write_manual_download_page(
        ["https://example.test/yearly/1990.zip",
         "https://example.test/yearly/1991.zip"],
        output_path=str(page),
    )

    html = page.read_text(encoding="utf-8")
    assert "1990.zip" in html and "1991.zip" in html
    assert 'href="https://example.test/yearly/1990.zip"' in html
    assert "2 file(s) still needed" in html


def test_failed_run_writes_the_manual_download_page(download_mod, download_dir, tmp_path, monkeypatch):
    page = tmp_path / "manual.html"
    monkeypatch.setattr(download_mod, 'MANUAL_PAGE_PATH', str(page))

    with patch.object(download_mod, 'download_weekly_data', return_value=([], 0)), \
         patch.object(download_mod, 'download_yearly_data', return_value=["1995.zip"]):
        with pytest.raises(SystemExit):
            download_mod.main()

    assert page.exists()
    assert "1995.zip" in page.read_text(encoding="utf-8")
