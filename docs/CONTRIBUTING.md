# Contributing

## Documents

- https://manual.calibre-ebook.com

- https://docs.python.org

- https://github.com/kovidgoyal/calibre

- https://wiki.mobileread.com/wiki/E-book_formats

- https://wiki.mobileread.com/wiki/PDB

- https://www.mobileread.com/forums/showthread.php?t=291290

- https://www.nltk.org

- https://flake8.pycqa.org/en/latest

- https://docs.github.com/en/free-pro-team@latest/actions/reference/workflow-syntax-for-github-actions

- https://github.com/actions/virtual-environments

- https://www.crummy.com/software/BeautifulSoup/bs4/doc

- https://www.mediawiki.org/wiki/API:Query

- https://www.mediawiki.org/wiki/API:Etiquette

- https://spacy.io

- https://docs.python-requests.org

## Debug

```
$ calibre-customize -b . && calibre-debug -g
```

## Build

```
$ zip -r worddumb-vx.x.x.zip * -x@exclude.lst
```

## Add more words

Get `kll.en.en.klld` and `LanguageLayer.en.ASIN.kll` from your Kindle device(please read [word\_wise\_db](./word_wise_db.md)), then:

```
$ cd data
$ add_lemmas.py ./path-of-klld ./path-of-kll
```

## Kindle firmware

- https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW

- https://github.com/NiLuJe/KindleTool

- https://github.com/AdoptOpenJDK/homebrew-openjdk

- https://github.com/java-decompiler/jd-gui

- https://wiki.mobileread.com/wiki/Kindle_Touch_Hacking#Architecture
