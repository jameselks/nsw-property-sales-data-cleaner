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
* Install pandas in your virtual environment `(.venv)$ pip install pandas`
* Install scipy in your virtual environment `(.venv)$ pip install scipy`
* Install ploty.express in your virtual environment `(.venv)$ pip install plotly.express`
* Then open `1-download.py` then right-click > Run Python > Run Python in Terminal
* Same for `2-extract`
* Then open `analysis.ipynb` and run each cell to generate graphs or whatever