"""Analyzer for Statcast pitch data computing velocity and occurrence percentages with stance/hand splits."""

import io
import logging
from typing import List, Optional, Union
import numpy as np
import pandas as pd

from scraper.config import normalize_batter_stance, normalize_count, normalize_pitcher_hand

logger = logging.getLogger(__name__)


class PitchAnalyzer:
    """Computes pitch arsenals, average velocities, and occurrence percentages with flexible splits."""

    @classmethod
    def load_dataframe(cls, raw_data: Union[pd.DataFrame, str, bytes]) -> pd.DataFrame:
        """Convert input data (CSV string, bytes, or DataFrame) into a clean pandas DataFrame."""
        if isinstance(raw_data, pd.DataFrame):
            df = raw_data.copy()
        elif isinstance(raw_data, (str, bytes)):
            text = raw_data.decode("utf-8", errors="ignore") if isinstance(raw_data, bytes) else raw_data
            if not text.strip():
                return pd.DataFrame()
            try:
                df = pd.read_csv(io.StringIO(text))
            except Exception as e:
                logger.error(f"Failed to parse CSV pitch data: {e}")
                return pd.DataFrame()
        else:
            raise TypeError(f"Unsupported data type for pitch analyzer: {type(raw_data)}")

        # Ensure required columns exist
        for col in ["pitch_name", "pitch_type", "release_speed", "p_throws", "stand"]:
            if col not in df.columns:
                df[col] = np.nan

        # Normalize pitch identifier
        def get_pitch_label(row):
            if "resolved_pitch" in row and pd.notna(row["resolved_pitch"]):
                val = str(row["resolved_pitch"]).strip()
                if val and val.lower() not in ["nan", "null", "none", ""]:
                    return val
            p_name = str(row["pitch_name"]).strip() if pd.notna(row["pitch_name"]) else ""
            if p_name and p_name.lower() not in ["nan", "null", "none", ""]:
                return p_name
            p_type = str(row["pitch_type"]).strip() if pd.notna(row["pitch_type"]) else ""
            if p_type and p_type.lower() not in ["nan", "null", "none", ""]:
                return p_type
            return None

        clean_pitches = df.apply(get_pitch_label, axis=1)
        data_dict = {
            "resolved_pitch": clean_pitches,
            "release_speed": pd.to_numeric(df["release_speed"], errors="coerce"),
            "p_throws": df["p_throws"].astype(str).str.strip().str.upper(),
            "stand": df["stand"].astype(str).str.strip().str.upper(),
        }
        if "balls" in df.columns:
            data_dict["balls"] = pd.to_numeric(df["balls"], errors="coerce")
        if "strikes" in df.columns:
            data_dict["strikes"] = pd.to_numeric(df["strikes"], errors="coerce")

        clean_df = pd.DataFrame(data_dict)
        clean_df = clean_df.dropna(subset=["resolved_pitch"]).copy()

        return clean_df

    def analyze(
        self,
        raw_data: Union[pd.DataFrame, str, bytes],
        pitcher_hand: str,
        batter_stance: str,
        count: Optional[str] = None,
    ) -> pd.DataFrame:
        """Analyze pitch data and generate a formatted DataFrame.
        
        Args:
            raw_data: Raw CSV string or DataFrame from Statcast.
            pitcher_hand: Pitcher throwing hand ('L', 'R', or 'both').
            batter_stance: Batter stance ('left', 'right', or 'both').
            count: Optional ball-strike count filter ('0-0', '2-1', etc.).
            
        Returns:
            Formatted pd.DataFrame with pitch types as rows and the requested columns.
        """
        norm_hand = normalize_pitcher_hand(pitcher_hand)
        if not norm_hand:
            raise ValueError(f"Invalid pitcher throwing hand: '{pitcher_hand}'. Must be 'L', 'R', or 'both'.")

        norm_stance = normalize_batter_stance(batter_stance)
        if not norm_stance:
            raise ValueError(f"Invalid batter stance: '{batter_stance}'. Must be 'left', 'right', or 'both'.")

        df = self.load_dataframe(raw_data)

        p_both = (norm_hand == "both")
        b_both = (norm_stance == "both")

        # Determine target headers for this combination
        target_headers = self.get_output_headers(norm_hand, norm_stance)

        if df.empty:
            logger.warning("No pitch data available for analysis.")
            return pd.DataFrame(columns=target_headers)

        # Apply single-hand / single-stance filters
        work_df = df.copy()
        if not p_both:
            work_df = work_df[work_df["p_throws"] == norm_hand]

        if not b_both:
            target_stand = "L" if norm_stance == "left" else "R"
            work_df = work_df[work_df["stand"] == target_stand]

        # Apply count filter if specified
        if count:
            norm_count = normalize_count(count)
            if norm_count and "balls" in work_df.columns and "strikes" in work_df.columns:
                b_target, s_target = [int(x) for x in norm_count.split("-")]
                work_df = work_df[(work_df["balls"] == b_target) & (work_df["strikes"] == s_target)]

        if work_df.empty:
            logger.warning("Pitch data is empty after applying filters.")
            return pd.DataFrame(columns=target_headers)

        # Unique pitches ordered by overall frequency descending
        pitch_order = list(work_df["resolved_pitch"].value_counts().index)

        rows = []
        for pitch in pitch_order:
            row_dict = {"Pitch Type": pitch}
            pitch_subset = work_df[work_df["resolved_pitch"] == pitch]

            if not p_both and not b_both:
                # Scenario 1: Single pitcher hand, Single batter stance
                total_pitches = len(work_df)
                cnt = len(pitch_subset)
                avg_velo = pitch_subset["release_speed"].mean() if cnt > 0 else np.nan
                pct = (cnt / total_pitches * 100.0) if total_pitches > 0 else 0.0

                row_dict["Average Velocity (mph)"] = f"{avg_velo:.1f}" if not np.isnan(avg_velo) else "N/A"
                row_dict["Occurrence Percentage (%)"] = f"{pct:.1f}%"

            elif not p_both and b_both:
                # Scenario 2: Single pitcher hand, Both batter stance (splits by stand L vs R)
                df_l = work_df[work_df["stand"] == "L"]
                df_r = work_df[work_df["stand"] == "R"]

                cnt_l = len(df_l[df_l["resolved_pitch"] == pitch])
                cnt_r = len(df_r[df_r["resolved_pitch"] == pitch])

                velo_l = df_l[df_l["resolved_pitch"] == pitch]["release_speed"].mean()
                velo_r = df_r[df_r["resolved_pitch"] == pitch]["release_speed"].mean()

                pct_l = (cnt_l / len(df_l) * 100.0) if len(df_l) > 0 else 0.0
                pct_r = (cnt_r / len(df_r) * 100.0) if len(df_r) > 0 else 0.0

                row_dict["Average Velocity - Left (mph)"] = f"{velo_l:.1f}" if not np.isnan(velo_l) else "N/A"
                row_dict["Average Velocity - Right (mph)"] = f"{velo_r:.1f}" if not np.isnan(velo_r) else "N/A"
                row_dict["Occurrence Percentage - Left (%)"] = f"{pct_l:.1f}%"
                row_dict["Occurrence Percentage - Right (%)"] = f"{pct_r:.1f}%"

            elif p_both and not b_both:
                # Scenario 3: Both pitcher hand (splits by p_throws L vs R), Single batter stance
                df_l = work_df[work_df["p_throws"] == "L"]
                df_r = work_df[work_df["p_throws"] == "R"]

                cnt_l = len(df_l[df_l["resolved_pitch"] == pitch])
                cnt_r = len(df_r[df_r["resolved_pitch"] == pitch])

                velo_l = df_l[df_l["resolved_pitch"] == pitch]["release_speed"].mean()
                velo_r = df_r[df_r["resolved_pitch"] == pitch]["release_speed"].mean()

                pct_l = (cnt_l / len(df_l) * 100.0) if len(df_l) > 0 else 0.0
                pct_r = (cnt_r / len(df_r) * 100.0) if len(df_r) > 0 else 0.0

                row_dict["Average Velocity - Left (mph)"] = f"{velo_l:.1f}" if not np.isnan(velo_l) else "N/A"
                row_dict["Average Velocity - Right (mph)"] = f"{velo_r:.1f}" if not np.isnan(velo_r) else "N/A"
                row_dict["Occurrence Percentage - Left (%)"] = f"{pct_l:.1f}%"
                row_dict["Occurrence Percentage - Right (%)"] = f"{pct_r:.1f}%"

            else:
                # Scenario 4: Both pitcher hand AND Both batter stance
                p_left = work_df[work_df["p_throws"] == "L"]
                p_right = work_df[work_df["p_throws"] == "R"]
                b_left = work_df[work_df["stand"] == "L"]
                b_right = work_df[work_df["stand"] == "R"]

                # Pitcher hand metrics
                pl_pitch = p_left[p_left["resolved_pitch"] == pitch]
                pr_pitch = p_right[p_right["resolved_pitch"] == pitch]
                v_pl = pl_pitch["release_speed"].mean()
                v_pr = pr_pitch["release_speed"].mean()
                pct_pl = (len(pl_pitch) / len(p_left) * 100.0) if len(p_left) > 0 else 0.0
                pct_pr = (len(pr_pitch) / len(p_right) * 100.0) if len(p_right) > 0 else 0.0

                # Batter stance metrics
                bl_pitch = b_left[b_left["resolved_pitch"] == pitch]
                br_pitch = b_right[b_right["resolved_pitch"] == pitch]
                v_bl = bl_pitch["release_speed"].mean()
                v_br = br_pitch["release_speed"].mean()
                pct_bl = (len(bl_pitch) / len(b_left) * 100.0) if len(b_left) > 0 else 0.0
                pct_br = (len(br_pitch) / len(b_right) * 100.0) if len(b_right) > 0 else 0.0

                row_dict["Average Velocity - Pitcher Left (mph)"] = f"{v_pl:.1f}" if not np.isnan(v_pl) else "N/A"
                row_dict["Average Velocity - Pitcher Right (mph)"] = f"{v_pr:.1f}" if not np.isnan(v_pr) else "N/A"
                row_dict["Average Velocity - Batter Left (mph)"] = f"{v_bl:.1f}" if not np.isnan(v_bl) else "N/A"
                row_dict["Average Velocity - Batter Right (mph)"] = f"{v_br:.1f}" if not np.isnan(v_br) else "N/A"
                row_dict["Occurrence Percentage - Pitcher Left (%)"] = f"{pct_pl:.1f}%"
                row_dict["Occurrence Percentage - Pitcher Right (%)"] = f"{pct_pr:.1f}%"
                row_dict["Occurrence Percentage - Batter Left (%)"] = f"{pct_bl:.1f}%"
                row_dict["Occurrence Percentage - Batter Right (%)"] = f"{pct_br:.1f}%"

            rows.append(row_dict)

        result_df = pd.DataFrame(rows)
        return result_df[target_headers]

    @classmethod
    def get_output_headers(cls, norm_hand: str, norm_stance: str) -> List[str]:
        """Return the list of output column names based on hand and stance selections."""
        p_both = (norm_hand == "both")
        b_both = (norm_stance == "both")

        if not p_both and not b_both:
            return [
                "Pitch Type",
                "Average Velocity (mph)",
                "Occurrence Percentage (%)",
            ]
        elif not p_both and b_both:
            return [
                "Pitch Type",
                "Average Velocity - Left (mph)",
                "Average Velocity - Right (mph)",
                "Occurrence Percentage - Left (%)",
                "Occurrence Percentage - Right (%)",
            ]
        elif p_both and not b_both:
            return [
                "Pitch Type",
                "Average Velocity - Left (mph)",
                "Average Velocity - Right (mph)",
                "Occurrence Percentage - Left (%)",
                "Occurrence Percentage - Right (%)",
            ]
        else:
            return [
                "Pitch Type",
                "Average Velocity - Pitcher Left (mph)",
                "Average Velocity - Pitcher Right (mph)",
                "Average Velocity - Batter Left (mph)",
                "Average Velocity - Batter Right (mph)",
                "Occurrence Percentage - Pitcher Left (%)",
                "Occurrence Percentage - Pitcher Right (%)",
                "Occurrence Percentage - Batter Left (%)",
                "Occurrence Percentage - Batter Right (%)",
            ]

