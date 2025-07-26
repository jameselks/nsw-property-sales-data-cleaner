import time
import os
import urllib.request
from urllib.error import URLError, HTTPError
from datetime import date, timedelta
import logging

# Constants
URL_BASE = 'https://www.valuergeneral.nsw.gov.au/__psi/'
WEEKLY_URL = URL_BASE + 'weekly/'
YEARLY_URL = URL_BASE + 'yearly/'
DOWNLOAD_DIR = 'data/'
YEARS_TO_COLLECT = 35
RECENT_WEEKS_TO_EXCLUDE = 14  # Number of days to exclude from recent weekly downloads.
RETRY_ATTEMPTS = 3

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler("propsales.log"), logging.StreamHandler()])

def download_file(url, filepath):
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

def download_weekly_data(start_date, end_date):
    """Downloads weekly data files."""
    end_date = end_date - timedelta(days=RECENT_WEEKS_TO_EXCLUDE)
    current_date = start_date
    while current_date < end_date:
        filename = current_date.strftime('%Y%m%d') + '.zip'
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        url = WEEKLY_URL + filename
        download_file(url, filepath)
        current_date += timedelta(days=7)

def download_yearly_data(start_year, end_year):
    """Downloads yearly data files."""
    for year in range(start_year, end_year):
        filename = str(year) + '.zip'
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        url = YEARLY_URL + filename
        download_file(url, filepath)

def main():
    """Main function to download data."""
    logging.info('Start downloading the data')
    start_time = time.time()

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        logging.info(f"Created directory: {DOWNLOAD_DIR}")

    today = date.today()
    start_weekly_date = date(today.year, 1, 7) - timedelta(days=date(today.year, 1, 7).weekday())
    end_weekly_date = today

    download_weekly_data(start_weekly_date, end_weekly_date)
    download_yearly_data(today.year - YEARS_TO_COLLECT, today.year)

    logging.info('Complete: the data has been downloaded.')
    logging.info(f'Total elapsed time was {int(time.time() - start_time)} seconds')

if __name__ == "__main__":
    main()