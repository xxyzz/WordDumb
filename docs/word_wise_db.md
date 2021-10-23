# kll.en.en.klld/WordWise.kll.en.en.db

Find in Kindle device at path `/system/kll/`

or install Kindle Android app and extract Word Wise file at: `/data/data/com.amazon.kindle/databases/wordwise/WordWise.kll.en.en.db`

Get the file in TWRP File Manager or ROOT your phone.

## android_metadata

| locale |
|--------|
| en_US  |

## lemmas

| id | lemma                       |
|----|-----------------------------|
|  1 | a                           |
|  2 | from a to z                 |
|  3 | from A to Z                 |
|  4 | from point a to point b     |
|  5 | from (point) A to (point) B |

## metadata

| key                | value                                          |
|--------------------|------------------------------------------------|
| maxTermLength      | 3                                              |
| termTerminatorList | ,    ;       .       "       '       !       ? |
| definitionLanguage | en                                             |
| id                 | cn-kll.en.en                                   |
| lemmaLanguage      | en                                             |
| version            | 2016-03-09                                     |
| revision           | 52                                             |
| tokenSeparator     |                                                |
| encoding           | 1                                              |

## pos_types

| id | label       |
|----|-------------|
|  0 | noun        |
|  1 | verb        |
|  2 | adjective   |
|  3 | adverb      |
|  4 | article     |
|  5 | number      |
|  6 | conjunction |
|  7 | other       |
|  8 | preposition |
|  9 | pronoun     |
| 10 | particle    |
| 11 | punctuation |

## senses

| id | display\_lemma\_id | term\_id | term\_lemma\_id | pos\_type | source\_id | sense\_number | synset\_id | corpus\_count | full\_def            | short\_def           | example\_sentence                |
|----|--------------------|----------|-----------------|-----------|------------|---------------|------------|---------------|----------------------|----------------------|----------------------------------|
|  1 |                910 |      878 |             910 |         0 |          1 |           1.0 |      34284 |             0 | YSBuYW1lIG9yIHRpdGxl | YSBuYW1lIG9yIHRpdGxl | YW4gaG9ub3JhcnkgYXBwZWxsYXRpb24= |

```
sqlite> SELECT * FROM lemmas WHERE id = 910;
id|lemma
910|appellation
sqlite> SELECT count(*) FROM lemmas;
74623
sqlite> SELECT count(*) FROM senses;
84770
// some lemmas have mutiple senses
```

```
>>> import base64
>>> base64.b64decode("YSBuYW1lIG9yIHRpdGxl")
b'a name or title'
>>> base64.b64decode("YW4gaG9ub3JhcnkgYXBwZWxsYXRpb24=")
b'an honorary appellation'
```

[Base64 - Wikipedia](https://en.wikipedia.org/wiki/Base64)

[base64 — Base16, Base32, Base64, Base85 Data Encodings — Python 3.9.0 documentation](https://docs.python.org/3/library/base64.html)

[codecs — Codec registry and base classes — Python 3.9.0 documentation](https://docs.python.org/3/library/codecs.html)

## sources

| id | label           |
|----|-----------------|
|  0 |                 |
|  1 | Merriam-Webster |
|  2 |                 |
|  3 | 现代英汉词典    |
|  4 |                 |
|  5 |                 |

# cn-kll.en.zh.klld/WordWise.kll.en.zh.db

## android_metadata

Same as en.

## lemmas

Same as en.

## metadata

| key                | value                                          |
|--------------------|------------------------------------------------|
| maxTermLength      | 3                                              |
| termTerminatorList | ,    ;       .       "       '       !       ? |
| definitionLanguage | zh                                             |
| id                 | cn-kll.en.zh                                   |
| lemmaLanguage      | en                                             |
| version            | 2016-04-07                                     |
| revision           | 52                                             |
| tokenSeparator     |                                                |
| encoding           | 1                                              |

## pos_types

Same as en.

## senses

| id | display\_lemma\_id | term\_id | term\_lemma\_id | pos\_type | source\_id | sense\_number | synset\_id | corpus\_count | full\_def                        | short\_def                       | example\_sentence |
|----|--------------------|----------|-----------------|-----------|------------|---------------|------------|---------------|----------------------------------|----------------------------------|-------------------|
|  1 |                910 |      878 |             910 |         0 |          3 |           1.0 |      34284 |             0 | 5ZCN56ew77yb56ew5Y+377yb56ew5ZG8 | 5ZCN56ew77yb56ew5Y+377yb56ew5ZG8 |                   |


```
>>> import base64
>>> base64.b64decode("5ZCN56ew77yb56ew5Y+377yb56ew5ZG8").decode("utf-8")
'名称；称号；称呼'
```

## sources

Same as en.

# LanguageLayer.en.ASIN.kll

Kindle device path: `/documents/book_name.sdr`

## metadata

| key                  | value                           |
|----------------------|---------------------------------|
| acr                  | CR!AX4P53SCH15WF68KNBX4NWWVZXKG |
| targetLanguages      | en                              |
| sidecarRevision      | 9                               |
| bookRevision         | 8d271dc3                        |
| sourceLanguage       | en                              |
| enDictionaryVersion  | 2016-09-14                      |
| enDictionaryRevision | 57                              |
| enDictionaryId       | kll.en.en                       |
| sidecarFormat        | 1.0                             |

acr: Palm DB name, first 32 bytes of MOBI file. `asset_id` in KFX metadata.

bookRevision: Unique-ID of MOBI header.

## glosses

| start | end | difficulty | sense\_id | low\_confidence |
|-------|-----|------------|-----------|-----------------|
|  2625 |     |          1 |    113403 |               0 |
|  2644 |     |          1 |    114411 |               0 |
|  2682 |     |          2 |    106210 |               0 |
|  2763 |     |          2 |     33584 |               0 |
|  2812 |     |          2 |     10189 |               0 |

difficulty = 1 -> Fewer Hints

difficulty = 5 -> More Hints

start: bytes offsets for MOBI and AZW3, Unicode character offsets for KFX.
