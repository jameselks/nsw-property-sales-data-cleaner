import pandas as pd

#---
# Import the data from the text file

column_names = ["Record type", "District code", "Property ID", "Sale counter", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Area type", "Contract date", "Settlement date", "Purchase price", "Zoning", "Nature of property", "Primary purpose", "Strata lot number", "Component code", "Sale code", "% interest of sale", "Dealing number", "Empty"]

df = pd.read_csv("extract-compact.txt", delimiter=";", names=column_names)

#---
# Processing the data

# Convert hectares to square metres
df.loc[df['Area type'] == "H", 'Area'] = df['Area'] * 10000

df['Primary purpose'] = df['Primary purpose'].str.capitalize()
df['Property name'] = df['Property name'].str.title()
df['Property street name'] = df['Property street name'].str.title()
df['Property locality'] = df['Property locality'].str.title()

#---
# Exporting to a CSV for further analysis

include_columns = ["Property ID", "Sale counter", "Download date / time", "Property name", "Property unit number", "Property house number", "Property street name", "Property locality", "Property post code", "Area", "Contract date", "Settlement date", "Purchase price", "Zoning", "Primary purpose", "Strata lot number"]

df.to_csv("extract.csv", columns=include_columns)

print("And we're done - " + str(int(time.time() - start)) + " seconds")