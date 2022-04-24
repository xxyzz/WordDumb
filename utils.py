#!/usr/bin/env python3

import json
import pickle
import zipfile
import subprocess
import platform


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


def run_subprocess(args):
    if platform.system() == "Windows":
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        return subprocess.run(args, check=True, capture_output=True, text=True)


def homebrew_mac_bin_path(package):
    # stupid macOS loses PATH when calibre is not launched in terminal
    if platform.machine() == "arm64":
        return f"/opt/homebrew/bin/{package}"
    else:
        return f"/usr/local/bin/{package}"
