import pytest

def test_parse_modern_record(extract_mod, sample_modern_b_line):
    parts = [p.strip() for p in sample_modern_b_line.split(";")]
    record = extract_mod.parse_current_record(parts)
    
    assert record is not None
    assert record["District code"] == "077"
    assert record["Property ID"] == "2885891"
    assert record["Sale counter"] == "1"
    assert record["Property house number"] == "91"
    assert record["Property street name"] == "ADAMS ST"
    assert record["Property locality"] == "HEDDON GRETA"
    assert record["Property post code"] == "2321"
    assert record["Area"] == "1150"
    assert record["Area type"] == "M"
    assert record["Contract date"] == "20161024"
    assert record["Settlement date"] == "20161121"
    assert record["Purchase price"] == "250000"
    assert record["Zoning"] == "R2"
    assert record["Nature of property"] == "R"
    assert record["Primary purpose"] == "RESIDENCE"
    assert record["Dealing number"] == "AK123456"
    assert record["Property legal description"] is None

def test_parse_modern_record_too_short(extract_mod):
    short_line = "B;077;2885891;1;20170102;"
    parts = [p.strip() for p in short_line.split(";")]
    assert extract_mod.parse_current_record(parts) is None

def test_parse_archived_record_dmy(extract_mod, sample_archived_b_line):
    parts = [p.strip() for p in sample_archived_b_line.split(";")]
    record = extract_mod.parse_archived_record(parts)
    
    assert record is not None
    assert record["District code"] == "011"
    assert record["Property ID"] == "292674"
    assert record["Property street name"] == "ELDON ST"
    assert record["Property locality"] == "ABERDEEN"
    assert record["Property post code"] == "2336"
    # Date converted from 20/11/1990 to 19901120
    assert record["Contract date"] == "19901120"
    assert record["Purchase price"] == "145000"
    assert record["Property legal description"] == "LOT 7 SEC 1 DP 1234"
    assert record["Area"] == "2365"
    assert record["Area type"] == "M"
    assert record["Zoning"] == "A"

def test_parse_archived_record_ccyymmdd(extract_mod, sample_archived_b_line_ccyymmdd):
    parts = [p.strip() for p in sample_archived_b_line_ccyymmdd.split(";")]
    record = extract_mod.parse_archived_record(parts)
    
    assert record is not None
    assert record["District code"] == "011"
    assert record["Property ID"] == "292704"
    assert record["Contract date"] == "19901122"
    assert record["Zoning"] == "R"

def test_parse_archived_record_too_short(extract_mod):
    short_line = "B;011;ARCHIVE;123;"
    parts = [p.strip() for p in short_line.split(";")]
    assert extract_mod.parse_archived_record(parts) is None

def test_parse_data_lines_joins_multiple_c_records(extract_mod, sample_modern_b_line, sample_modern_c_lines):
    # Pass A header, B record, multiple C records, D owner record, and Z trailer
    lines = [
        "A;RTSALEDATA;077;20170102 01:00;USER1;",
        sample_modern_b_line,
        sample_modern_c_lines[0],
        sample_modern_c_lines[1],
        "D;077;2885891;1;20170102 01:00;P;;;;;;;",
        "Z;5;1;2;1;"
    ]
    
    records = extract_mod.parse_data_lines(lines)
    assert len(records) == 1
    # Both C records concatenated without spaces per Valuer General specification
    assert records[0]["Property legal description"] == "LOT 1 DP 123456 / SEC A"

def test_parse_data_lines_mixed_modern_and_archived(extract_mod, sample_modern_b_line, sample_archived_b_line):
    lines = [
        sample_modern_b_line,
        sample_archived_b_line
    ]
    records = extract_mod.parse_data_lines(lines)
    assert len(records) == 2
    assert records[0]["Property ID"] == "2885891"
    assert records[1]["Property ID"] == "292674"
