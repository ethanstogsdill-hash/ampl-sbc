#!/usr/bin/env python3
"""
SaaS SBC Analysis Engine - Main Script
Collects and analyzes stock-based compensation data for SaaS IPO cohorts
"""

import pandas as pd
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

from sec_data_collector import SECDataCollector
from data_processor import DataProcessor
from pattern_analyzer import PatternAnalyzer
from amplitude_predictor import AmplitudePredictor
from excel_exporter import ExcelExporter


# Configuration
IPO_DATES_FILE = 'ipo_dates.csv'
OUTPUT_FILE = 'sbc_analysis_output.xlsx'
LOG_FILE = 'sbc_analysis.log'
MIN_QUALITY_SCORE = 'C'  # Minimum quality score to include
MIN_QUARTERS = 16  # Minimum quarters required


def setup_logging():
    """Configure logging to both file and console"""
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # File handler
    file_handler = logging.FileHandler(LOG_FILE, mode='w')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def load_ipo_dates(file_path: str) -> pd.DataFrame:
    """
    Load IPO dates from CSV file

    Args:
        file_path: Path to ipo_dates.csv

    Returns:
        DataFrame with IPO dates
    """
    logger = logging.getLogger(__name__)

    if not Path(file_path).exists():
        logger.error(f"IPO dates file not found: {file_path}")
        logger.error("Please create ipo_dates.csv with columns: Ticker, Company_Name, IPO_Date, Notes")
        sys.exit(1)

    try:
        df = pd.read_csv(file_path)

        # Validate required columns
        required_cols = ['Ticker', 'Company_Name', 'IPO_Date']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            logger.error(f"Missing required columns in {file_path}: {missing_cols}")
            sys.exit(1)

        # Parse dates
        df['IPO_Date'] = pd.to_datetime(df['IPO_Date'], errors='coerce')

        # Count valid entries
        valid_count = df['IPO_Date'].notna().sum()
        invalid_count = df['IPO_Date'].isna().sum()

        logger.info(f"Loaded {len(df)} companies from {file_path}")
        logger.info(f"  Valid IPO dates: {valid_count}")
        logger.info(f"  Invalid/missing IPO dates: {invalid_count}")

        return df

    except Exception as e:
        logger.error(f"Error loading IPO dates file: {e}")
        sys.exit(1)


def collect_all_company_data(ipo_df: pd.DataFrame, collector: SECDataCollector) -> Dict[str, Dict]:
    """
    Collect data for all companies

    Args:
        ipo_df: DataFrame with IPO information
        collector: SEC data collector instance

    Returns:
        Dictionary mapping ticker to {df, quality, source}
    """
    logger = logging.getLogger(__name__)
    all_data = {}

    logger.info(f"\n{'='*60}")
    logger.info("STARTING DATA COLLECTION")
    logger.info(f"{'='*60}\n")

    for idx, row in ipo_df.iterrows():
        ticker = row['Ticker']
        company_name = row['Company_Name']
        ipo_date = row['IPO_Date']

        # Skip if missing IPO date
        if pd.isna(ipo_date):
            logger.warning(f"{ticker} ({company_name}): Skipping - missing IPO date")
            continue

        logger.info(f"\n[{idx + 1}/{len(ipo_df)}] Processing {ticker} ({company_name})...")
        logger.info(f"  IPO Date: {ipo_date.strftime('%Y-%m-%d')}")

        try:
            # Collect data
            df, quality, source = collector.collect_company_data(ticker, company_name, ipo_date)

            if len(df) > 0:
                # Validate data
                df_validated, warnings = collector.validate_data(df)

                all_data[ticker] = {
                    'df': df_validated,
                    'quality': quality,
                    'source': source,
                    'warnings': warnings
                }

                logger.info(f"  ✓ Success: {len(df)} quarters, quality {quality}")

                if warnings:
                    logger.warning(f"  Warnings for {ticker}:")
                    for warning in warnings:
                        logger.warning(f"    - {warning}")
            else:
                logger.warning(f"  ✗ Failed: No data collected (quality {quality})")
                all_data[ticker] = {
                    'df': df,
                    'quality': quality,
                    'source': source,
                    'warnings': []
                }

        except Exception as e:
            logger.error(f"  ✗ Error collecting data for {ticker}: {e}")
            continue

    logger.info(f"\n{'='*60}")
    logger.info(f"DATA COLLECTION COMPLETE")
    logger.info(f"  Successfully collected: {sum(1 for d in all_data.values() if len(d['df']) > 0)}/{len(ipo_df)}")
    logger.info(f"{'='*60}\n")

    return all_data


def main():
    """Main execution function"""
    logger = setup_logging()

    logger.info("="*60)
    logger.info("SaaS SBC Analysis Engine")
    logger.info("="*60)
    logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Output will be saved to: {OUTPUT_FILE}")
    logger.info(f"Log file: {LOG_FILE}\n")

    # Step 1: Load IPO dates
    logger.info("Step 1: Loading IPO dates...")
    ipo_df = load_ipo_dates(IPO_DATES_FILE)

    # Step 2: Collect data from SEC
    logger.info("\nStep 2: Collecting data from SEC EDGAR...")
    collector = SECDataCollector(use_cache=True)
    all_data = collect_all_company_data(ipo_df, collector)

    # Step 3: Process and filter data
    logger.info("\nStep 3: Processing and filtering data...")
    processor = DataProcessor()

    # Process each company's data
    for ticker, data in all_data.items():
        if len(data['df']) > 0:
            data['df'] = processor.process_company_data(data['df'], ticker)

    # Filter by quality
    included_companies, excluded_companies = processor.filter_quality_companies(
        all_data, min_quality=MIN_QUALITY_SCORE
    )

    logger.info(f"  Included: {len(included_companies)} companies")
    logger.info(f"  Excluded: {len(excluded_companies)} companies")

    # Create master dataset
    master_df = processor.create_master_dataset(included_companies)
    master_df = processor.add_ipo_cohorts(master_df)

    logger.info(f"  Master dataset: {len(master_df)} rows")

    # Step 4: Analyze patterns
    logger.info("\nStep 4: Analyzing SBC decline patterns...")
    analyzer = PatternAnalyzer()

    # Q16 cliff analysis
    cliff_df = analyzer.analyze_q16_cliff(master_df)
    logger.info(f"  Q16 cliff analysis: {len(cliff_df)} companies at Q16+")

    # Overall pattern statistics
    pattern_stats = analyzer.calculate_pattern_statistics(cliff_df, traditional_ipo_only=False)
    logger.info(f"  Pattern statistics calculated for {pattern_stats.get('n_companies', 0)} companies with Q20+ data")

    # 2021 cohort statistics (for Amplitude)
    cliff_df_2021 = cliff_df[cliff_df['ipo_year'] == 2021]
    if len(cliff_df_2021) > 0:
        pattern_stats_2021 = analyzer.calculate_pattern_statistics(cliff_df_2021, traditional_ipo_only=True)
        logger.info(f"  2021 cohort statistics: {pattern_stats_2021.get('n_companies', 0)} companies")
    else:
        pattern_stats_2021 = {}
        logger.info("  2021 cohort: No companies with Q20+ data yet")

    # Segmentation analysis
    by_ipo_year = analyzer.segment_by_ipo_year(cliff_df)
    by_listing_type = analyzer.segment_by_listing_type(cliff_df)
    distribution = analyzer.create_decline_distribution(cliff_df)

    segmentation_data = {
        'by_ipo_year': by_ipo_year,
        'by_listing_type': by_listing_type,
        'distribution': distribution
    }

    # Leading indicators
    correlations = analyzer.analyze_leading_indicators(cliff_df)
    logger.info(f"  Leading indicators analyzed")

    # Step 5: Amplitude predictions
    logger.info("\nStep 5: Generating Amplitude predictions...")
    predictor = AmplitudePredictor()

    amplitude_state = predictor.get_amplitude_current_state(master_df, cliff_df)

    if amplitude_state.get('found', False):
        logger.info(f"  Amplitude current state: Q{amplitude_state['current_quarter_number']}, "
                   f"SBC={amplitude_state['current_sbc_pct']:.2f}%")

        if amplitude_state.get('at_q16', False):
            # Generate predictions
            amplitude_prediction = predictor.predict_trajectory(
                amplitude_state, pattern_stats, pattern_stats_2021
            )

            # Peer comparison
            amplitude_comparison = predictor.compare_to_peers(amplitude_state, cliff_df)

            logger.info(f"  Prediction generated using: {amplitude_prediction.get('cohort_used', 'N/A')}")
            logger.info(f"  Base case Q16→Q20 decline: {amplitude_prediction.get('base_decline_q16_q20', 0):.2f}%")

            if not amplitude_comparison.get('error'):
                logger.info(f"  Amplitude vs peers: {amplitude_comparison.get('outlier_note', 'N/A')}")
        else:
            amplitude_prediction = {
                'error': 'Amplitude not yet at Q16',
                'current_quarter': amplitude_state['current_quarter_number']
            }
            amplitude_comparison = {}
            logger.info(f"  Amplitude is at Q{amplitude_state['current_quarter_number']}, not yet at Q16 for prediction")
    else:
        amplitude_prediction = {'error': 'Amplitude data not found'}
        amplitude_comparison = {}
        logger.warning("  Amplitude data not found in dataset")

    # Step 6: Export to Excel
    logger.info("\nStep 6: Exporting to Excel...")

    metadata = {
        'run_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_as_of': master_df['quarter_end'].max().strftime('%Y-%m-%d') if len(master_df) > 0 else 'N/A',
        'total_companies': len(ipo_df),
        'companies_collected': len([d for d in all_data.values() if len(d['df']) > 0]),
        'companies_included': len(included_companies),
        'companies_excluded': len(excluded_companies),
        'excluded_tickers': list(excluded_companies.keys()),
        'min_quality': MIN_QUALITY_SCORE,
        'min_quarters': MIN_QUARTERS
    }

    exporter = ExcelExporter(OUTPUT_FILE)
    exporter.export_full_workbook(
        master_df=master_df,
        cliff_df=cliff_df,
        pattern_stats=pattern_stats,
        pattern_stats_2021=pattern_stats_2021,
        segmentation_data=segmentation_data,
        amplitude_prediction=amplitude_prediction,
        amplitude_comparison=amplitude_comparison,
        excluded_companies=excluded_companies,
        metadata=metadata
    )

    logger.info(f"  Excel workbook saved: {OUTPUT_FILE}")

    # Step 7: Print summary report
    logger.info("\n" + "="*60)
    logger.info("ANALYSIS COMPLETE - SUMMARY")
    logger.info("="*60)
    logger.info(f"Total companies processed: {len(all_data)}")
    logger.info(f"  Included in analysis: {len(included_companies)}")
    logger.info(f"  Excluded (low quality): {len(excluded_companies)}")
    logger.info(f"")
    logger.info(f"Companies at Q16+: {len(cliff_df)}")
    logger.info(f"Companies with Q20+ data: {pattern_stats.get('n_companies', 0)}")
    logger.info(f"")
    logger.info(f"Q16→Q20 Decline Statistics:")
    logger.info(f"  Median: {pattern_stats.get('median_decline', 0):.2f} percentage points")
    logger.info(f"  25th percentile: {pattern_stats.get('pct_25', 0):.2f} pts (conservative)")
    logger.info(f"  75th percentile: {pattern_stats.get('pct_75', 0):.2f} pts (aggressive)")
    logger.info(f"  % with >5pt decline: {pattern_stats.get('pct_decline_gt_5pts', 0):.1f}%")
    logger.info(f"")

    if amplitude_state.get('found', False) and amplitude_state.get('at_q16', False):
        logger.info(f"Amplitude Prediction:")
        logger.info(f"  Current Q{amplitude_state['current_quarter_number']} SBC: {amplitude_state['current_sbc_pct']:.2f}%")
        if 'error' not in amplitude_prediction:
            logger.info(f"  Predicted Q20 SBC (base): {amplitude_state['q16_sbc_pct'] + amplitude_prediction.get('base_decline_q16_q20', 0):.2f}%")

    logger.info(f"")
    logger.info(f"Output file: {OUTPUT_FILE}")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"")
    logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)

    # Print warnings if any companies need manual review
    manual_review = [ticker for ticker, data in all_data.items()
                    if data['quality'] == 'D']

    if manual_review:
        logger.warning("\nCompanies flagged for manual review (Quality D):")
        for ticker in manual_review:
            logger.warning(f"  - {ticker}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"\nFatal error: {e}", exc_info=True)
        sys.exit(1)
