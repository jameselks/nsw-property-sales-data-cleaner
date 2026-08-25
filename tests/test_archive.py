import os
import shutil
import zipfile
from datetime import datetime
import pytest

def test_archive_process(tmp_path, monkeypatch):
    # Set current working directory to tmp_path for the test
    monkeypatch.chdir(tmp_path)
    
    test_csv = "extract-3-very-clean.csv"
    with open(test_csv, "w", encoding="utf-8") as f:
        f.write("Property ID,Contract date,Purchase price\n101,2023-01-01,500000\n")
    
    # Import and run the packaging half of 3-publish.py
    from conftest import load_module
    publish_mod = load_module("publish_test_mod", "3-publish.py")
    publish_mod.create_archives()
    
    dated_zip = f"nsw-property-sales-data-updated{datetime.now().strftime('%Y%m%d')}.zip"
    
    # Verify outputs
    assert os.path.exists(test_csv), "Source CSV must remain intact after archiving"
    assert os.path.exists(dated_zip), f"Expected {dated_zip} to exist"
    assert os.path.exists("archive.zip"), "Expected archive.zip to exist"
    
    # Verify zip content
    expected_entry = f"nsw-property-sales-data-updated{datetime.now().strftime('%Y%m%d')}.csv"
    with zipfile.ZipFile(dated_zip, "r") as zf:
        assert expected_entry in zf.namelist()
        
    with zipfile.ZipFile("archive.zip", "r") as zf:
        assert expected_entry in zf.namelist()
