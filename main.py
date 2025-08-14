#!/usr/bin/env python3
"""
NSW Property Visualiser - Main Orchestration Script

This script coordinates the three main components:
1. Historical Data Extraction
2. Current Property Data Extraction  
3. Property Analysis and Insights

Usage:
    python main.py --extract-historical    # Extract historical data only
    python main.py --extract-current       # Extract current data only
    python main.py --analyze               # Run analysis only
    python main.py --full-pipeline         # Run complete pipeline
"""

import argparse
import logging
import sys
import os
from datetime import datetime

# Import our custom modules
from src.extractors.historical_data_extractor import HistoricalDataExtractor
from src.extractors.current_property_extractor import CurrentPropertyExtractor
from src.analysis.property_analyzer import PropertyAnalyzer

# Configure main logging
# Ensure logs directory exists
logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, f"property_visualiser_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class PropertyVisualiser:
    """Main orchestration class for the NSW Property Visualiser."""
    
    def __init__(self):
        self.historical_extractor = HistoricalDataExtractor()
        self.current_extractor = CurrentPropertyExtractor()
        self.analyzer = PropertyAnalyzer()
        
    def extract_historical_data(self):
        """Extract historical property sales data."""
        logger.info("Starting historical data extraction")
        try:
            output_file = self.historical_extractor.run_full_extraction()
            logger.info(f"Historical data extraction completed: {output_file}")
            return True
        except Exception as e:
            logger.error(f"Historical data extraction failed: {e}")
            return False
            
    def extract_current_data(self):
        """Extract current property listings data."""
        logger.info("Starting current data extraction")
        try:
            output_file = self.current_extractor.run_full_extraction()
            logger.info(f"Current data extraction completed: {output_file}")
            return True
        except Exception as e:
            logger.error(f"Current data extraction failed: {e}")
            return False
            
    def run_analysis(self, location_filter=None):
        """Run property market analysis."""
        logger.info("Starting property market analysis")
        try:
            insights = self.analyzer.run_full_analysis(location_filter)
            logger.info("Property market analysis completed")
            return insights
        except Exception as e:
            logger.error(f"Property market analysis failed: {e}")
            return None
            
    def run_full_pipeline(self, location_filter=None):
        """Run the complete property visualisation pipeline."""
        logger.info("Starting full property visualisation pipeline")
        
        # Step 1: Extract historical data
        logger.info("Step 1/3: Extracting historical data")
        if not self.extract_historical_data():
            logger.error("Pipeline failed at historical data extraction")
            return False
            
        # Step 2: Extract current data
        logger.info("Step 2/3: Extracting current data")
        if not self.extract_current_data():
            logger.warning("Current data extraction failed, continuing with historical data only")
            
        # Step 3: Run analysis
        logger.info("Step 3/3: Running property analysis")
        insights = self.run_analysis(location_filter)
        
        if insights:
            logger.info("Full pipeline completed successfully")
            self._print_summary(insights)
            return True
        else:
            logger.error("Pipeline failed at analysis stage")
            return False
            
    def _print_summary(self, insights):
        """Print a summary of the analysis results."""
        print("\n" + "="*60)
        print("NSW PROPERTY VISUALISER - ANALYSIS SUMMARY (PAST 5 YEARS)")
        print("="*60)
        
        if insights.get('market_trends'):
            trends = insights['market_trends']
            print(f"\n📊 MARKET TRENDS:")
            print(f"   📅 Analysis Period: {trends.get('date_range', 'N/A')}")
            print(f"   🏠 Total properties analyzed: {trends.get('total_sales', 'N/A'):,}")
            print(f"   💰 Average price: ${trends.get('avg_price', 0):,.0f}")
            print(f"   📈 Median price: ${trends.get('median_price', 0):,.0f}")
            print(f"   📊 Recent trend: {trends.get('recent_trend', 'N/A')}")
            
            # Add price per square meter information
            if 'median_price_per_sqm' in trends:
                print(f"   📏 Median price/sq.m: ${trends.get('median_price_per_sqm', 0):,.0f}")
                print(f"   📏 Properties with area data: {trends.get('properties_with_area', 0):,}")
                if 'sqm_growth_pct' in trends:
                    print(f"   📈 Price/sq.m growth: {trends.get('sqm_growth_pct', 0):+.1f}%")
            
        if insights.get('current_vs_historical'):
            comparison = insights['current_vs_historical']
            print(f"\n🏠 CURRENT vs HISTORICAL:")
            print(f"   Current listings: {comparison.get('current_listings_count', 0)}")
            print(f"   Historical sales: {comparison.get('historical_sales_count', 0)}")
            print(f"   Current avg price: ${comparison.get('current_avg_price', 0):,.0f}")
            print(f"   Historical avg price: ${comparison.get('historical_avg_price', 0):,.0f}")
            
            price_diff = comparison.get('price_difference', 0)
            if price_diff != 0:
                print(f"   Price difference: ${price_diff:+,.0f}")
            
            # Add price per square meter comparison
            if 'current_median_price_per_sqm' in comparison and 'historical_median_price_per_sqm' in comparison:
                print(f"\n📏 PRICE PER SQUARE METER COMPARISON:")
                print(f"   Current median price/sq.m: ${comparison.get('current_median_price_per_sqm', 0):,.0f}")
                print(f"   Historical median price/sq.m: ${comparison.get('historical_median_price_per_sqm', 0):,.0f}")
                
                sqm_diff_pct = comparison.get('sqm_price_difference_pct', 0)
                if sqm_diff_pct != 0:
                    print(f"   Price/sq.m difference: {sqm_diff_pct:+.1f}%")
                    
                    if sqm_diff_pct > 10:
                        print("   📈 Current listings significantly higher than historical sales")
                    elif sqm_diff_pct > 5:
                        print("   📊 Current listings moderately higher than historical sales")
                    elif sqm_diff_pct > -5:
                        print("   📉 Current listings in line with historical sales")
                    else:
                        print("   📉 Current listings below historical sales - potential opportunity")
                
        if insights.get('recommendations'):
            print(f"\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(insights['recommendations'], 1):
                print(f"   {i}. {rec}")
                
        print(f"\n📁 Generated files:")
        print(f"   - historical_property_data.csv")
        print(f"   - current_property_data.csv")
        print(f"   - combined_property_analysis.csv")
        print(f"   - price_distribution.png")
        print("="*60)

def main():
    """Main entry point for the property visualiser."""
    parser = argparse.ArgumentParser(
        description="NSW Property Visualiser - Analyze property market data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --full-pipeline                    # Run complete analysis
  python main.py --extract-historical               # Download historical data only
  python main.py --analyze --locations "Lawson,Springwood"  # Analyze specific locations
        """
    )
    
    parser.add_argument(
        '--extract-historical',
        action='store_true',
        help='Extract historical property sales data only'
    )
    
    parser.add_argument(
        '--extract-current',
        action='store_true',
        help='Extract current property listings data only'
    )
    
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Run property market analysis only'
    )
    
    parser.add_argument(
        '--full-pipeline',
        action='store_true',
        help='Run the complete pipeline (extract + analyze)'
    )
    
    parser.add_argument(
        '--locations',
        type=str,
        help='Comma-separated list of locations to analyze (e.g., "Lawson,Springwood")'
    )
    
    args = parser.parse_args()
    
    # Parse location filter
    location_filter = None
    if args.locations:
        location_filter = [loc.strip() for loc in args.locations.split(',')]
        logger.info(f"Location filter applied: {location_filter}")
    
    # Initialize the visualiser
    visualiser = PropertyVisualiser()
    
    # Execute based on arguments
    if args.extract_historical:
        success = visualiser.extract_historical_data()
        sys.exit(0 if success else 1)
        
    elif args.extract_current:
        success = visualiser.extract_current_data()
        sys.exit(0 if success else 1)
        
    elif args.analyze:
        insights = visualiser.run_analysis(location_filter)
        sys.exit(0 if insights else 1)
        
    elif args.full_pipeline:
        success = visualiser.run_full_pipeline(location_filter)
        sys.exit(0 if success else 1)
        
    else:
        # Default: run full pipeline
        print("No specific action specified, running full pipeline...")
        success = visualiser.run_full_pipeline(location_filter)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
