import os
import sys
import importlib.util
import pytest

# Add repo root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

def load_module(name, filename):
    filepath = os.path.join(REPO_ROOT, filename)
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.fixture(scope="session")
def extract_mod():
    return load_module("extract_module", "2-extract.py")

@pytest.fixture(scope="session")
def download_mod():
    return load_module("download_module", "1-download.py")

@pytest.fixture(scope="session")
def publish_mod():
    # 3-archive.py and 4-validate.py used to be separate files. They were merged
    # into 3-publish.py so the checks cannot be skipped by leaving one out.
    return load_module("publish_module", "3-publish.py")

@pytest.fixture
def sample_modern_b_line():
    # Record B (2001 - Current format)
    # B;District;PropertyId;SaleCounter;DownloadDateTime;PropName;Unit;HouseNum;Street;Locality;Postcode;Area;AreaType;ContractDate;SettlementDate;Price;Zoning;Nature;Purpose;Strata;Comp;SaleCode;%Interest;Dealing;
    return "B;077;2885891;1;20170102 01:00;;;91;ADAMS ST;HEDDON GRETA;2321;1150;M;20161024;20161121;250000;R2;R;RESIDENCE;;;;;AK123456;"

@pytest.fixture
def sample_modern_c_lines():
    # Record C (Legal description)
    return [
        "C;077;2885891;1;20170102 01:00;LOT 1 DP 123456;",
        "C;077;2885891;1;20170102 01:00; / SEC A;"
    ]

@pytest.fixture
def sample_archived_b_line():
    # Record B (1990 - 2001 Archived format)
    # B;District;Source;ValuationNum;PropertyId;Unit;House;Street;Locality;Postcode;ContractDate;Price;LegalDesc;Area;AreaType;Dimensions;CompCode;ZoneCode;
    return "B;011;VALNET1;0145900000000;292674;;;ELDON ST;ABERDEEN;2336;20/11/1990;145000;LOT 7 SEC 1 DP 1234;2365;M;20.72 X 40.23;01;A;"

@pytest.fixture
def sample_archived_b_line_ccyymmdd():
    # Archived format where date is CCYYMMDD
    return "B;011;ARCHIVE;0147700000000;292704;;;GRAEME ST;ABERDEEN;2336;19901122;95000;LOT 2 DP 5678;1011;M;20 X 40;01;R;"

@pytest.fixture
def sample_hectare_record():
    return "B;077;3001002;1;20200101 00:00;RURAL RETREAT;;100;OLD COACH ROAD;SPRINGWOOD;2777;2.5;H;20200510;20200615;1200000;RU2;R;RURAL RESIDENCE;;;;;AL999888;"


# --- Fixture builders for realistic Valuer General archives ------------------
# These build the same shape as the real files: a yearly .zip containing weekly
# .zip files, each containing .dat files of A/B/C/D/Z records.

import io
import zipfile


def make_b_record(district="001", prop_id="1000", counter="1", download="20260105 01:00",
                  unit="", house="10", street="TEST ST", locality="SPRINGWOOD",
                  postcode="2777", area="600", area_type="M", contract="20260101",
                  settlement="20260201", price="750000", zoning="R2", nature="R",
                  purpose="RESIDENCE", strata="", component="", sale_code="",
                  interest="0", dealing="AB1000"):
    """Builds one post-2001 'B' line (25 fields including the trailing delimiter)."""
    return (f"B;{district};{prop_id};{counter};{download};;{unit};{house};{street};"
            f"{locality};{postcode};{area};{area_type};{contract};{settlement};{price};"
            f"{zoning};{nature};{purpose};{strata};{component};{sale_code};{interest};{dealing};")


def make_c_record(description, district="001", prop_id="1000", counter="1",
                  download="20260105 01:00"):
    """Builds one 'C' legal-description line."""
    return f"C;{district};{prop_id};{counter};{download};{description};"


def make_dat(b_records, c_records=(), district="001", download="20260105 01:00",
             b_count_override=None):
    """
    Builds the full text of one .dat file: A header, the records, Z trailer.

    b_count_override lets a test deliberately corrupt the Z trailer count so the
    reconciliation check has something to catch.
    """
    lines = [f"A;RTSALEDATA;{district};{download};VALNET;"]
    lines.extend(b_records)
    lines.extend(c_records)
    b_count = len(b_records) if b_count_override is None else b_count_override
    total = len(lines) + 1
    lines.append(f"Z;{total};{b_count};{len(c_records)};0;")
    return "\n".join(lines)


def make_weekly_zip(dats):
    """Builds the bytes of a weekly zip. `dats` maps filename -> .dat text."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("creative_commons.txt", "Licence")
        for name, text in dats.items():
            z.writestr(name, text)
    return buf.getvalue()


def write_yearly_zip(path, weeklies):
    """
    Writes a yearly archive containing nested weekly zips, as the real ones do.
    `weeklies` maps weekly-zip-filename -> {dat filename: dat text}.
    """
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for weekly_name, dats in weeklies.items():
            z.writestr(weekly_name, make_weekly_zip(dats))
    return path


def make_archived_b_record(district="011", source="ARCHIVE", valuation_num="148506000000",
                           prop_id="", unit="", house="113", street="GRAEME ST",
                           suburb="ABERDEEN", postcode="2336", contract="14/09/2000",
                           price="126000", legal="LOT 20 DP 261048.", area="1072",
                           area_type="M", dimensions="", comp_code="AA", zone="A"):
    """
    Builds one pre-2001 archived 'B' line.

    Real archived files have 22 semicolon-separated parts (verified against
    1990-2000 archives), versus 25 for the current format. Note that prop_id is
    routinely EMPTY in real archived data - about 31% of records.
    """
    return (f"B;{district};{source};{valuation_num};{prop_id};{unit};{house};{street};"
            f"{suburb};{postcode};{contract};{price};{legal};{area};{area_type};"
            f"{dimensions};{comp_code};{zone};;;;")
