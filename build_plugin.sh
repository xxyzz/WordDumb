#!/usr/bin/env bash

pip_install() {
    if [[ $(uname -v) == *"Ubuntu"* && -n "$CI" ]]; then
        python -m pip install --no-cache-dir -U pip
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

# Download the latest Kindle lemmas dump file
wget -nv -O - https://api.github.com/repos/xxyzz/Proficiency/releases/latest \
    | grep "/kindle_lemmas_dump_v*" \
    | cut -d : -f 2,3 \
    | tr -d '" ' \
    | wget -P data -nv -i -

cp Proficiency/en/dump_kindle_lemmas.py ./
cp Proficiency/tst.py ./libs/
cp Proficiency/dump_wiktionary.py ./

# Compile translation files
calibre-debug -c "from calibre.translations.msgfmt import main; main()" translations/*.po
