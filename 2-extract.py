# 

print('Start extracting and processing data')
import time
start = time.time()

import os
import io
import zipfile
import csv

datadir = "./data"

output_rawarr = []
output_rawfile = ""

def extract (filename):
    zip = zipfile.ZipFile(filename)
    for file in zip.namelist():
        if (os.path.splitext(file)[1]).lower() == ".dat":
            output_rawarr.append(zip.read(file).decode("utf-8") + "\n")
        elif (os.path.splitext(file)[1]).lower() == ".zip":
            zipInner = zipfile.ZipFile(io.BytesIO(zip.read(file)))
            for file2 in zipInner.namelist():
                if (os.path.splitext(file2)[1]).lower() == ".dat":
                    output_rawarr.append((zipInner.read(file2)).decode("utf-8") + "\n")
                else:
                    print("Ignored file " + file2)
        else:
            print("Ignored file " + file)

    return

for file in os.listdir(datadir):
    filename = os.fsdecode(file)
    if filename.endswith(".zip"):
        print("Processing " + datadir + "/" + filename)
        extract(datadir + "/" + filename)

output_rawfile = ''.join(output_rawarr)
f = open("extract-1-raw.txt", "w+")
f.write(output_rawfile)
f.close()
print(str(int(time.time() - start)) + " seconds elapsed")
print("Begin merging the data")

outputarray = []
outputfile = ""
found = False
print('Merging ' + str(len(output_rawfile.splitlines())) + ' rows of data')
for line in output_rawfile.splitlines():
    if line[0:1] == "B":
        outputarray.append("\n" + line)
    elif line[0:1] == "C":
        outputarray.append(line.split(";")[-2])


outputfile = ''.join(outputarray)

f = open("extract-2-clean.txt", "w+")
f.write(outputfile)
f.close()

import pandas as pd
print(str(int(time.time() - start)) + " seconds elapsed")
print("Begin processing the data")

#---
# Import the data from the text file

date_converter = lambda x: pd.to_datetime(x, format="%Y%m%d", errors='coerce')
columns_with_dates = ["Contract date", "Settlement date"]
column_names = ["Record type", "District code", "Property ID", "Sale counter", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Area type", "Contract date", "Settlement date", "Purchase price", "Zoning", "Nature of property", "Primary purpose", "Strata lot number", "Component code", "Sale code", "% interest of sale", "Dealing number", "Property legal description"]
include_columns = ["Property ID", "Sale counter", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Area type", "Contract date", "Settlement date", "Purchase price", "Zoning", "Primary purpose", "Strata lot number", "Property legal description"]

df = pd.read_csv("extract-2-clean.txt", delimiter=";", header=None, names=column_names, encoding='utf8', usecols=include_columns, parse_dates=columns_with_dates, date_parser=date_converter, quoting=csv.QUOTE_NONE)

#---
# Processing the data

# Convert hectares to square metres
df.loc[df['Area type'] == "H", 'Area'] = df['Area'] * 10000
df['Area'] = pd.to_numeric(df['Area'], errors='coerce')

df['Property post code'] = pd.to_numeric(df['Property post code'], errors='coerce', downcast='float')
df['Primary purpose'] = df['Primary purpose'].str.capitalize()
df['Property name'] = df['Property name'].str.title()
df['Property street name'] = df['Property street name'].str.title()
df['Property locality'] = df['Property locality'].str.title()

#Fix zoning
#But only for vals before 1 Dec 2021
#https://legislation.nsw.gov.au/view/pdf/asmade/epi-2021-650
z = df['Contract date'] < pd.to_datetime('2021-12-01')
df.loc[z, 'Zoning'] = df.loc[z, 'Zoning'].replace({'E2': 'C2', 'E3': 'C3', 'E4': 'C4'})

#---
# Exporting to a CSV for further analysis
print(str(int(time.time() - start)) + " seconds elapsed")
print("Begin exporting to CSV")

export_columns = ["Property ID", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Contract date", "Settlement date", "Purchase price", "Zoning", "Primary purpose", "Strata lot number"]
df.to_csv("extract-3-very-clean.csv", columns=export_columns)

print("Complete: data has been extracted and processed.")
print('Total elapsed time was ' + str(int(time.time() - start)) + " seconds")