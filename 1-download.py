# 

print('Hello! Python is up and running.')
import time
start = time.time()

import os
import urllib.request
from datetime import datetime, date, timedelta

download_dir = 'data/'
url_base = 'https://www.valuergeneral.nsw.gov.au/__psi/'
url_base_weekly = 'weekly/'
url_base_yearly = 'yearly/'
now = datetime.now()
this_year = now.year
years_to_collect = 6

if not os.path.isdir(download_dir):
    os.mkdir(download_dir)

d = datetime(this_year, 1, 7)
offset = -d.weekday() #weekday = 0 means monday
this_date = (d + timedelta(offset))

while this_date < (now - timedelta(days=14)):
    this_date = this_date + timedelta(days=7)  
    download_url = url_base + url_base_weekly + this_date.strftime('%Y%m%d') + '.zip'
    print('Downloading... ' + download_url)
    urllib.request.urlretrieve(download_url, download_dir + this_date.strftime('%Y%m%d') + '.zip')

for year in range(int(this_year-years_to_collect), int(this_year)):
    download_url = url_base + url_base_yearly + str(year) + '.zip'
    print('Downloading... ' + download_url)
    urllib.request.urlretrieve(download_url, download_dir + str(year) + '.zip')

print('Downloading complete')