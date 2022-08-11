#!/usr/bin/env bash

pip_install() {
    if [[ $(uname -v) == *"Ubuntu"* && -n "$CI" ]]; then
        python -m pip install --no-cache-dir -U pip
    fi
    python -m pip install --no-cache-dir --disable-pip-version-check -U git+https://github.com/vi3k6i5/flashtext#egg=flashtext lemminflect
    python data/dump_lemmas.py
    deactivate
    mkdir -p libs
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

calibre-debug -c "from calibre.translations.msgfmt import main; main()" translations/*.po
