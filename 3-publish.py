"""
3-publish.py: NSW Property Sales Data Publish Step

Checks the cleaned dataset, then packages it for distribution. Two jobs in one
file because they are two halves of a single decision - "is this fit to go out,
and if so, wrap it up" - and splitting them meant the gate could be skipped by
forgetting one line in a cron job or a deploy config. It cannot be skipped now.

    python 1-download.py && python 2-extract.py && python 3-publish.py

Order matters: nothing is packaged until every check has passed.

Why the checks exist:
  Every silent failure found in this project has the same shape - the pipeline
  produced *something*, so nothing complained, and the something was wrong. The
  live site served stale data for 81 days while reporting a fresh timestamp
  every morning. You cannot anticipate the specific bug; you can notice that
  today's output does not look like yesterday's.

What it checks:
  1. Row count has not dropped more than MAX_ROW_COUNT_DROP_PERCENT.
  2. No column's null rate rose by more than MAX_NULL_RATE_RISE_POINTS.
  3. No glued legal descriptions (an A1 regression canary).
  4. The newest source record is no older than MAX_DATA_AGE_DAYS.
  5. The column set has not changed unannounced.
  6. The CSV itself was written by this run, not left over from an older one.

Checks 3, 4 and 6 are absolute and run even on the very first execution. Checks
1, 2 and 5 need a baseline, which is written to BASELINE_PATH after every
successful run.

  NOTE ON DRIFT: because the baseline is rewritten on success, a slow decline
  - say 4% a day, every day - never trips the row-count check. This gate is
  built to catch a cliff, not a slope. Watching for a slope means keeping a
  fixed reference point, which is a bigger idea than this pipeline needs.

What it produces:
  1. Dated archive: `nsw-property-sales-data-updatedYYYYMMDD.zip`, containing
     the dated CSV (e.g. `nsw-property-sales-data-updated20260820.csv`).
  2. Generic archive: `archive.zip`, an exact copy, used for the permanent
     download link on nswpropertysalesdata.com.

Uses only the standard library's `zipfile` and `shutil`, so it runs the same on
Windows, Linux and macOS without any shell-specific commands.
"""

import json
import logging
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime

import pandas as pd

# --- Constants & File Paths ---
FINAL_CSV_PATH = "extract-3-very-clean.csv"
BASELINE_PATH = "validation-baseline.json"
GENERIC_ZIP_NAME = "archive.zip"
LOG_FILE_PATH = "propsales.log"

# --- Thresholds ---
# Row count is allowed to fall a little - the Valuer General does restate and
# withdraw sales - but a real drop means a truncated download or an archive that
# failed to open.
MAX_ROW_COUNT_DROP_PERCENT = 5.0

# A field silently moving position in the source layout shows up as a column
# that was mostly populated yesterday and is mostly empty today.
MAX_NULL_RATE_RISE_POINTS = 10.0

# How stale the newest source record may be. 1-download.py deliberately skips
# the most recent RECENT_WEEKS_TO_EXCLUDE (14) days and the files are weekly, so
# roughly 21 days behind is healthy. Past 35 days the weekly downloads have
# stopped - which is precisely the failure that went unnoticed for 81 days.
MAX_DATA_AGE_DAYS = 35

# A floor to catch a header-only or otherwise gutted file on a first run, when
# there is no baseline to compare against. Deliberately low: production ingests
# fewer years than a full local corpus, so this must not encode an expectation
# about how much data there should be.
MIN_PLAUSIBLE_ROWS = 1000

# How old the cleaned CSV file itself is allowed to be before we refuse to
# publish it.
#
# This is a different question from MAX_DATA_AGE_DAYS above, which asks how old
# the *records* are. This one asks whether this run actually wrote the file.
# Checking that the file merely EXISTS is not enough: if 2-extract.py fails, the
# previous run's CSV is still sitting on disk, so an existence check passes and
# we cheerfully republish it with today's date on the filename. Production did
# exactly that every morning for 81 days.
#
# The pipeline is meant to run start to finish in one cron job, so a CSV written
# by the run that just finished is minutes old. A generous ceiling still catches
# the failure without tripping on a slow run or a manual re-publish.
MAX_CSV_AGE_HOURS = 12

# Signature of the A1 corruption: two legal descriptions concatenated with no
# separator, e.g. '1/SP104291' + '71/SP104291' -> '1/SP10429171/SP104291'.
#
# A legitimate reference reads <lot>/<PLAN PREFIX><number>, so a plan reference
# followed by a slash and ANOTHER plan prefix cannot occur naturally.
#
# Chosen by measurement, not by eye. Looser candidates were tested and rejected:
# '[A-Z]{2}\d+/' fires on 5,932 legitimate rows (pre-2001 dimension text such as
# 'IRR100/CK...' and 'CP38/2'), which would have failed every single run. This
# pattern fires on ZERO of the 7,009,235 clean descriptions.
#
# It catches ~4% of any individual glued row, which is enough: at that rate a
# 100-row regression is caught with 98% probability and a 1,000-row regression
# with certainty. A1 affected 15,081 rows.
GLUED_DESCRIPTION_PATTERN = r'(?:DP|SP|CP)\d+/(?:DP|SP|CP)'

# Columns the checks read by name. Kept here so a schema rename fails loudly at
# the top rather than halfway through.
DESCRIPTION_COLUMN = "Property legal description"
DOWNLOAD_COLUMN = "Download date / time"

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)


# =========================================================================
#  Part 1: checking the dataset
# =========================================================================

def check_csv_freshness(csv_path: str) -> list:
    """
    Confirms the CSV was written by the run that just finished.

    Deliberately runs before anything reads the file, because reading 1.7 GB
    takes half a minute and there is no point spending it on a file we already
    know is stale.

    Args:
        csv_path (str): Path to the cleaned CSV.

    Returns:
        list: Human-readable failure messages; empty means everything passed.
    """
    age_hours = (time.time() - os.path.getmtime(csv_path)) / 3600
    if age_hours > MAX_CSV_AGE_HOURS:
        return [
            f"{csv_path} was last written {age_hours:.1f} hours ago, which is "
            f"older than MAX_CSV_AGE_HOURS ({MAX_CSV_AGE_HOURS}). This usually "
            f"means 2-extract.py did not run or did not finish, and publishing "
            f"now would stamp today's date on stale data."
        ]

    logging.info(f"Source CSV is {age_hours:.1f} hours old - written by this run.")
    return []


def collect_metrics(csv_path: str) -> dict:
    """
    Reads the cleaned CSV and summarises it into the handful of numbers the
    checks below care about.

    Everything is read as text. We are measuring shape - how many rows, how
    many blanks, does anything look glued - and letting pandas infer types
    would only invite it to guess differently between runs.

    Args:
        csv_path (str): Path to the cleaned CSV.

    Returns:
        dict: Metrics, safe to serialise straight to JSON.
    """
    logging.info(f"Reading {csv_path} to collect metrics.")
    df = pd.read_csv(csv_path, dtype=str, na_values=[''], low_memory=False)

    row_count = len(df)
    null_rates = {
        column: round(df[column].isna().sum() / row_count * 100, 4)
        for column in df.columns
    } if row_count else {}

    glued = 0
    if DESCRIPTION_COLUMN in df.columns and row_count:
        glued = int(df[DESCRIPTION_COLUMN].str.contains(
            GLUED_DESCRIPTION_PATTERN, regex=True, na=False).sum())

    newest_download = None
    if DOWNLOAD_COLUMN in df.columns and row_count:
        # 2-extract.py writes this as an ISO timestamp, but parse permissively
        # so this gate still works if handed an older CSV.
        downloads = pd.to_datetime(df[DOWNLOAD_COLUMN], errors='coerce',
                                   format='mixed')
        if downloads.notna().any():
            newest_download = downloads.max().strftime('%Y-%m-%d')

    return {
        "generated": datetime.now().strftime('%Y-%m-%d %H:%M'),
        "row_count": row_count,
        "columns": list(df.columns),
        "null_rates": null_rates,
        "glued_descriptions": glued,
        "newest_download": newest_download,
    }


def check_absolute(metrics: dict) -> list:
    """
    The checks that need no baseline, so they also protect the very first run.

    Args:
        metrics (dict): Output of collect_metrics().

    Returns:
        list: Human-readable failure messages; empty means everything passed.
    """
    failures = []

    if metrics["row_count"] < MIN_PLAUSIBLE_ROWS:
        failures.append(
            f"Only {metrics['row_count']:,} rows, below the floor of "
            f"{MIN_PLAUSIBLE_ROWS:,}. The file is effectively empty."
        )

    if metrics["glued_descriptions"]:
        failures.append(
            f"{metrics['glued_descriptions']:,} legal descriptions look like two "
            f"records glued together. This is the A1 corruption returning - "
            f"check that the 'C' record join is still scoped to one source file."
        )

    newest = metrics["newest_download"]
    if newest is None:
        failures.append(
            f"No usable '{DOWNLOAD_COLUMN}' values, so the age of the data "
            f"cannot be established."
        )
    else:
        age_days = (datetime.now() - datetime.strptime(newest, '%Y-%m-%d')).days
        if age_days > MAX_DATA_AGE_DAYS:
            failures.append(
                f"The newest source record is dated {newest}, {age_days} days "
                f"ago, over the {MAX_DATA_AGE_DAYS}-day limit. Weekly downloads "
                f"have most likely stopped - publishing now would serve stale "
                f"data with a fresh timestamp."
            )

    return failures


def check_against_baseline(metrics: dict, baseline: dict) -> list:
    """
    The checks that compare this run against the previous successful one.

    Args:
        metrics (dict): This run.
        baseline (dict): The previous successful run.

    Returns:
        list: Human-readable failure messages; empty means everything passed.
    """
    failures = []

    previous_rows = baseline.get("row_count", 0)
    if previous_rows:
        drop_percent = (previous_rows - metrics["row_count"]) / previous_rows * 100
        if drop_percent > MAX_ROW_COUNT_DROP_PERCENT:
            failures.append(
                f"Row count fell {drop_percent:.1f}% "
                f"({previous_rows:,} -> {metrics['row_count']:,}), more than the "
                f"{MAX_ROW_COUNT_DROP_PERCENT}% allowed."
            )

    if baseline.get("columns") and baseline["columns"] != metrics["columns"]:
        added = [c for c in metrics["columns"] if c not in baseline["columns"]]
        removed = [c for c in baseline["columns"] if c not in metrics["columns"]]
        failures.append(
            f"The column set changed - added {added or 'none'}, removed "
            f"{removed or 'none'}. If this was intended, delete "
            f"{BASELINE_PATH} to accept the new schema."
        )

    for column, previous_rate in baseline.get("null_rates", {}).items():
        if column not in metrics["null_rates"]:
            continue
        rise = metrics["null_rates"][column] - previous_rate
        if rise > MAX_NULL_RATE_RISE_POINTS:
            failures.append(
                f"'{column}' is {rise:.1f} percentage points emptier than last "
                f"run ({previous_rate:.1f}% -> {metrics['null_rates'][column]:.1f}% "
                f"null). A field may have moved position in the source layout."
            )

    return failures


def load_baseline(path: str) -> dict:
    """Returns the previous run's metrics, or an empty dict if there is none."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError) as error:
        # A corrupt baseline must not block publishing - treat it as absent and
        # say so, rather than failing a run that may be perfectly good.
        logging.warning(f"Could not read {path} ({error}); treating as a first run.")
        return {}


def save_baseline(metrics: dict, path: str) -> None:
    """Writes this run's metrics for the next run to compare against."""
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(metrics, handle, indent=2)
    logging.info(f"Baseline written to {path}.")


# =========================================================================
#  Part 2: packaging the dataset
# =========================================================================

def create_archives(
    source_csv: str = FINAL_CSV_PATH,
    generic_zip_name: str = GENERIC_ZIP_NAME
) -> None:
    """
    Compresses the cleaned CSV into a dated zip archive and creates the
    canonical archive.zip copy.

    Called by main() only after every check has passed. If you call it
    directly you are skipping the gate, so it repeats the two cheap safety
    checks - the file exists, and this run wrote it - rather than trusting the
    caller to have done them.

    Args:
        source_csv (str): Filename of the cleaned CSV source.
        generic_zip_name (str): Filename for the generic web distribution copy.
    """
    logging.info('Creating zip archive')
    start_time = time.time()

    if not os.path.exists(source_csv):
        # Exit non-zero, don't just return. A bare `return` reports success to
        # the shell, so a cron chained with `&&` treats "there was nothing to
        # publish" as "publishing worked".
        logging.error(f"Source file not found: {source_csv}. Cannot create archives.")
        sys.exit(1)

    stale = check_csv_freshness(source_csv)
    if stale:
        for failure in stale:
            logging.error(failure)
        logging.error("Refusing to publish.")
        sys.exit(1)

    today_str = datetime.now().strftime('%Y%m%d')
    dated_base_name = f"nsw-property-sales-data-updated{today_str}"
    dated_zip_name = f"{dated_base_name}.zip"
    internal_csv_name = f"{dated_base_name}.csv"

    # Create dated zip archive directly using arcname mapping
    logging.info(f"Writing compressed archive: {dated_zip_name} containing {internal_csv_name}")
    with zipfile.ZipFile(dated_zip_name, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(source_csv, arcname=internal_csv_name)

    # Create cross-platform canonical copy for generic web links
    logging.info(f"Copying {dated_zip_name} to {generic_zip_name}")
    shutil.copyfile(dated_zip_name, generic_zip_name)

    elapsed_seconds = int(time.time() - start_time)
    logging.info(f"Complete: zip archive has been created.")
    logging.info(f"Total elapsed time was {elapsed_seconds} seconds")


# =========================================================================
#  Entry point
# =========================================================================

def main() -> None:
    """
    Checks FINAL_CSV_PATH, and packages it only if everything passes.
    Exits non-zero if it should not be published.
    """
    start_time = time.time()
    logging.info("Start: checking the cleaned dataset before publishing.")

    if not os.path.exists(FINAL_CSV_PATH):
        logging.error(f"{FINAL_CSV_PATH} does not exist. Did 2-extract.py run?")
        sys.exit(1)

    # Cheapest check first, before reading a very large file.
    failures = check_csv_freshness(FINAL_CSV_PATH)

    if not failures:
        metrics = collect_metrics(FINAL_CSV_PATH)
        baseline = load_baseline(BASELINE_PATH)

        logging.info(
            f"{metrics['row_count']:,} rows, {len(metrics['columns'])} columns, "
            f"newest source record {metrics['newest_download']}."
        )

        failures = check_absolute(metrics)
        if baseline:
            failures.extend(check_against_baseline(metrics, baseline))
        else:
            logging.info(
                f"No {BASELINE_PATH} found, so this run establishes the baseline. "
                f"Only the absolute checks applied."
            )

    if failures:
        logging.error(f"Checks FAILED with {len(failures)} problem(s):")
        for failure in failures:
            logging.error(f"  - {failure}")
        logging.error("Refusing to publish. No archive will be written.")
        sys.exit(1)

    save_baseline(metrics, BASELINE_PATH)
    logging.info("Checks passed; the dataset is safe to publish.")

    create_archives(FINAL_CSV_PATH, GENERIC_ZIP_NAME)
    logging.info(f"Total elapsed time was {int(time.time() - start_time)} seconds.")


if __name__ == "__main__":
    main()
