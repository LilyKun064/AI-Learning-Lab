"""Local-only research exports. These contain private rubrics and model candidates."""
import argparse
import json
from pathlib import Path
from storage import Store


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export', metavar='ATTEMPT_ID', help='Export one attempt, or all')
    p.add_argument('--output', default='research-export.json')
    args = p.parse_args()
    attempts = Store().list()
    if args.export:
        selected = [a for a in attempts if args.export == 'all' or a['attempt_id'] == args.export]
        if not selected:
            raise SystemExit('No matching attempt.')
        Path(args.output).write_text(json.dumps(selected, indent=2, ensure_ascii=False), encoding='utf-8')
        print('Exported', len(selected), 'attempt(s) to', args.output)
    else:
        for a in attempts:
            print(a['attempt_id'], a['started_at'], a['bundle']['activity']['title'], a['stage'])


if __name__ == '__main__':
    main()
