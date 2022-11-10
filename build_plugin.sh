#!/usr/bin/env bash

set -e

pip_install() {
    if [[ $(uname -v) == *"Ubuntu"* && -n "$CI" ]]; then
        python -m pip install -U pip
    fi
    python -m pip install -t libs git+https://github.com/vi3k6i5/flashtext@b316c7e9e54b6b4d078462b302a83db85f884a94
    deactivate
}

if [[ "$OSTYPE" != "msys" ]]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip_install
else
    py -m venv .venv
    source .venv/Scripts/activate
    pip_install
fi

# Could use /releases/latest/download/file_name at here
wget -P data -nv "https://github.com/xxyzz/Proficiency/releases/download/v0.3.1/kindle_lemmas_dump_v0"

cp Proficiency/en/dump_kindle_lemmas.py ./
cp Proficiency/tst.py ./libs/
cp Proficiency/dump_wiktionary.py ./

# Compile translation files
calibre-debug -c "from calibre.translations.msgfmt import main; main()" translations/*.po
