#!/usr/bin/env bash

pip_install() {
    if [[ $(uname -v) == *"Ubuntu"* ]]; then
        python -m pip install -U wheel
    fi
    python -m pip install -U git+https://github.com/vi3k6i5/flashtext#egg=flashtext lemminflect
    python data/dump_lemmas.py
    deactivate
    mkdir libs
}

if [[ "$OSTYPE" != "msys" ]]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip_install
    cp -R .venv/lib/python*/site-packages/flashtext libs
else
    py -m venv .venv
    source .venv/Scripts/activate
    pip_install
    cp -R .venv/lib/site-packages/flashtext libs
fi
