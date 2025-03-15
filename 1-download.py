import time
import os
import urllib.request
from datetime import datetime, date, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('Start downloading the data')
start = time.time()

download_dir = 'data/'
url_base = 'https://www.valuergeneral.nsw.gov.au/__psi/'
url_base_weekly = 'weekly/'
url_base_yearly = 'yearly/'
now = datetime.now()
this_year = now.year
years_to_collect = 6

if not os.path.isdir(download_dir):
    os.mkdir(download_dir)
    logging.info(f"Created directory: {download_dir}")

d = datetime(this_year, 1, 7)
offset = -d.weekday() #weekday = 0 means monday
this_date = (d + timedelta(offset))

while this_date < (now - timedelta(days=14)):
    this_date = this_date + timedelta(days=7)
    download_url = url_base + url_base_weekly + this_date.strftime('%Y%m%d') + '.zip'
    logging.info(f'Downloading {download_url}')
    try:
        urllib.request.urlretrieve(download_url, download_dir + this_date.strftime('%Y%m%d') + '.zip')
        logging.info(f'Downloaded {download_url} to {download_dir + this_date.strftime("%Y%m%d") + ".zip"}')
    except Exception as e:
        logging.error(f'Error downloading {download_url}: {e}')

for year in range(int(this_year-years_to_collect), int(this_year)):
    download_url = url_base + url_base_yearly + str(year) + '.zip'
    logging.info(f'Downloading {download_url}')
    try:
        urllib.request.urlretrieve(download_url, download_dir + str(year) + '.zip')
        logging.info(f'Downloaded {download_url} to {download_dir + str(year) + ".zip"}')
    except Exception as e:
        logging.error(f'Error downloading {download_url}: {e}')

logging.info('Complete: the data has been downloaded.')
logging.info(f'Total elapsed time was {int(time.time() - start)} seconds')