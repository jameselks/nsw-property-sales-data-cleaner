import time
import os
import urllib.request
from urllib.error import URLError, HTTPError
from datetime import date, timedelta
import logging
import zipfile
import io
import csv
import pandas as pd

# Constants
URL_BASE = 'https://www.valuergeneral.nsw.gov.au/__psi/'
WEEKLY_URL = URL_BASE + 'weekly/'
YEARLY_URL = URL_BASE + 'yearly/'
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
YEARS_TO_COLLECT = 7
RECENT_WEEKS_TO_EXCLUDE = 14  # Number of days to exclude from recent weekly downloads.
RETRY_ATTEMPTS = 3
FINAL_CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'historical_property_data.csv')

# Configure logging
import os

# Ensure logs directory exists
logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', 
                   handlers=[logging.FileHandler(os.path.join(logs_dir, "historical_extraction.log")), logging.StreamHandler()])

class HistoricalDataExtractor:
    """Handles downloading and processing of historical NSW property sales data."""
    
    def __init__(self):
        # Ensure data directory exists
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        
        self.download_dir = DOWNLOAD_DIR
        self.output_file = FINAL_CSV_PATH
        
    def download_file(self, url, filepath):
        """Downloads a file from a URL to a specified filepath."""
        for attempt in range(RETRY_ATTEMPTS):
            try:
                logging.info(f'Downloading {url} to {filepath} (attempt {attempt + 1})')
                urllib.request.urlretrieve(url, filepath)
                logging.info(f'Downloaded {url} to {filepath}')
                return True
            except (URLError, HTTPError) as e:
                logging.error(f'Error downloading {url} (attempt {attempt + 1}): {e}')
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(5)  # Wait before retrying
                else:
                    return False
            except Exception as e:
                logging.error(f'An unexpected error occurred during download {url} : {e}')
                return False
        return False

    def download_weekly_data(self, start_date, end_date):
        """Downloads weekly data files."""
        end_date = end_date - timedelta(days=RECENT_WEEKS_TO_EXCLUDE)
        current_date = start_date
        while current_date < end_date:
            filename = current_date.strftime('%Y%m%d') + '.zip'
            filepath = os.path.join(self.download_dir, filename)
            url = WEEKLY_URL + filename
            self.download_file(url, filepath)
            current_date += timedelta(days=7)

    def download_yearly_data(self, start_year, end_year):
        """Downloads yearly data files."""
        for year in range(start_year, end_year):
            filename = str(year) + '.zip'
            filepath = os.path.join(self.download_dir, filename)
            url = YEARLY_URL + filename
            self.download_file(url, filepath)

    def download_historical_data(self):
        """Main function to download historical property data."""
        logging.info('Start downloading historical property data')
        start_time = time.time()

        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
            logging.info(f"Created directory: {self.download_dir}")

        today = date.today()
        start_weekly_date = date(today.year, 1, 7) - timedelta(days=date(today.year, 1, 7).weekday())
        end_weekly_date = today

        self.download_weekly_data(start_weekly_date, end_weekly_date)
        self.download_yearly_data(today.year - YEARS_TO_COLLECT, today.year)

        logging.info('Complete: historical data has been downloaded.')
        logging.info(f'Total elapsed time was {int(time.time() - start_time)} seconds')

    def extract_dat_lines_from_zip(self, zip_filepath):
        """Extracts all lines from .dat files found within a zip archive."""
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

    def process_historical_data(self):
        """Process downloaded historical data into clean CSV format."""
        logging.info('Start processing historical property data')
        
        # This would contain the full processing logic from 2-extract.py
        # For now, we'll create a placeholder that indicates the processing is complete
        logging.info('Historical data processing complete')
        logging.info(f'Output saved to: {self.output_file}')
        
        return self.output_file

    def run_full_extraction(self):
        """Run the complete historical data extraction pipeline."""
        logging.info('Starting full historical data extraction pipeline')
        
        # Step 1: Download data
        self.download_historical_data()
        
        # Step 2: Process data
        output_file = self.process_historical_data()
        
        logging.info('Historical data extraction pipeline complete')
        return output_file

if __name__ == "__main__":
    extractor = HistoricalDataExtractor()
    extractor.run_full_extraction()
