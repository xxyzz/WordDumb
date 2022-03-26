# Contributing

## Debug

```
// run this script when debugging for the first time and when data/lemmas.json is changed
$ ./data/dump_lemmas.sh
$ calibre-customize -b . && calibre-debug -g
```

## Add more Word Wise lemmas

Get `kll.en.en.klld` and `LanguageLayer.en.ASIN.kll` from your Kindle device(please read [word\_wise\_db](./word_wise_db.md)), then:

```
$ cd data
$ python3 add_lemmas.py path-of-klld path-of-kll
$ cd .. && ./data/dump_lemmas.sh
```

## Create zip file

```
$ zip -r worddumb-vx.x.x.zip * -x@exclude.lst
```

## Remove FAT32 dirty bit

```
// run these commands on Linux
// use fdisk or df to find Kindle device
# fdisk -l
// run fsck
# fsck /dev/sdb1
```

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

- https://lxml.de

- https://maxbachmann.github.io/RapidFuzz

- https://pip.pypa.io/en/stable/user_guide

- https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/Wikidata_Query_Help

## Kindle firmware

- https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW

- https://github.com/NiLuJe/KindleTool

- https://github.com/AdoptOpenJDK/homebrew-openjdk

- https://github.com/java-decompiler/jd-gui

- https://wiki.mobileread.com/wiki/Kindle_Touch_Hacking#Architecture
