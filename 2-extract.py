import logging
import os
import io
import zipfile
import csv
import pandas as pd
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DATA_DIR = "./data"
RAW_FILE_PATH = "extract-1-raw.txt"
CLEAN_FILE_PATH = "extract-2-clean.txt"
FINAL_CSV_PATH = "extract-3-very-clean.csv"

def extract_data_from_zip(zip_filepath):
    """Extracts .dat files from a zip archive, including nested zips."""
    raw_data_lines = []
    try:
        with zipfile.ZipFile(zip_filepath) as zip_file:
            for file_info in zip_file.namelist():
                if file_info.lower().endswith(".dat"):
                    raw_data_lines.append(zip_file.read(file_info).decode("utf-8") + "\n")
                elif file_info.lower().endswith(".zip"):
                    with zipfile.ZipFile(io.BytesIO(zip_file.read(file_info))) as inner_zip:
                        for inner_file_info in inner_zip.namelist():
                            if inner_file_info.lower().endswith(".dat"):
                                raw_data_lines.append(inner_zip.read(inner_file_info).decode("utf-8") + "\n")
                            else:
                                logging.info(f"Ignored inner zip file: {inner_file_info}")
                else:
                    logging.info(f"Ignored file: {file_info}")
    except FileNotFoundError:
        logging.error(f"File not found: {zip_filepath}")
    except zipfile.BadZipFile:
        logging.error(f"Bad zip file: {zip_filepath}")
    return raw_data_lines

def merge_data(raw_data_string):
    """Merges and cleans the extracted raw data."""
    merged_lines = []
    for line in raw_data_string.splitlines():
        if line.startswith("B"):
            merged_lines.append("\n" + line)
        elif line.startswith("C"):
            merged_lines.append(line.split(";")[-2])
    return ''.join(merged_lines)

def process_data(clean_file_path):
    """Processes the cleaned data using pandas."""
    date_converter = lambda x: pd.to_datetime(x, format="%Y%m%d", errors='coerce')
    columns_with_dates = ["Contract date", "Settlement date"]
    column_names = ["Record type", "District code", "Property ID", "Sale counter", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Area type", "Contract date", "Settlement date", "Purchase price", "Zoning", "Nature of property", "Primary purpose", "Strata lot number", "Component code", "Sale code", "% interest of sale", "Dealing number", "Property legal description"]
    include_columns = ["Property ID", "Sale counter", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Area type", "Contract date", "Settlement date", "Purchase price", "Zoning", "Primary purpose", "Strata lot number", "Property legal description"]

    df = pd.read_csv(clean_file_path, delimiter=";", header=None, names=column_names, encoding='utf8', usecols=include_columns, parse_dates=columns_with_dates, quoting=csv.QUOTE_NONE)
    for col in columns_with_dates:
      df[col] = pd.to_datetime(df[col], format="%Y%m%d", errors='coerce')

    # Processing the data
    df.loc[df['Area type'] == "H", 'Area'] = df['Area'] * 10000
    df['Area'] = pd.to_numeric(df['Area'], errors='coerce')
    df['Property post code'] = pd.to_numeric(df['Property post code'], errors='coerce', downcast='float')
    df['Primary purpose'] = df['Primary purpose'].str.capitalize()
    df['Property name'] = df['Property name'].str.title()
    df['Property street name'] = df['Property street name'].str.title()
    df['Property locality'] = df['Property locality'].str.title()

    # Zoning logic removed as it was not working as expected.
    return df

def main():
    start_time = time.time()
    logging.info('Start extracting and processing data')

    # Extraction
    raw_data_lines = []
    for file_name in os.listdir(DATA_DIR):
        if file_name.lower().endswith(".zip"):
            zip_filepath = os.path.join(DATA_DIR, file_name)
            raw_data_lines.extend(extract_data_from_zip(zip_filepath))

    raw_data_string = ''.join(raw_data_lines)
    with open(RAW_FILE_PATH, "w") as raw_file:
        raw_file.write(raw_data_string)

    logging.info(f"{int(time.time() - start_time)} seconds elapsed")
    logging.info("Begin merging the data")

    # Merging
    merged_data_string = merge_data(raw_data_string)
    with open(CLEAN_FILE_PATH, "w") as clean_file:
        clean_file.write(merged_data_string)

    logging.info(f"{int(time.time() - start_time)} seconds elapsed")
    logging.info("Begin processing the data")

    # Processing
    df = process_data(CLEAN_FILE_PATH)

    # Exporting
    logging.info(f"{int(time.time() - start_time)} seconds elapsed")
    logging.info("Begin exporting to CSV")

    export_columns = ["Property ID", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Contract date", "Settlement date", "Purchase price", "Zoning", "Primary purpose", "Strata lot number"]
    df.to_csv(FINAL_CSV_PATH, columns=export_columns, index=False)

    logging.info("Complete: data has been extracted and processed.")
    logging.info(f"Total elapsed time was {int(time.time() - start_time)} seconds")

if __name__ == "__main__":
    main()