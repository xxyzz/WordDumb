# WordDumb

A calibre plugin for creating Kindle Word Wise file. Supports MOBI, AZW3 and KFX ebooks.

## Contribute

Please read [CONTRIBUTING](./docs/CONTRIBUTING.md).

## How to use

- Install calibre 5+

```
# macOS
$ brew install calibre

# Linux
$ sudo -v && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sudo sh /dev/stdin
```

- Install redis 5+

```
# macOS
$ brew install redis

# Ubuntu
$ sudo apt install redis
$ sudo systemctl stop redis
$ sudo systemctl disable redis
```

- Install jhowell's [KFX Input](https://www.mobileread.com/forums/showthread.php?t=291290) plugin for KFX books.

- Install WordDumb plugin

    From calibre's "Preference" -> "Plugins" -> "Get new plugins". Add the plugin to "The context menu for the books in the calibre library" in "Preferences" -> "Toolbars & menus".

- Select one book or multiple books, right click then click the WordDumb plugin menu. If your Kindle device is connected, it will send the book(if your device doesn't have it) and the Word Wise file to your device. Make sure the book has **only one** supported format.

## Donate

<a href="https://liberapay.com/xxyzz/donate"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a>

## License

This work is licensed under GPL version 3 or later.

Icon made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon">www.flaticon.com</a>.

[NLTK license](https://github.com/nltk/nltk/blob/develop/LICENSE.txt).

[WordNet license](https://wordnet.princeton.edu/license-and-commercial-use).

[redis-py license](https://github.com/andymccurdy/redis-py/blob/master/LICENSE).
