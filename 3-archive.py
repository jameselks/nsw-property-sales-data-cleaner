# 

print('Hello! Python is up and running.')
import time
start = time.time()

import os
import zipfile
from datetime import datetime

name_original = 'extract-3-very-clean.csv'
name_new = 'nsw-property-sales-data-to' + datetime.now().strftime('%Y%m%d')

os.rename(name_original, name_new + '.csv')

zipfile.ZipFile(name_new + '.zip', mode='w').write(name_new + ".csv", compress_type=zipfile.ZIP_DEFLATED)

os.rename(name_new + '.csv', name_original)

print('Finished')