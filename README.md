# SaaS IPO Cohort SBC Analysis Engine

**Automated data collection and prediction engine for analyzing stock-based compensation patterns across 60 SaaS companies**

## Overview

This Python-based analysis engine automatically:
- Collects quarterly SBC data from SEC EDGAR filings for 60 SaaS companies
- Filters companies with reliable SBC reporting (quality scoring)
- Analyzes SBC decline patterns 4+ years post-IPO (Q16 onwards)
- Predicts Amplitude's (AMPL) SBC trajectory based on peer patterns
- Exports comprehensive Excel workbook with analysis and predictions

## Features

- **Multi-Tier Data Collection**: XBRL API → Cash Flow Parsing → Non-GAAP Reconciliation
- **Quality Scoring**: A-F grading system to ensure data reliability
- **Pattern Analysis**: Statistical analysis of Q16→Q20 SBC decline patterns
- **Cohort Segmentation**: By IPO year, listing type, company size
- **Amplitude Predictions**: Conservative, Base, and Bull case scenarios
- **Professional Excel Output**: 7 comprehensive sheets with formatting and charts

## Requirements

- Python 3.8 or higher
- Internet connection (for SEC EDGAR API access)
- ~30 minutes runtime for full 60-company analysis

## Installation

### 1. Clone or Download Repository

```bash
cd /path/to/ampl-sbc
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**
- requests (SEC API communication)
- pandas (data processing)
- numpy (statistical calculations)
- openpyxl (Excel export)
- beautifulsoup4 (HTML parsing)
- sec-edgar-downloader (SEC filing downloads)

### 3. Verify IPO Dates File

The `ipo_dates.csv` file is pre-populated with all 60 companies. Verify it exists:

```bash
ls ipo_dates.csv
```

## Usage

### Basic Usage

Run the analysis with default settings:

```bash
python main.py
```

This will:
1. Load company list from `ipo_dates.csv`
2. Collect data from SEC EDGAR for all 60 companies
3. Process and analyze SBC patterns
4. Generate predictions for Amplitude
5. Export results to `sbc_analysis_output.xlsx`
6. Create detailed log in `sbc_analysis.log`

### Expected Runtime

- Full analysis: **20-30 minutes**
- Per company: ~20-30 seconds (SEC rate limiting)
- The script respects SEC's 10 requests/second limit

### Output Files

After completion, you'll have:
- **sbc_analysis_output.xlsx** - Main Excel workbook with all analysis
- **sbc_analysis.log** - Detailed execution log

## Excel Workbook Structure

The output workbook contains 7 sheets:

### 1. Raw_Data
Complete quarterly financial data for all companies:
- Ticker, Company, IPO Date
- Quarter End, Filing Date, Quarters Since IPO
- Revenue, SBC $M, SBC %, Shares Outstanding
- Year-over-year growth metrics
- Data quality scores

### 2. Q16_Cliff_Analysis
SBC patterns at Q16 (4 years post-IPO):
- Q16 SBC% baseline
- Q20 SBC% (5 years)
- Q24 SBC% (6 years)
- Decline from Q16→Q20 and Q16→Q24
- Company status (complete data, acquired, etc.)

### 3. Pattern_Summary
Statistical analysis of decline patterns:
- Overall statistics (mean, median, percentiles)
- 2021 IPO cohort statistics (for Amplitude comparison)
- Segmentation by IPO year
- Segmentation by listing type
- Decline distribution histogram data

### 4. Amplitude_Prediction
Amplitude-specific predictions:
- Current state summary
- Peer comparison at Q16
- Prediction methodology
- Quarterly projections (Q16-Q24)
- Three scenarios: Conservative, Base (median), Bull
- Implied GAAP margin improvements

### 5. Data_Quality_Report
Quality assessment for each company:
- Data quality score (A-F)
- Data source (XBRL tag used)
- Completeness (quarters available)
- Inclusion status

### 6. Excluded_Companies
Companies that failed quality checks:
- Exclusion reason
- Quality score
- Partial data available

### 7. Metadata
Analysis run information:
- Run date/time
- Data as of date
- Company counts
- Methodology notes

## Understanding Quality Scores

### Quality Score Definitions

- **A (Excellent)**: Clean XBRL with standard tags, 12+ consistent quarters
- **B (Good)**: XBRL available but required alternate tags
- **C (Acceptable)**: XBRL with non-standard tags OR parsed from cash flow
- **D (Manual Review)**: Extracted from non-GAAP reconciliation, needs verification
- **F (Excluded)**: Insufficient or unreliable data

### Filtering Logic

By default, the script includes companies with scores **A, B, or C** in analysis.

Companies with score **D** are flagged for manual review.

Companies with score **F** are automatically excluded.

## Customization

### Change Minimum Quality Score

Edit `main.py`, line ~16:

```python
MIN_QUALITY_SCORE = 'C'  # Change to 'B' for stricter filtering
```

### Change Minimum Quarters Required

Edit `main.py`, line ~17:

```python
MIN_QUARTERS = 16  # Change to 20 for companies with 5+ years of data
```

### Modify Company List

Edit `ipo_dates.csv`:
- Add rows: Include Ticker, Company_Name, IPO_Date, Notes
- Remove rows: Delete unwanted companies
- Update IPO dates if incorrect

**CSV Format:**
```csv
Ticker,Company_Name,IPO_Date,Notes
SNOW,Snowflake,2020-09-16,
PLTR,Palantir,2020-09-29,Direct listing
```

### Change Output File Name

Edit `main.py`, line ~15:

```python
OUTPUT_FILE = 'custom_output_name.xlsx'
```

## Troubleshooting

### Common Issues

#### 1. "IPO dates file not found"

**Solution**: Ensure `ipo_dates.csv` is in the same directory as `main.py`

```bash
ls ipo_dates.csv
```

#### 2. "Could not find CIK for ticker XXX"

**Cause**: Ticker symbol may be incorrect or company delisted

**Solution**:
- Verify ticker symbol in `ipo_dates.csv`
- For acquired companies, this is expected - data will be collected up to acquisition
- Check SEC EDGAR manually: https://www.sec.gov/edgar/searchedgar/companysearch

#### 3. "No data available" for many companies

**Cause**: SEC API rate limiting or connection issues

**Solution**:
- Wait a few minutes and re-run (script caches successfully collected data)
- Check internet connection
- Verify SEC EDGAR is accessible: https://data.sec.gov

#### 4. "Quality score F - insufficient data"

**Cause**: Company doesn't report SBC in standard format

**Solution**: This is expected for ~20% of companies. The script automatically:
- Tries multiple XBRL tags
- Attempts cash flow statement parsing
- Flags for manual review if needed

#### 5. Script crashes or hangs

**Solution**:
- Check `sbc_analysis.log` for error details
- Interrupt with Ctrl+C and restart (script has caching)
- For persistent issues, test with single company:

```python
# In main.py, temporarily filter IPO dates to one company:
ipo_df = ipo_df[ipo_df['Ticker'] == 'SNOW']  # Test with Snowflake
```

### Validation Checks

The script performs automatic validation and warns about:
- SBC% > 40% (unrealistic)
- Negative SBC% (data error)
- Large Q/Q changes >15% (potential error)
- Revenue declining >20% Q/Q
- Irregular quarter spacing

**Check warnings in log file** if results seem unusual.

## Data Sources

### Primary: SEC EDGAR Company Facts API

- **Endpoint**: `https://data.sec.gov/api/xbrl/companyfacts/`
- **Data**: Standardized XBRL financial data
- **Coverage**: All public companies with XBRL filings
- **Update Frequency**: Typically 1-2 days after 10-Q/10-K filing

### Backup: Traditional Filing Downloads

For companies with non-standard reporting, the script can parse:
- 10-Q/10-K HTML filings
- Cash flow statement text
- Non-GAAP reconciliation tables

## Methodology

### Q16 Cliff Hypothesis

The analysis focuses on **Q16 (4 years post-IPO)** as a key inflection point where:
1. Initial IPO RSU grants (typically 4-year vest) have fully vested
2. Replacement grants are typically smaller than IPO grants
3. SBC as % of revenue begins declining structurally

### Prediction Approach

Amplitude predictions use:
1. **Cohort Selection**: 2021 IPO cohort (same vintage) or all companies if insufficient data
2. **Statistical Distribution**: 25th percentile (conservative), median (base), 75th percentile (bull)
3. **Linear Interpolation**: Q16→Q20 decline spread evenly over 4 quarters
4. **Margin Impact**: SBC decline directly improves GAAP operating margin

### Special Situations

- **Direct Listings** (PLTR, ASAN): Flagged separately, may have different patterns
- **Acquired Companies**: Data included up to acquisition date
- **SPACs**: Identified and flagged if in dataset

## API Rate Limiting

The script automatically:
- Limits to 10 requests/second (SEC requirement)
- Implements retry logic for failed requests (3 attempts)
- Caches API responses to avoid redundant calls

**Do not modify rate limiting** - violating SEC fair access policy may result in IP ban.

## Updating with New Quarterly Data

To update analysis with latest quarterly data:

1. **Re-run the script** - it automatically fetches most recent SEC filings
2. **No changes needed** - script dynamically determines current quarter
3. **Clear cache** (optional) - delete cached responses for fresh data:

```python
# In main.py, line ~137:
collector = SECDataCollector(use_cache=False)  # Disable cache
```

## Advanced Usage

### Test Individual Company

```python
from sec_data_collector import SECDataCollector
from datetime import datetime

collector = SECDataCollector()
df, quality, source = collector.collect_company_data(
    ticker='SNOW',
    company_name='Snowflake',
    ipo_date=datetime(2020, 9, 16)
)

print(f"Quality: {quality}")
print(f"Quarters: {len(df)}")
print(df.head())
```

### Export Only Certain Sheets

Modify `excel_exporter.py` to comment out unwanted sheets in `export_full_workbook()`.

### Custom Analysis

The modular architecture allows custom analysis:

```python
from pattern_analyzer import PatternAnalyzer

analyzer = PatternAnalyzer()

# Custom segmentation
custom_stats = analyzer.calculate_pattern_statistics(
    cliff_df[cliff_df['q16_revenue_m'] > 500],  # Only large companies
    traditional_ipo_only=True
)
```

## File Structure

```
ampl-sbc/
├── main.py                    # Main orchestration script
├── sec_data_collector.py      # SEC data collection (multi-tier)
├── data_processor.py          # Data cleaning and calculations
├── pattern_analyzer.py        # Statistical analysis
├── amplitude_predictor.py     # Amplitude predictions
├── excel_exporter.py          # Excel workbook generation
├── ipo_dates.csv             # Input: Company list with IPO dates
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── sbc_analysis_output.xlsx  # Output: Analysis results (generated)
└── sbc_analysis.log          # Output: Execution log (generated)
```

## Contributing

To modify or extend the analysis:

1. **Add XBRL Tags**: Edit `PRIMARY_SBC_TAGS` in `sec_data_collector.py`
2. **Change Statistics**: Modify `calculate_pattern_statistics()` in `pattern_analyzer.py`
3. **Add Excel Sheets**: Create new `_create_xxx_sheet()` method in `excel_exporter.py`
4. **Custom Predictions**: Edit `predict_trajectory()` in `amplitude_predictor.py`

## Known Limitations

1. **XBRL Dependency**: Companies with inconsistent XBRL reporting may be excluded
2. **Quarterly Data Only**: Annual data not included
3. **US Companies Only**: SEC EDGAR API limited to US public companies
4. **Historical Data**: Cannot predict macro changes (market conditions, accounting changes)
5. **No Forward-Looking Grants**: Analysis based on historical patterns, doesn't account for company-specific grant decisions

## Support

For issues or questions:
1. Check `sbc_analysis.log` for detailed error messages
2. Review this README troubleshooting section
3. Verify SEC EDGAR API is accessible
4. Test with single company to isolate issues

## License

This script is for research and analysis purposes. SEC data is public domain.

Respects SEC.gov fair access policy: https://www.sec.gov/os/accessing-edgar-data

## Version

**Version 1.0** - Initial release

Last updated: 2025-11-13

---

**Built for analysis of Amplitude (AMPL) SBC trajectory using peer company patterns**
