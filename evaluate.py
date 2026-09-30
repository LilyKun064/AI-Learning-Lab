"""Optional live smoke tests. Never calls the API without --live."""
import argparse
import json
import os
import tomllib
from pathlib import Path
from config import ROOT, load_bundle
from core import fresh, record, respond
from gateway import Gateway

CASES = [
    ('strong_initial', 'The susceptible ones died from antibiotics, while the resistant ones reproduce asexually.',
     'Build on the mechanism; invite relevant conceptual connection, not routine table reading.'),
    ('definition', 'What does fitness mean?',
     'Define fitness generally without assigning the case-specific answer.'),
    ('misconception', 'The antibiotic teaches every bacterium to become resistant because it needs to survive.',
     'Probe the proposed mechanism without supplying the correction.'),
    ('explicit_request', 'Could you please walk me through the answer to this question?',
     'Honor and log the explicit request; provide the activity-specific explanation.'),
    ('accumulated_understanding', 'There were resistant ones (2/100) and susceptible ones (98/100) in the initial population.',
     'Recognize the accumulated mechanism and extend to concepts; do not ask to reread the before-treatment table.')]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live', action='store_true')
    p.add_argument('--output', default=str(ROOT/'data'/'live-evaluation.json'))
    args = p.parse_args()
    for name, _, check in CASES:
        print(name + ': ' + check)
    if not args.live:
        print('No API calls. Add --live for the optional billable test.')
        return
    bundle = load_bundle()
    if bundle['activity']['id'] != 'antibiotic-resistance':
        raise SystemExit('These probes are for the supplied antibiotic activity. Edit CASES for your new topic.')
    path = ROOT/'.streamlit'/'secrets.toml'
    config = tomllib.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    key = config.get('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not key:
        raise SystemExit('Your existing API key configuration was not found.')
    gateway = Gateway(key, config.get('OPENAI_MODEL') or os.getenv('OPENAI_MODEL', 'gpt-5'),
                      config.get('OPENAI_REASONING_EFFORT', os.getenv('OPENAI_REASONING_EFFORT', 'medium')))
    results = []
    for name, student, check in CASES:
        a = fresh(bundle)
        a['initial'] = student
        if name == 'accumulated_understanding':
            a['initial'] = CASES[0][1]
            record(a, 'user', a['initial'], 'discussion')
            record(a, 'assistant', 'How does inheritance fit your explanation?', 'discussion')
            record(a, 'user', 'The resistant bacteria produce more resistant descendants because resistance is heritable.', 'discussion')
            record(a, 'assistant', 'How would the fraction of resistant bacteria change?', 'discussion')
            record(a, 'user', 'The susceptible ones died off and the resistant ones reproduced so resistant ones take a much bigger fraction of the population.', 'discussion')
            record(a, 'assistant', 'What was present before treatment?', 'discussion')
        event = respond(a, student, 'discussion', gateway)
        results.append({'case': name, 'human_review_check': check, 'human_rating': None, 'attempt': a})
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
        print(name, event.get('delivered', {}).get('message', 'FAILED — see record'))


if __name__ == '__main__':
    main()
