import pytest
import pandas as pd
from datetime import datetime, timedelta

def test_hectare_to_square_metres_conversion(extract_mod):
    records = [
        {
            "District code": "077",
            "Property ID": "1001",
            "Sale counter": "1",
            "Download date / time": "20200101",
            "Property name": "RANCH",
            "Property unit number": None,
            "Property house number": "1",
            "Property street name": "VALLEY ROAD",
            "Property locality": "SPRINGWOOD",
            "Property post code": "2777",
            "Area": "3.5",
            "Area type": "H", # Hectares
            "Contract date": "20200115",
            "Settlement date": "20200215",
            "Purchase price": "1500000",
            "Zoning": "RU2",
            "Nature of property": "R",
            "Primary purpose": "RESIDENCE",
            "Strata lot number": None,
            "Dealing number": "AB123",
            "Property legal description": "LOT 1 DP 1"
        },
        {
            "District code": "077",
            "Property ID": "1002",
            "Sale counter": "1",
            "Download date / time": "20200101",
            "Property name": None,
            "Property unit number": None,
            "Property house number": "2",
            "Property street name": "VALLEY ROAD",
            "Property locality": "SPRINGWOOD",
            "Property post code": "2777",
            "Area": "850",
            "Area type": "M", # Square metres
            "Contract date": "20200115",
            "Settlement date": "20200215",
            "Purchase price": "800000",
            "Zoning": "R2",
            "Nature of property": "R",
            "Primary purpose": "RESIDENCE",
            "Strata lot number": None,
            "Dealing number": "AB124",
            "Property legal description": "LOT 2 DP 1"
        }
    ]
    
    df = extract_mod.create_and_clean_dataframe(records)
    assert len(df) == 2
    # 3.5 Hectares -> 35000 m²
    assert df.loc[df['Property ID'] == '1001', 'Area (m2)'].iloc[0] == 35000.0
    # 850 m² -> 850 m²
    assert df.loc[df['Property ID'] == '1002', 'Area (m2)'].iloc[0] == 850.0

def test_string_title_casing(extract_mod):
    records = [{
        "District code": "077",
        "Property ID": "1001",
        "Sale counter": "1",
        "Download date / time": "20200101",
        "Property name": "THE GRAND MANOR",
        "Property unit number": None,
        "Property house number": "10",
        "Property street name": "GREAT WESTERN HIGHWAY",
        "Property locality": "BLUE MOUNTAINS",
        "Property post code": "2777",
        "Area": "1000",
        "Area type": "M",
        "Contract date": "20200115",
        "Settlement date": "20200215",
        "Purchase price": "900000",
        "Zoning": "R2",
        "Nature of property": "R",
        "Primary purpose": "SINGLE DWELLING",
        "Strata lot number": None,
        "Dealing number": "AB123",
        "Property legal description": "LOT 1 DP 1"
    }]
    
    df = extract_mod.create_and_clean_dataframe(records)
    assert df['Property name'].iloc[0] == "The Grand Manor"
    assert df['Property street name'].iloc[0] == "Great Western Highway"
    assert df['Property locality'].iloc[0] == "Blue Mountains"
    assert df['Primary purpose'].iloc[0] == "Single Dwelling"

def test_future_date_filtering(extract_mod):
    future_date = (datetime.today() + timedelta(days=365)).strftime("%Y%m%d")
    records = [
        {
            "District code": "077",
            "Property ID": "FUTURE_PROP",
            "Sale counter": "1",
            "Download date / time": "20200101",
            "Property name": None,
            "Property unit number": None,
            "Property house number": "1",
            "Property street name": "ROAD",
            "Property locality": "LOCALITY",
            "Property post code": "2000",
            "Area": "500",
            "Area type": "M",
            "Contract date": future_date,
            "Settlement date": future_date,
            "Purchase price": "500000",
            "Zoning": "R2",
            "Nature of property": "R",
            "Primary purpose": "RESIDENCE",
            "Strata lot number": None,
            "Dealing number": "AB1",
            "Property legal description": None
        },
        {
            "District code": "077",
            "Property ID": "VALID_PROP",
            "Sale counter": "1",
            "Download date / time": "20200101",
            "Property name": None,
            "Property unit number": None,
            "Property house number": "2",
            "Property street name": "ROAD",
            "Property locality": "LOCALITY",
            "Property post code": "2000",
            "Area": "500",
            "Area type": "M",
            "Contract date": "20210501",
            "Settlement date": "20210601",
            "Purchase price": "600000",
            "Zoning": "R2",
            "Nature of property": "R",
            "Primary purpose": "RESIDENCE",
            "Strata lot number": None,
            "Dealing number": "AB2",
            "Property legal description": None
        }
    ]
    df = extract_mod.create_and_clean_dataframe(records)
    assert len(df) == 2
    
    # Check that FUTURE_PROP was kept but dates are NaT
    future_prop_row = df[df['Property ID'] == "FUTURE_PROP"].iloc[0]
    assert pd.isna(future_prop_row['Contract date'])
    assert pd.isna(future_prop_row['Settlement date'])
    
    # Check that VALID_PROP dates are untouched
    valid_prop_row = df[df['Property ID'] == "VALID_PROP"].iloc[0]
    assert not pd.isna(valid_prop_row['Contract date'])
    assert not pd.isna(valid_prop_row['Settlement date'])

def test_pre_1990_date_filtering(extract_mod):
    records = [
        {
            "District code": "077",
            "Property ID": "OLD_PROP",
            "Sale counter": "1",
            "Download date / time": "20200101",
            "Property name": None,
            "Property unit number": None,
            "Property house number": "1",
            "Property street name": "ROAD",
            "Property locality": "LOCALITY",
            "Property post code": "2000",
            "Area": "500",
            "Area type": "M",
            "Contract date": "19850101", # Pre-1990
            "Settlement date": "19890101", # Pre-1990
            "Purchase price": "50000",
            "Zoning": "R2",
            "Nature of property": "R",
            "Primary purpose": "RESIDENCE",
            "Strata lot number": None,
            "Dealing number": "AB1",
            "Property legal description": None
        },
        {
            "District code": "077",
            "Property ID": "VALID_PROP",
            "Sale counter": "1",
            "Download date / time": "20200101",
            "Property name": None,
            "Property unit number": None,
            "Property house number": "2",
            "Property street name": "ROAD",
            "Property locality": "LOCALITY",
            "Property post code": "2000",
            "Area": "500",
            "Area type": "M",
            "Contract date": "20200101", # Valid
            "Settlement date": "20200201", # Valid
            "Purchase price": "60000",
            "Zoning": "R2",
            "Nature of property": "R",
            "Primary purpose": "RESIDENCE",
            "Strata lot number": None,
            "Dealing number": "AB2",
            "Property legal description": None
        }
    ]
    df = extract_mod.create_and_clean_dataframe(records)
    assert len(df) == 2
    
    # Check that OLD_PROP was kept but dates are NaT
    old_prop_row = df[df['Property ID'] == "OLD_PROP"].iloc[0]
    assert pd.isna(old_prop_row['Contract date'])
    assert pd.isna(old_prop_row['Settlement date'])
    
    # Check that VALID_PROP dates are untouched
    valid_prop_row = df[df['Property ID'] == "VALID_PROP"].iloc[0]
    assert not pd.isna(valid_prop_row['Contract date'])
    assert not pd.isna(valid_prop_row['Settlement date'])

def test_empty_records_returns_empty_dataframe(extract_mod):
    df = extract_mod.create_and_clean_dataframe([])
    assert isinstance(df, pd.DataFrame)
    assert df.empty
