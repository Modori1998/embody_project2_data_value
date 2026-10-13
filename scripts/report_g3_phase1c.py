"""Summarize genuine saved human reviews; no scores means pending."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from project2_g3.simple_review import read_csv, summarize

def main():
    p=argparse.ArgumentParser();p.add_argument('--selection',type=Path,default=Path('0-doc/90-implementation-local/review_selection.csv'));p.add_argument('--results',type=Path,default=Path('outputs/g3_phase1c_reviews'));p.add_argument('--output',type=Path);a=p.parse_args()
    f=a.results/'simple_review.json';reviews=list(json.loads(f.read_text(encoding='utf-8')).values()) if f.exists() else []
    result=summarize(read_csv(a.selection),reviews)
    result['launch_command']='python scripts/run_g3_phase1c_simple.py --assets <PHASE1B_AB_OUTPUT> --port 18871'
    s=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(s,encoding='utf-8')
    print(s)
if __name__=='__main__':main()
