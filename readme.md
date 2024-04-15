As a human who wants to buy a house and is interested in data, I want to analyse sales data for the suburbs I'm interested in so that I can make better offers.

The data from the bulk NSW Valuer General's Property Sales Information (PSI) makes it really hard to download and analyse. And a subscription to Core Logic is really expensive. So here we are.

Basically:

* Python to download the latest copy of the (.zip) data files as they are regularly updated

* Python to extract the data from the data (.zip) files and delete all the junk

* Jupyter to do whatever analysis you want.

The code is a hot mess, but gets the job done.

## Install

If you do code, you know what to do. If not, download Visual Studio Code and follow these prompts.

* Install Python (if you have VS Code open, restart it or it won't recognise Python)
* Copy this project to a folder
* Open folder in VS Code
* Open Terminal (CTRL+\`) to project folder, then create virual environment `py -3 -m venv .venv`
* VS Code popup will appear asking if you want to switch to this new interpreter, say Yes (if no popup then Ctrl + P, then type 'Python: Select interpreter')
* Open Terminal (CTRL+\`) and activate virtual environment `$ .venv\Scripts\activate.bat`
* Upgrade pip in your virtual environment `(.venv)$ pip install --upgrade pip` (don't worry about the error)
* Install requiremented packages in your virtual environment `(.venv)$ pip install -r requirements.txt`
* Then open `1-download.py` then right-click > Run Python > Run Python in Terminal
* Same for `2-extract`
* Then open `analysis.ipynb` and run each cell to generate graphs or whatever

## Valuer General documentation

Sales data is available online via the Valuer General's [Bulk property sales information website](https://valuation.property.nsw.gov.au/embed/propertySalesInformation).

I have included their documentation as part of this repository.

### General information
[Instructions](/Valuer%20General%20documentation/Property_Sales_Data_File_-_Instructions_V2.pdf) (PDF 63KB)

### Technical documentation
[Current property sales data file format (2001 to Current)](/Valuer%20General%20documentation/Current_Property_Sales_Data_File_Format_2001_to_Current.pdf) (PDF 75KB)
[Archived property sales data file format (1990 to 2001)](/Valuer%20General%20documentation/Archived_Property_Sales_Data_File_Format_1990_to_2001_V2.pdf) (PDF 72KB)
[Data elements](/Valuer%20General%20documentation/Property_Sales_Data_File_-_Data_Elements_V3.pdf) (PDF 66KB)
[Property sales data file (District Codes and names)](/Valuer%20General%20documentation/Property_Sales_Data_File_District_Codes_and_Names.pdf) (PDF 75KB)
[Property sales data file (Zone Codes and descriptions)](/Valuer%20General%20documentation/Property_Sales_Data_File_Zone_Codes_and_Descriptions_V2.pdf) (PDF 61KB)
[Property sales information data files user guide](/Valuer%20General%20documentation/Property_Sales_Information_Data_Files_User_guide.pdf) (PDF 1.9MB)