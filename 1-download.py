"""
1-download.py: NSW Property Sales Data Download Pipeline

This module automates the fetching of bulk Property Sales Information (PSI)
from the official NSW Valuer General portal (https://www.valuergeneral.nsw.gov.au/__psi/).

The download process retrieves:
  1. Weekly Delta Files: Semicolon-delimited .zip files for the current calendar year,
     skipping the most recent 14 days to allow for publication settlement windows.
  2. Yearly Archive Files: Complete annual historical archives from EARLIEST_YEAR (1990)
     through current_year - 1.

All downloaded archives are placed into the local './data/' directory for subsequent
extraction by `2-extract.py`.

Files already in './data/' are skipped rather than downloaded again - see the
FORCE_REDOWNLOAD constant below if you want a clean re-fetch.

If any yearly archive fails to download, this script exits with a non-zero status
so the rest of the pipeline does not run and publish an incomplete dataset.

Official Source Reference:
  - NSW Valuer General Bulk PSI: https://valuation.property.nsw.gov.au/embed/propertySalesInformation
  - Licensing: Creative Commons Attribution, per the creative_commons.txt file
    bundled in every archive. Note that file is an Australian port (its
    governing-law clause names the ACT) and does not state a version number
    in its body, so no specific version is claimed here. It carries no
    NonCommercial, NoDerivatives or ShareAlike terms.
"""

import time
import os
import shutil
import sys
import urllib.request
from urllib.error import URLError, HTTPError
from datetime import date, timedelta
import logging

# --- Constants & Configuration ---
URL_BASE = 'https://www.valuergeneral.nsw.gov.au/__psi/'
WEEKLY_URL = URL_BASE + 'weekly/'
YEARLY_URL = URL_BASE + 'yearly/'
DOWNLOAD_DIR = 'data/'

# The first year the Valuer General published sales data. This controls how far
# back we FETCH files. It should match EARLIEST_DATE in 2-extract.py, which is a
# separate control deciding which contract/settlement DATES are treated as junk.
EARLIEST_YEAR = 1990

RECENT_WEEKS_TO_EXCLUDE = 14  # Number of days to exclude from recent weekly downloads
RETRY_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 5   # Wait between retry attempts
PAUSE_BETWEEN_FILES = 1  # Small pause so we don't hammer the server
DOWNLOAD_TIMEOUT = 60    # Give up on a stalled connection instead of hanging forever

# Nothing in DOWNLOAD_DIR is ever deleted. Last year's weekly files are
# superseded by that year's annual archive, so a cleanup would be tidy - but the
# source is behind a Cloudflare bot challenge and anything removed cannot
# currently be re-fetched. A superseded file on disk is worth more than the disk
# space it costs. Revisit if the block is ever lifted.
#
# Files already in DOWNLOAD_DIR are kept and not downloaded again. The Valuer
# General's yearly archives don't change once published, so re-fetching 35 of
# them every day is wasted effort. Set this to True to force a clean re-fetch
# of everything (e.g. if you suspect a file was revised upstream).
FORCE_REDOWNLOAD = False

# When downloads are blocked, we write a page of links here so the missing files
# can be fetched in a browser instead. See write_manual_download_page().
MANUAL_PAGE_PATH = 'manual-download.html'

# Configure logging to file and standard console output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("propsales.log"),
        logging.StreamHandler()
    ]
)


def download_file(url: str, filepath: str) -> bool:
    """
    Downloads a single file from a given URL to a local destination filepath
    retrying up to RETRY_ATTEMPTS times with a fixed wait between attempts.

    Args:
        url (str): The complete URL of the remote archive to download.
        filepath (str): The local destination file path where the archive will be saved.

    Returns:
        bool: True if the file was downloaded successfully, False otherwise.
    """
    for attempt in range(RETRY_ATTEMPTS):
        try:
            logging.info(f'Downloading {url} to {filepath} (attempt {attempt + 1})')

            # Download to a temporary ".part" file first, then rename it into place.
            # If the download is interrupted we're left with a .part file rather than
            # a half-written .zip that 2-extract.py would silently read as valid.
            temp_filepath = filepath + '.part'
            with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:
                with open(temp_filepath, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)

            # Every real file here is a zip, which always starts with "PK".
            # If we got something else the server sent us an error page with a
            # 200 status, and we must not let it land in data/ looking valid.
            if not is_zip_file(temp_filepath):
                os.remove(temp_filepath)
                logging.error(f'{url} did not return a zip file (got something else)')
                return False

            os.replace(temp_filepath, filepath)

            logging.info(f'Successfully downloaded {url} to {filepath}')
            return True
        except HTTPError as e:
            # A 403 with an HTML body means Cloudflare's bot protection blocked us,
            # not that the file is missing. Say so plainly - a bare "403 Forbidden"
            # sends you looking for the wrong problem.
            content_type = e.headers.get('Content-Type', '') if e.headers else ''
            if e.code == 403 and 'text/html' in content_type:
                logging.error(
                    f'Blocked by bot protection downloading {url} '
                    f'(HTTP 403, Cf-Mitigated: {e.headers.get("Cf-Mitigated")}). '
                    f'This is not a missing file - the server refused an automated request.'
                )
            else:
                logging.error(f'Error downloading {url} (attempt {attempt + 1}): {e}')
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_WAIT_SECONDS)
            else:
                return False
        except URLError as e:
            logging.error(f'Error downloading {url} (attempt {attempt + 1}): {e}')
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_WAIT_SECONDS)
            else:
                return False
        except Exception as e:
            logging.error(f'An unexpected error occurred during download {url}: {e}')
            return False
    return False


def is_zip_file(filepath: str) -> bool:
    """Returns True if the file starts with the standard zip signature ('PK')."""
    try:
        with open(filepath, 'rb') as f:
            return f.read(2) == b'PK'
    except OSError:
        return False


def write_manual_download_page(missing_urls: list, output_path: str) -> None:
    """
    Writes a small HTML page of download links for files this script could not fetch.

    The Valuer General's site sits behind bot protection that blocks automated
    requests but lets ordinary browser traffic through. Opening this page and
    clicking the links downloads the files the normal way - as a person using
    the website. Save them into ./data/ and re-run this script; anything already
    there will be skipped.
    """
    links = '\n'.join(
        f'    <li><a href="{url}" download>{os.path.basename(url)}</a></li>'
        for url in missing_urls
    )
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Missing property sales files</title></head>
<body style="font-family: sans-serif; max-width: 42em; margin: 2em auto; line-height: 1.5;
             background: #fff; color: #111;">
  <h1>{len(missing_urls)} file(s) still needed</h1>
  <p>The download script was blocked by the Valuer General's bot protection, which
     allows normal browser traffic but refuses automated requests. Downloading them
     here uses the site the intended way.</p>
  <ol>
    <li>Point your browser's download folder at this project's <code>data/</code>
        folder (Chrome: Settings &rarr; Downloads &rarr; Location).</li>
    <li>Click <b>Download all</b> and allow multiple downloads when prompted.</li>
    <li>Run <code>1-download.py</code> again. Files already in <code>data/</code>
        are skipped, so nothing is fetched twice.</li>
  </ol>
  <p><button id="all" style="font-size:1.1em; padding:.6em 1.2em;">Download all</button>
     <span id="progress"></span></p>
  <script>
    // Clicks each link in turn, with a pause so the browser doesn't drop any.
    document.getElementById('all').onclick = async function () {{
      const links = [...document.querySelectorAll('#files a')];
      for (let i = 0; i < links.length; i++) {{
        links[i].click();
        document.getElementById('progress').textContent =
          ` starting ${{i + 1}} of ${{links.length}}...`;
        await new Promise(r => setTimeout(r, 1500));
      }}
      document.getElementById('progress').textContent =
        ' all started - check your downloads finished, then re-run the script.';
    }};
  </script>
  <ol id="files">
{links}
  </ol>
</body></html>
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    logging.info(f'Wrote {output_path} listing {len(missing_urls)} file(s) to fetch manually.')
    logging.info(f'Open it in your browser, download the files into {DOWNLOAD_DIR}, then re-run.')


def summarise(filenames: list, limit: int = 5) -> str:
    """Joins filenames for a log message, trimming very long lists."""
    if len(filenames) <= limit:
        return ', '.join(filenames)
    return f'{", ".join(filenames[:limit])} ... and {len(filenames) - limit} more'


def already_downloaded(filepath: str) -> bool:
    """
    Returns True if we already have this file and should skip downloading it.

    Because download_file() only moves a file into place once it has fully
    downloaded, a file existing here always means a complete file.
    """
    if FORCE_REDOWNLOAD:
        return False
    return os.path.exists(filepath)


def download_weekly_data(start_date: date, end_date: date) -> list:
    """
    Downloads all available weekly zip files within the specified date range.

    Weekly files on the NSW Valuer General server follow the naming convention:
    'YYYYMMDD.zip' where the date represents the Monday of that reporting week.

    Files already present in DOWNLOAD_DIR are skipped (see FORCE_REDOWNLOAD).

    Args:
        start_date (date): Starting date (typically the first Monday of the current year).
        end_date (date): End date cutoff (typically today minus RECENT_WEEKS_TO_EXCLUDE).

    Returns:
        tuple: (list of filenames that failed, number of files we actually tried)
    """
    failures = []
    attempted = 0
    end_date = end_date - timedelta(days=RECENT_WEEKS_TO_EXCLUDE)
    current_date = start_date
    while current_date < end_date:
        filename = current_date.strftime('%Y%m%d') + '.zip'
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        if already_downloaded(filepath):
            logging.info(f'Already have {filename}, skipping')
        else:
            attempted += 1
            if not download_file(WEEKLY_URL + filename, filepath):
                failures.append(filename)
            time.sleep(PAUSE_BETWEEN_FILES)

        current_date += timedelta(days=7)
    return failures, attempted


def download_yearly_data(start_year: int, end_year: int) -> list:
    """
    Downloads all historical annual archive zip files for the specified year range.

    Yearly archive files on the NSW Valuer General server follow the naming convention:
    'YYYY.zip' (e.g., '1990.zip', '2023.zip').

    Files already present in DOWNLOAD_DIR are skipped (see FORCE_REDOWNLOAD).

    Args:
        start_year (int): The starting year (inclusive, e.g. EARLIEST_YEAR).
        end_year (int): The ending year (exclusive, typically current_year).

    Returns:
        list: Filenames that failed to download.
    """
    failures = []
    for year in range(start_year, end_year):
        filename = f"{year}.zip"
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        if already_downloaded(filepath):
            logging.info(f'Already have {filename}, skipping')
            continue

        if not download_file(YEARLY_URL + filename, filepath):
            failures.append(filename)
        time.sleep(PAUSE_BETWEEN_FILES)
    return failures


def main() -> None:
    """
    Main orchestration function to initialize download directories and trigger
    both weekly delta downloads and annual historical archive fetches.

    Exits with a non-zero status if any yearly archive could not be downloaded,
    so that a failed run stops the pipeline instead of letting 2-extract.py build
    an incomplete CSV that 3-publish.py would then publish over a good one.
    """
    logging.info('Start downloading the data')
    start_time = time.time()

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        logging.info(f"Created directory: {DOWNLOAD_DIR}")

    today = date.today()
    # Calculate the first Monday of the current calendar year
    first_week_date = date(today.year, 1, 7)
    start_weekly_date = first_week_date - timedelta(days=first_week_date.weekday())
    end_weekly_date = today

    # Fetch weekly delta files for current year
    weekly_failures, weekly_attempted = download_weekly_data(start_weekly_date, end_weekly_date)

    # Fetch annual archive files from EARLIEST_YEAR up to (not including) this year
    yearly_failures = download_yearly_data(EARLIEST_YEAR, today.year)

    # A few weekly files failing is normal - the most recent ones may not be
    # published yet. But if EVERY weekly download failed, the connection or the
    # server is the problem and we'd be publishing a dataset with no current year.
    all_weeklies_failed = weekly_attempted > 0 and len(weekly_failures) == weekly_attempted

    if weekly_failures and not all_weeklies_failed:
        logging.warning(
            f'{len(weekly_failures)} of {weekly_attempted} weekly file(s) could not be '
            f'downloaded (normal for very recent weeks): {summarise(weekly_failures)}'
        )

    if all_weeklies_failed or yearly_failures:
        if all_weeklies_failed:
            logging.error(
                f'FAILED: all {weekly_attempted} weekly download(s) failed. '
                f'This is a connection or server problem, not missing files.'
            )
        if yearly_failures:
            logging.error(
                f'FAILED: {len(yearly_failures)} yearly archive(s) could not be downloaded: '
                f'{summarise(yearly_failures)}'
            )

        # Give the user a way forward rather than just a dead end.
        write_manual_download_page(
            [WEEKLY_URL + name for name in weekly_failures] +
            [YEARLY_URL + name for name in yearly_failures],
            MANUAL_PAGE_PATH
        )
        logging.error('Stopping so an incomplete dataset is not published.')
        sys.exit(1)

    logging.info('Complete: the data has been downloaded.')
    logging.info(f'Total elapsed time was {int(time.time() - start_time)} seconds')


if __name__ == "__main__":
    main()