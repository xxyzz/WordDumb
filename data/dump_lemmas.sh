#!/usr/bin/env bash

pip_install() {
    pip install flashtext lemminflect
    mkdir libs
    cp -R .venv/lib/python*/site-packages/flashtext* libs
}

if [[ "$OSTYPE" != "msys" ]]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip_install
    python3 data/dump_lemmas.py
    deactivate
else
    py -m venv .venv
    .venv/Scripts/activate
    pip_install
    py data/dump_lemmas.py
    deactivate
fi
