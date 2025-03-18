import logging
import time
import os
import zipfile
from datetime import datetime
#
# Configure logging
logging.basicConfig(filename='propsales.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('Creating zip archive')
start = time.time()

name_original = 'extract-3-very-clean.csv'
name_new = 'nsw-property-sales-data-updated' + datetime.now().strftime('%Y%m%d')

os.rename(name_original, name_new + '.csv')

zipfile.ZipFile(name_new + '.zip', mode='w').write(name_new + ".csv", compress_type=zipfile.ZIP_DEFLATED)

os.rename(name_new + '.csv', name_original)

# Also create a generic a copy that doesn't have the date attached
os.system('cp ' + name_new + '.zip' + ' ' + 'archive.zip') 

logging.info("Complete: zip archive has been created.")
logging.info('Total elapsed time was ' + str(int(time.time() - start)) + " seconds")