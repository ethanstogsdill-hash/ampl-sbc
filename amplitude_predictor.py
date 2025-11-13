"""
Amplitude Predictor - Generate SBC trajectory predictions for Amplitude
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from dateutil.relativedelta import relativedelta


class AmplitudePredictor:
    """Generate SBC trajectory predictions for Amplitude based on peer patterns"""

    def __init__(self):
        """Initialize Amplitude predictor"""
        self.logger = logging.getLogger(__name__)

    def get_amplitude_current_state(self, master_df: pd.DataFrame,
                                   cliff_df: pd.DataFrame) -> Dict[str, any]:
        """
        Get Amplitude's current state from the data

        Args:
            master_df: Master dataset
            cliff_df: Q16 cliff analysis

        Returns:
            Dictionary with Amplitude's current state
        """
        self.logger.info("Getting Amplitude current state...")

        # Get Amplitude data
        ampl_data = master_df[master_df['ticker'] == 'AMPL']

        if len(ampl_data) == 0:
            self.logger.warning("No Amplitude data found")
            return {
                'found': False,
                'reason': 'No data available'
            }

        # Get most recent quarter
        latest = ampl_data.iloc[-1]
        max_quarter = int(ampl_data['quarters_since_ipo'].max())

        # Get Q16 data if available
        q16_data = ampl_data[ampl_data['quarters_since_ipo'] == 16]
        if len(q16_data) > 0:
            q16_sbc_pct = q16_data.iloc[0]['sbc_pct']
            at_q16 = True
        else:
            q16_sbc_pct = None
            at_q16 = False

        state = {
            'found': True,
            'ticker': 'AMPL',
            'company': 'Amplitude',
            'ipo_date': latest['ipo_date'],
            'current_quarter_number': max_quarter,
            'current_quarter_end': latest['quarter_end'],
            'current_sbc_pct': float(latest['sbc_pct']),
            'current_revenue_m': float(latest['revenue_m']),
            'current_sbc_m': float(latest['sbc_m']),
            'at_q16': at_q16,
            'q16_sbc_pct': float(q16_sbc_pct) if q16_sbc_pct is not None else None,
            'listing_type': latest['listing_type']
        }

        # Get GAAP margin if available
        if 'gaap_op_margin' in latest and pd.notna(latest['gaap_op_margin']):
            state['current_gaap_margin'] = float(latest['gaap_op_margin'])
        else:
            state['current_gaap_margin'] = None

        self.logger.info(f"Amplitude current state: Q{max_quarter}, SBC={state['current_sbc_pct']:.1f}%")

        return state

    def predict_trajectory(self, current_state: Dict[str, any],
                          pattern_stats: Dict[str, any],
                          pattern_stats_2021: Optional[Dict[str, any]] = None) -> Dict[str, any]:
        """
        Predict Amplitude's SBC trajectory

        Args:
            current_state: Amplitude's current state
            pattern_stats: Overall pattern statistics
            pattern_stats_2021: 2021 cohort-specific statistics (optional)

        Returns:
            Dictionary with predictions
        """
        self.logger.info("Predicting Amplitude trajectory...")

        if not current_state.get('found', False):
            return {'error': 'Amplitude data not found'}

        if not current_state.get('at_q16', False):
            return {
                'error': 'Amplitude not yet at Q16',
                'current_quarter': current_state.get('current_quarter_number')
            }

        # Base prediction on Q16 SBC %
        q16_sbc = current_state['q16_sbc_pct']
        ipo_date = current_state['ipo_date']

        # Use 2021 cohort if available, otherwise use overall stats
        if pattern_stats_2021 and pattern_stats_2021.get('n_companies', 0) >= 3:
            self.logger.info("Using 2021 cohort statistics for prediction")
            stats_to_use = pattern_stats_2021
            cohort_label = "2021 IPO Cohort"
        else:
            self.logger.info("Using overall statistics for prediction")
            stats_to_use = pattern_stats
            cohort_label = "All Companies"

        # Extract decline statistics
        conservative_decline = stats_to_use.get('pct_25', -3.0)  # 25th percentile
        base_decline = stats_to_use.get('median_decline', -5.0)  # Median
        bull_decline = stats_to_use.get('pct_75', -7.0)  # 75th percentile

        # Generate quarterly projections from current quarter to Q24
        current_q = current_state['current_quarter_number']
        projections = []

        for q in range(current_q, 25):  # Project through Q24
            quarter_end = ipo_date + relativedelta(months=3 * (q - 1))

            if q <= current_q:
                # Historical data
                proj = {
                    'quarter': f"Q{q}",
                    'quarters_since_ipo': q,
                    'quarter_end': quarter_end,
                    'conservative_sbc_pct': current_state['current_sbc_pct'],
                    'base_sbc_pct': current_state['current_sbc_pct'],
                    'bull_sbc_pct': current_state['current_sbc_pct'],
                    'is_actual': True
                }
            else:
                # Calculate linear interpolation from Q16 to Q20
                if q <= 20:
                    progress = (q - 16) / 4  # Progress from Q16 to Q20

                    conservative_sbc = q16_sbc + (conservative_decline * progress)
                    base_sbc = q16_sbc + (base_decline * progress)
                    bull_sbc = q16_sbc + (bull_decline * progress)
                else:
                    # After Q20, continue the trend
                    quarters_past_20 = q - 20
                    additional_decline = quarters_past_20 * 0.5  # Slower decline rate

                    conservative_sbc = q16_sbc + conservative_decline - additional_decline
                    base_sbc = q16_sbc + base_decline - (additional_decline * 1.2)
                    bull_sbc = q16_sbc + bull_decline - (additional_decline * 1.5)

                proj = {
                    'quarter': f"Q{q}",
                    'quarters_since_ipo': q,
                    'quarter_end': quarter_end,
                    'conservative_sbc_pct': round(conservative_sbc, 2),
                    'base_sbc_pct': round(base_sbc, 2),
                    'bull_sbc_pct': round(bull_sbc, 2),
                    'is_actual': False
                }

            projections.append(proj)

        projections_df = pd.DataFrame(projections)

        # Calculate implied GAAP margin improvement
        # Assume current GAAP margin (if available) improves by SBC decline
        current_margin = current_state.get('current_gaap_margin', 0.0)

        projections_df['conservative_implied_margin'] = (
            current_margin + (current_state['current_sbc_pct'] - projections_df['conservative_sbc_pct'])
        ).round(2)

        projections_df['base_implied_margin'] = (
            current_margin + (current_state['current_sbc_pct'] - projections_df['base_sbc_pct'])
        ).round(2)

        projections_df['bull_implied_margin'] = (
            current_margin + (current_state['current_sbc_pct'] - projections_df['bull_sbc_pct'])
        ).round(2)

        # Create summary
        summary = {
            'company': 'Amplitude (AMPL)',
            'ipo_date': ipo_date,
            'current_quarter': f"Q{current_q}",
            'q16_sbc_pct': q16_sbc,
            'current_sbc_pct': current_state['current_sbc_pct'],
            'cohort_used': cohort_label,
            'n_companies_in_cohort': stats_to_use.get('n_companies', 0),
            'conservative_decline_q16_q20': conservative_decline,
            'base_decline_q16_q20': base_decline,
            'bull_decline_q16_q20': bull_decline,
            'projections': projections_df
        }

        self.logger.info(f"Prediction complete: {len(projections_df)} quarters projected")

        return summary

    def compare_to_peers(self, current_state: Dict[str, any],
                        cliff_df: pd.DataFrame) -> Dict[str, any]:
        """
        Compare Amplitude to peer companies at Q16

        Args:
            current_state: Amplitude's current state
            cliff_df: Q16 cliff analysis

        Returns:
            Dictionary with peer comparison
        """
        self.logger.info("Comparing Amplitude to peers...")

        if not current_state.get('at_q16', False):
            return {
                'error': 'Amplitude not yet at Q16',
                'current_quarter': current_state.get('current_quarter_number')
            }

        ampl_q16_sbc = current_state['q16_sbc_pct']

        # Get peer companies (traditional IPOs only)
        peers = cliff_df[
            (cliff_df['listing_type'] == 'Traditional IPO') &
            (cliff_df['ticker'] != 'AMPL')
        ]

        if len(peers) == 0:
            return {'error': 'No peer companies available'}

        # Get Q16 SBC distribution
        q16_values = peers['q16_sbc_pct'].dropna()

        comparison = {
            'amplitude_q16_sbc_pct': ampl_q16_sbc,
            'peer_mean': float(q16_values.mean()),
            'peer_median': float(q16_values.median()),
            'peer_std': float(q16_values.std()),
            'peer_min': float(q16_values.min()),
            'peer_max': float(q16_values.max()),
            'peer_25th_pct': float(q16_values.quantile(0.25)),
            'peer_75th_pct': float(q16_values.quantile(0.75)),
            'amplitude_percentile': float((q16_values < ampl_q16_sbc).sum() / len(q16_values) * 100),
            'n_peers': len(q16_values)
        }

        # Determine if Amplitude is unusual
        z_score = (ampl_q16_sbc - comparison['peer_mean']) / comparison['peer_std']
        comparison['z_score'] = float(z_score)

        if abs(z_score) > 2:
            comparison['is_outlier'] = True
            if z_score > 2:
                comparison['outlier_note'] = "Amplitude's Q16 SBC% is significantly HIGHER than peers"
            else:
                comparison['outlier_note'] = "Amplitude's Q16 SBC% is significantly LOWER than peers"
        else:
            comparison['is_outlier'] = False
            comparison['outlier_note'] = "Amplitude's Q16 SBC% is within normal range for peers"

        return comparison

    def create_scenario_summary(self, prediction: Dict[str, any]) -> pd.DataFrame:
        """
        Create summary table of scenarios at key quarters

        Args:
            prediction: Prediction dictionary from predict_trajectory()

        Returns:
            DataFrame with scenario summary
        """
        if 'error' in prediction:
            return pd.DataFrame()

        proj_df = prediction['projections']

        # Filter to key quarters (Q16, Q20, Q24)
        key_quarters = [16, 20, 24]
        summary_rows = []

        for q in key_quarters:
            quarter_data = proj_df[proj_df['quarters_since_ipo'] == q]

            if len(quarter_data) == 0:
                continue

            row = quarter_data.iloc[0]

            summary_rows.append({
                'quarter': row['quarter'],
                'quarter_end': row['quarter_end'],
                'conservative_sbc_pct': row['conservative_sbc_pct'],
                'base_sbc_pct': row['base_sbc_pct'],
                'bull_sbc_pct': row['bull_sbc_pct'],
                'conservative_margin': row['conservative_implied_margin'],
                'base_margin': row['base_implied_margin'],
                'bull_margin': row['bull_implied_margin']
            })

        return pd.DataFrame(summary_rows)


def test_predictor():
    """Test the Amplitude predictor"""
    logging.basicConfig(level=logging.INFO)

    # Create sample current state
    current_state = {
        'found': True,
        'ticker': 'AMPL',
        'company': 'Amplitude',
        'ipo_date': datetime(2021, 9, 28),
        'current_quarter_number': 16,
        'current_quarter_end': datetime(2025, 9, 30),
        'current_sbc_pct': 16.0,
        'current_revenue_m': 88.6,
        'current_sbc_m': 14.2,
        'at_q16': True,
        'q16_sbc_pct': 16.0,
        'current_gaap_margin': 0.6,
        'listing_type': 'Traditional IPO'
    }

    # Sample pattern statistics
    pattern_stats = {
        'n_companies': 25,
        'median_decline': -5.2,
        'pct_25': -3.5,
        'pct_75': -7.1
    }

    predictor = AmplitudePredictor()

    # Test prediction
    prediction = predictor.predict_trajectory(current_state, pattern_stats)

    print("\nAmplitude Prediction:")
    print(f"Cohort: {prediction.get('cohort_used')}")
    print(f"Base case Q20 decline: {prediction.get('base_decline_q16_q20'):.2f} points")

    print("\nProjection Summary (first 5 quarters):")
    print(prediction['projections'][['quarter', 'base_sbc_pct', 'base_implied_margin']].head())

    # Test scenario summary
    scenario_summary = predictor.create_scenario_summary(prediction)
    print("\nKey Quarter Summary:")
    print(scenario_summary)


if __name__ == "__main__":
    test_predictor()
