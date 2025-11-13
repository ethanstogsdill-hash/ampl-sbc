# Quick Start Guide - SaaS SBC Analysis Engine

## Installation (2 minutes)

```bash
# 1. Navigate to project directory
cd /home/user/ampl-sbc

# 2. Install dependencies
pip install -r requirements.txt

# This installs: requests, pandas, numpy, openpyxl, beautifulsoup4, sec-edgar-downloader
```

## Running the Analysis (20-30 minutes)

```bash
# Run the complete analysis
python main.py
```

**What happens:**
1. Loads 60 SaaS companies from `ipo_dates.csv`
2. Collects quarterly financial data from SEC EDGAR
3. Filters by data quality (A, B, C scores included)
4. Analyzes Q16 SBC cliff patterns
5. Predicts Amplitude's trajectory
6. Exports to `sbc_analysis_output.xlsx`

## Monitoring Progress

Watch the console output:
```
INFO: Starting data collection for SNOW (Snowflake)...
INFO:   ✓ Success: 16 quarters, quality A
INFO: Starting data collection for PLTR (Palantir)...
```

Or check the detailed log:
```bash
tail -f sbc_analysis.log
```

## Expected Results

### Success Metrics
- **45+ companies** with quality data (75%+ success rate)
- **25+ companies** with Q20+ data for pattern analysis
- **Amplitude prediction** with 3 scenarios (conservative/base/bull)

### Output Files
1. **sbc_analysis_output.xlsx** - 7-sheet workbook with all analysis
2. **sbc_analysis.log** - Detailed execution log

## Viewing Results

Open `sbc_analysis_output.xlsx` and check:

1. **Sheet: Pattern_Summary** - Overall Q16→Q20 decline statistics
2. **Sheet: Amplitude_Prediction** - Amplitude's projected trajectory
3. **Sheet: Q16_Cliff_Analysis** - Individual company patterns
4. **Sheet: Raw_Data** - Complete quarterly data

## Key Metrics to Review

### Pattern Statistics
- Median Q16→Q20 decline: ~5 percentage points
- 75% of companies decline by X+ points
- Conservative (25th pct): ~3 points
- Aggressive (75th pct): ~7 points

### Amplitude Prediction
- Current Q16 SBC%: [calculated from latest filing]
- Predicted Q20 SBC% (Base): [Q16 minus median decline]
- Implied GAAP margin improvement: [SBC decline = margin improvement]

## Troubleshooting

### Issue: ModuleNotFoundError
**Solution:** Install dependencies
```bash
pip install -r requirements.txt
```

### Issue: "IPO dates file not found"
**Solution:** Ensure you're in the correct directory
```bash
ls ipo_dates.csv  # Should show the file
```

### Issue: Many companies showing "No data"
**Solution:** This is expected for ~20% of companies due to:
- Non-standard SBC reporting
- Recent IPOs (< 16 quarters of data)
- Acquired companies

The script automatically filters these out.

### Issue: Script is slow
**Reason:** SEC rate limiting (10 requests/second)
- 60 companies × 20-30 seconds each = 20-30 minutes total
- This is normal and expected

## Next Steps After First Run

1. **Review Pattern_Summary sheet** - Understand overall cohort patterns
2. **Check Amplitude_Prediction sheet** - Review three scenarios
3. **Examine Data_Quality_Report** - See which companies were included/excluded
4. **Read Metadata sheet** - Understand methodology and assumptions

## Updating with New Quarterly Data

Simply re-run the script after new 10-Q filings:
```bash
python main.py
```

The script automatically:
- Fetches latest quarterly data
- Recalculates all statistics
- Updates predictions
- Overwrites output file

## Common Customizations

### Include only high-quality data (A/B only)
Edit `main.py` line 16:
```python
MIN_QUALITY_SCORE = 'B'  # Was 'C'
```

### Change output filename
Edit `main.py` line 15:
```python
OUTPUT_FILE = 'my_custom_analysis.xlsx'  # Was 'sbc_analysis_output.xlsx'
```

### Add/remove companies
Edit `ipo_dates.csv` - add or delete rows

## Support

For detailed information:
- **README.md** - Comprehensive guide
- **sbc_analysis.log** - Detailed execution log
- **Individual module test functions** - Run `python sec_data_collector.py` for testing

---

**Time to first results: ~30 minutes**

**Questions about methodology?** See "Methodology" section in README.md
