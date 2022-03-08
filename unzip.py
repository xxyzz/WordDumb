#!/usr/bin/env python3

import json
import pickle
import zipfile


def load_json_or_pickle(plugin_path, filepath):
    with zipfile.ZipFile(plugin_path) as zf:
        with zf.open(filepath) as f:
            if filepath.endswith('.json'):
                return json.load(f)
            else:
                return pickle.load(f)
