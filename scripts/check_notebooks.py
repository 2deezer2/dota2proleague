"""Execute both notebooks on explicit synthetic data; save outputs outside source notebooks."""
import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parents[1]
os.environ['SCOUT_DATA_PATH'] = str(root/'tests/fixtures/demo.json')
output=root/'data/notebook_checks'
output.mkdir(parents=True,exist_ok=True)
for path in sorted((root/'notebooks').glob('*.ipynb')):
    notebook=nbformat.read(path,as_version=4)
    nbformat.validate(notebook)
    executed=NotebookClient(notebook,timeout=120,kernel_name='python3',
                            resources={'metadata':{'path':str(root)}}).execute()
    nbformat.write(executed,output/path.name)
    print(f'Executed {path.name} on labelled synthetic demo')
