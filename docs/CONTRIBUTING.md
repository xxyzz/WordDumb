# Contributing

## Debug

Run the `data/dump_lemmas.sh` Bash script when debugging for the first time and when `data/lemmas.json` is changed.

```
$ ./data/dump_lemmas.sh
$ calibre-customize -b . && calibre-debug -g
```

## Add translations

You can use [Poedit](https://poedit.net)'s "New From POT/PO File..." option then select any .po file in the `translations` folder to create new translation file.

Run this command to compile .mo files, you don't need to do this if you're using Poedit.

```bash
calibre-debug -c "from calibre.translations.msgfmt import main; main()" translations/*.po
```

## Create zip file

```bash
zip -r worddumb-vx.x.x.zip * -x@exclude.lst
```

## Add more Word Wise lemmas

Get `kll.en.en.klld` and `LanguageLayer.en.ASIN.kll` from your Kindle device(please read [word\_wise\_db](./word_wise_db.md)), then:

```bash
cd data
python3 add_lemmas.py path-of-klld path-of-kll
cd .. && ./data/dump_lemmas.sh
```

## Remove FAT32 dirty bit

```
// run these commands on Linux
// use fdisk or df to find Kindle device
# fdisk -l
# umount /dev/sdb1
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

- https://en.wikibooks.org/wiki/SPARQL

## Kindle firmware

- https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW

- https://github.com/NiLuJe/KindleTool

- https://adoptium.net

- https://github.com/java-decompiler/jd-gui

- https://wiki.mobileread.com/wiki/Kindle_Touch_Hacking#Architecture
