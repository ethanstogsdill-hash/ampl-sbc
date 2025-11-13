"""
Excel Exporter - Generate comprehensive Excel workbook with analysis results
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import logging
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.chart import LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule


class ExcelExporter:
    """Export analysis results to comprehensive Excel workbook"""

    def __init__(self, output_path: str):
        """
        Initialize Excel exporter

        Args:
            output_path: Path to output Excel file
        """
        self.output_path = output_path
        self.logger = logging.getLogger(__name__)

        # Define styles
        self.header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        self.header_font = Font(color="FFFFFF", bold=True, size=11)
        self.title_font = Font(bold=True, size=14)
        self.section_font = Font(bold=True, size=12)

    def export_full_workbook(self, master_df: pd.DataFrame, cliff_df: pd.DataFrame,
                            pattern_stats: Dict, pattern_stats_2021: Dict,
                            segmentation_data: Dict, amplitude_prediction: Dict,
                            amplitude_comparison: Dict, excluded_companies: Dict,
                            metadata: Dict):
        """
        Export complete workbook with all analysis sheets

        Args:
            master_df: Master dataset with all companies
            cliff_df: Q16 cliff analysis
            pattern_stats: Overall pattern statistics
            pattern_stats_2021: 2021 cohort statistics
            segmentation_data: Dictionary with segmentation analyses
            amplitude_prediction: Amplitude prediction results
            amplitude_comparison: Amplitude peer comparison
            excluded_companies: Dictionary of excluded companies
            metadata: Run metadata
        """
        self.logger.info(f"Creating Excel workbook: {self.output_path}")

        # Create workbook
        wb = Workbook()
        wb.remove(wb.active)  # Remove default sheet

        # Sheet 1: Raw Data
        self._create_raw_data_sheet(wb, master_df)

        # Sheet 2: Q16 Cliff Analysis
        self._create_cliff_analysis_sheet(wb, cliff_df)

        # Sheet 3: Pattern Summary
        self._create_pattern_summary_sheet(wb, pattern_stats, pattern_stats_2021,
                                          segmentation_data, cliff_df)

        # Sheet 4: Amplitude Prediction
        self._create_amplitude_prediction_sheet(wb, amplitude_prediction, amplitude_comparison)

        # Sheet 5: Data Quality Report
        self._create_data_quality_sheet(wb, master_df, cliff_df)

        # Sheet 6: Excluded Companies
        self._create_excluded_companies_sheet(wb, excluded_companies)

        # Sheet 7: Metadata
        self._create_metadata_sheet(wb, metadata)

        # Save workbook
        wb.save(self.output_path)
        self.logger.info(f"Excel workbook saved: {self.output_path}")

    def _create_raw_data_sheet(self, wb: Workbook, master_df: pd.DataFrame):
        """Create Raw_Data sheet"""
        self.logger.info("Creating Raw_Data sheet...")

        ws = wb.create_sheet("Raw_Data")

        # Select and order columns
        columns = [
            'company', 'ticker', 'ipo_date', 'quarter_end', 'filing_date',
            'quarters_since_ipo', 'fiscal_quarter',
            'revenue_m', 'sbc_m', 'sbc_pct', 'sbc_pct_qoq', 'sbc_pct_yoy',
            'shares_m', 'shares_yoy_growth',
            'gaap_op_margin', 'data_quality', 'data_source', 'listing_type'
        ]

        # Filter to available columns
        available_columns = [col for col in columns if col in master_df.columns]
        export_df = master_df[available_columns].copy()

        # Format dates
        if 'ipo_date' in export_df.columns:
            export_df['ipo_date'] = pd.to_datetime(export_df['ipo_date']).dt.date
        if 'quarter_end' in export_df.columns:
            export_df['quarter_end'] = pd.to_datetime(export_df['quarter_end']).dt.date
        if 'filing_date' in export_df.columns:
            export_df['filing_date'] = pd.to_datetime(export_df['filing_date']).dt.date

        # Write data
        for r in dataframe_to_rows(export_df, index=False, header=True):
            ws.append(r)

        # Style header row
        self._style_header_row(ws)

        # Freeze panes
        ws.freeze_panes = 'C2'

        # Auto-fit columns
        self._auto_fit_columns(ws)

    def _create_cliff_analysis_sheet(self, wb: Workbook, cliff_df: pd.DataFrame):
        """Create Q16_Cliff_Analysis sheet"""
        self.logger.info("Creating Q16_Cliff_Analysis sheet...")

        ws = wb.create_sheet("Q16_Cliff_Analysis")

        # Select columns
        columns = [
            'company', 'ticker', 'ipo_date', 'ipo_year', 'listing_type', 'status',
            'q16_sbc_pct', 'q16_revenue_m', 'q16_quarter_end',
            'q20_sbc_pct', 'decline_q16_to_q20',
            'q24_sbc_pct', 'decline_q16_to_q24',
            'q14_15_shares_yoy'
        ]

        available_columns = [col for col in columns if col in cliff_df.columns]
        export_df = cliff_df[available_columns].copy()

        # Sort by decline (largest decline first)
        if 'decline_q16_to_q20' in export_df.columns:
            export_df = export_df.sort_values('decline_q16_to_q20', na_position='last')

        # Format dates
        if 'ipo_date' in export_df.columns:
            export_df['ipo_date'] = pd.to_datetime(export_df['ipo_date']).dt.date
        if 'q16_quarter_end' in export_df.columns:
            export_df['q16_quarter_end'] = pd.to_datetime(export_df['q16_quarter_end']).dt.date

        # Write data
        for r in dataframe_to_rows(export_df, index=False, header=True):
            ws.append(r)

        # Style header
        self._style_header_row(ws)

        # Add conditional formatting for decline columns
        if 'decline_q16_to_q20' in export_df.columns:
            decline_col_idx = available_columns.index('decline_q16_to_q20') + 1
            decline_col_letter = self._get_column_letter(decline_col_idx)

            # Green for large declines (good), red for increases (unusual)
            ws.conditional_formatting.add(
                f'{decline_col_letter}2:{decline_col_letter}{len(export_df)+1}',
                ColorScaleRule(
                    start_type='num', start_value=-10, start_color='00FF00',
                    mid_type='num', mid_value=0, mid_color='FFFF00',
                    end_type='num', end_value=2, end_color='FF0000'
                )
            )

        # Auto-fit columns
        self._auto_fit_columns(ws)

        # Freeze panes
        ws.freeze_panes = 'C2'

    def _create_pattern_summary_sheet(self, wb: Workbook, pattern_stats: Dict,
                                     pattern_stats_2021: Dict, segmentation_data: Dict,
                                     cliff_df: pd.DataFrame):
        """Create Pattern_Summary sheet"""
        self.logger.info("Creating Pattern_Summary sheet...")

        ws = wb.create_sheet("Pattern_Summary")

        row = 1

        # Title
        ws.cell(row, 1, "SBC Decline Pattern Analysis - Q16 to Q20").font = self.title_font
        row += 2

        # Overall Statistics
        ws.cell(row, 1, "Overall Statistics (All Companies)").font = self.section_font
        row += 1

        stats_data = [
            ['Companies with Q20+ data', pattern_stats.get('n_companies', 0)],
            ['Companies at Q16+', pattern_stats.get('n_total_at_q16', 0)],
            ['', ''],
            ['Mean decline (Q16→Q20)', f"{pattern_stats.get('mean_decline', 0):.2f}%"],
            ['Median decline (Q16→Q20)', f"{pattern_stats.get('median_decline', 0):.2f}%"],
            ['Std deviation', f"{pattern_stats.get('std_decline', 0):.2f}%"],
            ['', ''],
            ['25th percentile (Conservative)', f"{pattern_stats.get('pct_25', 0):.2f}%"],
            ['75th percentile (Aggressive)', f"{pattern_stats.get('pct_75', 0):.2f}%"],
            ['', ''],
            ['% with >3pt decline', f"{pattern_stats.get('pct_decline_gt_3pts', 0):.1f}%"],
            ['% with >5pt decline', f"{pattern_stats.get('pct_decline_gt_5pts', 0):.1f}%"],
            ['% with >7pt decline', f"{pattern_stats.get('pct_decline_gt_7pts', 0):.1f}%"],
            ['% with increase', f"{pattern_stats.get('pct_increase', 0):.1f}%"]
        ]

        for data_row in stats_data:
            ws.cell(row, 1, data_row[0])
            ws.cell(row, 2, data_row[1])
            if data_row[0]:  # Bold the labels
                ws.cell(row, 1).font = Font(bold=True)
            row += 1

        row += 2

        # 2021 Cohort Statistics (if available)
        if pattern_stats_2021 and pattern_stats_2021.get('n_companies', 0) > 0:
            ws.cell(row, 1, "2021 IPO Cohort Statistics").font = self.section_font
            row += 1

            cohort_data = [
                ['Companies with Q20+ data', pattern_stats_2021.get('n_companies', 0)],
                ['', ''],
                ['Mean decline (Q16→Q20)', f"{pattern_stats_2021.get('mean_decline', 0):.2f}%"],
                ['Median decline (Q16→Q20)', f"{pattern_stats_2021.get('median_decline', 0):.2f}%"],
                ['25th percentile', f"{pattern_stats_2021.get('pct_25', 0):.2f}%"],
                ['75th percentile', f"{pattern_stats_2021.get('pct_75', 0):.2f}%"]
            ]

            for data_row in cohort_data:
                ws.cell(row, 1, data_row[0])
                ws.cell(row, 2, data_row[1])
                if data_row[0]:
                    ws.cell(row, 1).font = Font(bold=True)
                row += 1

            row += 2

        # Segmentation by IPO Year
        if 'by_ipo_year' in segmentation_data:
            ws.cell(row, 1, "Analysis by IPO Year").font = self.section_font
            row += 1

            seg_df = segmentation_data['by_ipo_year']
            for r in dataframe_to_rows(seg_df, index=False, header=True):
                ws.append(r)

            # Style the segmentation table header
            for col in range(1, len(seg_df.columns) + 1):
                cell = ws.cell(row, col)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

            row += len(seg_df) + 2

        # Segmentation by Listing Type
        if 'by_listing_type' in segmentation_data:
            ws.cell(row, 1, "Analysis by Listing Type").font = self.section_font
            row += 1

            seg_df = segmentation_data['by_listing_type']
            for r in dataframe_to_rows(seg_df, index=False, header=True):
                ws.append(r)

            # Style the segmentation table header
            for col in range(1, len(seg_df.columns) + 1):
                cell = ws.cell(row, col)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

            row += len(seg_df) + 2

        # Distribution
        if 'distribution' in segmentation_data:
            ws.cell(row, 1, "Q16→Q20 Decline Distribution").font = self.section_font
            row += 1

            dist_df = segmentation_data['distribution']
            for r in dataframe_to_rows(dist_df, index=False, header=True):
                ws.append(r)

            # Style header
            for col in range(1, len(dist_df.columns) + 1):
                cell = ws.cell(row, col)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

        # Auto-fit columns
        self._auto_fit_columns(ws)

    def _create_amplitude_prediction_sheet(self, wb: Workbook, prediction: Dict,
                                          comparison: Dict):
        """Create Amplitude_Prediction sheet"""
        self.logger.info("Creating Amplitude_Prediction sheet...")

        ws = wb.create_sheet("Amplitude_Prediction")

        row = 1

        # Title
        ws.cell(row, 1, "Amplitude (AMPL) SBC Trajectory Prediction").font = self.title_font
        row += 2

        # Check if prediction available
        if 'error' in prediction:
            ws.cell(row, 1, f"Error: {prediction['error']}")
            return

        # Current State
        ws.cell(row, 1, "Current State").font = self.section_font
        row += 1

        current_data = [
            ['IPO Date', prediction.get('ipo_date', '').strftime('%Y-%m-%d') if isinstance(prediction.get('ipo_date'), datetime) else prediction.get('ipo_date', '')],
            ['Current Quarter', prediction.get('current_quarter', '')],
            ['Q16 SBC %', f"{prediction.get('q16_sbc_pct', 0):.2f}%"],
            ['Current SBC %', f"{prediction.get('current_sbc_pct', 0):.2f}%"]
        ]

        for data_row in current_data:
            ws.cell(row, 1, data_row[0]).font = Font(bold=True)
            ws.cell(row, 2, data_row[1])
            row += 1

        row += 2

        # Peer Comparison
        if not comparison.get('error'):
            ws.cell(row, 1, "Peer Comparison at Q16").font = self.section_font
            row += 1

            comp_data = [
                ['Amplitude Q16 SBC%', f"{comparison.get('amplitude_q16_sbc_pct', 0):.2f}%"],
                ['Peer Median', f"{comparison.get('peer_median', 0):.2f}%"],
                ['Peer Mean', f"{comparison.get('peer_mean', 0):.2f}%"],
                ['Peer 25th percentile', f"{comparison.get('peer_25th_pct', 0):.2f}%"],
                ['Peer 75th percentile', f"{comparison.get('peer_75th_pct', 0):.2f}%"],
                ['Amplitude Percentile', f"{comparison.get('amplitude_percentile', 0):.1f}%"],
                ['Number of Peers', comparison.get('n_peers', 0)],
                ['', ''],
                ['Outlier Status', comparison.get('outlier_note', '')]
            ]

            for data_row in comp_data:
                ws.cell(row, 1, data_row[0])
                if data_row[0]:
                    ws.cell(row, 1).font = Font(bold=True)
                ws.cell(row, 2, data_row[1])
                row += 1

            row += 2

        # Prediction Methodology
        ws.cell(row, 1, "Prediction Methodology").font = self.section_font
        row += 1

        method_data = [
            ['Cohort Used', prediction.get('cohort_used', '')],
            ['Companies in Cohort', prediction.get('n_companies_in_cohort', 0)],
            ['', ''],
            ['Conservative (25th pct) decline', f"{prediction.get('conservative_decline_q16_q20', 0):.2f}%"],
            ['Base (Median) decline', f"{prediction.get('base_decline_q16_q20', 0):.2f}%"],
            ['Bull (75th pct) decline', f"{prediction.get('bull_decline_q16_q20', 0):.2f}%"]
        ]

        for data_row in method_data:
            ws.cell(row, 1, data_row[0])
            if data_row[0]:
                ws.cell(row, 1).font = Font(bold=True)
            ws.cell(row, 2, data_row[1])
            row += 1

        row += 2

        # Quarterly Projections
        ws.cell(row, 1, "Quarterly Projections").font = self.section_font
        row += 1

        proj_df = prediction['projections']

        # Select key columns for display
        display_cols = [
            'quarter', 'quarter_end', 'quarters_since_ipo',
            'conservative_sbc_pct', 'base_sbc_pct', 'bull_sbc_pct',
            'conservative_implied_margin', 'base_implied_margin', 'bull_implied_margin',
            'is_actual'
        ]

        display_df = proj_df[[col for col in display_cols if col in proj_df.columns]].copy()

        # Format dates
        if 'quarter_end' in display_df.columns:
            display_df['quarter_end'] = pd.to_datetime(display_df['quarter_end']).dt.date

        # Write projections
        for r in dataframe_to_rows(display_df, index=False, header=True):
            ws.append(r)

        # Style header
        proj_header_row = row
        for col in range(1, len(display_df.columns) + 1):
            cell = ws.cell(proj_header_row, col)
            cell.font = self.header_font
            cell.fill = self.header_fill

        # Highlight actual vs projected
        if 'is_actual' in display_df.columns:
            actual_col_idx = display_df.columns.tolist().index('is_actual') + 1
            for row_idx in range(proj_header_row + 1, proj_header_row + len(display_df) + 1):
                is_actual = ws.cell(row_idx, actual_col_idx).value
                if is_actual:
                    for col in range(1, len(display_df.columns) + 1):
                        ws.cell(row_idx, col).fill = PatternFill(
                            start_color="E7E6E6", end_color="E7E6E6", fill_type="solid"
                        )

        # Auto-fit columns
        self._auto_fit_columns(ws)

    def _create_data_quality_sheet(self, wb: Workbook, master_df: pd.DataFrame,
                                   cliff_df: pd.DataFrame):
        """Create Data_Quality_Report sheet"""
        self.logger.info("Creating Data_Quality_Report sheet...")

        ws = wb.create_sheet("Data_Quality_Report")

        # Group by company and calculate completeness
        quality_data = []

        for ticker in master_df['ticker'].unique():
            company_df = master_df[master_df['ticker'] == ticker]

            quality_data.append({
                'company': company_df['company'].iloc[0],
                'ticker': ticker,
                'data_quality': company_df['data_quality'].iloc[0],
                'data_source': company_df['data_source'].iloc[0],
                'total_quarters': len(company_df),
                'max_quarter': int(company_df['quarters_since_ipo'].max()),
                'has_q16': company_df['quarters_since_ipo'].max() >= 16,
                'has_q20': company_df['quarters_since_ipo'].max() >= 20,
                'listing_type': company_df['listing_type'].iloc[0],
                'included_in_analysis': ticker in cliff_df['ticker'].values
            })

        quality_df = pd.DataFrame(quality_data)
        quality_df = quality_df.sort_values(['included_in_analysis', 'data_quality'],
                                            ascending=[False, True])

        # Write data
        for r in dataframe_to_rows(quality_df, index=False, header=True):
            ws.append(r)

        # Style header
        self._style_header_row(ws)

        # Auto-fit columns
        self._auto_fit_columns(ws)

        # Freeze panes
        ws.freeze_panes = 'B2'

    def _create_excluded_companies_sheet(self, wb: Workbook, excluded_companies: Dict):
        """Create Excluded_Companies sheet"""
        self.logger.info("Creating Excluded_Companies sheet...")

        ws = wb.create_sheet("Excluded_Companies")

        if len(excluded_companies) == 0:
            ws.cell(1, 1, "No companies excluded - all passed quality checks!")
            return

        # Prepare excluded data
        excluded_data = []

        for ticker, data in excluded_companies.items():
            excluded_data.append({
                'ticker': ticker,
                'company': data['df']['company'].iloc[0] if len(data['df']) > 0 else '',
                'quality_score': data['quality'],
                'data_source': data['source'],
                'quarters_available': len(data['df']),
                'exclusion_reason': data.get('exclusion_reason', 'Unknown')
            })

        excluded_df = pd.DataFrame(excluded_data)
        excluded_df = excluded_df.sort_values('quality_score')

        # Write data
        for r in dataframe_to_rows(excluded_df, index=False, header=True):
            ws.append(r)

        # Style header
        self._style_header_row(ws)

        # Auto-fit columns
        self._auto_fit_columns(ws)

    def _create_metadata_sheet(self, wb: Workbook, metadata: Dict):
        """Create Metadata sheet"""
        self.logger.info("Creating Metadata sheet...")

        ws = wb.create_sheet("Metadata")

        row = 1

        # Title
        ws.cell(row, 1, "Analysis Metadata").font = self.title_font
        row += 2

        # Metadata rows
        metadata_rows = [
            ['Script Run Date/Time', metadata.get('run_datetime', '')],
            ['Data As Of Date', metadata.get('data_as_of', '')],
            ['', ''],
            ['Total Companies Attempted', metadata.get('total_companies', 0)],
            ['Companies Successfully Collected', metadata.get('companies_collected', 0)],
            ['Companies Included in Analysis', metadata.get('companies_included', 0)],
            ['Companies Excluded', metadata.get('companies_excluded', 0)],
            ['', ''],
            ['Minimum Quality Score', metadata.get('min_quality', 'C')],
            ['Minimum Quarters Required', metadata.get('min_quarters', 16)]
        ]

        for data_row in metadata_rows:
            ws.cell(row, 1, data_row[0])
            if data_row[0]:
                ws.cell(row, 1).font = Font(bold=True)
            ws.cell(row, 2, data_row[1])
            row += 1

        row += 2

        # Excluded companies list
        if metadata.get('excluded_tickers'):
            ws.cell(row, 1, "Excluded Companies:").font = Font(bold=True)
            row += 1
            ws.cell(row, 1, ', '.join(metadata['excluded_tickers']))
            row += 2

        # Methodology notes
        ws.cell(row, 1, "Methodology Notes").font = self.section_font
        row += 1

        notes = [
            "1. Data collected from SEC EDGAR Company Facts API using XBRL tags",
            "2. Quality scores: A (best) = clean XBRL, B = alternate tags, C = non-standard, D = parsed, F = excluded",
            "3. Q16 cliff analysis focuses on 4 years post-IPO as key inflection point",
            "4. Predictions use median (base case) and 25th/75th percentile (conservative/bull) declines",
            "5. Only traditional IPOs included in Amplitude comparison (direct listings excluded)",
            "6. All SBC figures represent quarterly expense, not run-rate"
        ]

        for note in notes:
            ws.cell(row, 1, note)
            row += 1

        # Auto-fit columns
        self._auto_fit_columns(ws)

    def _style_header_row(self, ws, row: int = 1):
        """Apply header styling to first row"""
        for cell in ws[row]:
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.alignment = Alignment(horizontal='left', vertical='center')

    def _auto_fit_columns(self, ws, max_width: int = 50):
        """Auto-fit column widths"""
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter

            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass

            adjusted_width = min(max_length + 2, max_width)
            ws.column_dimensions[column_letter].width = adjusted_width

    def _get_column_letter(self, col_idx: int) -> str:
        """Convert column index to letter (1=A, 2=B, etc.)"""
        letter = ''
        while col_idx > 0:
            col_idx, remainder = divmod(col_idx - 1, 26)
            letter = chr(65 + remainder) + letter
        return letter


def test_exporter():
    """Test the Excel exporter"""
    logging.basicConfig(level=logging.INFO)

    # Create sample data
    sample_master_df = pd.DataFrame({
        'company': ['Test Co'] * 16,
        'ticker': ['TEST'] * 16,
        'ipo_date': [datetime(2020, 9, 16)] * 16,
        'quarter_end': pd.date_range('2020-12-31', periods=16, freq='Q'),
        'quarters_since_ipo': range(1, 17),
        'revenue_m': np.random.uniform(200, 400, 16),
        'sbc_m': np.random.uniform(30, 50, 16),
        'sbc_pct': np.random.uniform(12, 18, 16),
        'data_quality': ['A'] * 16,
        'listing_type': ['Traditional IPO'] * 16
    })

    sample_cliff_df = pd.DataFrame({
        'ticker': ['TEST'],
        'company': ['Test Co'],
        'ipo_date': [datetime(2020, 9, 16)],
        'q16_sbc_pct': [16.0],
        'q20_sbc_pct': [11.0],
        'decline_q16_to_q20': [-5.0]
    })

    metadata = {
        'run_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_companies': 60,
        'companies_collected': 50,
        'companies_included': 45,
        'companies_excluded': 5
    }

    exporter = ExcelExporter('test_output.xlsx')
    exporter._create_metadata_sheet(exporter.wb if hasattr(exporter, 'wb') else Workbook(), metadata)

    print("Excel exporter test complete")


if __name__ == "__main__":
    test_exporter()
