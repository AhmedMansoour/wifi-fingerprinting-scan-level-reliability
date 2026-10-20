"""Local paths for recovered numerical drivers."""
import os
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
WORKSPACE=Path(os.environ.get("WIFI_RESEARCH_ROOT",REPO/"results/research_workspace")).resolve()
def output_dir(stage):
    p=REPO/"results/advanced"/stage
    p.mkdir(parents=True,exist_ok=True)
    return p
