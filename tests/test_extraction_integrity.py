"""
Tests for the correctness problems found in Review-Claude.md.

Every test here was written BEFORE the fix and must fail against the old
behaviour - otherwise it isn't proving anything. See Plan-Claude.md Phase 1.
"""

import logging

import pandas as pd
import pytest

from conftest import make_b_record, make_c_record, make_dat, write_yearly_zip


# --- A1: legal descriptions must not leak between files ----------------------

def test_legal_descriptions_do_not_leak_between_files(extract_mod, tmp_path):
    """
    The Valuer General spec says Sale Counter is "Unique for file", so the same
    (district, property ID, sale counter) key legitimately refers to DIFFERENT
    sales in different weekly files.

    The old code built one global dict of 'C' records across every file and
    concatenated collisions, producing descriptions like '1/SP10429171/SP104291'
    - two unrelated strata lots glued together. 13.8% of rows were affected in a
    single year of real data.
    """
    key = dict(district="008", prop_id="4515682", counter="5")

    week1 = make_dat(
        b_records=[make_b_record(**key, download="20260105 01:00", unit="101",
                                 dealing="AU100001", contract="20260102")],
        c_records=[make_c_record("1/SP104291", **key, download="20260105 01:00")],
        district="008", download="20260105 01:00",
    )
    # Same key, a week later, describing a completely different sale.
    week2 = make_dat(
        b_records=[make_b_record(**key, download="20260112 01:00", unit="710",
                                 dealing="AU200002", contract="20260109")],
        c_records=[make_c_record("71/SP104291", **key, download="20260112 01:00")],
        district="008", download="20260112 01:00",
    )

    write_yearly_zip(tmp_path / "2026.zip", {
        "20260105.zip": {"008_SALES.DAT": week1},
        "20260112.zip": {"008_SALES.DAT": week2},
    })

    df = extract_mod.build_dataframe(str(tmp_path))
    descriptions = sorted(df["Property legal description"].tolist())

    assert descriptions == ["1/SP104291", "71/SP104291"], (
        f"legal descriptions leaked between files: {descriptions}"
    )


def test_each_record_keeps_only_its_own_description(extract_mod, tmp_path):
    """
    The many-file version of the test above: every 'B' record must end up with
    exactly the description from its own file, no more.

    NOTE: an earlier version of this test asserted "no description exceeds 70
    characters", on the theory that the spec's 70-char cap on a 'C' record made
    anything longer a sign of concatenation. That was wrong, and running it
    against the real corpus proved it - 85,570 legitimate rows are longer than
    70 characters:
      - pre-2001 archived records hold the whole description in one 1000-char
        field, so the 70-char cap does not apply to them at all; and
      - the spec explicitly says multiple 'C' records "join without a space",
        so a genuine multi-lot subdivision runs to thousands of characters.
    Asserting exact expected values is the correct invariant. Length is not.
    """
    # Realistic-length descriptions: four of these concatenated blow past 70,
    # which is exactly what the real corruption looked like.
    descriptions = [
        "432/1029900 Enclosure Permit 408979",
        "7, 8/7/7634 Crown Land Lease 22841",
        "15/SP104291 Common Property",
        "22/DP270142 Right of Carriageway",
    ]
    weeklies = {}
    for i, desc in enumerate(descriptions):
        download = f"2026010{i + 1} 01:00"
        weeklies[f"2026010{i + 1}.zip"] = {
            "001_SALES.DAT": make_dat(
                b_records=[make_b_record(
                    prop_id="999", counter="3", download=download,
                    dealing=f"AB{i:04d}",
                    # Genuinely different sales - otherwise deduplication
                    # correctly collapses them and there is nothing to compare.
                    contract=f"2026020{i + 1}", price=str(700000 + i * 1000),
                )],
                c_records=[make_c_record(desc, prop_id="999",
                                         counter="3", download=download)],
                download=download,
            )
        }
    write_yearly_zip(tmp_path / "2026.zip", weeklies)

    df = extract_mod.build_dataframe(str(tmp_path))
    got = sorted(df["Property legal description"].tolist())

    assert got == sorted(descriptions), (
        "each record must keep exactly its own description; got:\n  "
        + "\n  ".join(got)
    )


# --- A3: deduplication --------------------------------------------------------

def _record(**overrides):
    """A complete record dict with sensible defaults, for dedup tests."""
    base = {
        "District code": "001", "Property ID": "1416830", "Sale counter": "65",
        "Download date / time": "20260105 01:00", "Property name": None,
        "Property unit number": None, "Property house number": "12",
        "Property street name": "FLEET AVE", "Property locality": "SPRINGWOOD",
        "Property post code": "2777", "Area": "520.15", "Area type": "M",
        "Contract date": "20260122", "Settlement date": "20260215",
        "Purchase price": "2075000", "Zoning": "R2", "Nature of property": "R",
        "Primary purpose": "RESIDENCE", "Strata lot number": None,
        "Dealing number": "AT837692", "Property legal description": "1/DP1000",
    }
    base.update(overrides)
    return base


def test_dedup_keeps_newest_restatement_of_a_corrected_sale(extract_mod):
    """
    When the VG restates a sale, the corrected field is often the contract date
    itself - so a key of (Property ID, Contract date, Purchase price) sees two
    different rows and keeps both. Two such pairs survived in the real output.

    The same dealing number for the same property is the same sale; the row from
    the later download wins.
    """
    # Both dates must be in the past: future contract dates are nulled to NaT
    # before deduplication runs, which would mask what this test is checking.
    records = [
        _record(**{"Download date / time": "20260219 01:06", "Contract date": "20260122"}),
        # Same dealing, same price, same settlement - contract date typo corrected.
        _record(**{"Download date / time": "20260401 01:10", "Contract date": "20260322"}),
    ]

    df = extract_mod.create_and_clean_dataframe(records)

    assert len(df) == 1, f"restated sale not deduplicated: {len(df)} rows"
    assert df["Contract date"].iloc[0] == pd.Timestamp("2026-03-22"), (
        "kept the stale row instead of the corrected one"
    )


def test_genuinely_different_sales_of_one_property_are_kept(extract_mod):
    """Guard against over-deduplicating: different dealings are different sales."""
    records = [
        _record(**{"Dealing number": "AT111111", "Contract date": "20260122",
                   "Purchase price": "2075000"}),
        _record(**{"Dealing number": "AT222222", "Contract date": "20260610",
                   "Purchase price": "2300000"}),
    ]

    df = extract_mod.create_and_clean_dataframe(records)
    assert len(df) == 2


def test_output_is_independent_of_file_order(extract_mod, tmp_path, monkeypatch):
    """
    Row order came from os.listdir(), which is arbitrary on ext4 - so keep='last'
    picked a different winner depending on the filesystem. The same inputs must
    always produce the same output, whatever order the files arrive in.
    """
    def make_data_dir(name):
        """
        Two SEPARATE top-level zips, so the order os.listdir() returns them in
        actually matters. Both describe the same sale (same property, contract
        date and price) but disagree on zoning, so we can see which one won.
        """
        d = tmp_path / name
        d.mkdir()
        write_yearly_zip(d / "archive_a.zip", {"20260105.zip": {"001_SALES.DAT": make_dat(
            b_records=[make_b_record(prop_id="500", counter="1", zoning="R2",
                                     download="20260105 01:00", dealing="AA1")],
            download="20260105 01:00")}})
        write_yearly_zip(d / "archive_b.zip", {"20260112.zip": {"001_SALES.DAT": make_dat(
            b_records=[make_b_record(prop_id="500", counter="1", zoning="R4",
                                     download="20260112 01:00", dealing="AA1")],
            download="20260112 01:00")}})
        return d

    forward = extract_mod.build_dataframe(str(make_data_dir("fwd")))

    # Simulate a filesystem that hands back names in the opposite order.
    real_listdir = extract_mod.os.listdir
    monkeypatch.setattr(extract_mod.os, "listdir",
                        lambda p: list(reversed(real_listdir(p))))
    reverse = extract_mod.build_dataframe(str(make_data_dir("rev")))

    pd.testing.assert_frame_equal(
        forward.reset_index(drop=True), reverse.reset_index(drop=True)
    )


# --- A10: silent data loss ----------------------------------------------------

def test_trailer_mismatch_is_reported(extract_mod, tmp_path, caplog):
    """
    Every .dat ends with a 'Z' trailer stating its own B/C record counts - a free
    integrity check the pipeline ignored. A truncated download should be loud.
    """
    bad = make_dat(
        b_records=[make_b_record(prop_id="1"), make_b_record(prop_id="2")],
        b_count_override=99,  # trailer claims 99 B records, file has 2
    )
    write_yearly_zip(tmp_path / "2026.zip", {"20260105.zip": {"001_SALES.DAT": bad}})

    with caplog.at_level(logging.WARNING):
        extract_mod.build_dataframe(str(tmp_path))

    assert "trailer" in caplog.text.lower() or "mismatch" in caplog.text.lower(), (
        "a Z-trailer count mismatch was not reported"
    )


# --- A11: archived records with no Property ID must not be merged -------------
# Found while implementing 1.4, not in the original review: 31% of pre-2001
# records have an EMPTY Property Id, so a key of (Property ID, Contract date,
# Purchase price) collapses unrelated properties that happen to share a date and
# price. Measured on 1995+2000 alone: 26,851 records silently deleted.

def test_archived_records_at_different_addresses_are_not_merged(extract_mod):
    """
    Two different pre-2001 properties, both with a blank Property Id, sold on
    the same day for the same price. They are not the same sale.
    """
    from conftest import make_archived_b_record
    lines = [
        make_archived_b_record(prop_id="", house="", street="BLAXLAND RIDGE",
                               suburb="BLAXLAND RIDGE", contract="01/01/1995",
                               price="174000", legal="LOT 167 DP 729325.(CLOSED RD)"),
        make_archived_b_record(prop_id="", house="100", street="BLAXLANDS RIDGE RD",
                               suburb="EAST KURRAJONG", contract="01/01/1995",
                               price="174000", legal="LOT 10 DP 31340."),
    ]
    records = extract_mod.parse_data_lines(lines)
    assert len(records) == 2, "both archived records should parse"

    df = extract_mod.create_and_clean_dataframe(records)
    assert len(df) == 2, (
        "two different properties with no Property ID were merged into one"
    )


def test_identical_archived_duplicates_are_still_removed(extract_mod):
    """The other side of the guard: a genuine repeat must still collapse."""
    from conftest import make_archived_b_record
    line = make_archived_b_record(prop_id="", house="83 - 87", street="WOLSELEY ST",
                                  suburb="BEXLEY", contract="19/01/2000",
                                  price="375000", legal="LOT 20 DP 1009947.")
    records = extract_mod.parse_data_lines([line, line])
    df = extract_mod.create_and_clean_dataframe(records)
    assert len(df) == 1


# --- A2: fields that were being silently dropped ------------------------------

def test_current_record_carries_sale_code_component_and_interest(extract_mod):
    """
    Component code, Sale code and % Interest of Sale sit at fields 20-22 and were
    read straight past. % Interest matters most: a 50% share sold for $400k is
    not a $400k property.
    """
    line = make_b_record(component="RAN", sale_code="XA", interest="50",
                         dealing="AU123456")
    records = extract_mod.parse_data_lines([line])
    assert len(records) == 1
    r = records[0]
    assert r["Component code"] == "RAN"
    assert r["Sale code"] == "XA"
    assert r["% Interest of sale"] == "50"


def test_full_interest_is_recorded_as_null_not_zero(extract_mod):
    """
    The source writes '0' or an empty field to mean 'the whole property'. Both
    must become null so the column means what its name says.
    """
    records = extract_mod.parse_data_lines([
        make_b_record(prop_id="1", interest="0", dealing="A1"),
        make_b_record(prop_id="2", interest="", dealing="A2"),
        make_b_record(prop_id="3", interest="25", dealing="A3"),
    ])
    by_id = {r["Property ID"]: r["% Interest of sale"] for r in records}
    assert by_id["1"] is None
    assert by_id["2"] is None
    assert by_id["3"] == "25"


def test_district_code_reaches_the_output(extract_mod):
    """District code was parsed into every record and then dropped on export."""
    df = extract_mod.create_and_clean_dataframe(
        extract_mod.parse_data_lines([make_b_record(district="077")])
    )
    assert "District code" in df.columns
    assert df["District code"].iloc[0] == "077"


def test_archived_record_carries_dimensions(extract_mod):
    """Frontage x depth is useful to a buyer and exists only pre-2001."""
    from conftest import make_archived_b_record
    records = extract_mod.parse_data_lines([
        make_archived_b_record(dimensions="20.72 X 40.23")
    ])
    assert records[0]["Dimensions"] == "20.72 X 40.23"


# --- 1.6: schema discriminator ------------------------------------------------

def test_schema_is_chosen_by_field_count(extract_mod):
    """
    The old test was `not parts[2].isdigit()`, which also fires on an EMPTY
    field - so a malformed current-format line would be fed to the archived
    parser and produce plausible-looking nonsense. Real files are unambiguous:
    25 fields for current, 22 for archived.
    """
    from conftest import make_archived_b_record

    current = extract_mod.parse_data_lines([make_b_record(prop_id="12345")])
    assert current[0]["Property ID"] == "12345"
    assert current[0]["Dealing number"] == "AB1000"

    archived = extract_mod.parse_data_lines([make_archived_b_record(prop_id="292674")])
    assert archived[0]["Property ID"] == "292674"
    assert archived[0]["Dealing number"] is None


def test_unrecognised_line_length_is_logged_not_silently_dropped(extract_mod, caplog):
    """A 'B' line matching neither schema should be counted, not vanish."""
    with caplog.at_level(logging.WARNING):
        records = extract_mod.parse_data_lines(["B;001;123;1;20260105 01:00;junk;"])
    assert records == []
    assert "unrecognised" in caplog.text.lower() or "skipped" in caplog.text.lower()


# --- Multi-parcel sales and the pre-2001 identifier gap -----------------------

def test_archived_record_carries_valuation_number(extract_mod):
    """
    About 31% of pre-2001 records have no Property Id at all, which makes the old
    valuation number their only identifier. It was being read past and dropped.
    """
    from conftest import make_archived_b_record
    records = extract_mod.parse_data_lines([
        make_archived_b_record(prop_id="", valuation_num="0610300000000")
    ])
    assert records[0]["Valuation number"] == "0610300000000"


def test_parcels_in_sale_counts_rows_sharing_a_dealing(extract_mod):
    """
    One dealing can cover several parcels - 50,357 of them across the corpus.
    Each parcel is its own row carrying the FULL sale price, so summing or taking
    a median over them double-counts. Expose the count so callers can filter.
    """
    records = [
        _record(**{"Property ID": "1", "Dealing number": "AA1", "Property legal description": "LOT 1"}),
        _record(**{"Property ID": "2", "Dealing number": "AA1", "Property legal description": "LOT 2"}),
        _record(**{"Property ID": "3", "Dealing number": "BB2", "Property legal description": "LOT 3"}),
    ]
    df = extract_mod.create_and_clean_dataframe(records)
    counts = dict(zip(df["Property ID"], df["Parcels in sale"]))
    assert counts["1"] == 2 and counts["2"] == 2, "two parcels share dealing AA1"
    assert counts["3"] == 1


def test_parcels_in_sale_is_null_without_a_dealing_number(extract_mod):
    """Pre-2001 records have no dealing number, so the count is unknowable."""
    from conftest import make_archived_b_record
    records = extract_mod.parse_data_lines([make_archived_b_record(prop_id="99")])
    df = extract_mod.create_and_clean_dataframe(records)
    assert pd.isna(df["Parcels in sale"].iloc[0])
