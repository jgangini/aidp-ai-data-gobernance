"""Refresh declared source hashes after an intentional candidate edit."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'src/ai_data_governance'
path = root / 'package/lab.json'
metadata = json.loads(path.read_text(encoding='utf-8'))
metadata['pack_version'] = '5.0.0'
for item in metadata['runtime_files']:
    item['sha256'] = hashlib.sha256((root / item['file']).read_bytes()).hexdigest()
path.write_bytes((json.dumps(metadata, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
