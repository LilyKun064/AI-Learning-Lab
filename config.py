"""Validated content snapshots; no topic-dependent logic."""
import hashlib
import json
from pathlib import Path
from models import Activity, Rubric

ROOT = Path(__file__).resolve().parent
RUNTIME_FILES = ('core.py', 'models.py', 'config.py', 'gateway.py', 'app.py', 'storage.py')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def runtime_version():
    return fingerprint({n: (ROOT / n).read_text(encoding='utf-8') for n in RUNTIME_FILES})


def load_bundle(root=ROOT):
    root = Path(root)
    activity = Activity.model_validate_json((root / 'activity.json').read_text(encoding='utf-8-sig'))
    rubric = Rubric.model_validate_json((root / 'rubric.json').read_text(encoding='utf-8-sig'))
    if rubric.activity_id != activity.id:
        raise ValueError('rubric.json activity_id must match activity.json id.')
    ids = [c.id for c in rubric.criteria]
    if len(ids) != len(set(ids)):
        raise ValueError('Rubric criterion IDs must be unique.')
    if activity.table:
        if not activity.table.columns or len(set(activity.table.columns)) != len(activity.table.columns):
            raise ValueError('Table columns must be nonempty and unique.')
        if any(len(row) != len(activity.table.columns) for row in activity.table.rows):
            raise ValueError('Every table row must match the number of columns.')
    bundle = {'activity': activity.model_dump(), 'rubric': rubric.model_dump(),
              'teaching_policy': (root / 'teaching_policy.md').read_text(encoding='utf-8-sig'),
              'boundary_policy': (root / 'boundary_policy.md').read_text(encoding='utf-8-sig')}
    if not bundle['teaching_policy'].strip() or not bundle['boundary_policy'].strip():
        raise ValueError('Policy files cannot be empty.')
    bundle['version'] = fingerprint(bundle)
    bundle['runtime_version'] = runtime_version()
    return bundle


if __name__ == '__main__':
    b = load_bundle()
    print(f"Valid: {b['activity']['title']} | {len(b['rubric']['criteria'])} criteria | version {b['version']}")
