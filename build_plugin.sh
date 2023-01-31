#!/usr/bin/env bash

set -e

pip_install() {
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

# Compile translation files
calibre-debug -c "from calibre.translations.msgfmt import main; main()" translations/*.po
