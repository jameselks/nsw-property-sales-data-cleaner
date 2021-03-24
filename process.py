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

print("And we're done!")