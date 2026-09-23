"""Run frozen G1-P3 Stage A1/A2 calibration and stop for owner review."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from project2_g1.stage_a12_calibration import run_stage_a12

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--project-root",type=Path,default=ROOT); a=p.parse_args(argv)
    result=run_stage_a12(project_root=a.project_root)
    print(json.dumps({**result["summary"],"output_run":result["output_run"]},indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
