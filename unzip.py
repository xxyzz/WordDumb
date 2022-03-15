#!/usr/bin/env python3

import json
import pickle
import zipfile


def load_json_or_pickle(plugin_path, filepath):
    with zipfile.ZipFile(plugin_path) as zf:
        if filepath.endswith(".json"):
            path = zipfile.Path(zf, filepath)
            if path.exists():
                with path.open() as f:
                    return json.load(f)
            return None
        with zf.open(filepath) as f:
            return pickle.load(f)
