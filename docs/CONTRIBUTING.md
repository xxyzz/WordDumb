# Contributing

## Documents

- https://manual.calibre-ebook.com

- https://docs.python.org/3

- https://github.com/kovidgoyal/calibre

- https://wiki.mobileread.com/wiki/E-book_formats

- https://www.mobileread.com/forums/showthread.php?t=291290

- https://www.nltk.org

- https://redis.io/documentation

- https://redis-py.readthedocs.io/en/stable

- https://flake8.pycqa.org/en/latest

## Install dependencies

```
$ ./install_nltk.sh
```

## Debug

```
$ calibre-customize -b .
$ calibre-debug -g
```

## Build

```
$ zip -r worddumb-vx.x.x.zip *
$ zip -r worddumb-vx.x.x.zip . -i@include.lst
```

## Add more words

Get `cn-kll.en.en.klld` and `LanguageLayer.en.ASIN.kll` from your Kindle device(please read [word\_wise\_db](./word_wise_db.md)), then:

```
$ cd data
$ create_ww_db.py ./path-of-klld ./path-of-kll
```
