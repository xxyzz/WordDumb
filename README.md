# WordDumb

A calibre plugin for creating Kindle Word Wise file.

## Contribute

Please read [CONTRIBUTING](./docs/CONTRIBUTING.md)

## How to use

Install calibre **5+** and jhowell's [KFX Input](https://www.mobileread.com/forums/showthread.php?t=291290) plugin for KFX books. Then install WordDumb plugin from calibre "Preference" -> "Plugins" -> "Get new plugins". Add the plugin to "The context menu for the books in the calibre library" in "Preferences" -> "Toolbars & menus".

Right click a **MOBI**, **AZW3** or **KFX** format book then click the plugin menu, it will start generating Word Wise file in a few minutes that depends on the book size and your computer speed.

If your Kindle device is connected, it will send the book(if your device doesn't have it) and the Word Wise file to your device. Make sure the book has **only one** supported format.

If your device doesn't have dictionary file at `/system/kll/`, you need to connect it to Wi-Fi and wait for it to download `kll.en.en.klld` file(19.5 MB).

## License

This work is licensed under GPL version 3 or later.

Icon made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon">www.flaticon.com</a>

[NLTK](https://github.com/nltk/nltk) source code is distributed under the Apache 2.0 License.

[WordNet License](https://wordnet.princeton.edu/license-and-commercial-use).
