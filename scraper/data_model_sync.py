"""Synchronization service to copy parsed Statcast files into dataModel inputs."""

from datetime import datetime
import json
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

# Default location for the dataModel directory relative to repository root
DEFAULT_DATA_MODEL_DIR = Path(__file__).resolve().parent.parent / "dataModel"


def _has_csv_data_rows(file_path: Path) -> bool:
    """Check if a CSV file has at least one data row (beyond the header)."""
    if not file_path.exists():
        return False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            return len(lines) > 1
    except Exception:
        return False


def _atomic_copy(source_path: Path, target_path: Path) -> None:
    """Copy source_path to target_path atomically using a temporary file in the target directory."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target_path.with_name(f".{target_path.name}.tmp")
    shutil.copy2(source_path, temp_target)
    os.replace(temp_target, target_path)


class DataModelSync:
    """Copies scraper output files into dataModel/input*.csv and updates run metadata."""

    def __init__(self, data_model_dir: Optional[Union[str, Path]] = None):
        self.data_model_dir = Path(data_model_dir) if data_model_dir else DEFAULT_DATA_MODEL_DIR

    def sync_matchup(
        self,
        matchup_result: Dict[str, Any],
        pitcher_hand: Optional[str] = None,
        batter_stance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synchronize the 3 files generated from a head-to-head scrape into dataModel.

        Args:
            matchup_result: Dictionary returned by ScraperPipeline.scrape_head_to_head_to_csv.
            pitcher_hand: Pitcher throwing hand ('L', 'R', or 'both').
            batter_stance: Batter stance ('left', 'right', or 'both').

        Returns:
            Dictionary describing the synchronization result.
        """
        self.data_model_dir.mkdir(parents=True, exist_ok=True)

        player1 = matchup_result.get("player1", {})
        player2 = matchup_result.get("player2", {})
        matchup = matchup_result.get("matchup", {})

        # Identify which player is pitcher and which is batter
        if player1.get("type") == "pitcher" or player1.get("role") == "Pitcher":
            pitcher_info = player1
            batter_info = player2
        else:
            pitcher_info = player2
            batter_info = player1

        pitcher_file = Path(pitcher_info.get("file", ""))
        batter_file = Path(batter_info.get("file", ""))
        h2h_file = Path(matchup.get("file", ""))

        if not pitcher_file.exists():
            raise FileNotFoundError(f"Pitcher source file '{pitcher_file}' does not exist.")
        if not batter_file.exists():
            raise FileNotFoundError(f"Batter source file '{batter_file}' does not exist.")
        if not h2h_file.exists():
            raise FileNotFoundError(f"Head-to-head source file '{h2h_file}' does not exist.")

        target_pitcher = self.data_model_dir / "inputPitcher.csv"
        target_batter = self.data_model_dir / "inputBatter.csv"
        target_h2h = self.data_model_dir / "inputH2H.csv"
        target_meta = self.data_model_dir / "run_meta.json"

        # Perform atomic copies
        _atomic_copy(pitcher_file, target_pitcher)
        _atomic_copy(batter_file, target_batter)
        _atomic_copy(h2h_file, target_h2h)

        # Invalidate previous model run outputs so newly synced matchup starts clean
        for stale in ("model_output.json", "model_plot.png"):
            stale_path = self.data_model_dir / stale
            if stale_path.exists():
                try:
                    stale_path.unlink()
                except OSError:
                    pass

        has_h2h_data = _has_csv_data_rows(target_h2h)

        # Derive recommended column splits for threeSourceModel.py:
        # In threeSourceModel.py:
        # - arsenal_column is the BATTER's hand ('Left' for lefty batter, 'Right' for righty)
        # - batter_column is the PITCHER's hand ('Left' for lefty pitcher, 'Right' for righty)
        rec_arsenal_col = "Right"
        if batter_stance:
            rec_arsenal_col = "Left" if str(batter_stance).strip().lower() == "left" else "Right"

        rec_batter_col = "Right"
        if pitcher_hand:
            rec_batter_col = "Left" if str(pitcher_hand).strip().upper() == "L" else "Right"

        meta_content = {
            "synced_at": datetime.now().isoformat(),
            "mode": matchup_result.get("mode", "pitcher"),
            "season": matchup_result.get("season"),
            "count": matchup_result.get("count"),
            "pitcher": {
                "name": pitcher_info.get("name"),
                "hand": pitcher_hand or "both",
                "source_file": pitcher_file.name,
            },
            "batter": {
                "name": batter_info.get("name"),
                "stance": batter_stance or "both",
                "source_file": batter_file.name,
            },
            "matchup": {
                "name": matchup.get("name"),
                "source_file": h2h_file.name,
                "has_data": has_h2h_data,
            },
            "files": {
                "inputPitcher": target_pitcher.name,
                "inputBatter": target_batter.name,
                "inputH2H": target_h2h.name,
            },
            "recommended_model_settings": {
                "arsenal_column": rec_arsenal_col,
                "batter_column": rec_batter_col,
                "has_h2h_data": has_h2h_data,
            },
        }

        # Atomically write run_meta.json
        temp_meta = target_meta.with_name(".run_meta.json.tmp")
        with open(temp_meta, "w", encoding="utf-8") as f:
            json.dump(meta_content, f, indent=2)
        os.replace(temp_meta, target_meta)

        logger.info(
            f"Successfully synced matchup data to '{self.data_model_dir}': "
            f"inputPitcher.csv, inputBatter.csv, inputH2H.csv"
        )

        return {
            "success": True,
            "data_model_dir": str(self.data_model_dir),
            "files": {
                "pitcher": str(target_pitcher),
                "batter": str(target_batter),
                "h2h": str(target_h2h),
                "meta": str(target_meta),
            },
            "has_h2h_data": has_h2h_data,
            "recommended_model_settings": {
                "arsenal_column": rec_arsenal_col,
                "batter_column": rec_batter_col,
            },
        }
