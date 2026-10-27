"""Private, stdlib-only search process; invoked by native_synthesis in sandbox."""
import argparse
import json
from fractions import Fraction
from pathlib import Path

# Executed as a file with -E -S -B: only these two reviewed source files and
# the Python runtime are mounted, not the caller's repository or environment.
from contract_synthesis import synthesize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('problem', type=Path)
    args = parser.parse_args()
    with args.problem.open('rb') as stream:
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError('Search input byte budget exceeded')
    doc = json.loads(data)
    result = synthesize(doc['variables'], doc['constants'],
                        [(case['inputs'], case['output']) for case in doc['examples']],
                        max_nodes=doc['max_nodes'], max_candidates=doc['max_candidates'])
    def encode(value):
        if type(value) is Fraction:
            return str(value)
        raise TypeError('Unexpected search result')
    print(json.dumps({'format': 'omega-scalar-search-1', 'candidate': result}, default=encode))


if __name__ == '__main__':
    main()
