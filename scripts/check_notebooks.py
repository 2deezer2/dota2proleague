"""Execute both notebooks on explicit synthetic data; save outputs outside source notebooks."""
import os
import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--data',default=str(root/'tests/fixtures/demo.json'))
parser.add_argument('--output',default=str(root/'data/notebook_checks'))
args=parser.parse_args()
os.environ['SCOUT_DATA_PATH'] = str(Path(args.data).resolve())
output=Path(args.output).resolve()
output.mkdir(parents=True,exist_ok=True)
for path in sorted((root/'notebooks').glob('*.ipynb')):
    notebook=nbformat.read(path,as_version=4)
    nbformat.validate(notebook)
    executed=NotebookClient(notebook,timeout=120,kernel_name='python3',
                            resources={'metadata':{'path':str(root)}}).execute()
    nbformat.write(executed,output/path.name)
    print(f'Executed {path.name} using {args.data}',flush=True)
