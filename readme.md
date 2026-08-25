# NSW property sales data cleaner

As a human who wants to buy a house and is interested in data, I want to analyse sales data for the suburbs I'm interested in so that I can make better offers.

The bulk NSW Valuer General's Property Sales Information (PSI) makes that really hard. It's 35 years of semicolon-delimited files, inside zips, inside more zips, in two different formats, with no column headers. And a CoreLogic subscription is really expensive. So here we are.

Basically:

* `1-download.py` grabs the data files as they're updated
* `2-extract.py` pulls the data out and deletes all the junk
* `3-publish.py` checks the result isn't broken, then zips it up
* `analysis.ipynb` does whatever analysis you want

Out the back you get one CSV - about 7 million sales from 1990 to now, every LGA in NSW. Published daily at [nswpropertysalesdata.com](https://nswpropertysalesdata.com/).

Most people only need 1 and 2, then the notebook.

## 🚨 **Heads up: data downloads are blocked right now by the Valuer General website**

Since about June 2026 the Valuer General's server has been sitting behind Cloudflare's bot protection, and `1-download.py` can't get through it. You'll see `HTTP 403` with `Cf-Mitigated: challenge` in the log. **This isn't a bug in this repo and there's nothing here to fix** - the same URLs work fine pasted into a browser.

**The workaround.** When downloads fail, `1-download.py` writes `manual-download.html` - a page of links to just the files it couldn't get. Open it in a normal browser, click through them, and drop the zips into `data/`. Then run `2-extract.py` as usual. Tedious, but it works. It's also why nothing in `data/` ever gets deleted: anything you throw away can't currently be fetched again.

**Where it's at.** I'm in touch with the Valuer General's office about it. It's not clear yet if they'll change anything, or when. If you're reading this well after mid-2026, the situation may have moved - try a run and see.

## What's changed in this version

This is a massive update. The short version: the old pipeline was quietly producing wrong numbers, and nothing ever complained, so nobody knew.

### Data that was wrong in ways you couldn't see

* **Deduplication was deleting real sales.** Two different sales of the same property, same day, same price, were treated as one record - 23,639 groups of genuinely separate transactions were being collapsed. Sales are now keyed on the dealing number, which is the actual registered identifier. 36,271 rows came back.
* **15,081 legal descriptions were glued together**, so one property's description ran straight into the next one's. Now zero.
* **1990 was missing.** The download loop counted back 35 years from the current year, so it actually started at 1991 - and would have started at 1992 next January. It's an absolute year now.
* **Hectares were being reported as square metres.** Land area comes through in either unit and the column didn't say which. `Area (m2)` is now always square metres.
* **Every price and postcode had a fake decimal point** - `2000.0` instead of `2000`. Gone.
* **Scottish and Irish names were mangled.** `MCMAHONS` came out as `Mcmahons` (52,906 rows) and `BENNY'S` as `Benny'S` (9,210 rows). Both fixed. `Mac` names are deliberately left alone, because Macquarie and Macleay really are lower-case.

### Thirteen new columns

20 columns became 33, and nothing was dropped to get there.

**Seven were in the source all along and were being thrown away** - `District code`, `Valuation number`, `Dimensions`, `Component code`, `Sale code`, `% Interest of sale` and `Parcels in sale`. The old extract simply didn't keep them.

**Three make coded fields readable:**

* `Area (source)` - the original untouched area figure, so the unit code always describes a number you can actually see
* `Nature of property (description)` - `R`/`V`/`3` spelled out as Residence / Vacant land / Other
* `Primary purpose (normalised)` - 10,946 free-text values (`RESIDENCE`, `Resdience`, `SHOP & DWELLING`) sorted into 7 categories. 99.55% land somewhere useful, and the raw text is still there in `Primary purpose` if you disagree with me.

**Three are quality flags** - `Part interest flag`, `Non-market price flag` and `Date error flag`, marking rows that aren't ordinary market sales. They flag rows. They never delete them.

Two columns were also renamed: `Area` is now `Area (m2)` and `Area type` is now `Area type (source)`. `Download date / time` is a real timestamp instead of text. **If you're reading the CSV with existing code, those three will break it** - that's deliberate, because the old names were lying about what they contained.

### Nothing told you when it broke

* Every script exits with an error code when it fails. None of the three did before, so the shell had no way to tell a broken run from a good one.
* `3-publish.py` is new, and replaces the old `3-archive.py`. It runs six checks over the finished dataset and refuses to package anything that fails one. Checking and packaging sit in the same file on purpose - as two separate scripts, the checks could be skipped by forgetting a line in a cron job.
* The cron job chains with `&&`, so a failure stops the line instead of publishing anyway.
* Downloads are cached, written atomically, and time out - a half-written file can't be mistaken for a good one.
* There are now 102 automated tests. There were none at all before - see below.

## Install

If you do code, you know what to do. If not, download Visual Studio Code and follow these prompts.

* Install Python 3.10 or newer (if VS Code is already open, restart it or it won't recognise Python)
* Copy this project to a folder, open the folder in VS Code
* Open Terminal (CTRL+\`) and create a virtual environment: `py -3 -m venv .venv`
* A popup will ask if you want to switch to the new interpreter - say yes (no popup? Ctrl+P, then `Python: Select interpreter`)
* Activate it: `.venv\Scripts\activate`
* `pip install --upgrade pip` (don't worry about the error)
* `pip install -r requirements.txt`

## Running it

```bash
python 1-download.py    # fetch the archives into ./data/ (slow the first time)
python 2-extract.py     # unzip, clean, dedupe -> extract-3-very-clean.csv
python 3-publish.py     # check it, then zip it for publishing
```

Then open `analysis.ipynb` and run the cells for graphs or whatever.

You only need the first two if you just want the data for yourself. `3-publish.py` is for putting it somewhere.

Before it packages anything, `3-publish.py` compares the new CSV against the last good run and stops if the row count has collapsed, a column has suddenly emptied out, legal descriptions are glued together, the newest record is too old, the column set has changed, or the CSV wasn't written by this run. On success it writes `validation-baseline.json` for next time to compare against.

## What the cleaning does

* **Two formats, one output.** Pre-2001 and post-2001 files have different layouts. Which one a file uses is decided by its field count, never by its date - the dates in this data contain real errors, and using them to guess the format misfiles tens of thousands of rows.
* **Zips inside zips** are opened in memory, so no intermediate files land on disk.
* **Multi-line legal descriptions** are joined back onto their parent record without spaces, per the VG spec.
* **Hectares to square metres.** `Area (m2)` is multiplied by 10,000 where the source unit is `H`. The original number and unit stay in `Area (source)` and `Area type (source)`.
* **ALL CAPS to Title Case** for names, streets, suburbs and purpose - then `Mc` and `'s` repaired afterwards, because `.str.title()` gets both wrong.
* **Impossible dates nulled.** Anything in the future or before 1990-01-01 becomes empty. The row stays; only the bad date goes.
* **Duplicates removed**, keyed on `(Property ID, Dealing number)` where there's a dealing number, falling back to a key including the address where there isn't. About 31% of pre-2001 records have no property ID at all, and a key without the address merged unrelated properties sold on the same day for the same price.
* **Flags, not deletions.** Part interests, non-market prices and reversed dates get a flag column. Nothing is dropped on your behalf.

## Documentation

* **[DATA_DICTIONARY.md](DATA_DICTIONARY.md)** - all 33 columns, the quality flags, pre-2001 vs post-2001 mappings, zoning codes and district/LGA codes.

Sales data comes from the Valuer General's [bulk property sales information website](https://valuation.property.nsw.gov.au/embed/propertySalesInformation). Their documentation is included in this repository:

* [Instructions](/Valuer%20General%20documentation/Property_Sales_Data_File_-_Instructions_V2.pdf) (PDF 63KB)
* [Current file format, 2001 to current](/Valuer%20General%20documentation/Current_Property_Sales_Data_File_Format_2001_to_Current.pdf) (PDF 75KB)
* [Archived file format, 1990 to 2001](/Valuer%20General%20documentation/Archived_Property_Sales_Data_File_Format_1990_to_2001_V2.pdf) (PDF 72KB)
* [Data elements](/Valuer%20General%20documentation/Property_Sales_Data_File_-_Data_Elements_V3.pdf) (PDF 66KB)
* [District codes and names](/Valuer%20General%20documentation/Property_Sales_Data_File_District_Codes_and_Names.pdf) (PDF 75KB)
* [Zone codes and descriptions](/Valuer%20General%20documentation/Property_Sales_Data_File_Zone_Codes_and_Descriptions_V2.pdf) (PDF 61KB)
* [User guide](/Valuer%20General%20documentation/Property_Sales_Information_Data_Files_User_guide.pdf) (PDF 1.9MB)

## Running it daily

Chain the scripts with `&&`. Not `;`, and not separate cron lines.

```bash
cd /home/jameselk/sites/nswpropertysalesdata.com-ops/pythonapp \
  && python 1-download.py \
  && python 2-extract.py \
  && python 3-publish.py
```

`&&` is what makes a failure stop the line. With `;` a failed download still gets extracted, and an extract that produced nothing still gets published - which is exactly how the site served stale data for 81 days.

Only relevant if you're deploying to cPanel like I am:

* `.cpanel.yml` copies only the files it names. A new script needs a new `cp` line, or the server quietly keeps running the old pipeline. This is half the reason the checks live inside `3-publish.py` - a gate you have to remember in two places is a gate that eventually gets forgotten in one.
* It doesn't run `pip install`. Versions are pinned in `requirements.txt` but have to be installed on the server by hand after a bump.
* **Nothing in `data/` is ever deleted, deliberately.** Last year's weekly files are superseded by the annual archives and could in principle be cleaned up, but the source is behind a Cloudflare bot challenge, so anything removed can't currently be re-fetched. A stale file on disk beats 150 MB of free space. Revisit if the block lifts.
* `validation-baseline.json` is deliberately not committed. It records row counts from whichever machine wrote it, so a local baseline built from the full corpus would clobber the server's and fail the next production run for no reason.

### About the tests

These are new, and most people tinkering with a repo like this haven't used automated tests, so: a test is a small piece of code that runs the real code against a made-up example and checks the answer. One of them feeds in `MCMAHONS POINT` and checks it comes back as `McMahons Point` rather than `Mcmahons Point`.

The point isn't ceremony. This pipeline runs unattended overnight, and every failure it's had has been a quiet one - plausible-looking numbers that were wrong. A test per fix means the next time someone breaks it (me, probably) the break is loud.

```bash
pytest
```

102 of them, about a second. Worth running before you change anything and after.

If you're adding one: write it before the fix and watch it fail first. A test that has never failed isn't proving anything - I shipped one early on that passed against the broken code and told me nothing.

## Licensing

### The data

**Creative Commons Attribution.** Every archive ships a `creative_commons.txt`, and that file is what this project follows, because it's the licence actually delivered with the data. Read in full it has no NonCommercial, NoDerivatives or ShareAlike terms, and it expressly permits derivative works. Attribution goes to Valuation NSW (formerly Valuer General NSW).

The Valuer General website contradicts itself - the [bulk PSI page](https://www.valuergeneral.nsw.gov.au/design/bulk_psi_content/bulk_psi) says CC BY-NC-ND 4.0, and the factsheets cite "Attribution 4.0" while linking to a `by-nd` URL. If you need certainty for your own use, ask valuergeneral@ovg.nsw.gov.au.

### The code

**[MIT](LICENSE)**. That covers this repository only - it doesn't grant you anything over the underlying data.
