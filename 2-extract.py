"""
2-extract.py: NSW Property Sales Data Extraction & Transformation Pipeline

This module processes raw NSW Valuer General Property Sales Information (PSI)
archives located in `./data/`, performing extraction, schema normalization,
data cleaning, deduplication, and final export to `extract-3-very-clean.csv`.

Key Pipeline Stages:
  1. In-Memory Nested Zip Extraction:
     Extracts .dat lines from top-level and nested zip archives without saving
     millions of uncompressed text files to disk.
  2. Dual-Schema Classification & Parsing:
     - Post-2001 Schema: Parses 'B' (Property/Sale) and 'C' (Legal Description) records.
       Legal descriptions spanning multiple 'C' records are concatenated without spaces
       per Valuer General specifications.
     - Pre-2001 Schema: Parses historical 'B' records (22 fields, source tags
       'ARCHIVE'/'VALNET1') and converts DD/MM/YYYY dates to ISO CCYYMMDD format.
       The two layouts are told apart by field count, not by inspecting field 2.
  3. Data Sanitization & Cleaning:
     - Date Coercion: Validates contract and settlement dates; nullifies future dates
       and pre-1990 dates to protect data integrity against entry typos.
     - Metric Normalization: Converts land measurements in Hectares ('H') to square
       metres via `Area * 10000`, keeping the raw figure in 'Area (source)' so the
       type code always describes the number beside it.
     - Whole-number columns use the nullable 'Int64' type, so a price is written
       670000 rather than 670000.0.
     - Text Standardization: Normalizes government all-caps strings via
       fix_title_case(), which repairs what `.str.title()` gets wrong.
     - Deduplication: Removes overlapping sales across annual and weekly batches.
       Records that carry a dealing number are keyed on (Property ID, Dealing
       number and legal description, see MODERN_DEDUP_KEY); pre-2001 records,
       which have no dealing number, fall back to ARCHIVED_DEDUP_KEY.
  4. Derived columns (schema v2):
     - Plain-English companions for the two coded columns ('Nature of property',
       'Primary purpose'). The raw values are always kept alongside them.
     - Three quality flags marking rows that are not ordinary market sales.
       These FLAG rows; they never remove them.
  5. Consolidated CSV Export:
     Exports 33 standardized, fully-quoted columns to `extract-3-very-clean.csv`.

Official Specifications Reference:
  - Current Property Sales Data File Format (2001 - Current): Record Types A, B, C, D, Z
  - Archived Property Sales Data File Format (1990 - 2001): Record Types A, B, Z
  - Property Sales Data File Data Elements (Fact Sheet May 2020)
"""

import logging
import os
import io
import sys
import zipfile
import csv
from typing import List, Dict, Any, Optional
import pandas as pd
import time
from datetime import datetime

# --- Constants & File Paths ---
DATA_DIR = "./data"
FINAL_CSV_PATH = "extract-3-very-clean.csv"
LOG_FILE_PATH = "propsales.log"

# How many semicolon-separated fields each record layout needs. Verified against
# the real archives: 1990-2000 files carry 22 fields, 2001-onwards carry 25.
# The archived threshold is the minimum needed to read every field we map (the
# zone code sits at index 17), so a slightly shorter line is still usable.
CURRENT_FORMAT_FIELDS = 25
ARCHIVED_FORMAT_MIN_FIELDS = 18

# Deduplication key for pre-2001 records, which have no dealing number to
# identify a sale by. The address fields are essential: roughly a third of
# archived records have no Property Id at all. See clean_dataframe().
ARCHIVED_DEDUP_KEY = [
    'Property ID', 'Contract date', 'Purchase price',
    'Property street name', 'Property house number',
    'Property legal description', 'Property locality', 'Area',
]

# Post-2001 records. The legal description is in the key because one dealing
# routinely covers several parcels, and each parcel is its own row.
#
# Measured on 2019-2026 (1,605,876 raw rows), a (Property ID, Dealing number)
# key destroyed 22,978 real records. Example: property 3200869, dealing
# AN975735 covers strata lots 5/SP75684 AND 6/SP75684 - two different units in
# one building, sold together. Keyed without the legal description, unit 6
# silently disappears.
#
# Two patterns share the shape "one dealing, several rows", and the key has to
# tell them apart:
#
#   1. Different parcels - different legal descriptions. 14,603 groups. Both
#      rows are real and must survive.
#   2. The same parcel recorded twice under different Sale counters, identical
#      in every other field. 36,752 groups. One must go.
#
# The legal description separates them exactly: it keeps 14,603/14,603 of the
# first and collapses 36,751/36,752 of the second. Adding 'Sale counter'
# instead was tried and rejected - it keeps the distinct parcels but collapses
# NONE of the repeats, leaving 101,295 duplicate rows in the output.
#
# Only 30 rows in 1.6M have no legal description, so a blank key value is not a
# meaningful risk here.
MODERN_DEDUP_KEY = ['Property ID', 'Dealing number', 'Property legal description']

# Every column the two parsers can produce, i.e. everything clean_dataframe()
# reads before it starts deriving new columns of its own.
SOURCE_COLUMNS = [
    'District code', 'Property ID', 'Valuation number', 'Sale counter',
    'Download date / time', 'Property name', 'Property unit number',
    'Property house number', 'Property street name', 'Property locality',
    'Property post code', 'Area', 'Area type', 'Dimensions', 'Contract date',
    'Settlement date', 'Purchase price', 'Zoning', 'Nature of property',
    'Primary purpose', 'Strata lot number', 'Component code', 'Sale code',
    '% Interest of sale', 'Dealing number', 'Property legal description',
]

# Columns renamed for the v2 schema. The old names described the SOURCE FILE
# rather than the value in the column beside them: 'Area' held metres after the
# hectare conversion while 'Area type' still said 'H'. The '(source)' suffix
# marks the two columns that describe the raw input. See Plan-Claude.md 2.1.
SCHEMA_V2_RENAMES = {
    'Area': 'Area (m2)',
    'Area type': 'Area type (source)',
}

# The source's one-character property classification. The raw code stays in the
# output beside this, so the decode can always be checked against it.
NATURE_OF_PROPERTY_DESCRIPTIONS = {
    'R': 'Residence',
    'V': 'Vacant land',
    '3': 'Other',
}

# 'Primary purpose' is effectively a free-text field, not a code list: 10,946
# distinct values across the corpus, 7,257 of which appear exactly once, plus
# truncation at 14 characters ('Commercial Off', 'Primary Produc'). These rules
# collapse it into a handful of categories - the first keyword found anywhere in
# the lower-cased value wins.
#
# ORDER MATTERS, and it is the whole trick. Specific categories must be listed
# before general ones. An earlier version put Residence first and matched the
# keyword 'unit', which filed 'Factory Unit' and 'Storage Unit' as housing -
# 4,688 rows. When adding a keyword, put it under the most specific category
# that fits, and add new categories above Residence rather than below it.
PRIMARY_PURPOSE_RULES = [
    ('Car space', ['carspace', 'car space', 'car park', 'carpark', 'parking',
                   'garage', 'lock up gar']),
    ('Industrial', ['industrial', 'factory', 'warehouse', 'workshop', 'storage',
                    'depot', 'quarry', 'mine']),
    ('Commercial', ['commercial', 'commerical', 'shop', 'office', 'retail',
                    'restaurant', 'hotel', 'motel', 'tavern', 'supermarket',
                    'service stat', 'servicestation', 'service stn', 'petrol',
                    'showroom', 'medical', 'surgery', 'child care', 'childcare',
                    'nursing', 'clinic', 'bank', 'caravan park', 'business',
                    'marina', 'marine berth', 'boarding house']),
    ('Rural', ['farm', 'rural', 'grazing', 'orchard', 'vineyard', 'agricultur',
               'primary produc', 'cattle', 'dairy', 'poultry', 'winery',
               'piggery', 'horticultur']),
    ('Vacant land', ['vacant', 'vacamt', 'land only', 'building lot',
                     'building block']),
    ('Residence', ['residence', 'residential', 'house', 'home unit', 'townhouse',
                   'villa', 'duplex', 'cottage', 'flat', 'unit', 'apartment',
                   'strata', 'granny', 'dwelling', 'terrace', 'semi']),
]

# Values that carry no information at all: a blank field, or the literal
# four-character string 'Null', which really does arrive that way on 5,280 rows.
# These become null in the normalised column, because "the source told us
# nothing" is a different fact from "the source told us something we could not
# categorise" - and that second case is what PRIMARY_PURPOSE_FALLBACK is for.
PRIMARY_PURPOSE_MISSING = ('', 'null')
PRIMARY_PURPOSE_FALLBACK = 'Unclassified'

# How the source writes its extraction timestamp: 'CCYYMMDD HH24:MI'. Parsed
# into a real datetime on the way out, so consumers get something they can do
# arithmetic on instead of a string in the source's private format sitting next
# to two ISO date columns.
DOWNLOAD_TIMESTAMP_FORMAT = '%Y%m%d %H:%M'

# A price below this is not a market transaction. 52,280 rows are exactly $0 -
# family transfers, related-party dealings and government acquisitions - and a
# further 10,476 sit under $1,000. Flagged, never removed.
NON_MARKET_PRICE_THRESHOLD = 1000

# --- Filtering & Data Quality Controls ---
# Set to True to nullify records with contract and settlement dates in the future
NULL_FUTURE_DATES = True
# Set to True to nullify contract and settlement dates outside the valid range.
NULL_OUT_OF_RANGE_DATES = True

# The Valuer General published no sales data before 1990, so any earlier date is a
# data entry error.
#
# READ THIS BEFORE CHANGING IT. This is a DATA QUALITY control, not a filter. A
# row with an earlier date keeps every one of its other fields and stays in the
# output - it just has an empty date afterwards. Setting this to, say,
# '2019-01-01' does NOT give you a 2019-onwards dataset; it gives you the same
# dataset with a few hundred thousand blank contract dates in it.
#
# If what you want is less data, use EARLIEST_EXTRACT_YEAR below.
EARLIEST_DATE = '1990-01-01'

# Skip yearly archives older than this - they are never opened, so this saves
# both time and memory. Set to None to process everything in DATA_DIR.
#
# This is the knob for "I only want recent data", and it is the one that
# actually works. It exists because nothing in data/ is ever deleted (the source
# is Cloudflare-blocked, so a deleted archive cannot be re-fetched), which means
# limiting the dataset by removing files is not an option.
#
# Only yearly archives ('2019.zip') are affected. Weekly files ('20260824.zip')
# are always current-year and are always processed.
EARLIEST_EXTRACT_YEAR = None

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)


def decode_dat(raw_bytes: bytes, source_label: str) -> List[str]:
    """
    Turns the raw bytes of a .dat file into a list of lines.

    Uses errors='replace' rather than letting one bad byte throw away a whole
    file. The old code caught UnicodeDecodeError and skipped the entire .dat,
    which could silently drop megabytes of sales records; losing one character
    is much better than losing the file.

    Args:
        raw_bytes (bytes): The undecoded contents of the .dat file.
        source_label (str): Where it came from, for the log message.

    Returns:
        List[str]: The decoded lines.
    """
    text = raw_bytes.decode("utf-8", errors="replace")
    bad_characters = text.count("�")
    if bad_characters:
        logging.warning(
            f"{source_label}: {bad_characters} character(s) could not be decoded "
            f"and were replaced. The records were kept."
        )
    return text.splitlines()


def iter_dat_files(zip_filepath: str):
    """
    Yields the contents of each .dat file in an archive, one file at a time.

    Yields (source_label, lines) so the caller can process one file, then let it
    go. This matters for two reasons:

      1. CORRECTNESS. The Valuer General spec says Sale Counter is "Unique for
         file", so the (District, Property Id, Sale Counter) key used to attach
         'C' legal descriptions to 'B' sale records is only meaningful WITHIN a
         single .dat. Reading everything into one list, as the old code did, let
         descriptions from different weeks collide and be concatenated together.
      2. MEMORY. Holding every line of 35 years of archives in one list needed
         many gigabytes. One file at a time needs almost nothing.

    Valuer General yearly archives usually package each weekly batch as a nested
    .zip; some older years contain .dat files directly. Both are handled.

    Args:
        zip_filepath (str): Path to the outer zip file.

    Yields:
        tuple: (source_label, list of lines) for each .dat file found.
    """
    archive_name = os.path.basename(zip_filepath)
    try:
        with zipfile.ZipFile(zip_filepath, 'r') as zip_file:
            for entry in sorted(zip_file.namelist()):
                # .dat files sitting directly in the archive
                if entry.lower().endswith(".dat"):
                    label = f"{archive_name}!{entry}"
                    yield label, decode_dat(zip_file.read(entry), label)
                # Nested weekly zips, read in memory without unpacking to disk
                elif entry.lower().endswith(".zip"):
                    with zipfile.ZipFile(io.BytesIO(zip_file.read(entry))) as inner_zip:
                        for inner_entry in sorted(inner_zip.namelist()):
                            if inner_entry.lower().endswith(".dat"):
                                label = f"{archive_name}!{entry}!{inner_entry}"
                                yield label, decode_dat(inner_zip.read(inner_entry), label)
    except FileNotFoundError:
        logging.error(f"File not found: {zip_filepath}")
    except zipfile.BadZipFile:
        logging.error(f"Bad zip file: {zip_filepath}")


def reconcile_trailer(lines: List[str], source_label: str) -> bool:
    """
    Checks the parsed record counts against the file's own 'Z' trailer record.

    Every .dat ends with a trailer stating how many B, C and D records it should
    contain. Comparing against it is a free integrity check that catches a
    truncated or partially-read file immediately.

    Args:
        lines (List[str]): The decoded lines of one .dat file.
        source_label (str): Where it came from, for the log message.

    Returns:
        bool: True if the counts agree (or there is no trailer to check).
    """
    trailer = next((line for line in reversed(lines) if line.startswith("Z;")), None)
    if trailer is None:
        logging.warning(f"{source_label}: no 'Z' trailer record - cannot verify completeness.")
        return False

    parts = trailer.split(";")
    actual_b = sum(1 for line in lines if line.startswith("B;"))
    try:
        expected_b = int(parts[2])
    except (IndexError, ValueError):
        logging.warning(f"{source_label}: could not read the B-record count from its 'Z' trailer.")
        return False

    if expected_b != actual_b:
        logging.warning(
            f"{source_label}: trailer mismatch - the file says it holds {expected_b} "
            f"B records but {actual_b} were found. The file may be truncated."
        )
        return False
    return True


def parse_data_lines(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Parses raw data lines into structured records, supporting both the post-2001
    and pre-2001 NSW Valuer General file specifications.

    Processing Workflow:
      1. First Pass: Collects and concatenates 'C' records (legal descriptions).
         According to the Valuer General spec:
         "If more than one 'C' record they join without a space."
      2. Second Pass: Identifies 'B' record schema:
         - Archived layout if 3rd field is non-numeric (e.g. 'ARCHIVE', 'VALNET1').
         - Modern layout if 3rd field is a numeric Property ID.
      3. Joins legal descriptions onto modern 'B' records using (District, Property ID, Sale Counter).

    Args:
        lines (List[str]): Raw string lines extracted from .dat files.

    Returns:
        List[Dict[str, Any]]: List of dictionary representations of property sale records.
    """
    processed_records: List[Dict[str, Any]] = []
    legal_descriptions: Dict[tuple, str] = {}  # Key: (District code, Property ID, Sale counter)
    unrecognised = 0  # 'B' lines matching neither schema

    # First pass: Collect and concatenate legal descriptions from 'C' records
    for line in lines:
        if line.startswith("C;"):
            parts = line.split(";")
            if len(parts) >= 6:
                # Key: (District code, Property ID, Sale counter)
                key = (parts[1].strip(), parts[2].strip(), parts[3].strip())
                # Concatenate without space per Valuer General specification
                legal_descriptions[key] = legal_descriptions.get(key, "") + parts[5]

    # Clean leading/trailing whitespace on aggregated legal descriptions
    for key in legal_descriptions:
        legal_descriptions[key] = legal_descriptions[key].strip()

    # Second pass: Process 'B' sales records and attach legal descriptions
    for line in lines:
        if not line.startswith("B;"):
            continue

        parts = [p.strip() for p in line.split(";")]

        # Tell the two schemas apart by how many fields the line has. Verified
        # against the real archives: 1990-2000 files always have 22 fields,
        # 2001-onwards always have 25.
        #
        # The previous test was `not parts[2].isdigit()`, on the basis that the
        # archived format has a text source ('ARCHIVE', 'VALNET1') where the
        # current format has a numeric Property Id. That also matches an EMPTY
        # field, so a malformed current-format line was quietly handed to the
        # archived parser, which read completely the wrong fields and produced a
        # record that looked plausible. Field count cannot misfire that way.
        record = None
        if len(parts) >= CURRENT_FORMAT_FIELDS:
            record = parse_current_record(parts)
            if record:
                # Match legal description for current format records
                key = (record.get("District code"), record.get("Property ID"), record.get("Sale counter"))
                if key in legal_descriptions:
                    record["Property legal description"] = legal_descriptions[key]
        elif len(parts) >= ARCHIVED_FORMAT_MIN_FIELDS:
            record = parse_archived_record(parts)

        if record:
            processed_records.append(record)
        else:
            unrecognised += 1

    if unrecognised:
        logging.warning(
            f"Skipped {unrecognised} 'B' record(s) whose layout matched neither "
            f"the current ({CURRENT_FORMAT_FIELDS} fields) nor the archived "
            f"({ARCHIVED_FORMAT_MIN_FIELDS}+ fields) format."
        )

    return processed_records


def parse_current_record(parts: List[str]) -> Optional[Dict[str, Any]]:
    """
    Parses a 'B' (Property/Sale) record using the post-2001 Current File Format.

    Field Position Mapping (0-indexed):
      - 0: Record type ('B')
      - 1: District Code (e.g. '077')
      - 2: Property Id (numeric)
      - 3: Sale Counter (unique within file)
      - 4: Download Date / Time (CCYYMMDD HH24:MI)
      - 5: Property Name
      - 6: Property Unit Number
      - 7: Property House Number
      - 8: Property Street Name
      - 9: Property Locality (Suburb)
      - 10: Property Post Code
      - 11: Area
      - 12: Area Type ('M' = sq metres, 'H' = hectares)
      - 13: Contract Date (CCYYMMDD)
      - 14: Settlement Date (CCYYMMDD)
      - 15: Purchase Price
      - 16: Zoning
      - 17: Nature of Property ('V', 'R', '3')
      - 18: Primary Purpose
      - 19: Strata Lot Number
      - 20: Component Code
      - 21: Sale Code
      - 22: % Interest of Sale (null/'0' means the whole property was sold)
      - 23: Dealing Number

    Args:
        parts (List[str]): Semicolon-split tokens from a modern 'B' line.

    Returns:
        Optional[Dict[str, Any]]: Parsed record dictionary, or None if invalid length.
    """
    if len(parts) < 25:
        return None

    # The source writes '0' or nothing when the whole property changed hands.
    # Store that as null so a value in this column always means a part share -
    # a 50% interest sold for $400,000 is not a $400,000 property.
    percent_interest = parts[22] if parts[22] not in ('', '0') else None

    return {
        "District code": parts[1],
        "Property ID": parts[2],
        "Sale counter": parts[3],
        "Download date / time": parts[4],
        "Property name": parts[5],
        "Property unit number": parts[6],
        "Property house number": parts[7],
        "Property street name": parts[8],
        "Property locality": parts[9],
        "Property post code": parts[10],
        "Area": parts[11],
        "Area type": parts[12],
        "Contract date": parts[13],
        "Settlement date": parts[14],
        "Purchase price": parts[15],
        "Zoning": parts[16],
        "Nature of property": parts[17],
        "Primary purpose": parts[18],
        "Strata lot number": parts[19],
        "Valuation number": None,  # Pre-2001 archived records only
        "Component code": parts[20],
        "Sale code": parts[21],
        "% Interest of sale": percent_interest,
        "Dealing number": parts[23],
        "Dimensions": None,  # Pre-2001 archived records only
        "Property legal description": None  # Populated via 'C' record merge
    }


def parse_archived_record(parts: List[str]) -> Optional[Dict[str, Any]]:
    """
    Parses a 'B' (Property/Sale) record using the pre-2001 Archived File Format (1990 - 2001).

    Field Position Mapping (0-indexed):
      - 0: Record type ('B')
      - 1: District Code (e.g. '077')
      - 2: Source ('ARCHIVE', 'VALNET1', etc.)
      - 3: Valuation Number (old valuation reference)
      - 4: Property Id
      - 5: Unit Number
      - 6: House Number
      - 7: Street Name
      - 8: Suburb Name (Locality)
      - 9: Postcode
      - 10: Contract Date (DD/MM/YYYY converted to YYYYMMDD)
      - 11: Purchase Price
      - 12: Land Description (embedded legal description)
      - 13: Area
      - 14: Area Type ('M' = sq metres, 'H' = hectares)
      - 15: Dimensions
      - 16: Component Code
      - 17: Zone Code

    Args:
        parts (List[str]): Semicolon-split tokens from an archived 'B' line.

    Returns:
        Optional[Dict[str, Any]]: Parsed record dictionary, or None if invalid length.
    """
    if len(parts) < 18:
        return None

    # Archived contract dates use DD/MM/YYYY; convert to CCYYMMDD for downstream uniformity
    contract_date_str = ""
    try:
        contract_date = datetime.strptime(parts[10], "%d/%m/%Y")
        contract_date_str = contract_date.strftime("%Y%m%d")
    except ValueError:
        # Handles cases where CCYYMMDD already appears, or preserves raw text for error coercion
        contract_date_str = parts[10]

    return {
        "District code": parts[1],
        "Property ID": parts[4],
        "Sale counter": None,
        "Download date / time": None,
        "Property name": None,
        "Property unit number": parts[5],
        "Property house number": parts[6],
        "Property street name": parts[7],
        "Property locality": parts[8],
        "Property post code": parts[9],
        "Area": parts[13],
        "Area type": parts[14],
        "Contract date": contract_date_str,
        "Settlement date": None,  # Not present in pre-2001 archived specification
        "Purchase price": parts[11],
        "Zoning": parts[17],
        "Nature of property": None,
        "Primary purpose": None,
        "Strata lot number": None,
        # For the ~31% of archived records with no Property Id, this old
        # valuation number is the only identifier the property has.
        "Valuation number": parts[3],
        "Component code": parts[16],
        "Sale code": None,          # Not present in the archived specification
        "% Interest of sale": None, # Not present in the archived specification
        "Dealing number": None,     # Not present in the archived specification
        "Dimensions": parts[15],    # e.g. '20.72 X 40.23' - frontage x depth
        "Property legal description": parts[12]
    }


def fix_title_case(series: pd.Series) -> pd.Series:
    """
    Title-cases a column of government all-caps text, then repairs the two
    things str.title() gets wrong.

    1. 'MCMAHONS POINT' becomes 'Mcmahons Point'; it should be 'McMahons
       Point'. 52,906 rows across the corpus.

       This deliberately does NOT do the same for 'Mac'. In NSW the Mac names
       are correctly lower-case - Macquarie, Great Mackerel Beach, Macleay St,
       Central Macdonald - so a symmetric rule would corrupt 83,452 locality
       rows in order to fix none.

    2. "BENNY'S TOPS" becomes "Benny'S Tops", because str.title() treats an
       apostrophe as a word break. 9,210 rows.

       The \\b in the pattern means only a word-FINAL 'S is lowered, so
       O'Sullivan and O'Shea (1,642 rows) come through untouched.

    Args:
        series (pd.Series): A column of raw all-caps text.

    Returns:
        pd.Series: The same column, cased for humans.
    """
    values = series.str.title()

    # The Mc rule needs a Python callable to upper-case the captured letter,
    # which pandas has to run one row at a time. Selecting the rows that
    # actually contain 'Mc' first keeps that off the other seven million.
    needs_mc_fix = values.str.contains(r'\bMc[a-z]', regex=True, na=False)
    if needs_mc_fix.any():
        values.loc[needs_mc_fix] = values.loc[needs_mc_fix].str.replace(
            r'\bMc([a-z])', lambda match: 'Mc' + match.group(1).upper(), regex=True
        )

    return values.str.replace(r"'S\b", "'s", regex=True)


def classify_primary_purpose(value: str) -> Optional[str]:
    """
    Returns the category for a single 'Primary purpose' string.

    Walks PRIMARY_PURPOSE_RULES in order and takes the first keyword that
    appears anywhere in the value; see the comment on that constant for why the
    order is load-bearing. Anything unmatched is reported as 'Unclassified'
    rather than guessed at - 0.55% of populated rows across the corpus.

    Args:
        value (str): One raw purpose string, e.g. 'Commercial Off'.

    Returns:
        Optional[str]: The category name, PRIMARY_PURPOSE_FALLBACK where the
        value could not be matched, or None where the source said nothing.
    """
    text = value.strip().lower()
    if text in PRIMARY_PURPOSE_MISSING:
        return None

    for category, keywords in PRIMARY_PURPOSE_RULES:
        for keyword in keywords:
            if keyword in text:
                return category

    return PRIMARY_PURPOSE_FALLBACK


def normalise_primary_purpose(series: pd.Series) -> pd.Series:
    """
    Adds a tidy category alongside the free-text 'Primary purpose'.

    Classification runs over the DISTINCT values (about 11,000) and the answers
    are mapped back onto the rows, rather than testing seven million strings.

    Args:
        series (pd.Series): The cleaned 'Primary purpose' column.

    Returns:
        pd.Series: The category per row; null where the source said nothing.
    """
    lookup = {value: classify_primary_purpose(value)
              for value in series.dropna().unique()}
    return series.map(lookup)


def create_and_clean_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Constructs a pandas DataFrame from parsed records and applies domain cleaning,
    unit normalization, casing standardization, date validation, and deduplication.

    Cleaning Operations:
      1. Type Coercion: Dates to datetime64[ns] (errors='coerce'); Price, Postcode
         and Strata lot number to nullable Int64; Area to float, which keeps its
         genuine decimals.
      2. Date Sanitization:
         - Future dates (Contract / Settlement > today) nulled to NaT.
         - Pre-1990 dates (Contract / Settlement < 1990-01-01) nulled to NaT.
      3. Metric Conversion: Where Area Type == 'H' (Hectares), Area is multiplied by
         10,000 to yield m². The untouched figure is kept as 'Area (source)'.
      4. Text Standardization: Names, Street Names, Localities, and Primary Purpose
         converted to Title Case, then corrected by fix_title_case().
      5. Deduplication: Removes duplicate sales rows across batch overlaps, keyed on
         the dealing number where there is one and ARCHIVED_DEDUP_KEY where there
         is not.
      6. Derived columns: decoded companions for the two coded columns, and three
         quality flags. No step here removes a row.
      7. Column Alignment: Orders the DataFrame into the exact 33 standard output
         columns, applying SCHEMA_V2_RENAMES on the way.

    Args:
        records (List[Dict[str, Any]]): List of parsed record dictionaries.

    Returns:
        pd.DataFrame: Cleaned, structured pandas DataFrame ready for CSV export.
    """
    if not records:
        return pd.DataFrame()
    return clean_dataframe(pd.DataFrame(records))


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies all cleaning, normalization and deduplication to an assembled
    DataFrame. See create_and_clean_dataframe() above for the full list of
    operations; this is the same logic, taking a DataFrame instead of a list of
    record dictionaries so build_dataframe() can assemble one archive at a time.
    """
    if df.empty:
        return df

    # --- 0. Make sure every source column exists ---
    # The two parsers fill in None for the fields their layout doesn't have, so
    # in production this changes nothing. It means the steps below can just read
    # a column instead of first checking whether it is there.
    for col in SOURCE_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # --- 1. Data Type Conversion and Coercion ---
    df['Contract date'] = pd.to_datetime(df['Contract date'], format='%Y%m%d', errors='coerce')
    df['Settlement date'] = pd.to_datetime(df['Settlement date'], format='%Y%m%d', errors='coerce')
    df['Download date / time'] = pd.to_datetime(
        df['Download date / time'], format=DOWNLOAD_TIMESTAMP_FORMAT, errors='coerce')

    # Whole-number columns. Int64 with a capital I is pandas' nullable integer;
    # plain int cannot hold a missing value, which is exactly how these ended up
    # as floats and why 100% of prices and postcodes used to be written '2481.0'
    # - a value that will not join against a postcode lookup table.
    # .round() is a no-op on real data (every price and postcode in the corpus
    # is whole) and stops one odd fractional value from killing a nightly run.
    integer_cols = ['Purchase price', 'Property post code', 'Strata lot number']
    for col in integer_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').round().astype('Int64')

    # Area stays floating point - 2,728,419 rows have a genuine fractional part
    # (e.g. 992.7 m²), so rounding it would lose real precision.
    df['Area'] = pd.to_numeric(df['Area'], errors='coerce')

    # --- 2. Data Sanitization & Date Filtering ---
    # Null out dates in the future (keeps record but prevents impossible future dates)
    if NULL_FUTURE_DATES:
        today = pd.to_datetime('today').normalize()

        future_contract = df['Contract date'] > today
        if future_contract.any():
            count = future_contract.sum()
            df.loc[future_contract, 'Contract date'] = pd.NaT
            logging.info(f"Nulled out {count} future Contract dates.")

        future_settlement = df['Settlement date'] > today
        if future_settlement.any():
            count = future_settlement.sum()
            df.loc[future_settlement, 'Settlement date'] = pd.NaT
            logging.info(f"Nulled out {count} future Settlement dates.")

    # Null out dates before EARLIEST_DATE (i.e. before the Valuer General's
    # electronic archives begin). The message quotes the constant rather than
    # hard-coding 1990 - if someone changes EARLIEST_DATE, a log that still says
    # "pre-1990" sends them looking in the wrong place.
    if NULL_OUT_OF_RANGE_DATES:
        earliest_date = pd.to_datetime(EARLIEST_DATE).normalize()

        early_contract = df['Contract date'] < earliest_date
        if early_contract.any():
            count = early_contract.sum()
            df.loc[early_contract, 'Contract date'] = pd.NaT
            logging.info(f"Nulled out {count} Contract dates before {EARLIEST_DATE}.")

        early_settlement = df['Settlement date'] < earliest_date
        if early_settlement.any():
            count = early_settlement.sum()
            df.loc[early_settlement, 'Settlement date'] = pd.NaT
            logging.info(f"Nulled out {count} Settlement dates before {EARLIEST_DATE}.")

    # --- 3. Metric Normalization: Hectares (H) to Square Metres (m²) ---
    # Keep the untouched source number as well as the converted one. Before v2
    # the output had a single 'Area' column already converted to m² sitting next
    # to an 'Area type' that still said 'H'. The careful thing for a reader to
    # do - re-convert the hectare rows themselves - therefore multiplied 552,850
    # rows by 10,000 a second time, turning a 9.5 hectare farm into 9,497
    # hectares. Both columns are renamed on the way out (SCHEMA_V2_RENAMES) so
    # the type unambiguously describes 'Area (source)' beside it.
    df['Area (source)'] = df['Area']
    df.loc[df['Area type'] == 'H', 'Area'] = df['Area'] * 10000

    # --- 4. Text Standardization: Convert Government All-Caps to Title Case ---
    string_cols = ['Property name', 'Property street name', 'Property locality', 'Primary purpose']
    for col in string_cols:
        df[col] = fix_title_case(df[col])

    # --- 5. Deduplication: Drop Overlapping Batch Records ---
    initial_count = len(df)

    # Sort oldest-first so keep='last' means "the most recently published version
    # of this sale", not "whichever file the operating system happened to list
    # last". Download date / time is a real datetime by this point, and rows
    # without one (every pre-2001 record) sort first via na_position. The extra
    # sort keys only break ties, so the result is the same no matter what order
    # the archives were read in.
    df = df.sort_values(
        ['Download date / time', 'Property ID', 'Sale counter', 'Dealing number'],
        kind='stable', na_position='first'
    )

    # Which key we can use depends on whether the record has a dealing number.
    # IMPORTANT: split on the dealing number, never on the contract date. Dates in
    # this dataset are unreliable (the same sale has been published with the year
    # mistyped), so using them to guess which format a record came from would
    # misfile tens of thousands of rows.
    has_dealing = df['Dealing number'].notna() & (df['Dealing number'] != '')

    # Post-2001 records: one dealing covering one parcel is one sale. This
    # catches sales the Valuer General later restated with a corrected date,
    # while keeping the separate parcels of a multi-parcel dealing. See
    # MODERN_DEDUP_KEY for why the legal description has to be in the key.
    deduped_with_dealing = df[has_dealing].drop_duplicates(
        subset=MODERN_DEDUP_KEY, keep='last'
    )

    # Pre-2001 archived records have no dealing number, so fall back to the
    # transaction itself - but the address has to be part of the key.
    #
    # About 31% of archived records have an EMPTY Property Id, so a key of just
    # (Property ID, Contract date, Purchase price) treats every blank-ID property
    # sold on the same day for the same price as one sale. Measured on 1995 and
    # 2000 alone, that silently deleted 26,851 records (7.8%) - for example a
    # closed road at Blaxland Ridge and a house at East Kurrajong, both sold on
    # 01/01/1995 for $174,000, became a single row. Including the address brings
    # the same two years down to 47 removals, all of them byte-identical repeats.
    deduped_without_dealing = df[~has_dealing].drop_duplicates(
        subset=ARCHIVED_DEDUP_KEY, keep='last'
    )

    df = pd.concat([deduped_with_dealing, deduped_without_dealing], ignore_index=True)

    # --- 5b. How many parcels each sale covered ---
    # One dealing can cover several parcels (115,054 dealings across the corpus,
    # 287,179 rows, the largest single sale spanning 195 parcels), and each
    # parcel is a separate row carrying the FULL sale price. Summing or taking a
    # median across them double-counts, so expose the count and let callers
    # decide. This is only correct because MODERN_DEDUP_KEY keeps the parcel
    # rows - keyed without the legal description, this column reported 1 for
    # sales that covered a dozen lots. Left null for pre-2001 records, which have no dealing number and
    # therefore no way to know.
    df['Parcels in sale'] = pd.NA
    dealing_rows = df['Dealing number'].notna() & (df['Dealing number'] != '')
    df.loc[dealing_rows, 'Parcels in sale'] = (
        df.loc[dealing_rows].groupby('Dealing number')['Dealing number'].transform('size')
    )
    df['Parcels in sale'] = df['Parcels in sale'].astype('Int64')

    deduped_count = initial_count - len(df)
    if deduped_count > 0:
        logging.info(
            f"Deduplicated {deduped_count} overlapping records "
            f"({len(deduped_with_dealing)} kept by dealing number, "
            f"{len(deduped_without_dealing)} kept by property/date/price)."
        )

    # --- 6. Decoded companion columns ---
    # Both are additions, never replacements: the raw source value stays in the
    # column beside them so our reading of it can always be checked. Both are
    # null for the 1,988,863 pre-2001 rows, which carry neither source field.
    df['Nature of property (description)'] = df['Nature of property'].map(
        NATURE_OF_PROPERTY_DESCRIPTIONS
    )
    df['Primary purpose (normalised)'] = normalise_primary_purpose(df['Primary purpose'])

    # Note there is deliberately NO decoded zoning column. The 2022 Employment
    # Zones Reform recycled the letter codes for different purposes - 'E1' meant
    # National Parks before it and Local Centre (retail) after - so a lookup
    # keyed on the code alone would label shopfronts as national parks across a
    # 36-year dataset. The caveat lives in DATA_DICTIONARY.md, where it travels
    # with the explanation.

    # --- 7. Quality flags ---
    # Flags only. This pipeline describes the data; it does not decide for the
    # reader which rows count as a real sale, so nothing here removes a row.

    # A null '% Interest of sale' means 100% in the source, so a value present
    # means the price bought a PART SHARE. Those 35,691 sales have a median
    # price of $206,000 against $360,000 for whole properties, and are otherwise
    # indistinguishable from cheap houses. This boolean is redundant with the
    # column it reads, and earns its place because that null-means-everything
    # inversion is the single most-missed trap in this dataset.
    df['Part interest flag'] = (
        df['% Interest of sale'].notna() & (df['% Interest of sale'] != '')
    )

    # Not a market transaction: see NON_MARKET_PRICE_THRESHOLD.
    price = df['Purchase price']
    df['Non-market price flag'] = (
        price.isna() | (price < NON_MARKET_PRICE_THRESHOLD)
    ).fillna(False).astype(bool)

    # A property cannot settle before it is sold, so on these 933 rows at least
    # one of the two dates is wrong. Comparisons against a missing date are
    # False, so an absent settlement date is not reported as an error.
    df['Date error flag'] = df['Settlement date'] < df['Contract date']

    # Deliberately NOT flagged: a long settlement. The median is 42 days, but
    # 281,643 rows (4%) exceed a year and most of those are legitimate
    # off-the-plan apartment sales, so the flag would mark ordinary sales as
    # suspicious and teach people to ignore it. Multi-parcel sales are likewise
    # left to 'Parcels in sale' above, where '> 1' says it more clearly than a
    # boolean would.

    # --- 8. Final Column Structure & Ordering ---
    df = df.rename(columns=SCHEMA_V2_RENAMES)

    final_columns = [
        "District code", "Property ID", "Valuation number", "Sale counter", "Download date / time",
        "Property name", "Property unit number", "Property house number",
        "Property street name", "Property locality", "Property post code",
        "Area (m2)", "Area (source)", "Area type (source)", "Dimensions",
        "Contract date", "Settlement date", "Purchase price", "Zoning",
        "Nature of property", "Nature of property (description)",
        "Primary purpose", "Primary purpose (normalised)", "Strata lot number",
        "Component code", "Sale code", "% Interest of sale",
        "Dealing number", "Parcels in sale", "Property legal description",
        "Part interest flag", "Non-market price flag", "Date error flag"
    ]
    for col in final_columns:
        if col not in df.columns:
            df[col] = None

    return df[final_columns]


def should_skip_archive(file_name: str) -> bool:
    """
    True if this file is a yearly archive from before EARLIEST_EXTRACT_YEAR.

    Yearly archives are named 'YYYY.zip'. Weekly files are 'YYYYMMDD.zip' and are
    never skipped - they only ever contain current-year sales. Anything that
    matches neither shape is processed rather than guessed at.

    Args:
        file_name (str): Bare filename, e.g. '2019.zip'.

    Returns:
        bool: True to skip the file entirely.
    """
    if EARLIEST_EXTRACT_YEAR is None:
        return False

    stem = os.path.splitext(file_name)[0]
    if len(stem) != 4 or not stem.isdigit():
        return False

    return int(stem) < EARLIEST_EXTRACT_YEAR


def build_dataframe(data_dir: str) -> pd.DataFrame:
    """
    Reads every zip in data_dir and returns the cleaned, deduplicated DataFrame.

    This is the whole extract pipeline in one call, kept separate from main() so
    it can be tested against a small folder of fixture zips.

    Args:
        data_dir (str): Folder containing the downloaded .zip archives.

    Returns:
        pd.DataFrame: The cleaned dataset, ready to write to CSV.
    """
    start_time = time.time()

    if not os.path.exists(data_dir):
        logging.error(f"Data directory not found: {data_dir}")
        return pd.DataFrame()

    # Work through one archive at a time and keep only the resulting DataFrame,
    # so we never hold every line of every year in memory at once.
    frames: List[pd.DataFrame] = []
    total_files = 0
    total_records = 0
    trailer_problems = 0

    skipped = 0
    if EARLIEST_EXTRACT_YEAR is not None:
        logging.info(
            f"EARLIEST_EXTRACT_YEAR is {EARLIEST_EXTRACT_YEAR}, so yearly "
            f"archives before then will be skipped.")

    for file_name in sorted(os.listdir(data_dir)):
        if not file_name.lower().endswith(".zip"):
            continue

        if should_skip_archive(file_name):
            skipped += 1
            continue

        zip_filepath = os.path.join(data_dir, file_name)
        logging.info(f"Extracting from: {zip_filepath}")

        records: List[Dict[str, Any]] = []
        for source_label, lines in iter_dat_files(zip_filepath):
            total_files += 1
            if not reconcile_trailer(lines, source_label):
                trailer_problems += 1
            # Parse each .dat on its own so 'C' legal descriptions can only ever
            # attach to 'B' records from the same file (see iter_dat_files).
            records.extend(parse_data_lines(lines))

        if records:
            total_records += len(records)
            frames.append(pd.DataFrame(records))
        del records

    logging.info(f"Read {total_files} data files, {total_records} property records.")
    if trailer_problems:
        logging.warning(f"{trailer_problems} data file(s) failed the trailer check - see warnings above.")
    logging.info(f"{int(time.time() - start_time)} seconds elapsed.")

    if not frames:
        logging.warning("No property records were found.")
        return pd.DataFrame()

    logging.info("Begin: Creating and cleaning DataFrame.")
    df = clean_dataframe(pd.concat(frames, ignore_index=True))
    del frames
    logging.info("DataFrame processing complete.")
    logging.info(f"{int(time.time() - start_time)} seconds elapsed.")
    return df


def main() -> None:
    """
    Main orchestration entry point:
      1. Discovers and extracts all .zip files from DATA_DIR in memory.
      2. Parses raw lines according to historical & current NSW specifications.
      3. Constructs, sanitizes, normalizes, and deduplicates the pandas DataFrame.
      4. Exports the final dataset to FINAL_CSV_PATH (`extract-3-very-clean.csv`).
    """
    start_time = time.time()
    logging.info('Start: Extracting and processing data.')

    df = build_dataframe(DATA_DIR)

    # 4. Exporting to CSV
    if df.empty:
        # Exit non-zero rather than returning quietly. An empty result means
        # something upstream broke - a corrupt archive, an empty data/, a parser
        # that matched nothing - and the previous run's CSV is usually still
        # sitting at FINAL_CSV_PATH. Returning 0 here instead would let the cron's `&&` chain
        # continue, and 3-publish.py then republishes that stale file stamped
        # with today's date.
        logging.error(
            f"No records were extracted from {DATA_DIR}. Refusing to continue, "
            f"because any existing {FINAL_CSV_PATH} is from an earlier run and "
            f"would be republished as though it were today's data."
        )
        sys.exit(1)

    logging.info(f"Begin: Exporting {len(df)} records to {FINAL_CSV_PATH}")
    df.to_csv(FINAL_CSV_PATH, index=False, quoting=csv.QUOTE_ALL)

    logging.info("Complete: Data has been extracted and processed.")
    logging.info(f"Total elapsed time was {int(time.time() - start_time)} seconds.")


if __name__ == "__main__":
    main()
