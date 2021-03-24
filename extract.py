import process

print('Hello! Python is up and running.')
import time
start = time.time()

import os
import io
import zipfile

datadir = "./data"
outputdata = ""

def extract (filename):
    outputdata = ""
    zip = zipfile.ZipFile(filename)
    for file in zip.namelist():
        if (os.path.splitext(file)[1]).lower() == ".dat":
            outputdata = outputdata + zip.read(file).decode("utf-8")
        elif (os.path.splitext(file)[1]).lower() == ".zip":
            zipInner = zipfile.ZipFile(io.BytesIO(zip.read(file)))
            for file2 in zipInner.namelist():
                if (os.path.splitext(file2)[1]).lower() == ".dat":
                    outputdata = outputdata + (zipInner.read(file2)).decode("utf-8")
                else:
                    print("Ignored file - " + file2)
        else:
            print("Ignored file - " + file)

    return outputdata

for file in os.listdir(datadir):
    filename = os.fsdecode(file)
    if filename.endswith(".zip"):
        print("Extracting " + datadir + "/" + filename)
        outputdata = outputdata + extract(datadir + "/" + filename)

print("Writing extract file")
f = open("extract.txt", "w+")
f.write(outputdata)
f.close()
print("Now compacting the data - " + str(int(time.time() - start)) + " seconds")

outputarray = []
outputfile = ""
print(len(outputdata.splitlines()))
for line in outputdata.splitlines():
    if line[0:1] == "B":
        outputarray.append(line + "\n")

outputfile = ''.join(outputarray)


f = open("extract-compact.txt", "w+")
f.write(outputfile)
f.close()

import pandas as pd
import pandas_profiling
from pandas_profiling import ProfileReport

#---
# Import the data from the text file
print("Reading the data")

columns_with_dates = ["Contract date", "Settlement date"]
column_names = ["Record type", "District code", "Property ID", "Sale counter", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Area type", "Contract date", "Settlement date", "Purchase price", "Zoning", "Nature of property", "Primary purpose", "Strata lot number", "Component code", "Sale code", "% interest of sale", "Dealing number", "Empty"]
include_columns = ["Property ID", "Sale counter", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Area type", "Contract date", "Settlement date", "Purchase price", "Zoning", "Primary purpose", "Strata lot number"]
df = pd.read_csv("extract-compact.txt", delimiter=";", header=None, names=column_names, encoding='utf8', usecols=include_columns, parse_dates=columns_with_dates)

#---
# Processing the data
print("Processing the data")

# Convert hectares to square metres
df.loc[df['Area type'] == "H", 'Area'] = df['Area'] * 10000
df['Primary purpose'] = df['Primary purpose'].str.capitalize()
df['Property name'] = df['Property name'].str.title()
df['Property street name'] = df['Property street name'].str.title()
df['Property locality'] = df['Property locality'].str.title()

#---
# Exporting to a CSV for further analysis
print("Finally - exporting to CSV")

export_columns = ["Property ID", "Sale counter", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Contract date", "Settlement date", "Purchase price", "Zoning", "Primary purpose", "Strata lot number"]
df.to_csv("extract.csv", columns=export_columns)

#---
# Creating profie report of subset

profile = ProfileReport(df, title="Pandas Profiling Report")
profile.to_file("your_report.html")

print("And we're done!")




