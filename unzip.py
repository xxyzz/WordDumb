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


def load_wiki_cache(cache_path):
    if cache_path.exists():
        with cache_path.open() as f:
            return json.load(f)
    else:
        return {}


def save_wiki_cache(cache_path, cache_dic, lang):
    if not cache_path.exists():
        if not cache_path.parent.exists():
            cache_path.parent.mkdir()
        cache_path.touch()
    with cache_path.open('w') as f:
        json.dump(cache_dic, f)
