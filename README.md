# WordDumb

A calibre plugin for creating Kindle Word Wise and X-Ray file. Supports MOBI, AZW3 and KFX ebooks.

## Contribute

Please read [CONTRIBUTING](./docs/CONTRIBUTING.md).

## How to use

- Install calibre 5+

  - macOS: use [Homebrew](https://brew.sh) or download from https://calibre-ebook.com/download_osx

  ```
  $ brew install calibre
  ```

  - Linux

  ```
  $ sudo -v && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sudo sh /dev/stdin
  ```

  - Windows: https://calibre-ebook.com/download_windows64

- Install Python3

  - macOS includes Python3 since Catalina 10.15

  ```
  // optional, run this if you use older macOS
  $ brew install python
  ```

  - Ubuntu

  ```
  $ sudo apt install python3
  ```

  - Windows: https://www.python.org/downloads

    If you've installed 64-bit calibre, you should install 64-bit Python. If you have 32-bit calibre then download 32-bit Python. 'Add Python to PATH' option must be selected.

- Install WordDumb plugin

    calibre preference -> plugins -> get new plugins. Add the plugin to "The context menu for the books in the calibre library" in preferences -> "Toolbars & menus".

- Install jhowell's [KFX Input](https://www.mobileread.com/forums/showthread.php?t=291290) plugin for KFX books(optional).

- Disable X-Ray(optional)

    If you don't need X-Ray, you can disable it at calibre preference -> plugins -> search WordDumb -> click "customize plugin". It's enabled by default except on macOS. X-Ray doesn't work on macOS with library validation enabled.

- Select one book or multiple books, right click then click the WordDumb plugin menu. If your Kindle device is connected, it will send the book(if your device doesn't have it) and created files to your device. Make sure the book has **only one** supported format.

## I need about tree-fiddy

<a href="https://liberapay.com/xxyzz/donate"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a>

## License

This work is licensed under GPL version 3 or later.

Icon made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon">www.flaticon.com</a>.
