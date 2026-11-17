"""Gate only versioned/unignored product source, never build, secrets or caches."""
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    stage = ROOT / '.local' / ('sentrux-' + uuid.uuid4().hex)
    stage.mkdir(parents=True)
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    for name in sorted(set(names)):
        path = Path(name)
        if path.parts[0] not in {'src', 'tests', 'scripts', 'terraform'} or path.suffix not in {'.py', '.ps1', '.tf', '.hcl'}:
            continue
        origin = (ROOT / path).resolve()
        if not origin.is_relative_to(ROOT) or origin.is_symlink():
            raise ValueError('Architecture source escaped the repository')
        target = stage / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
    baseline = ROOT / '.sentrux/baseline.json'
    initial = ROOT / '.sentrux/initial-baseline.json'
    if not baseline.exists() and initial.exists():
        shutil.copyfile(initial, baseline)
    if baseline.exists():
        (stage / '.sentrux').mkdir()
        shutil.copyfile(baseline, stage / '.sentrux/baseline.json')
        command = ['sentrux', 'gate', str(stage)]
    elif '--save' in sys.argv:
        command = ['sentrux', 'gate', '--save', str(stage)]
    else:
        raise ValueError('Architecture baseline is missing')
    result = subprocess.run(command)
    if not baseline.exists() and result.returncode == 0:
        baseline.parent.mkdir(exist_ok=True)
        shutil.copyfile(stage / '.sentrux/baseline.json', baseline)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
