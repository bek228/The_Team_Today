"""
Run the complete analyst-rating event study from the repository root.

Usage:
    python run_all.py
"""

from pathlib import Path
import runpy
import os
import sys

ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT / "src" / "pipeline.py"

if not PIPELINE.exists():
    raise FileNotFoundError(
        f"Could not find {PIPELINE}. Make sure src/pipeline.py is in the repository."
    )

os.chdir(ROOT)
print(f"Running analyst-rating pipeline from: {ROOT}")
runpy.run_path(str(PIPELINE), run_name="__main__")
print("\nPipeline finished.")
