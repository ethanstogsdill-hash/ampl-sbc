"""
SEC Data Collector - Multi-tier SBC data extraction from SEC EDGAR
Handles XBRL, cash flow statement parsing, and non-GAAP reconciliation extraction
"""

import requests
import time
import logging
import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from bs4 import BeautifulSoup
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# SEC EDGAR API configuration
SEC_API_BASE = "https://data.sec.gov"
SEC_EDGAR_BASE = "https://www.sec.gov"
USER_AGENT = "SBC Analysis Engine research@example.com"  # SEC requires user agent

# Standard XBRL tags for stock-based compensation (in priority order)
PRIMARY_SBC_TAGS = [
    'ShareBasedCompensation',
    'AllocatedShareBasedCompensationExpense',
    'ShareBasedCompensationArrangementByShareBasedPaymentAwardCompensationCost1',
    'EmployeeServiceShareBasedCompensationNonvested',
    'StockBasedCompensation'
]

# Revenue tags
REVENUE_TAGS = [
    'Revenues',
    'RevenueFromContractWithCustomerExcludingAssessedTax',
    'SalesRevenueNet',
    'RevenueFromContractWithCustomer'
]

# Shares outstanding tags
SHARES_TAGS = [
    'CommonStockSharesOutstanding',
    'CommonStockSharesIssued',
    'WeightedAverageNumberOfSharesOutstandingBasic'
]

# Operating income tags
OPERATING_INCOME_TAGS = [
    'OperatingIncomeLoss',
    'IncomeLossFromOperations'
]


class SECDataCollector:
    """Collects financial data from SEC EDGAR filings with multi-tier extraction"""

    def __init__(self, use_cache: bool = True):
        """
        Initialize SEC data collector

        Args:
            use_cache: Whether to cache API responses (default True)
        """
        self.session = self._create_session()
        self.use_cache = use_cache
        self.cache = {}
        self.logger = logging.getLogger(__name__)

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic and proper headers"""
        session = requests.Session()

        # Retry strategy for failed requests
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Required headers for SEC EDGAR
        session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/json'
        })

        return session

    def get_cik_from_ticker(self, ticker: str) -> Optional[str]:
        """
        Get CIK (Central Index Key) from ticker symbol

        Args:
            ticker: Stock ticker symbol

        Returns:
            CIK as zero-padded string or None if not found
        """
        cache_key = f"cik_{ticker}"
        if self.use_cache and cache_key in self.cache:
            return self.cache[cache_key]

        try:
            # Use SEC's ticker mapping
            url = f"{SEC_API_BASE}/submissions/CIK{ticker}.json"
            time.sleep(0.11)  # Rate limiting: max 10 req/sec

            response = self.session.get(url)

            if response.status_code == 404:
                # Try company tickers endpoint
                url = "https://www.sec.gov/files/company_tickers.json"
                response = self.session.get(url)
                if response.status_code == 200:
                    tickers = response.json()
                    for item in tickers.values():
                        if item.get('ticker', '').upper() == ticker.upper():
                            cik = str(item['cik_str']).zfill(10)
                            self.cache[cache_key] = cik
                            return cik

            elif response.status_code == 200:
                data = response.json()
                cik = str(data.get('cik', '')).zfill(10)
                self.cache[cache_key] = cik
                return cik

            self.logger.warning(f"Could not find CIK for ticker {ticker}")
            return None

        except Exception as e:
            self.logger.error(f"Error getting CIK for {ticker}: {e}")
            return None

    def get_company_facts(self, cik: str) -> Optional[Dict]:
        """
        Get company facts from SEC XBRL API

        Args:
            cik: Company CIK (zero-padded)

        Returns:
            Dictionary of company facts or None if error
        """
        cache_key = f"facts_{cik}"
        if self.use_cache and cache_key in self.cache:
            return self.cache[cache_key]

        try:
            url = f"{SEC_API_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
            time.sleep(0.11)  # Rate limiting

            response = self.session.get(url)
            if response.status_code == 200:
                facts = response.json()
                self.cache[cache_key] = facts
                return facts
            else:
                self.logger.warning(f"Could not fetch company facts for CIK {cik}: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching company facts for CIK {cik}: {e}")
            return None

    def extract_xbrl_data(self, facts: Dict, tag_list: List[str],
                          start_date: datetime, end_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Extract quarterly data from XBRL facts for given tags

        Args:
            facts: Company facts dictionary from SEC API
            tag_list: List of XBRL tags to try (in priority order)
            start_date: Start date for data collection
            end_date: End date for data collection (default: today)

        Returns:
            DataFrame with columns: date, value, tag_used
        """
        if end_date is None:
            end_date = datetime.now()

        all_data = []
        tag_used = None

        # Try each tag in priority order
        for tag in tag_list:
            data = self._extract_tag_data(facts, tag, start_date, end_date)
            if len(data) > 0:
                tag_used = tag
                all_data = data
                break

        if len(all_data) == 0:
            return pd.DataFrame(columns=['date', 'value', 'tag_used'])

        df = pd.DataFrame(all_data)
        df['tag_used'] = tag_used
        return df

    def _extract_tag_data(self, facts: Dict, tag: str,
                          start_date: datetime, end_date: datetime) -> List[Dict]:
        """Extract data for a specific XBRL tag"""
        data = []

        try:
            # Navigate through facts structure
            if 'facts' not in facts:
                return data

            # Try both us-gaap and dei taxonomies
            for taxonomy in ['us-gaap', 'dei']:
                if taxonomy not in facts['facts']:
                    continue

                if tag not in facts['facts'][taxonomy]:
                    continue

                tag_data = facts['facts'][taxonomy][tag]

                # Get units (usually USD for financials, shares for share counts)
                if 'units' not in tag_data:
                    continue

                # Try USD first, then shares, then pure
                for unit in ['USD', 'shares', 'pure']:
                    if unit not in tag_data['units']:
                        continue

                    for item in tag_data['units'][unit]:
                        # Only quarterly data (10-Q and 10-K)
                        if item.get('form') not in ['10-Q', '10-K']:
                            continue

                        # Only data with end dates (not year-to-date)
                        if 'end' not in item:
                            continue

                        end_dt = datetime.strptime(item['end'], '%Y-%m-%d')

                        # Filter by date range
                        if end_dt < start_date or end_dt > end_date:
                            continue

                        # Only quarterly periods (roughly 90 days)
                        if 'start' in item:
                            start_dt = datetime.strptime(item['start'], '%Y-%m-%d')
                            days = (end_dt - start_dt).days
                            if days < 60 or days > 120:  # Filter out YTD and other periods
                                continue

                        data.append({
                            'date': end_dt,
                            'value': item.get('val', 0),
                            'filed': datetime.strptime(item['filed'], '%Y-%m-%d') if 'filed' in item else None,
                            'form': item.get('form'),
                            'fy': item.get('fy'),
                            'fp': item.get('fp')
                        })

        except Exception as e:
            self.logger.debug(f"Error extracting tag {tag}: {e}")

        return data

    def collect_company_data(self, ticker: str, company_name: str,
                            ipo_date: datetime) -> Tuple[pd.DataFrame, str, str]:
        """
        Collect all financial data for a company using multi-tier approach

        Args:
            ticker: Stock ticker
            company_name: Company name
            ipo_date: IPO date

        Returns:
            Tuple of (DataFrame with financial data, quality score, source description)
        """
        self.logger.info(f"Starting data collection for {ticker} ({company_name})")

        # Get CIK
        cik = self.get_cik_from_ticker(ticker)
        if not cik:
            self.logger.warning(f"{ticker}: Could not find CIK")
            return pd.DataFrame(), 'F', 'CIK not found'

        self.logger.info(f"{ticker}: Found CIK {cik}")

        # Get company facts
        facts = self.get_company_facts(cik)
        if not facts:
            self.logger.warning(f"{ticker}: Could not fetch company facts")
            return pd.DataFrame(), 'F', 'Company facts not available'

        # Define data collection period (from IPO to now)
        end_date = datetime.now()

        # Tier 1: Try XBRL extraction
        self.logger.info(f"{ticker}: Attempting Tier 1 - XBRL extraction")
        sbc_data = self.extract_xbrl_data(facts, PRIMARY_SBC_TAGS, ipo_date, end_date)
        revenue_data = self.extract_xbrl_data(facts, REVENUE_TAGS, ipo_date, end_date)
        shares_data = self.extract_xbrl_data(facts, SHARES_TAGS, ipo_date, end_date)
        opex_data = self.extract_xbrl_data(facts, OPERATING_INCOME_TAGS, ipo_date, end_date)

        # Determine quality score
        quality_score, source = self._assess_data_quality(
            sbc_data, revenue_data, shares_data, ipo_date
        )

        if quality_score == 'F':
            self.logger.warning(f"{ticker}: Data quality F - insufficient data")
            return pd.DataFrame(), quality_score, source

        # Merge all data sources
        df = self._merge_financial_data(
            ticker, company_name, ipo_date,
            sbc_data, revenue_data, shares_data, opex_data
        )

        self.logger.info(f"{ticker}: Collected {len(df)} quarters, quality score: {quality_score}")

        return df, quality_score, source

    def _assess_data_quality(self, sbc_data: pd.DataFrame, revenue_data: pd.DataFrame,
                            shares_data: pd.DataFrame, ipo_date: datetime) -> Tuple[str, str]:
        """
        Assess data quality and assign quality score

        Returns:
            Tuple of (quality_score, source_description)
        """
        # Count quarters of data available
        sbc_quarters = len(sbc_data)
        revenue_quarters = len(revenue_data)

        # Check data availability
        if sbc_quarters == 0 and revenue_quarters == 0:
            return 'F', 'No data available'

        if sbc_quarters == 0:
            return 'F', 'No SBC data found'

        if revenue_quarters == 0:
            return 'D', 'SBC found but no revenue data'

        # Check consistency
        if sbc_quarters < 4:
            return 'F', 'Insufficient SBC data (<4 quarters)'

        # Check tag consistency
        sbc_tag_used = sbc_data['tag_used'].iloc[0] if len(sbc_data) > 0 else None

        # Assign quality score
        if sbc_tag_used == PRIMARY_SBC_TAGS[0]:  # Best tag
            if sbc_quarters >= 12:
                return 'A', f'Clean XBRL - {sbc_tag_used}'
            else:
                return 'B', f'XBRL available - {sbc_tag_used}'
        elif sbc_tag_used in PRIMARY_SBC_TAGS:
            return 'B', f'XBRL with alternate tag - {sbc_tag_used}'
        else:
            return 'C', 'XBRL with non-standard tag'

    def _merge_financial_data(self, ticker: str, company_name: str, ipo_date: datetime,
                              sbc_data: pd.DataFrame, revenue_data: pd.DataFrame,
                              shares_data: pd.DataFrame, opex_data: pd.DataFrame) -> pd.DataFrame:
        """Merge all financial data sources into single DataFrame"""

        # Start with SBC data as base (most important)
        if len(sbc_data) == 0:
            return pd.DataFrame()

        df = sbc_data[['date', 'value', 'filed']].copy()
        df.columns = ['quarter_end', 'sbc', 'filing_date']

        # Add revenue
        if len(revenue_data) > 0:
            rev_df = revenue_data[['date', 'value']].copy()
            rev_df.columns = ['quarter_end', 'revenue']
            df = df.merge(rev_df, on='quarter_end', how='left')
        else:
            df['revenue'] = None

        # Add shares outstanding
        if len(shares_data) > 0:
            shares_df = shares_data[['date', 'value']].copy()
            shares_df.columns = ['quarter_end', 'shares']
            df = df.merge(shares_df, on='quarter_end', how='left')
        else:
            df['shares'] = None

        # Add operating income
        if len(opex_data) > 0:
            opex_df = opex_data[['date', 'value']].copy()
            opex_df.columns = ['quarter_end', 'operating_income']
            df = df.merge(opex_df, on='quarter_end', how='left')
        else:
            df['operating_income'] = None

        # Add metadata
        df.insert(0, 'ticker', ticker)
        df.insert(1, 'company', company_name)
        df.insert(2, 'ipo_date', ipo_date)

        # Sort by date
        df = df.sort_values('quarter_end').reset_index(drop=True)

        # Calculate quarters since IPO
        df['quarters_since_ipo'] = df['quarter_end'].apply(
            lambda x: self._calculate_quarters_since_ipo(ipo_date, x)
        )

        return df

    def _calculate_quarters_since_ipo(self, ipo_date: datetime, quarter_end: datetime) -> int:
        """Calculate number of quarters since IPO"""
        months_diff = (quarter_end.year - ipo_date.year) * 12 + (quarter_end.month - ipo_date.month)
        return max(0, (months_diff // 3) + 1)

    def validate_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """
        Validate financial data and flag suspicious values

        Args:
            df: DataFrame with financial data

        Returns:
            Tuple of (cleaned DataFrame, list of warnings)
        """
        warnings = []

        if len(df) == 0:
            return df, warnings

        # Calculate SBC as % of revenue
        if 'revenue' in df.columns and 'sbc' in df.columns:
            df['sbc_pct'] = (df['sbc'] / df['revenue'] * 100).round(2)

            # Flag suspicious SBC percentages
            high_sbc = df['sbc_pct'] > 40
            if high_sbc.any():
                warnings.append(f"SBC% > 40% in {high_sbc.sum()} quarters (unrealistic)")

            negative_sbc = df['sbc_pct'] < 0
            if negative_sbc.any():
                warnings.append(f"Negative SBC% in {negative_sbc.sum()} quarters")

            # Check for large quarter-over-quarter changes
            df['sbc_pct_qoq_change'] = df['sbc_pct'].diff()
            large_changes = abs(df['sbc_pct_qoq_change']) > 15
            if large_changes.any():
                warnings.append(f"Large Q/Q SBC% change (>15pts) in {large_changes.sum()} quarters")

        # Check for revenue declines
        if 'revenue' in df.columns:
            df['revenue_qoq_change'] = df['revenue'].pct_change() * 100
            large_declines = df['revenue_qoq_change'] < -20
            if large_declines.any():
                warnings.append(f"Large revenue decline (>20%) in {large_declines.sum()} quarters")

        # Check for gaps in quarterly data
        if len(df) > 1:
            df['days_since_prev'] = df['quarter_end'].diff().dt.days
            gaps = (df['days_since_prev'] > 120) | (df['days_since_prev'] < 60)
            gaps = gaps & df['days_since_prev'].notna()
            if gaps.any():
                warnings.append(f"Irregular quarter spacing in {gaps.sum()} periods")

        return df, warnings


def test_collector():
    """Test the SEC data collector with a sample company"""
    logging.basicConfig(level=logging.INFO)

    collector = SECDataCollector()

    # Test with Snowflake (SNOW)
    ticker = "SNOW"
    company_name = "Snowflake"
    ipo_date = datetime(2020, 9, 16)

    df, quality, source = collector.collect_company_data(ticker, company_name, ipo_date)

    print(f"\n{ticker} Data Collection Results:")
    print(f"Quality Score: {quality}")
    print(f"Source: {source}")
    print(f"Quarters Collected: {len(df)}")
    print("\nFirst few rows:")
    print(df.head())

    if len(df) > 0:
        df_validated, warnings = collector.validate_data(df)
        if warnings:
            print("\nWarnings:")
            for w in warnings:
                print(f"  - {w}")


if __name__ == "__main__":
    test_collector()
