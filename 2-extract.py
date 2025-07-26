import logging
import os
import io
import zipfile
import csv
import pandas as pd
import time
from datetime import datetime

# --- Constants ---
DATA_DIR = "./data"
FINAL_CSV_PATH = "property_sales_data.csv"
LOG_FILE_PATH = "propsales.log"
# --- Filtering Controls ---
# Set to True to remove records with contract dates in the future
FILTER_FUTURE_DATES = True
# Set to True to remove records with contract dates before EARLIEST_DATE
FILTER_PRE_1990_DATES = True
EARLIEST_DATE = '1990-01-01'


# --- Configure logging ---
# Set up logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)

def extract_dat_lines_from_zip(zip_filepath):
    """
    Extracts all lines from .dat files found within a zip archive,
    including those in nested zip files.

    Args:
        zip_filepath (str): The path to the zip file.

    Returns:
        list: A list of strings, where each string is a line from a .dat file.
    """
    dat_lines = []
    try:
        with zipfile.ZipFile(zip_filepath, 'r') as zip_file:
            for file_info in zip_file.namelist():
                # Process .dat files at the top level
                if file_info.lower().endswith(".dat"):
                    try:
                        content = zip_file.read(file_info).decode("utf-8")
                        dat_lines.extend(content.splitlines())
                    except UnicodeDecodeError:
                        logging.warning(f"Skipping file with encoding issues in {zip_filepath}: {file_info}")
                # Process .dat files within nested zips
                elif file_info.lower().endswith(".zip"):
                    with zip_file.open(file_info) as inner_zip_file:
                        with zipfile.ZipFile(io.BytesIO(inner_zip_file.read())) as inner_zip:
                            for inner_file_info in inner_zip.namelist():
                                if inner_file_info.lower().endswith(".dat"):
                                    try:
                                        content = inner_zip.read(inner_file_info).decode("utf-8")
                                        dat_lines.extend(content.splitlines())
                                    except UnicodeDecodeError:
                                        logging.warning(f"Skipping file with encoding issues in nested zip {file_info}: {inner_file_info}")
    except FileNotFoundError:
        logging.error(f"File not found: {zip_filepath}")
    except zipfile.BadZipFile:
        logging.error(f"Bad zip file: {zip_filepath}")
    return dat_lines

def parse_data_lines(lines):
    """
    Parses a list of raw data lines, identifying and processing both current
    and archived formats.

    Args:
        lines (list): A list of strings from the .dat files.

    Returns:
        list: A list of dictionaries, where each dictionary represents a processed record.
    """
    processed_records = []
    legal_descriptions = {} # For matching 'C' records to 'B' records in current format

    # First pass: Collect all legal descriptions from 'C' records
    for line in lines:
        if line.startswith("C;"):
            parts = line.split(";")
            if len(parts) >= 6:
                # Create a unique key for the C record based on its identifying parts
                key = (parts[1], parts[2], parts[3]) # District, Property ID, Sale counter
                legal_descriptions[key] = parts[5].strip()

    # Second pass: Process 'B' records and add legal descriptions
    for line in lines:
        if not line.startswith("B;"):
            continue

        parts = [p.strip() for p in line.split(";")]
        
        # Heuristic to differentiate between formats:
        # The archived format has a source like 'ARCHIVE' or 'VALNET1' in the 3rd field.
        # The current format has a numeric Property ID.
        is_archived = len(parts) > 2 and parts[2].isalpha()

        record = None
        if is_archived:
            record = parse_archived_record(parts)
        else:
            record = parse_current_record(parts)
            if record:
                # Match legal description for current format records
                key = (record.get("District code"), record.get("Property ID"), record.get("Sale counter"))
                if key in legal_descriptions:
                    record["Property legal description"] = legal_descriptions[key]
        
        if record:
            processed_records.append(record)

    return processed_records

def parse_current_record(parts):
    """Parses a 'B' record from the current data format."""
    if len(parts) < 25:
        return None
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
        "Dealing number": parts[23],
        "Property legal description": None # To be filled in later
    }

def parse_archived_record(parts):
    """Parses a 'B' record from the archived data format."""
    if len(parts) < 18:
        return None
    
    # As noted, archived dates are DD/MM/YYYY. We convert them to YYYYMMDD for consistency.
    contract_date_str = ""
    try:
        # Handles 'dd/mm/yyyy'
        contract_date = datetime.strptime(parts[10], "%d/%m/%Y")
        contract_date_str = contract_date.strftime("%Y%m%d")
    except ValueError:
        # Handles 'CCYYMMDD' if it appears in archived data, or invalid formats
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
        "Settlement date": None, # Not available in archived format
        "Purchase price": parts[11],
        "Zoning": parts[17],
        "Nature of property": None,
        "Primary purpose": None,
        "Strata lot number": None,
        "Dealing number": None,
        "Property legal description": parts[12]
    }

def create_and_clean_dataframe(records):
    """
    Creates and cleans a pandas DataFrame from a list of records.

    Args:
        records (list): A list of dictionaries representing parsed records.

    Returns:
        pandas.DataFrame: A cleaned and processed DataFrame.
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # --- Data Type Conversion and Cleaning ---
    
    # Convert date columns, coercing errors to NaT (Not a Time)
    df['Contract date'] = pd.to_datetime(df['Contract date'], format='%Y%m%d', errors='coerce')
    df['Settlement date'] = pd.to_datetime(df['Settlement date'], format='%Y%m%d', errors='coerce')

    # Convert numeric columns, coercing errors to NaN (Not a Number)
    numeric_cols = ['Purchase price', 'Area', 'Property post code']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # --- Data Transformation ---

    # Remove records with a future contract date if enabled
    if FILTER_FUTURE_DATES:
        today = pd.to_datetime('today').normalize() # Get today's date with time set to 00:00:00
        original_count = len(df)
        df = df[df['Contract date'] <= today]
        removed_count = original_count - len(df)
        if removed_count > 0:
            logging.info(f"Removed {removed_count} records with future contract dates.")

    # Remove records with a contract date before EARLIEST_DATE if enabled
    if FILTER_PRE_1990_DATES:
        earliest_date = pd.to_datetime(EARLIEST_DATE).normalize()
        original_count = len(df)
        # Keep rows where the date is >= earliest_date OR where the date is NaT (not a time/null)
        df = df[(df['Contract date'] >= earliest_date) | (df['Contract date'].isna())]
        removed_count = original_count - len(df)
        if removed_count > 0:
            logging.info(f"Removed {removed_count} records with contract dates before {EARLIEST_DATE}.")

    # Adjust area for Hectares (H) to square meters
    # Ensure 'Area' is numeric before performing calculation
    df.loc[df['Area type'] == 'H', 'Area'] = df['Area'] * 10000

    # Capitalize string fields for consistency
    string_cols = ['Property name', 'Property street name', 'Property locality', 'Primary purpose']
    for col in string_cols:
        df[col] = df[col].str.title()
        
    # Reorder columns for final output
    final_columns = [
        "Property ID", "Sale counter", "Download date / time", "Property name", 
        "Property unit number", "Property house number", "Property street name", 
        "Property locality", "Property post code", "Area", "Area type", 
        "Contract date", "Settlement date", "Purchase price", "Zoning", 
        "Nature of property", "Primary purpose", "Strata lot number", 
        "Dealing number", "Property legal description"
    ]
    # Ensure all final columns exist, filling missing ones with None
    for col in final_columns:
        if col not in df.columns:
            df[col] = None
            
    return df[final_columns]

def main():
    """Main function to orchestrate the data extraction, processing, and export."""
    start_time = time.time()
    logging.info('Start: Extracting and processing data.')

    # 1. Extraction
    all_dat_lines = []
    for file_name in os.listdir(DATA_DIR):
        if file_name.lower().endswith(".zip"):
            zip_filepath = os.path.join(DATA_DIR, file_name)
            logging.info(f"Extracting from: {zip_filepath}")
            all_dat_lines.extend(extract_dat_lines_from_zip(zip_filepath))
    
    logging.info(f"Extraction complete. Found {len(all_dat_lines)} total lines.")
    logging.info(f"{int(time.time() - start_time)} seconds elapsed.")

    # 2. Parsing
    logging.info("Begin: Parsing raw data lines.")
    processed_records = parse_data_lines(all_dat_lines)
    logging.info(f"Parsing complete. Found {len(processed_records)} property records.")
    logging.info(f"{int(time.time() - start_time)} seconds elapsed.")

    # 3. DataFrame Creation and Cleaning
    logging.info("Begin: Creating and cleaning DataFrame.")
    df = create_and_clean_dataframe(processed_records)
    logging.info("DataFrame processing complete.")
    logging.info(f"{int(time.time() - start_time)} seconds elapsed.")

    # 4. Exporting to CSV
    if not df.empty:
        logging.info(f"Begin: Exporting {len(df)} records to {FINAL_CSV_PATH}")
        df.to_csv(FINAL_CSV_PATH, index=False, quoting=csv.QUOTE_ALL)
    else:
        logging.warning("No data to export; the final CSV file will not be created.")

    logging.info("Complete: Data has been extracted and processed.")
    logging.info(f"Total elapsed time was {int(time.time() - start_time)} seconds.")

if __name__ == "__main__":
    main()
