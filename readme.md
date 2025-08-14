# NSW Property Visualiser

A comprehensive property market analysis tool for NSW, Australia. This tool downloads historical property sales data from the NSW Valuer General and provides advanced analytics to help homebuyers make informed decisions.

## 🏗️ Project Structure

```
Property_project/
├── main.py                          # Main orchestration script
├── requirements.txt                 # Python dependencies
├── README.md                       # This file
├── src/                            # Source code
│   ├── __init__.py
│   ├── extractors/                 # Data extraction modules
│   │   ├── __init__.py
│   │   ├── historical_data_extractor.py
│   │   └── current_property_extractor.py
│   ├── analysis/                   # Analysis modules
│   │   ├── __init__.py
│   │   └── property_analyzer.py
│   └── utils/                      # Utility modules
│       └── __init__.py
├── data/                           # Data storage
├── logs/                           # Log files
└── docs/                           # Documentation
    ├── README_REFACTORED.md       # Detailed documentation
    └── Valuer General documentation/
```

## 🚀 Quick Start

### Prerequisites
```bash
# Install Python dependencies
pip install pandas scipy plotly.express numpy matplotlib
```

### Basic Usage

#### Run Complete Pipeline
```bash
python main.py --full-pipeline
```

#### Extract Historical Data Only
```bash
python main.py --extract-historical
```

#### Analyze Specific Locations
```bash
python main.py --analyze --locations "Lawson,Springwood,Hazelbrook"
```

#### Run Individual Components
```bash
# Historical data extraction
python src/extractors/historical_data_extractor.py

# Current data extraction (placeholder)
python src/extractors/current_property_extractor.py

# Property analysis
python src/analysis/property_analyzer.py
```

## 📊 Features

### Historical Data Analysis
- ✅ Automatic data download from NSW Valuer General
- ✅ Data cleaning and validation
- ✅ Market trend analysis
- ✅ Price distribution analysis

### Current Data Integration (Future)
- 🔄 Web scraping from major real estate sites
- 🔄 API integration where available
- 🔄 Real-time market monitoring
- 🔄 Listing comparison tools

### Advanced Analytics
- ✅ Statistical outlier detection
- ✅ Price trend analysis
- ✅ Location-based filtering
- ✅ Market timing recommendations
- ✅ Visualization generation

## 📁 Output Files

### Data Files (in `data/` directory)
- `historical_property_data.csv`: Clean historical sales data
- `current_property_data.csv`: Current property listings
- `combined_property_analysis.csv`: Combined dataset with source identification
- `price_distribution.png`: Price comparison visualization

### Log Files (in `logs/` directory)
- `historical_extraction.log`: Historical data extraction logs
- `current_extraction.log`: Current data extraction logs
- `property_analysis.log`: Analysis execution logs
- `property_visualiser_YYYYMMDD_HHMMSS.log`: Main pipeline logs

## 🔧 Configuration

### Historical Data Settings
Edit `src/extractors/historical_data_extractor.py`:
```python
YEARS_TO_COLLECT = 7                    # Number of years to download
RECENT_WEEKS_TO_EXCLUDE = 14            # Exclude recent weeks from weekly data
DOWNLOAD_DIR = '../data/'               # Download directory
```

### Analysis Settings
Edit `src/analysis/property_analyzer.py`:
```python
# Default location filter
target_locations = ['Lawson', 'Hazelbrook', 'Woodford', 'Linden', 
                   'Faulconbridge', 'Springwood', 'Valley Heights', 'Warrimoo']
```

## 🎯 Use Cases

1. **Homebuyer Research**: Analyze property trends in specific suburbs
2. **Market Analysis**: Understand price movements over time
3. **Investment Decisions**: Compare different areas and property types
4. **Negotiation Support**: Use historical data to make better offers

## 📝 Logging

The system provides comprehensive logging in the `logs/` directory:
- **Historical extraction**: `historical_extraction.log`
- **Current extraction**: `current_extraction.log`
- **Analysis**: `property_analysis.log`
- **Main pipeline**: `property_visualiser_YYYYMMDD_HHMMSS.log`

## 🔮 Future Enhancements

### Current Property Data Extraction
The current property extraction module is designed for future implementation:
- Web scraping from real estate websites
- API integration where available
- RSS feeds for real-time updates
- Data standardization and cleaning

### Advanced Analytics
- Machine learning price prediction models
- Market timing algorithms
- Investment opportunity scoring
- Comparative market analysis (CMA)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is for educational and personal use. Please respect the terms of service of data sources used.

---

**Note**: The current property data extraction module is a placeholder. Implementation will require careful consideration of website terms of service and rate limiting.

For detailed documentation, see `docs/README_REFACTORED.md`.
