# 

print('Hello! Python is up and running.')
print('Creating zip archive')
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

# Also create a generic a copy that doesn't have the date attached
os.system('cp ' + name_new + '.zip' + ' ' + 'archive.zip') 

print("Archive has been created! Elapsed time was "  + str(int(time.time() - start)) + " seconds")
