# NSW Property Visualiser - Refactored Architecture

This repository has been refactored into a modular, three-component system for comprehensive NSW property market analysis.

## 🏗️ New Architecture

The system is now organized into three main components:

### 1. Historical Data Extraction (`historical_data_extractor.py`)
- **Purpose**: Downloads and processes historical NSW property sales data from the Valuer General
- **Data Source**: NSW Valuer General's Property Sales Information (PSI)
- **Time Range**: Configurable (default: 7 years)
- **Output**: `historical_property_data.csv`

### 2. Current Property Data Extraction (`current_property_extractor.py`)
- **Purpose**: Extracts current property listings from various real estate websites
- **Data Sources**: realestate.com.au, domain.com.au, onthehouse.com.au, etc.
- **Status**: Placeholder for future implementation
- **Output**: `current_property_data.csv`

### 3. Property Analysis (`property_analyzer.py`)
- **Purpose**: Combines historical and current data for comprehensive market analysis
- **Features**: Market trends, price comparisons, actionable insights
- **Output**: `combined_property_analysis.csv`, visualizations, recommendations

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

## 📁 File Structure

```
Property_project/
├── main.py                          # Main orchestration script
├── requirements.txt                 # Python dependencies
├── README.md                       # Main README
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
    ├── README_REFACTORED.md       # This file
    └── Valuer General documentation/
```

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

## 📊 Output Files

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

### Console Output
The system provides a comprehensive summary including:
- Market trends and statistics
- Current vs historical price comparisons
- Actionable recommendations
- File generation status

## 🎯 Key Features

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

## 🔮 Future Enhancements

### Current Property Data Extraction
The `current_property_extractor.py` module is designed for future implementation:

1. **Web Scraping**: Selenium-based extraction from real estate websites
2. **API Integration**: Direct API access where available
3. **RSS Feeds**: Real-time listing updates
4. **Data Standardization**: Address normalization and property categorization

### Advanced Analytics
- Machine learning price prediction models
- Market timing algorithms
- Investment opportunity scoring
- Comparative market analysis (CMA)

## 🛠️ Development

### Adding New Data Sources
To add a new current property data source:

1. Add a new method to `CurrentPropertyExtractor`:
```python
def extract_from_new_source(self):
    """Extract from new property website."""
    # Implementation here
    pass
```

2. Call it in `run_full_extraction()`:
```python
def run_full_extraction(self):
    # ... existing code ...
    self.extract_from_new_source()
    # ... existing code ...
```

### Extending Analysis
To add new analysis features:

1. Add methods to `PropertyAnalyzer`:
```python
def new_analysis_feature(self):
    """New analysis functionality."""
    # Implementation here
    pass
```

2. Integrate into `run_full_analysis()`:
```python
def run_full_analysis(self):
    # ... existing code ...
    self.new_analysis_feature()
    # ... existing code ...
```

## 📝 Logging

The system provides comprehensive logging in the `logs/` directory:
- **Historical extraction**: `historical_extraction.log`
- **Current extraction**: `current_extraction.log`
- **Analysis**: `property_analysis.log`
- **Main pipeline**: `property_visualiser_YYYYMMDD_HHMMSS.log`

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
