"""
Pattern Analyzer - Analyze SBC decline patterns 4+ years post-IPO
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging


class PatternAnalyzer:
    """Analyze SBC decline patterns across cohorts of companies"""

    def __init__(self):
        """Initialize pattern analyzer"""
        self.logger = logging.getLogger(__name__)

    def analyze_q16_cliff(self, master_df: pd.DataFrame) -> pd.DataFrame:
        """
        Analyze Q16 (4-year) cliff patterns for all companies

        Args:
            master_df: Master dataset with all companies

        Returns:
            DataFrame with Q16 cliff analysis for each company
        """
        self.logger.info("Analyzing Q16 cliff patterns...")

        results = []

        # Get unique tickers
        tickers = master_df['ticker'].unique()

        for ticker in tickers:
            company_df = master_df[master_df['ticker'] == ticker]

            # Get data at key quarters
            q16_data = self._get_quarter_data(company_df, 16)
            q20_data = self._get_quarter_data(company_df, 20)
            q24_data = self._get_quarter_data(company_df, 24)

            if q16_data is None:
                continue  # Skip if no Q16 data

            result = {
                'ticker': ticker,
                'company': company_df['company'].iloc[0],
                'ipo_date': company_df['ipo_date'].iloc[0],
                'ipo_year': company_df['ipo_date'].iloc[0].year,
                'listing_type': company_df['listing_type'].iloc[0],
                'is_acquired': company_df['is_acquired'].iloc[0],
                'q16_sbc_pct': q16_data['sbc_pct'],
                'q16_revenue_m': q16_data['revenue_m'],
                'q16_quarter_end': q16_data['quarter_end']
            }

            # Q20 analysis
            if q20_data is not None:
                result['q20_sbc_pct'] = q20_data['sbc_pct']
                result['q20_revenue_m'] = q20_data['revenue_m']
                result['decline_q16_to_q20'] = q20_data['sbc_pct'] - q16_data['sbc_pct']
                result['has_q20'] = True
            else:
                result['q20_sbc_pct'] = None
                result['q20_revenue_m'] = None
                result['decline_q16_to_q20'] = None
                result['has_q20'] = False

            # Q24 analysis
            if q24_data is not None:
                result['q24_sbc_pct'] = q24_data['sbc_pct']
                result['q24_revenue_m'] = q24_data['revenue_m']
                result['decline_q16_to_q24'] = q24_data['sbc_pct'] - q16_data['sbc_pct']
                result['has_q24'] = True
            else:
                result['q24_sbc_pct'] = None
                result['q24_revenue_m'] = None
                result['decline_q16_to_q24'] = None
                result['has_q24'] = False

            # Calculate share growth at Q14-15 (leading indicator)
            q14_data = self._get_quarter_data(company_df, 14)
            q15_data = self._get_quarter_data(company_df, 15)
            if q14_data is not None and q15_data is not None:
                result['q14_15_shares_yoy'] = (
                    q14_data.get('shares_yoy_growth', 0) + q15_data.get('shares_yoy_growth', 0)
                ) / 2
            else:
                result['q14_15_shares_yoy'] = None

            # Determine status
            max_quarter = company_df['quarters_since_ipo'].max()
            if result['is_acquired'] and max_quarter < 20:
                result['status'] = 'Acquired before Q20'
            elif max_quarter >= 24:
                result['status'] = 'Complete data'
            elif max_quarter >= 20:
                result['status'] = 'Data through Q20'
            else:
                result['status'] = 'Limited data'

            results.append(result)

        cliff_df = pd.DataFrame(results)

        self.logger.info(f"Q16 cliff analysis complete: {len(cliff_df)} companies")

        return cliff_df

    def _get_quarter_data(self, company_df: pd.DataFrame, quarter: int) -> Optional[pd.Series]:
        """Get data for specific quarter number"""
        quarter_data = company_df[company_df['quarters_since_ipo'] == quarter]

        if len(quarter_data) == 0:
            return None

        return quarter_data.iloc[0]

    def calculate_pattern_statistics(self, cliff_df: pd.DataFrame,
                                     traditional_ipo_only: bool = False) -> Dict[str, any]:
        """
        Calculate statistics on Q16→Q20 decline patterns

        Args:
            cliff_df: DataFrame from analyze_q16_cliff()
            traditional_ipo_only: If True, exclude direct listings

        Returns:
            Dictionary with pattern statistics
        """
        self.logger.info("Calculating pattern statistics...")

        # Filter to companies with Q20 data
        analysis_df = cliff_df[cliff_df['has_q20'] == True].copy()

        if traditional_ipo_only:
            analysis_df = analysis_df[analysis_df['listing_type'] == 'Traditional IPO']

        # Calculate basic statistics on Q16→Q20 decline
        decline_data = analysis_df['decline_q16_to_q20'].dropna()

        if len(decline_data) == 0:
            self.logger.warning("No decline data available for statistics")
            return {}

        stats = {
            'n_companies': len(decline_data),
            'n_total_at_q16': len(cliff_df),
            'mean_decline': float(decline_data.mean()),
            'median_decline': float(decline_data.median()),
            'std_decline': float(decline_data.std()),
            'min_decline': float(decline_data.min()),
            'max_decline': float(decline_data.max()),
            'pct_25': float(decline_data.quantile(0.25)),
            'pct_75': float(decline_data.quantile(0.75)),
            'pct_10': float(decline_data.quantile(0.10)),
            'pct_90': float(decline_data.quantile(0.90))
        }

        # Calculate % showing significant declines
        stats['pct_decline_gt_3pts'] = float((decline_data < -3).sum() / len(decline_data) * 100)
        stats['pct_decline_gt_5pts'] = float((decline_data < -5).sum() / len(decline_data) * 100)
        stats['pct_decline_gt_7pts'] = float((decline_data < -7).sum() / len(decline_data) * 100)

        # Calculate % showing increases (unusual)
        stats['pct_increase'] = float((decline_data > 0).sum() / len(decline_data) * 100)

        self.logger.info(f"Statistics calculated for {stats['n_companies']} companies")

        return stats

    def segment_by_ipo_year(self, cliff_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate statistics segmented by IPO year

        Args:
            cliff_df: DataFrame from analyze_q16_cliff()

        Returns:
            DataFrame with statistics by IPO year
        """
        self.logger.info("Segmenting analysis by IPO year...")

        # Filter to companies with Q20 data
        analysis_df = cliff_df[cliff_df['has_q20'] == True].copy()

        if len(analysis_df) == 0:
            return pd.DataFrame()

        # Group by IPO year
        by_year = analysis_df.groupby('ipo_year')['decline_q16_to_q20'].agg([
            ('n_companies', 'count'),
            ('mean_decline', 'mean'),
            ('median_decline', 'median'),
            ('std_decline', 'std'),
            ('pct_25', lambda x: x.quantile(0.25)),
            ('pct_75', lambda x: x.quantile(0.75))
        ]).round(2)

        by_year = by_year.reset_index()

        return by_year

    def segment_by_listing_type(self, cliff_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate statistics segmented by listing type

        Args:
            cliff_df: DataFrame from analyze_q16_cliff()

        Returns:
            DataFrame with statistics by listing type
        """
        self.logger.info("Segmenting analysis by listing type...")

        # Filter to companies with Q20 data
        analysis_df = cliff_df[cliff_df['has_q20'] == True].copy()

        if len(analysis_df) == 0:
            return pd.DataFrame()

        # Group by listing type
        by_type = analysis_df.groupby('listing_type')['decline_q16_to_q20'].agg([
            ('n_companies', 'count'),
            ('mean_decline', 'mean'),
            ('median_decline', 'median'),
            ('std_decline', 'std'),
            ('pct_25', lambda x: x.quantile(0.25)),
            ('pct_75', lambda x: x.quantile(0.75))
        ]).round(2)

        by_type = by_type.reset_index()

        return by_type

    def analyze_leading_indicators(self, cliff_df: pd.DataFrame) -> Dict[str, any]:
        """
        Analyze which metrics correlate with larger SBC declines

        Args:
            cliff_df: DataFrame from analyze_q16_cliff()

        Returns:
            Dictionary with correlation analysis
        """
        self.logger.info("Analyzing leading indicators...")

        # Filter to companies with complete data
        analysis_df = cliff_df[
            (cliff_df['has_q20'] == True) &
            (cliff_df['decline_q16_to_q20'].notna())
        ].copy()

        if len(analysis_df) < 5:  # Need minimum sample size
            return {'note': 'Insufficient data for correlation analysis'}

        correlations = {}

        # Correlation with Q16 SBC level
        if 'q16_sbc_pct' in analysis_df.columns:
            corr = analysis_df['decline_q16_to_q20'].corr(analysis_df['q16_sbc_pct'])
            if not np.isnan(corr):
                correlations['q16_sbc_pct'] = float(corr)

        # Correlation with share growth deceleration
        if 'q14_15_shares_yoy' in analysis_df.columns:
            valid_data = analysis_df[analysis_df['q14_15_shares_yoy'].notna()]
            if len(valid_data) >= 5:
                corr = valid_data['decline_q16_to_q20'].corr(valid_data['q14_15_shares_yoy'])
                if not np.isnan(corr):
                    correlations['q14_15_shares_yoy'] = float(corr)

        # Correlation with company size at Q16
        if 'q16_revenue_m' in analysis_df.columns:
            corr = analysis_df['decline_q16_to_q20'].corr(analysis_df['q16_revenue_m'])
            if not np.isnan(corr):
                correlations['q16_revenue_m'] = float(corr)

        return correlations

    def identify_outliers(self, cliff_df: pd.DataFrame, ticker: str) -> Dict[str, any]:
        """
        Identify if a specific company is an outlier

        Args:
            cliff_df: DataFrame from analyze_q16_cliff()
            ticker: Company ticker to analyze

        Returns:
            Dictionary with outlier analysis
        """
        # Get company data
        company_data = cliff_df[cliff_df['ticker'] == ticker]

        if len(company_data) == 0:
            return {'found': False, 'reason': 'Company not in dataset'}

        company_row = company_data.iloc[0]

        # Get overall statistics (traditional IPOs only)
        traditional_df = cliff_df[
            (cliff_df['listing_type'] == 'Traditional IPO') &
            (cliff_df['has_q20'] == True)
        ]

        if len(traditional_df) == 0:
            return {'found': False, 'reason': 'No comparable companies'}

        q16_sbc_values = traditional_df['q16_sbc_pct'].dropna()
        company_q16_sbc = company_row.get('q16_sbc_pct')

        if pd.isna(company_q16_sbc):
            return {'found': False, 'reason': 'Company missing Q16 data'}

        # Calculate z-score
        mean_sbc = q16_sbc_values.mean()
        std_sbc = q16_sbc_values.std()

        if std_sbc == 0:
            z_score = 0
        else:
            z_score = (company_q16_sbc - mean_sbc) / std_sbc

        # Determine if outlier (z-score > 2 or < -2)
        is_outlier = abs(z_score) > 2

        result = {
            'found': True,
            'is_outlier': is_outlier,
            'company_q16_sbc_pct': float(company_q16_sbc),
            'cohort_mean': float(mean_sbc),
            'cohort_median': float(q16_sbc_values.median()),
            'z_score': float(z_score),
            'percentile': float((q16_sbc_values < company_q16_sbc).sum() / len(q16_sbc_values) * 100)
        }

        if is_outlier:
            if z_score > 2:
                result['outlier_type'] = 'High SBC% (above peers)'
            else:
                result['outlier_type'] = 'Low SBC% (below peers)'

        return result

    def create_decline_distribution(self, cliff_df: pd.DataFrame,
                                   bins: Optional[List[float]] = None) -> pd.DataFrame:
        """
        Create distribution of Q16→Q20 declines

        Args:
            cliff_df: DataFrame from analyze_q16_cliff()
            bins: Optional custom bins for histogram

        Returns:
            DataFrame with distribution data
        """
        if bins is None:
            bins = [-20, -10, -7, -5, -3, -1, 0, 2, 5, 10]

        # Filter to companies with Q20 data
        analysis_df = cliff_df[cliff_df['has_q20'] == True].copy()
        decline_data = analysis_df['decline_q16_to_q20'].dropna()

        if len(decline_data) == 0:
            return pd.DataFrame()

        # Create histogram
        counts, bin_edges = np.histogram(decline_data, bins=bins)

        # Create labels
        labels = []
        for i in range(len(bin_edges) - 1):
            labels.append(f"{bin_edges[i]:.1f} to {bin_edges[i+1]:.1f}")

        dist_df = pd.DataFrame({
            'range': labels,
            'count': counts,
            'percentage': (counts / len(decline_data) * 100).round(1)
        })

        return dist_df


def test_analyzer():
    """Test the pattern analyzer"""
    logging.basicConfig(level=logging.INFO)

    # Create sample cliff data
    np.random.seed(42)
    n_companies = 30

    sample_cliff_df = pd.DataFrame({
        'ticker': [f'TICK{i}' for i in range(n_companies)],
        'company': [f'Company {i}' for i in range(n_companies)],
        'ipo_date': pd.date_range(start='2017-01-01', periods=n_companies, freq='90D'),
        'ipo_year': [2017] * 10 + [2018] * 10 + [2019] * 10,
        'listing_type': ['Traditional IPO'] * 28 + ['Direct Listing'] * 2,
        'is_acquired': [False] * 25 + [True] * 5,
        'q16_sbc_pct': np.random.uniform(12, 25, n_companies),
        'q20_sbc_pct': None,
        'decline_q16_to_q20': np.random.uniform(-10, -2, n_companies),
        'has_q20': [True] * 25 + [False] * 5,
        'has_q24': [True] * 20 + [False] * 10
    })

    # Calculate Q20 SBC from decline
    sample_cliff_df['q20_sbc_pct'] = sample_cliff_df.apply(
        lambda row: row['q16_sbc_pct'] + row['decline_q16_to_q20'] if row['has_q20'] else None,
        axis=1
    )

    analyzer = PatternAnalyzer()

    # Test statistics
    stats = analyzer.calculate_pattern_statistics(sample_cliff_df)
    print("\nPattern Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Test segmentation
    by_year = analyzer.segment_by_ipo_year(sample_cliff_df)
    print("\nBy IPO Year:")
    print(by_year)

    # Test distribution
    dist = analyzer.create_decline_distribution(sample_cliff_df)
    print("\nDecline Distribution:")
    print(dist)


if __name__ == "__main__":
    test_analyzer()
