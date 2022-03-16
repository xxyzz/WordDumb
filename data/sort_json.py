#!/usr/bin/env python3

import json
from pathlib import Path

for path in Path('.').glob('*.json'):
    with open(path) as f:
        d = json.load(f)

    with open(path, 'w') as f:
        json.dump(d, f, indent=2, sort_keys=True, ensure_ascii=False)
