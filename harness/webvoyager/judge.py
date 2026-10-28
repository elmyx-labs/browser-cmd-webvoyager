#!/usr/bin/env python3
"""Judge a run with the leader's own evaluator, unchanged: omxyz/webvoyager's
evaluation/auto_eval.py (GPT-5.5, Alumnium vanilla SUCCESS / NOT SUCCESS over the
task, the final answer and the final screenshot), fetched at a pinned commit and
checked against its hash, in a venv with the leader's own dependency lock.

    OPENAI_API_KEY=... python3 judge.py runs/final
"""
import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parents[1]
HOME = BENCH / '.judge'
COMMIT = 'df42681582be8125c5296473ad8efcd86f926cb6'
SOURCE = f'https://raw.githubusercontent.com/omxyz/webvoyager/{COMMIT}/'
FILES = {
    'evaluation/auto_eval.py': 'd09efb00afb25c40ab9c11e190aa166810e0a681a1baa77fff0bd69a1825b6dc',
    'requirements-webvoyager.txt': None,
}


def fetch():
    """The judge and its lock at the pinned commit, verified."""
    HOME.mkdir(exist_ok=True)
    for name, digest in FILES.items():
        path = HOME / Path(name).name
        if not path.exists():
            path.write_bytes(urllib.request.urlopen(SOURCE + name, timeout=60).read())
        if digest and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SystemExit(f'{path} does not match the pinned judge; delete it and run again')
    python = HOME / 'venv' / 'bin' / 'python'
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(HOME / 'venv')], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '-q', '-r', str(HOME / 'requirements-webvoyager.txt')], check=True)
    return python


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run', type=Path)
    parser.add_argument('--model', default='gpt-5.5')
    parser.add_argument('--resume', action='store_true', help='keep judgments already made')
    args = parser.parse_args()
    run = args.run.resolve()
    python = fetch()
    manifest = json.loads((run / 'manifest.json').read_text())
    command = [str(python), str(HOME / 'auto_eval.py'), '--results', str(run / 'results.json'), '--out-dir', str(run / 'judge'),
               '--task-data', str(run / 'tasks.jsonl'), '--model', args.model, '--max-attached-imgs', '1',
               '--max-completion-tokens', '2000', '--publish-to-run-dir', '--run-model-label', manifest['model']]
    subprocess.run(command + (['--resume'] if args.resume else []), cwd=ROOT, check=True)
    manifest.update(status='judged', judge={'commit': COMMIT, 'model': args.model})
    (run / 'manifest.json').write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
