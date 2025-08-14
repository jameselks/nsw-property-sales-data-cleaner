import logging
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import plotly.express as px
from datetime import datetime, date, timedelta
import os

# Configure logging
import os

# Ensure logs directory exists
logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', 
                   handlers=[logging.FileHandler(os.path.join(logs_dir, "property_analysis.log")), logging.StreamHandler()])

class PropertyAnalyzer:
    """Main analysis class that combines historical and current property data."""
    
    def __init__(self):
        # Ensure data directory exists
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # Historical data is in the root data directory
        root_data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        self.historical_data_file = os.path.join(root_data_dir, "extract-3-very-clean.csv")
        self.current_data_file = os.path.join(data_dir, "current_property_data.csv")
        self.combined_data_file = os.path.join(data_dir, "combined_property_analysis.csv")
        self.historical_df = None
        self.current_df = None
        self.combined_df = None
        
    def load_historical_data(self):
        """Load historical property sales data."""
        logging.info('Loading historical property data')
        try:
            if os.path.exists(self.historical_data_file):
                self.historical_df = pd.read_csv(self.historical_data_file)
                logging.info(f'Loaded {len(self.historical_df)} historical records')
            else:
                logging.warning(f'Historical data file not found: {self.historical_data_file}')
                self.historical_df = pd.DataFrame()
        except Exception as e:
            logging.error(f'Error loading historical data: {e}')
            self.historical_df = pd.DataFrame()
            
    def load_current_data(self):
        """Load current property listings data."""
        logging.info('Loading current property data')
        try:
            if os.path.exists(self.current_data_file):
                self.current_df = pd.read_csv(self.current_data_file)
                logging.info(f'Loaded {len(self.current_df)} current listings')
            else:
                logging.warning(f'Current data file not found: {self.current_data_file}')
                self.current_df = pd.DataFrame()
        except Exception as e:
            logging.error(f'Error loading current data: {e}')
            self.current_df = pd.DataFrame()
            
    def combine_datasets(self):
        """Combine historical and current property data for analysis."""
        logging.info('Combining historical and current property datasets')
        
        if self.historical_df.empty and self.current_df.empty:
            logging.error('No data available for analysis')
            return
            
        # Create combined dataset with source identification
        combined_data = []
        
        # Add historical data with source identifier
        if not self.historical_df.empty:
            historical_copy = self.historical_df.copy()
            historical_copy['data_source'] = 'historical_sales'
            historical_copy['data_type'] = 'sold'
            combined_data.append(historical_copy)
            
        # Add current data with source identifier
        if not self.current_df.empty:
            current_copy = self.current_df.copy()
            current_copy['data_source'] = 'current_listings'
            current_copy['data_type'] = 'for_sale'
            combined_data.append(current_copy)
            
        # Combine all data
        if combined_data:
            self.combined_df = pd.concat(combined_data, ignore_index=True)
            logging.info(f'Combined dataset contains {len(self.combined_df)} total records')
            
            # Save combined dataset
            self.combined_df.to_csv(self.combined_data_file, index=False)
            logging.info(f'Combined data saved to: {self.combined_data_file}')
        else:
            self.combined_df = pd.DataFrame()
            
    def analyze_market_trends(self, location_filter=None):
        """Analyze market trends using historical data (past 5 years)."""
        logging.info('Analyzing market trends (past 5 years)')
        
        if self.historical_df.empty:
            logging.warning('No historical data available for trend analysis')
            return
            
        # Apply location filter if specified
        analysis_df = self.historical_df.copy()
        if location_filter:
            analysis_df = analysis_df[analysis_df['Property locality'].isin(location_filter)]
            
        # Convert date fields
        if 'Contract date' in analysis_df.columns:
            analysis_df['Contract date'] = pd.to_datetime(analysis_df['Contract date'])
            
        # Filter for past 5 years only
        five_years_ago = datetime.now() - pd.DateOffset(years=5)
        analysis_df = analysis_df[analysis_df['Contract date'] >= five_years_ago]
            
        # Basic trend analysis
        if 'Purchase price' in analysis_df.columns and 'Contract date' in analysis_df.columns:
            # Monthly average prices
            monthly_avg = analysis_df.groupby(analysis_df['Contract date'].dt.to_period('M'))['Purchase price'].mean()
            
            # Calculate date range
            date_range = f"{analysis_df['Contract date'].min().strftime('%Y-%m')} to {analysis_df['Contract date'].max().strftime('%Y-%m')}"
            
            # Price trend analysis
            price_trend = {
                'total_sales': len(analysis_df),
                'date_range': date_range,
                'avg_price': analysis_df['Purchase price'].mean(),
                'median_price': analysis_df['Purchase price'].median(),
                'price_range': (analysis_df['Purchase price'].min(), analysis_df['Purchase price'].max()),
                'recent_trend': 'increasing' if len(monthly_avg) > 1 and monthly_avg.iloc[-1] > monthly_avg.iloc[-2] else 'decreasing'
            }
            
            # Add price per square meter analysis if Area data is available
            if 'Area' in analysis_df.columns:
                area_data = analysis_df.dropna(subset=['Area'])
                area_data = area_data[area_data['Area'] > 0]
                
                if len(area_data) > 0:
                    area_data['Price_per_sqm'] = area_data['Purchase price'] / area_data['Area']
                    
                    # Monthly price per sqm trends
                    monthly_sqm = area_data.groupby(area_data['Contract date'].dt.to_period('M'))['Price_per_sqm'].median()
                    
                    price_trend.update({
                        'properties_with_area': len(area_data),
                        'avg_price_per_sqm': area_data['Price_per_sqm'].mean(),
                        'median_price_per_sqm': area_data['Price_per_sqm'].median(),
                        'sqm_price_range': (area_data['Price_per_sqm'].min(), area_data['Price_per_sqm'].max()),
                        'sqm_trend': 'increasing' if len(monthly_sqm) > 1 and monthly_sqm.iloc[-1] > monthly_sqm.iloc[-2] else 'decreasing'
                    })
                    
                    # Calculate recent vs older price per sqm growth
                    if len(monthly_sqm) >= 6:
                        recent_sqm = monthly_sqm.tail(3).mean()
                        older_sqm = monthly_sqm.tail(6).head(3).mean()
                        sqm_growth = ((recent_sqm - older_sqm) / older_sqm) * 100
                        price_trend['sqm_growth_pct'] = sqm_growth
            
            logging.info(f'Market trend analysis complete (past 5 years): {price_trend}')
            return price_trend
            
    def compare_current_vs_historical(self, location_filter=None):
        """Compare current listings with historical sales data."""
        logging.info('Comparing current listings with historical sales')
        
        if self.combined_df.empty:
            logging.warning('No combined data available for comparison')
            return
            
        # Apply location filter if specified
        comparison_df = self.combined_df.copy()
        if location_filter:
            comparison_df = comparison_df[comparison_df['Property locality'].isin(location_filter)]
            
        # Separate current and historical data
        current_listings = comparison_df[comparison_df['data_type'] == 'for_sale']
        historical_sales = comparison_df[comparison_df['data_type'] == 'sold']
        
        comparison_results = {
            'current_listings_count': len(current_listings),
            'historical_sales_count': len(historical_sales),
            'current_avg_price': current_listings['Purchase price'].mean() if not current_listings.empty else 0,
            'historical_avg_price': historical_sales['Purchase price'].mean() if not historical_sales.empty else 0,
            'price_difference': 0
        }
        
        if comparison_results['historical_avg_price'] > 0:
            comparison_results['price_difference'] = (
                comparison_results['current_avg_price'] - comparison_results['historical_avg_price']
            )
        
        # Add price per square meter comparison if Area data is available
        if 'Area' in comparison_df.columns:
            # Historical price per sqm
            historical_area = historical_sales.dropna(subset=['Area'])
            historical_area = historical_area[historical_area['Area'] > 0]
            
            if len(historical_area) > 0:
                historical_area['Price_per_sqm'] = historical_area['Purchase price'] / historical_area['Area']
                comparison_results.update({
                    'historical_avg_price_per_sqm': historical_area['Price_per_sqm'].mean(),
                    'historical_median_price_per_sqm': historical_area['Price_per_sqm'].median(),
                    'historical_properties_with_area': len(historical_area)
                })
            
            # Current price per sqm
            current_area = current_listings.dropna(subset=['Area'])
            current_area = current_area[current_area['Area'] > 0]
            
            if len(current_area) > 0:
                current_area['Price_per_sqm'] = current_area['Purchase price'] / current_area['Area']
                comparison_results.update({
                    'current_avg_price_per_sqm': current_area['Price_per_sqm'].mean(),
                    'current_median_price_per_sqm': current_area['Price_per_sqm'].median(),
                    'current_properties_with_area': len(current_area)
                })
                
                # Calculate price per sqm difference
                if 'historical_median_price_per_sqm' in comparison_results:
                    sqm_difference = comparison_results['current_median_price_per_sqm'] - comparison_results['historical_median_price_per_sqm']
                    sqm_difference_pct = (sqm_difference / comparison_results['historical_median_price_per_sqm']) * 100
                    comparison_results.update({
                        'sqm_price_difference': sqm_difference,
                        'sqm_price_difference_pct': sqm_difference_pct
                    })
            
        logging.info(f'Comparison analysis complete: {comparison_results}')
        return comparison_results
        
    def generate_insights(self, location_filter=None):
        """Generate actionable insights for property buyers."""
        logging.info('Generating property market insights')
        
        insights = {
            'market_trends': self.analyze_market_trends(location_filter),
            'current_vs_historical': self.compare_current_vs_historical(location_filter),
            'recommendations': []
        }
        
        # Generate recommendations based on analysis
        if insights['market_trends'] and insights['current_vs_historical']:
            current_avg = insights['current_vs_historical']['current_avg_price']
            historical_avg = insights['current_vs_historical']['historical_avg_price']
            
            if current_avg > historical_avg * 1.1:
                insights['recommendations'].append("Current prices are significantly higher than recent sales - consider waiting or negotiating")
            elif current_avg < historical_avg * 0.9:
                insights['recommendations'].append("Current prices are below recent sales - good buying opportunity")
            else:
                insights['recommendations'].append("Current prices are in line with recent sales - market appears stable")
                
        logging.info(f'Generated {len(insights["recommendations"])} insights')
        return insights
        
    def create_visualizations(self, location_filter=None):
        """Create visualizations for the property analysis."""
        logging.info('Creating property market visualizations')
        
        if self.combined_df.empty:
            logging.warning('No data available for visualizations')
            return
            
        # Apply location filter if specified
        viz_df = self.combined_df.copy()
        if location_filter:
            viz_df = viz_df[viz_df['Property locality'].isin(location_filter)]
            
        # Create price distribution plot
        if 'Purchase price' in viz_df.columns:
            plt.figure(figsize=(12, 6))
            
            # Separate current and historical data for plotting
            current_prices = viz_df[viz_df['data_type'] == 'for_sale']['Purchase price']
            historical_prices = viz_df[viz_df['data_type'] == 'sold']['Purchase price']
            
            if not current_prices.empty:
                plt.hist(current_prices, alpha=0.7, label='Current Listings', bins=30)
            if not historical_prices.empty:
                plt.hist(historical_prices, alpha=0.7, label='Historical Sales', bins=30)
                
            plt.xlabel('Price')
            plt.ylabel('Frequency')
            plt.title('Property Price Distribution: Current vs Historical')
            plt.legend()
            plt.savefig(os.path.join(os.path.dirname(__file__), '..', 'data', 'price_distribution.png'))
            plt.close()
            
        logging.info('Visualizations created and saved')
        
    def run_full_analysis(self, location_filter=None):
        """Run the complete property analysis pipeline."""
        logging.info('Starting full property analysis pipeline')
        
        # Step 1: Load data
        self.load_historical_data()
        self.load_current_data()
        
        # Step 2: Combine datasets
        self.combine_datasets()
        
        # Step 3: Generate insights
        insights = self.generate_insights(location_filter)
        
        # Step 4: Create visualizations
        self.create_visualizations(location_filter)
        
        logging.info('Property analysis pipeline complete')
        return insights

if __name__ == "__main__":
    analyzer = PropertyAnalyzer()
    
    # Example usage with location filter
    target_locations = ['Lawson', 'Hazelbrook', 'Woodford', 'Linden', 'Faulconbridge', 
                       'Springwood', 'Valley Heights', 'Warrimoo']
    
    insights = analyzer.run_full_analysis(location_filter=target_locations)
    print("Analysis complete! Check the generated files and logs for results.")
