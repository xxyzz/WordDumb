#!/usr/bin/env python3

import json
import sqlite3


test_db = sqlite3.connect('LanguageLayer.en.B003JTHWKU.kll')
data = []
for d in test_db.execute('SELECT start, difficulty, sense_id FROM glosses'):
    data.append(d)

with open('LanguageLayer.en.B003JTHWKU.json', 'w') as f:
    json.dump(data, f, indent=2)
