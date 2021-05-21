# WordDumb

A calibre plugin that generates Word Wise and X-Ray files then sends them to Kindle. Supports KFX, AZW3 and MOBI eBooks.

## Contribute

Please read [CONTRIBUTING](./docs/CONTRIBUTING.md).

## How to use

- Install calibre

  - macOS: use [Homebrew](https://brew.sh) or download from https://calibre-ebook.com/download_osx

  ```
  $ brew install calibre
  ```

  - Arch Linux

  ```
  # pacman -S calibre
  ```

  - Other Linux

  ```
  $ sudo -v && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sudo sh /dev/stdin
  ```

  - Windows: https://calibre-ebook.com/download_windows64

- Install pip3(Python3)

  - macOS

    - install Python via Homebrew(recommended)

    ```
    $ brew install python
    ```

    - or update the built-in pip

    ```
    $ xcode-select --install
    $ sudo -H python3 -m pip install -U pip
    ```

  - Arch Linux

  ```
  # pacman -S python-pip
  ```

  - Ubuntu

  ```
  # apt install python3-pip
  ```

  - Windows: https://www.python.org/downloads

    If you've installed 64-bit calibre, you should install 64-bit Python. If you have 32-bit calibre then download 32-bit Python. 'Add Python to PATH' option must be selected.

- Install WordDumb plugin: [Video tutorial](https://upload.wikimedia.org/wikipedia/commons/transcoded/7/7f/Install_calibre_plugin.webm/Install_calibre_plugin.webm.1440p.vp9.webm)

    calibre preference -> plugins -> get new plugins. Add the plugin to "The context menu for the books in the calibre library" in preferences -> "Toolbars & menus".

- Install jhowell's [KFX Input](https://www.mobileread.com/forums/showthread.php?t=291290) plugin for KFX books(optional).

- Disable X-Ray(optional): [Video tutorial](https://upload.wikimedia.org/wikipedia/commons/transcoded/7/79/Configure_calibre_plugin.webm/Configure_calibre_plugin.webm.1440p.vp9.webm)

    If you don't need X-Ray, you can disable it at calibre preference -> plugins -> search WordDumb -> click "customize plugin". It's enabled by default except on macOS. X-Ray doesn't work on macOS with library validation enabled.

- Select one book or multiple books, right click then click the WordDumb plugin menu. If your Kindle device is connected, it will send the book(if your device doesn't have it) and created files to your device. [Video tutorial](https://upload.wikimedia.org/wikipedia/commons/transcoded/a/ae/Usage_tutorial_of_WordDumb.webm/Usage_tutorial_of_WordDumb.webm.1440p.vp9.webm)

## How to report bugs

Run calibre in debug mode:

```
$ calibre-debug -g

// for macOS users don't have calibre-debug in their PATH:
$ /Applications/calibre.app/Contents/MacOS/calibre-debug -g
```

then use the plugin as usual and copy the output.

## I need about tree-fiddy

<a href="https://liberapay.com/xxyzz/donate"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a>

## License

This work is licensed under GPL version 3 or later.

Icon made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon">www.flaticon.com</a>.
