"""
Data Processor - Clean and calculate financial metrics from raw SEC data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging


class DataProcessor:
    """Process and calculate financial metrics from raw SEC data"""

    def __init__(self):
        """Initialize data processor"""
        self.logger = logging.getLogger(__name__)

    def process_company_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """
        Process raw financial data for a single company

        Args:
            df: Raw financial DataFrame from SEC collector
            ticker: Company ticker

        Returns:
            Processed DataFrame with calculated metrics
        """
        if len(df) == 0:
            return df

        self.logger.info(f"Processing data for {ticker}: {len(df)} quarters")

        # Make a copy
        processed = df.copy()

        # Convert amounts from raw to millions
        processed['sbc_m'] = (processed['sbc'] / 1_000_000).round(2)
        processed['revenue_m'] = (processed['revenue'] / 1_000_000).round(2)
        processed['shares_m'] = (processed['shares'] / 1_000_000).round(2)

        # Calculate SBC as % of revenue
        processed['sbc_pct'] = (processed['sbc_m'] / processed['revenue_m'] * 100).round(2)

        # Calculate quarter-over-quarter changes
        processed['sbc_pct_qoq'] = processed['sbc_pct'].diff().round(2)
        processed['revenue_qoq_pct'] = (processed['revenue_m'].pct_change() * 100).round(2)

        # Calculate year-over-year changes (4 quarters ago)
        processed['sbc_pct_yoy'] = (
            processed['sbc_pct'] - processed['sbc_pct'].shift(4)
        ).round(2)

        processed['shares_yoy_growth'] = (
            processed['shares_m'].pct_change(4) * 100
        ).round(2)

        # Calculate operating margin if operating income available
        if 'operating_income' in processed.columns:
            processed['operating_income_m'] = (processed['operating_income'] / 1_000_000).round(2)
            processed['gaap_op_margin'] = (
                processed['operating_income_m'] / processed['revenue_m'] * 100
            ).round(2)
        else:
            processed['gaap_op_margin'] = None

        # Add fiscal quarter notation (Q1, Q2, Q3, Q4)
        processed['fiscal_quarter'] = processed.apply(
            lambda row: self._get_fiscal_quarter(row['quarter_end']), axis=1
        )

        # Remove intermediate calculation columns
        processed = processed.drop(columns=['sbc', 'revenue', 'shares'], errors='ignore')
        if 'operating_income' in processed.columns:
            processed = processed.drop(columns=['operating_income'], errors='ignore')

        return processed

    def _get_fiscal_quarter(self, date: datetime) -> str:
        """Get fiscal quarter string (Q1, Q2, Q3, Q4) from date"""
        month = date.month
        if month in [1, 2, 3]:
            return 'Q1'
        elif month in [4, 5, 6]:
            return 'Q2'
        elif month in [7, 8, 9]:
            return 'Q3'
        else:
            return 'Q4'

    def filter_quality_companies(self, all_data: Dict[str, Dict],
                                 min_quality: str = 'C') -> Tuple[Dict, Dict]:
        """
        Filter companies based on data quality score

        Args:
            all_data: Dictionary mapping ticker to {df, quality, source}
            min_quality: Minimum quality score to include ('A', 'B', 'C', 'D')

        Returns:
            Tuple of (included companies dict, excluded companies dict)
        """
        quality_order = {'A': 4, 'B': 3, 'C': 2, 'D': 1, 'F': 0}
        min_score = quality_order.get(min_quality, 2)

        included = {}
        excluded = {}

        for ticker, data in all_data.items():
            quality = data['quality']
            score = quality_order.get(quality, 0)

            if score >= min_score and len(data['df']) >= 16:  # At least Q1-Q16
                included[ticker] = data
            else:
                excluded[ticker] = data
                reason = []
                if score < min_score:
                    reason.append(f"Quality {quality} below threshold")
                if len(data['df']) < 16:
                    reason.append(f"Only {len(data['df'])} quarters (need 16+)")
                data['exclusion_reason'] = '; '.join(reason)

        self.logger.info(f"Filtered: {len(included)} included, {len(excluded)} excluded")

        return included, excluded

    def identify_special_situations(self, df: pd.DataFrame, ticker: str) -> Dict[str, any]:
        """
        Identify special situations (acquisitions, direct listings, etc.)

        Args:
            df: Company financial data
            ticker: Company ticker

        Returns:
            Dictionary with special situation flags
        """
        special_situations = {
            'WORK': {'acquired': datetime(2021, 7, 21), 'acquirer': 'Salesforce'},
            'HCP': {'acquired': datetime(2024, 4, 24), 'acquirer': 'IBM'},
            'PLAN': {'acquired': datetime(2022, 3, 21), 'acquirer': 'Thoma Bravo'},
            'MULE': {'acquired': datetime(2018, 5, 1), 'acquirer': 'Salesforce'},
            'PVTL': {'acquired': datetime(2019, 12, 30), 'acquirer': 'VMware'},
            'SVMK': {'acquired': datetime(2021, 11, 1), 'acquirer': 'Momentive'},
            'CBLK': {'acquired': datetime(2019, 10, 8), 'acquirer': 'VMware'},
            'PS': {'acquired': datetime(2021, 4, 12), 'acquirer': 'Vista Equity'},
            'MDLA': {'acquired': datetime(2021, 10, 22), 'acquirer': 'Thoma Bravo'},
        }

        direct_listings = ['PLTR', 'ASAN', 'COIN']
        spacs = []  # Add if identified

        result = {
            'is_acquired': ticker in special_situations,
            'is_direct_listing': ticker in direct_listings,
            'is_spac': ticker in spacs,
            'listing_type': 'Traditional IPO'
        }

        if result['is_acquired']:
            result['acquisition_date'] = special_situations[ticker]['acquired']
            result['acquirer'] = special_situations[ticker]['acquirer']

        if result['is_direct_listing']:
            result['listing_type'] = 'Direct Listing'

        if result['is_spac']:
            result['listing_type'] = 'SPAC'

        return result

    def calculate_data_completeness(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Calculate data completeness metrics

        Args:
            df: Company financial data

        Returns:
            Dictionary with completeness metrics
        """
        max_quarter = df['quarters_since_ipo'].max() if len(df) > 0 else 0

        completeness = {
            'total_quarters': len(df),
            'max_quarter_number': int(max_quarter),
            'has_q1_q16': max_quarter >= 16,
            'has_q17_q20': max_quarter >= 20,
            'has_q21_q24': max_quarter >= 24,
            'most_recent_quarter': df['quarter_end'].max() if len(df) > 0 else None
        }

        # Check for gaps
        if len(df) > 1:
            expected_quarters = set(range(1, int(max_quarter) + 1))
            actual_quarters = set(df['quarters_since_ipo'].astype(int))
            missing_quarters = expected_quarters - actual_quarters
            completeness['has_gaps'] = len(missing_quarters) > 0
            completeness['missing_quarters'] = sorted(list(missing_quarters))
        else:
            completeness['has_gaps'] = False
            completeness['missing_quarters'] = []

        return completeness

    def create_master_dataset(self, included_companies: Dict[str, Dict]) -> pd.DataFrame:
        """
        Create master dataset combining all companies

        Args:
            included_companies: Dictionary of included companies with their data

        Returns:
            Combined DataFrame with all companies
        """
        all_dfs = []

        for ticker, data in included_companies.items():
            df = data['df'].copy()
            df['data_quality'] = data['quality']
            df['data_source'] = data['source']

            # Add special situation flags
            special = self.identify_special_situations(df, ticker)
            df['listing_type'] = special['listing_type']
            df['is_acquired'] = special['is_acquired']

            all_dfs.append(df)

        if len(all_dfs) == 0:
            return pd.DataFrame()

        master_df = pd.concat(all_dfs, ignore_index=True)
        master_df = master_df.sort_values(['ticker', 'quarter_end']).reset_index(drop=True)

        self.logger.info(f"Created master dataset: {len(master_df)} rows, {len(included_companies)} companies")

        return master_df

    def get_company_at_quarter(self, df: pd.DataFrame, ticker: str, quarter: int) -> Optional[pd.Series]:
        """
        Get company data at specific quarter number since IPO

        Args:
            df: Master dataset
            ticker: Company ticker
            quarter: Quarter number since IPO

        Returns:
            Series with company data at that quarter, or None if not available
        """
        company_data = df[(df['ticker'] == ticker) & (df['quarters_since_ipo'] == quarter)]

        if len(company_data) == 0:
            return None

        return company_data.iloc[0]

    def calculate_cohort_stats(self, df: pd.DataFrame, column: str,
                              groupby: Optional[str] = None) -> pd.DataFrame:
        """
        Calculate statistics for a metric across cohorts

        Args:
            df: Master dataset
            column: Column to calculate stats for
            groupby: Optional column to group by (e.g., 'listing_type')

        Returns:
            DataFrame with statistics
        """
        if groupby:
            grouped = df.groupby(groupby)[column]
        else:
            grouped = df[column]

        if groupby:
            stats = grouped.agg([
                ('count', 'count'),
                ('mean', 'mean'),
                ('median', 'median'),
                ('std', 'std'),
                ('min', 'min'),
                ('25th_pct', lambda x: x.quantile(0.25)),
                ('75th_pct', lambda x: x.quantile(0.75)),
                ('max', 'max')
            ]).round(2)
        else:
            stats = pd.DataFrame({
                'count': [grouped.count()],
                'mean': [grouped.mean()],
                'median': [grouped.median()],
                'std': [grouped.std()],
                'min': [grouped.min()],
                '25th_pct': [grouped.quantile(0.25)],
                '75th_pct': [grouped.quantile(0.75)],
                'max': [grouped.max()]
            }).round(2)

        return stats

    def get_ipo_year_cohort(self, ipo_date: datetime) -> int:
        """Get IPO year cohort from IPO date"""
        return ipo_date.year

    def add_ipo_cohorts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add IPO year cohort column to DataFrame"""
        df['ipo_year'] = df['ipo_date'].apply(self.get_ipo_year_cohort)
        return df


def test_processor():
    """Test the data processor"""
    logging.basicConfig(level=logging.INFO)

    # Create sample data
    dates = pd.date_range(start='2020-12-31', periods=16, freq='Q')
    sample_df = pd.DataFrame({
        'ticker': 'TEST',
        'company': 'Test Company',
        'ipo_date': datetime(2020, 9, 16),
        'quarter_end': dates,
        'filing_date': dates + timedelta(days=45),
        'sbc': np.random.uniform(30_000_000, 50_000_000, 16),
        'revenue': np.random.uniform(200_000_000, 400_000_000, 16),
        'shares': np.random.uniform(200_000_000, 220_000_000, 16),
        'operating_income': np.random.uniform(-10_000_000, 20_000_000, 16),
        'quarters_since_ipo': range(1, 17)
    })

    processor = DataProcessor()
    processed = processor.process_company_data(sample_df, 'TEST')

    print("\nProcessed Data Sample:")
    print(processed[['ticker', 'quarters_since_ipo', 'revenue_m', 'sbc_m', 'sbc_pct']].head(10))

    completeness = processor.calculate_data_completeness(processed)
    print("\nData Completeness:")
    for key, value in completeness.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    test_processor()
