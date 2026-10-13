"""Lock a deterministic development sample from existing Phase 1B assets."""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from project2_g3.simple_review import read_csv, select, sha, validate_assets, blank

def write(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('0-doc/90-implementation-local'));a=p.parse_args()
    source=read_csv(a.assets/'ab_review_sheet_UNSCORED.csv');keys=read_csv(a.assets/'ab_blinding_key_SEALED.csv');prov=read_csv(a.assets/'evidence_frame_manifest.csv')
    validate_assets(source,keys,prov,a.assets)
    rows=select(source)
    for r in rows:
        for field in ('analyst_sheet','blinded_panel1','blinded_panel2'):
            r[field+'_sha256']=sha(a.assets/r[field])
        r['source_review_sha256']=sha(a.assets/'ab_review_sheet_UNSCORED.csv')
        r['source_provenance_sha256']=sha(a.assets/'evidence_frame_manifest.csv')
        r['blinding_key_sha256']=sha(a.assets/'ab_blinding_key_SEALED.csv')
    kept=('episode_id','segment_id','start_frame','end_frame','length','prev_status','next_status',
          'selection_strata','selection_seed','analyst_sheet','blinded_panel1','blinded_panel2',
          'analyst_sheet_sha256','blinded_panel1_sha256','blinded_panel2_sha256',
          'source_review_sha256','source_provenance_sha256','blinding_key_sha256')
    rows=[{k:r[k] for k in kept} for r in rows]
    write(a.output/'review_selection.csv',rows)
    write(a.output/'review_sheet_UNSCORED.csv',[blank(r) for r in rows])
    print(f'locked {len(rows)} segments from {len(source)}; {len({r["episode_id"] for r in rows})} episodes')

if __name__=='__main__':main()
