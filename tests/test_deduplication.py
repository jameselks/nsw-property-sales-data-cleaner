import pytest

def test_deduplication_exact_duplicate_sales(extract_mod):
    # Simulates a record present in both yearly and weekly zips
    records = [
        {
            "District code": "077",
            "Property ID": "55555",
            "Sale counter": "1",
            "Download date / time": "20230101",
            "Property name": None,
            "Property unit number": None,
            "Property house number": "15",
            "Property street name": "HIGH STREET",
            "Property locality": "SPRINGWOOD",
            "Property post code": "2777",
            "Area": "600",
            "Area type": "M",
            "Contract date": "20221010",
            "Settlement date": "20221110",
            "Purchase price": "750000",
            "Zoning": "R2",
            "Nature of property": "R",
            "Primary purpose": "RESIDENCE",
            "Strata lot number": None,
            "Dealing number": "AB111",
            "Property legal description": "LOT 1 DP 100"
        },
        # Overlapping record with newer download date but identical transaction
        {
            "District code": "077",
            "Property ID": "55555",
            "Sale counter": "1",
            "Download date / time": "20230108",
            "Property name": None,
            "Property unit number": None,
            "Property house number": "15",
            "Property street name": "HIGH STREET",
            "Property locality": "SPRINGWOOD",
            "Property post code": "2777",
            "Area": "600",
            "Area type": "M",
            "Contract date": "20221010",
            "Settlement date": "20221110",
            "Purchase price": "750000",
            "Zoning": "R2",
            "Nature of property": "R",
            "Primary purpose": "RESIDENCE",
            "Strata lot number": None,
            "Dealing number": "AB111",
            "Property legal description": "LOT 1 DP 100"
        }
    ]
    df = extract_mod.create_and_clean_dataframe(records)
    assert len(df) == 1
    assert df['Property ID'].iloc[0] == "55555"

def test_multiple_sales_of_same_property_preserved(extract_mod):
    # Same property sold in 2015 and again in 2021
    records = [
        {
            "District code": "077",
            "Property ID": "77777",
            "Sale counter": "1",
            "Download date / time": "20150601",
            "Property name": None,
            "Property unit number": None,
            "Property house number": "20",
            "Property street name": "PARK AVE",
            "Property locality": "LAWSON",
            "Property post code": "2783",
            "Area": "700",
            "Area type": "M",
            "Contract date": "20150501",
            "Settlement date": "20150601",
            "Purchase price": "500000",
            "Zoning": "R2",
            "Nature of property": "R",
            "Primary purpose": "RESIDENCE",
            "Strata lot number": None,
            "Dealing number": "AB222",
            "Property legal description": "LOT 2 DP 200"
        },
        {
            "District code": "077",
            "Property ID": "77777",
            "Sale counter": "2",
            "Download date / time": "20210601",
            "Property name": None,
            "Property unit number": None,
            "Property house number": "20",
            "Property street name": "PARK AVE",
            "Property locality": "LAWSON",
            "Property post code": "2783",
            "Area": "700",
            "Area type": "M",
            "Contract date": "20210501",
            "Settlement date": "20210601",
            "Purchase price": "850000",
            "Zoning": "R2",
            "Nature of property": "R",
            "Primary purpose": "RESIDENCE",
            "Strata lot number": None,
            "Dealing number": "AC333",
            "Property legal description": "LOT 2 DP 200"
        }
    ]
    df = extract_mod.create_and_clean_dataframe(records)
    assert len(df) == 2
