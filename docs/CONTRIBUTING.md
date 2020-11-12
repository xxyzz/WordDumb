# Contributing

## Documents

- https://manual.calibre-ebook.com

- https://docs.python.org/3

- https://github.com/kovidgoyal/calibre

- https://wiki.mobileread.com/wiki/E-book_formats

## Debug

```
$ calibre-customize -b .
$ calibre-debug -g
```

## Build

```
$ zip -r worddumb-vx.x.x.zip *
```

## Add more words

Get `cn-kll.en.en.klld` and `LanguageLayer.en.ASIN.kll` from your Kindle device, then:

```
$ create_ww_sql.py ./path-of-klld ./path-of-kll
```

## TODO

- Add GitHub action to test the code

- Improve performance, especially matching lemmas part

- Lemmatize words

- Supports kfx
