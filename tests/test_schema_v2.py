"""
Tests for the Phase 2 schema (v2).

Every test here guards a case where the OLD output was technically correct but
invited a wrong reading - a column whose name contradicted its contents, a
number formatted so it wouldn't join, a name mangled by .str.title(). See
Plan-Claude.md Phase 2 for the measured scale of each one.
"""
import pandas as pd
import pytest


def _record(**overrides):
    """One complete post-2001 record dict, as parse_current_record() returns."""
    record = {
        "District code": "077",
        "Property ID": "1001",
        "Sale counter": "1",
        "Download date / time": "20200101 01:00",
        "Property name": None,
        "Property unit number": None,
        "Property house number": "10",
        "Property street name": "TEST ST",
        "Property locality": "SPRINGWOOD",
        "Property post code": "2777",
        "Area": "600",
        "Area type": "M",
        "Contract date": "20200115",
        "Settlement date": "20200215",
        "Purchase price": "750000",
        "Zoning": "R2",
        "Nature of property": "R",
        "Primary purpose": "RESIDENCE",
        "Strata lot number": None,
        "Valuation number": None,
        "Component code": None,
        "Sale code": None,
        "% Interest of sale": None,
        "Dealing number": "AB1001",
        "Dimensions": None,
        "Property legal description": "LOT 1 DP 1",
    }
    record.update(overrides)
    return record


# --------------------------------------------------------------- 2.1 Area ---

def test_area_columns_separate_converted_from_source(extract_mod):
    """
    A hectare row must expose both numbers, and the type must describe the
    source column rather than contradicting the converted one.

    Before v2 a row read: Area=40000.0, Area type='H' - so anyone defending
    themselves by re-converting the 'H' rows multiplied 552,850 rows by 10,000
    a second time.
    """
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": "H1", "Area": "3.5", "Area type": "H",
                   "Dealing number": "AB1"}),
        _record(**{"Property ID": "M1", "Area": "850", "Area type": "M",
                   "Dealing number": "AB2"}),
    ])

    hectares = df.loc[df["Property ID"] == "H1"].iloc[0]
    assert hectares["Area (m2)"] == 35000.0
    assert hectares["Area (source)"] == 3.5
    assert hectares["Area type (source)"] == "H"

    metres = df.loc[df["Property ID"] == "M1"].iloc[0]
    assert metres["Area (m2)"] == 850.0
    assert metres["Area (source)"] == 850.0
    assert metres["Area type (source)"] == "M"


def test_old_area_column_names_are_gone(extract_mod):
    """The clean break means the ambiguous names must not survive."""
    df = extract_mod.create_and_clean_dataframe([_record()])
    assert "Area" not in df.columns
    assert "Area type" not in df.columns


def test_area_conversion_invariant_holds(extract_mod):
    """Area (m2) is always derivable from Area (source) and the type."""
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": str(i), "Dealing number": f"D{i}",
                   "Area": area, "Area type": kind})
        for i, (area, kind) in enumerate([("3.5", "H"), ("0.25", "H"),
                                          ("850", "M"), ("379.8", "M")])
    ])
    hect = df["Area type (source)"] == "H"
    assert (df.loc[hect, "Area (m2)"] == df.loc[hect, "Area (source)"] * 10000).all()
    assert (df.loc[~hect, "Area (m2)"] == df.loc[~hect, "Area (source)"]).all()


# ------------------------------------------------------- 2.2 Integer types ---

def test_price_and_postcode_are_nullable_integers(extract_mod):
    """
    100% of prices and postcodes carried a '.0' before v2 - '2481.0' won't
    join against a postcode lookup and looks broken in a spreadsheet.
    """
    df = extract_mod.create_and_clean_dataframe([_record()])
    assert df["Purchase price"].dtype == "Int64"
    assert df["Property post code"].dtype == "Int64"
    assert df["Strata lot number"].dtype == "Int64"


def test_integer_columns_write_without_decimal_point(extract_mod, tmp_path):
    """
    The artefact is a formatting one, so assert on the written file.

    The second record is what makes this bite: pd.to_numeric only falls back to
    float64 - and so only writes '.0' - when the column contains a null
    somewhere. One clean row would give int64 and quietly pass either way.
    """
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": "1", "Dealing number": "D1",
                   "Property post code": "2481", "Purchase price": "670000",
                   "Strata lot number": "3"}),
        _record(**{"Property ID": "2", "Dealing number": "D2",
                   "Property post code": "", "Purchase price": "",
                   "Strata lot number": ""}),
    ])
    out = tmp_path / "out.csv"
    df.to_csv(out, index=False)
    text = out.read_text()
    assert "2481.0" not in text
    assert "670000.0" not in text
    assert "2481" in text and "670000" in text


def test_integer_columns_still_allow_nulls(extract_mod):
    """Int64 rather than int precisely so a missing postcode stays missing."""
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property post code": "", "Strata lot number": None})
    ])
    assert pd.isna(df["Property post code"].iloc[0])
    assert pd.isna(df["Strata lot number"].iloc[0])


def test_area_keeps_its_real_decimals(extract_mod):
    """
    Area is NOT an integer - 2,728,419 rows have genuine decimals. Rounding
    them to satisfy a formatting preference would destroy real precision.
    """
    df = extract_mod.create_and_clean_dataframe([_record(**{"Area": "379.8"})])
    assert df["Area (m2)"].iloc[0] == pytest.approx(379.8)


# --------------------------------------------------------------- 2.3 Casing ---

def test_mc_names_are_capitalised(extract_mod):
    """.str.title() turns MCMAHONS into Mcmahons. 52,906 rows affected."""
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property street name": "MCEVOY ST",
                   "Property locality": "MCMAHONS POINT",
                   "Property name": "MCGRATHS HILL FARM"})
    ])
    row = df.iloc[0]
    assert row["Property street name"] == "McEvoy St"
    assert row["Property locality"] == "McMahons Point"
    assert row["Property name"] == "McGraths Hill Farm"


def test_mac_names_are_left_alone(extract_mod):
    """
    The deliberate asymmetry. In NSW the Mac names are correctly lowercase -
    Macquarie, Mackerel, Macleay, Macdonald. A symmetric rule would corrupt
    83,452 locality rows to fix none.
    """
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": "1", "Dealing number": "D1",
                   "Property street name": "MACLEAY ST",
                   "Property locality": "LAKE MACQUARIE"}),
        _record(**{"Property ID": "2", "Dealing number": "D2",
                   "Property street name": "MACQUARIE ST",
                   "Property locality": "GREAT MACKEREL BEACH"}),
        _record(**{"Property ID": "3", "Dealing number": "D3",
                   "Property street name": "MACDONALD RD",
                   "Property locality": "CENTRAL MACDONALD"}),
    ])
    assert list(df.sort_values("Property ID")["Property street name"]) == [
        "Macleay St", "Macquarie St", "Macdonald Rd"]
    assert list(df.sort_values("Property ID")["Property locality"]) == [
        "Lake Macquarie", "Great Mackerel Beach", "Central Macdonald"]


def test_possessive_apostrophe_stays_lowercase(extract_mod):
    """.str.title() capitalises after an apostrophe: BENNY'S -> Benny'S."""
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property street name": "SHANAHAN'S RD",
                   "Property locality": "DYER'S CROSSING"})
    ])
    row = df.iloc[0]
    assert row["Property street name"] == "Shanahan's Rd"
    assert row["Property locality"] == "Dyer's Crossing"


def test_irish_names_survive_the_apostrophe_rule(extract_mod):
    """
    O'Sullivan looks like it should be caught by the 'S rule but isn't - the
    word boundary requires the S to end the word, and here it's followed by 'u'.
    1,642 rows in the real corpus depend on this.
    """
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": "1", "Dealing number": "D1",
                   "Property street name": "O'SULLIVAN RD",
                   "Property locality": "O'CONNELL"}),
        _record(**{"Property ID": "2", "Dealing number": "D2",
                   "Property street name": "O'SHEA CCT",
                   "Property locality": "BRIGHTON-LE-SANDS"}),
    ])
    assert list(df.sort_values("Property ID")["Property street name"]) == [
        "O'Sullivan Rd", "O'Shea Cct"]
    assert list(df.sort_values("Property ID")["Property locality"]) == [
        "O'Connell", "Brighton-Le-Sands"]


# ------------------------------------------------- 2.4 Decoded companions ---

def test_nature_of_property_is_decoded(extract_mod):
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": "1", "Dealing number": "D1", "Nature of property": "R"}),
        _record(**{"Property ID": "2", "Dealing number": "D2", "Nature of property": "V"}),
        _record(**{"Property ID": "3", "Dealing number": "D3", "Nature of property": "3"}),
    ])
    got = dict(zip(df["Property ID"], df["Nature of property (description)"]))
    assert got == {"1": "Residence", "2": "Vacant land", "3": "Other"}
    # the raw code is kept so our reading can always be checked
    assert set(df["Nature of property"]) == {"R", "V", "3"}


def test_primary_purpose_is_normalised(extract_mod):
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": str(i), "Dealing number": f"D{i}",
                   "Primary purpose": purpose})
        for i, purpose in enumerate([
            "RESIDENCE", "HOME UNIT", "VACANT LAND", "COMMERCIAL OFF",
            "FARM LAND", "WAREHOUSE", "CARSPACE",
        ])
    ])
    got = list(df.sort_values("Property ID", key=lambda s: s.astype(int))
                 ["Primary purpose (normalised)"])
    assert got == ["Residence", "Residence", "Vacant land", "Commercial",
                   "Rural", "Industrial", "Car space"]


def test_primary_purpose_specific_categories_beat_general_ones(extract_mod):
    """
    The ordering trap. Matching the keyword 'unit' for Residence first files
    'Factory Unit' and 'Storage Unit' as housing - 4,688 rows in the real
    corpus. Specific categories must be tested before general ones.
    """
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": str(i), "Dealing number": f"D{i}",
                   "Primary purpose": purpose})
        for i, purpose in enumerate([
            "FACTORY UNIT", "STORAGE UNIT", "INDUSTRIAL UNI",
            "OFFICE UNIT", "COMMERCIAL UNI", "HOME UNIT",
        ])
    ])
    got = list(df.sort_values("Property ID", key=lambda s: s.astype(int))
                 ["Primary purpose (normalised)"])
    assert got == ["Industrial", "Industrial", "Industrial",
                   "Commercial", "Commercial", "Residence"]


def test_unrecognised_purpose_is_unclassified_not_guessed(extract_mod):
    """0.55% of populated rows don't match any rule. Say so rather than guess."""
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Primary purpose": "KEG ROLL"})
    ])
    assert df["Primary purpose (normalised)"].iloc[0] == "Unclassified"


def test_absent_purpose_is_null_not_unclassified(extract_mod):
    """
    "The source said nothing" is a different fact from "the source said
    something we could not categorise", and only the second is Unclassified.
    85,110 rows have an empty purpose; 5,280 more carry the literal word 'Null'.
    """
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": "1", "Dealing number": "D1",
                   "Primary purpose": ""}),
        _record(**{"Property ID": "2", "Dealing number": "D2",
                   "Primary purpose": "NULL"}),
    ])
    assert df["Primary purpose (normalised)"].isna().all()


def test_original_purpose_text_is_preserved(extract_mod):
    """Normalisation is a companion column; it never overwrites the source."""
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Primary purpose": "COMMERCIAL OFF"})
    ])
    assert df["Primary purpose"].iloc[0] == "Commercial Off"
    assert df["Primary purpose (normalised)"].iloc[0] == "Commercial"


def test_no_decoded_zoning_column_exists(extract_mod):
    """
    Deliberate omission, guarded. The 2022 Employment Zones Reform recycled
    codes - E1 was National Parks, then Local Centre. A code-only lookup would
    label shopfronts as national parks. See Plan-Claude.md 2.4.
    """
    df = extract_mod.create_and_clean_dataframe([_record()])
    assert "Zoning (description)" not in df.columns
    assert "Zoning (normalised)" not in df.columns
    assert df["Zoning"].iloc[0] == "R2"


def test_archived_rows_get_null_decoded_columns(extract_mod):
    """Pre-2001 records carry neither source field; null is the honest answer."""
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Nature of property": None, "Primary purpose": None,
                   "Dealing number": None})
    ])
    assert pd.isna(df["Nature of property (description)"].iloc[0])
    assert pd.isna(df["Primary purpose (normalised)"].iloc[0])


# ---------------------------------------------------------------- 2.5 Flags ---

def test_part_interest_flag(extract_mod):
    """
    Null means 100% in the source - the most-missed trap in this dataset.
    35,691 part-share sales have a median price of $206,000 against $360,000.
    """
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": "1", "Dealing number": "D1",
                   "% Interest of sale": "50"}),
        _record(**{"Property ID": "2", "Dealing number": "D2",
                   "% Interest of sale": None}),
    ])
    got = dict(zip(df["Property ID"], df["Part interest flag"]))
    assert got == {"1": True, "2": False}


def test_non_market_price_flag(extract_mod):
    """52,280 rows are $0 - family transfers, government acquisitions."""
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": str(i), "Dealing number": f"D{i}",
                   "Purchase price": price})
        for i, price in enumerate(["0", "1", "999", "1000", "750000", ""])
    ])
    got = list(df.sort_values("Property ID", key=lambda s: s.astype(int))
                 ["Non-market price flag"])
    assert got == [True, True, True, False, False, True]


def test_date_error_flag(extract_mod):
    """933 real rows settle before they are contracted, which is impossible."""
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": "1", "Dealing number": "D1",
                   "Contract date": "20200601", "Settlement date": "20200501"}),
        _record(**{"Property ID": "2", "Dealing number": "D2",
                   "Contract date": "20200501", "Settlement date": "20200601"}),
        # a missing settlement date is not an error
        _record(**{"Property ID": "3", "Dealing number": "D3",
                   "Contract date": "20200501", "Settlement date": ""}),
    ])
    got = dict(zip(df["Property ID"], df["Date error flag"]))
    assert got == {"1": True, "2": False, "3": False}


def test_flags_never_drop_rows(extract_mod):
    """
    The pipeline describes the data; it does not decide what counts as a real
    sale. Every flagged row must still be in the output.
    """
    records = [
        _record(**{"Property ID": "1", "Dealing number": "D1", "Purchase price": "0"}),
        _record(**{"Property ID": "2", "Dealing number": "D2", "% Interest of sale": "50"}),
        _record(**{"Property ID": "3", "Dealing number": "D3",
                   "Contract date": "20200601", "Settlement date": "20200501"}),
        _record(**{"Property ID": "4", "Dealing number": "D4"}),
    ]
    df = extract_mod.create_and_clean_dataframe(records)
    assert len(df) == 4
    assert set(df["Property ID"]) == {"1", "2", "3", "4"}


def test_flag_columns_are_boolean_not_nullable(extract_mod):
    """A flag is a yes or a no; there is no third state to represent."""
    df = extract_mod.create_and_clean_dataframe([_record()])
    for column in ["Part interest flag", "Non-market price flag", "Date error flag"]:
        assert df[column].dtype == bool, column


# --------------------------------------------------------------- Schema v2 ---

EXPECTED_COLUMNS = [
    "District code", "Property ID", "Valuation number", "Sale counter",
    "Download date / time",
    "Property name", "Property unit number", "Property house number",
    "Property street name", "Property locality", "Property post code",
    "Area (m2)", "Area (source)", "Area type (source)", "Dimensions",
    "Contract date", "Settlement date", "Purchase price", "Zoning",
    "Nature of property", "Nature of property (description)",
    "Primary purpose", "Primary purpose (normalised)", "Strata lot number",
    "Component code", "Sale code", "% Interest of sale",
    "Dealing number", "Parcels in sale", "Property legal description",
    "Part interest flag", "Non-market price flag", "Date error flag",
]


def test_output_matches_the_v2_column_contract(extract_mod):
    """
    33 columns in a fixed order. Nothing from v1 was removed - three columns
    were renamed and six added.
    """
    df = extract_mod.create_and_clean_dataframe([_record()])
    assert list(df.columns) == EXPECTED_COLUMNS
    assert len(df.columns) == 33


def test_download_timestamp_is_a_real_datetime(extract_mod):
    """
    The review's proposed schema said "parse to a real timestamp", and it was
    missed in the first pass. It shipped as the source's raw 'CCYYMMDD HH24:MI'
    text sitting next to two ISO date columns, so every consumer had to parse it
    by hand - analysis.ipynb and the publish gate both did exactly that.
    """
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Download date / time": "20010719 11:27"})
    ])
    value = df["Download date / time"].iloc[0]
    assert isinstance(value, pd.Timestamp)
    assert value == pd.Timestamp("2001-07-19 11:27")


def test_unparseable_download_timestamp_becomes_null(extract_mod):
    """Pre-2001 archived records carry no download timestamp at all."""
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": "1", "Dealing number": "D1",
                   "Download date / time": ""}),
        _record(**{"Property ID": "2", "Dealing number": "D2",
                   "Download date / time": "not a date"}),
    ])
    assert df["Download date / time"].isna().all()


def test_dedup_still_keeps_the_newest_after_the_timestamp_change(extract_mod):
    """
    The dedup sort orders on this column. It used to rely on the raw text
    sorting correctly as a string; this proves the datetime version still picks
    the most recently published version of a restated sale.
    """
    df = extract_mod.create_and_clean_dataframe([
        _record(**{"Property ID": "1", "Dealing number": "SAME",
                   "Download date / time": "20200101 01:00",
                   "Purchase price": "500000"}),
        _record(**{"Property ID": "1", "Dealing number": "SAME",
                   "Download date / time": "20200208 01:00",
                   "Purchase price": "600000"}),
    ])
    assert len(df) == 1
    assert df["Purchase price"].iloc[0] == 600000
