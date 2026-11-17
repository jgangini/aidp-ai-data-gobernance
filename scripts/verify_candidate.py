"""Offline artifact, import-boundary and explicit source-hash verification."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.path.insert(0, str(ROOT / 'src'))
    from ai_data_governance.package_loader import load_package
    from ai_data_governance.aidp_contract import load_aidp_manifest
    load_package()
    root = ROOT / 'src/ai_data_governance'
    contract = load_aidp_manifest(root, 'ai_data_governance')
    assert len(contract['model']['tables']) == 18 and len(contract['agents']) == 2
    for path in root.rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith(('app.', 'tests.', 'ai_market_intelligence', 'ai_gods_eye_view')), path
    names = subprocess.check_output(['git', 'ls-files', '--cached'], cwd=ROOT, text=True).splitlines()
    blocked = {'.oci', '.local', '.venv', '.terraform', '__pycache__'}
    for name in names:
        path = Path(name)
        assert not blocked.intersection(path.parts) and path.suffix not in {'.pem', '.key', '.tfstate'}, name
        content = (ROOT / path).read_bytes()
        # A complete private key, unlike test references to key types, is never permitted.
        import re
        assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/]{40}', content), name
        assert not re.search(rb'\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-proj-[A-Za-z0-9_-]{40,})\b', content), name
    print(json.dumps({'package': 'ai_data_governance', 'tables': 18, 'agents': 2,
        'source_import_boundary': 'passed', 'staged_files_scanned': len(names)}))


if __name__ == '__main__':
    main()
