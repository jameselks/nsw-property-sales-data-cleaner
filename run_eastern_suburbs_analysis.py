#!/usr/bin/env python3
"""
Eastern Suburbs Sydney Property Analysis Runner
Simple script to run the Eastern Suburbs analysis
"""

from src.analysis.eastern_suburbs_analyzer import EasternSuburbsAnalyzer

def main():
    """Run Eastern Suburbs property analysis"""
    print("🏠 Starting Eastern Suburbs Sydney Property Analysis")
    print("=" * 60)
    
    analyzer = EasternSuburbsAnalyzer()
    analyzer.run_full_analysis()
    
    print("\n" + "=" * 60)
    print("✅ Eastern Suburbs analysis completed successfully!")
    print("📁 Check the 'src/data/eastern_suburbs_analysis/' directory for results")

if __name__ == "__main__":
    main()
