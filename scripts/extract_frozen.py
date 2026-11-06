"""Reproduce the explicit Governance source extraction; never read private files."""
import hashlib
import json
from pathlib import Path
import subprocess

REVISION = '3c82617fd298933995e954955841007253cc0985'
SOURCE = Path('D:/dev/codex-oci-ai-data-platform-workbench-starter-kits')
ROOT = Path(__file__).resolve().parents[1]
PREFIXES = {
    'apps/backend/app/modules/ai_data_governance/': 'src/ai_data_governance/',
    'apps/backend/tests/modules/ai_data_governance/': 'tests/domain/',
    'scripts/modules/ai_data_governance/': 'scripts/domain/',
}
EXTRAS = {
    'apps/backend/tests/support/ai_dg_fixtures.py': 'tests/support/ai_dg_fixtures.py',
    'apps/backend/tests/fixtures/ai_dg_activity_recovery_entry.py': 'tests/fixtures/ai_dg_activity_recovery_entry.py',
    'LICENSE': 'LICENSE',
}


def main():
    paths = subprocess.check_output(['git', '-C', str(SOURCE), 'ls-tree', '-r', '--name-only', REVISION], text=True).splitlines()
    selected = dict(EXTRAS)
    for path in paths:
        for prefix, target in PREFIXES.items():
            if path.startswith(prefix):
                selected[path] = target + path[len(prefix):]
    records = []
    for source, target in sorted(selected.items()):
        content = subprocess.check_output(['git', '-C', str(SOURCE), 'show', REVISION + ':' + source])
        destination = ROOT / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        if target.endswith('.py'):
            content = content.replace(b'app.modules.ai_data_governance', b'ai_data_governance')
            content = content.replace(b'app.services.oci.aidp', b'ai_data_governance.client')
            content = content.replace(b'app.services.oci.contracts', b'ai_data_governance.errors')
        destination.write_bytes(content)
        original = subprocess.check_output(['git', '-C', str(SOURCE), 'show', REVISION + ':' + source])
        records.append({'source': source, 'target': target, 'source_sha256': hashlib.sha256(original).hexdigest()})
    (ROOT / 'provenance.json').write_text(json.dumps({'repository': 'jgangini/oci-ai-data-platform-workbench-starter-kits',
        'commit': REVISION, 'files': records}, indent=2) + '\n', encoding='utf-8')
    print(f'Extracted {len(records)} versioned files')


if __name__ == '__main__':
    main()
