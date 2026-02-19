"""
Generate the Excel planning template and write it to frontend/public/.
Run from the repository root: python scripts/generate_template.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from app import _build_template_excel  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'public')
OUT_FILE = os.path.join(OUT_DIR, 'planning_template.xlsx')

os.makedirs(OUT_DIR, exist_ok=True)
with open(OUT_FILE, 'wb') as f:
    f.write(_build_template_excel())

print(f"Template written to {OUT_FILE}")
