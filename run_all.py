"""Run the whole pipeline in order, from the repo root.

    python run_all.py            rebuild everything from the committed raw snapshot in data/raw/
                                 (this reproduces the committed numbers exactly)
    python run_all.py --refresh  re-download all raw data first (Wikipedia + Yahoo Finance);
                                 numbers will change, because Yahoo revises and rolls off history
"""
import runpy
import sys
from pathlib import Path

here = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(here))  # so each script can import _common
print('mode:', 'REFRESH (re-download raw data)' if '--refresh' in sys.argv else 'cached raw data')
for script in ['00_universe.py', '01_get_ratings.py', '02_get_earnings.py', '03_get_returns.py',
               '04_build_event_panel.py', '05_results.py', '99_hand_checks.py']:
    print(f'\n===== {script} =====')
    runpy.run_path(str(here / script), run_name='__main__')
print('\nPipeline finished.')
