"""Explicit single-product loader, with path and source hash validation."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from .aidp_contract import load_aidp_manifest, source_file


@dataclass(frozen=True)
class Package:
    pack_version: str
    lab_id: str = 'ai_data_governance'


def load_package(module_id='ai_data_governance', *, require_available=True):
    if module_id != 'ai_data_governance':
        raise ValueError('Only the Governance package is supported')
    root = Path(__file__).resolve().parent
    metadata = json.loads((root / 'package/lab.json').read_text(encoding='utf-8'))
    if metadata['lab_id'] != module_id or (require_available and metadata['status'] != 'available'):
        raise ValueError('Invalid or unavailable Governance package')
    load_aidp_manifest(root, module_id)
    for asset in metadata['runtime_files']:
        if hashlib.sha256(source_file(root, asset['file']).read_bytes()).hexdigest() != asset['sha256']:
            raise ValueError('Governance package source hash mismatch: ' + asset['file'])
    return Package(metadata['pack_version'])
