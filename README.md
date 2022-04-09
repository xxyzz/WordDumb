# WordDumb

A calibre plugin that generates Word Wise and X-Ray files then sends them to Kindle. Supports KFX, AZW3, AZW, MOBI and EPUB eBooks.

Languages supported by X-Ray: Català, Dansk, Deutsch, English, Español, Français, Italiano, Lietuvių, Nederlands, Norsk bokmål, Polski, Português, Română, Ελληνικά, Македонски, Русский, 中文, 日本語.

![screenshot](https://user-images.githubusercontent.com/21101839/130245435-b874f19a-7785-4093-9975-81596efc42bb.png)

## Contribute

Please read [CONTRIBUTING](./docs/CONTRIBUTING.md).

## How to use

- Install 64bit calibre

  - Arch Linux

  ```
  $ sudo pacman -Syu --needed calibre
  ```

  - Other Linux distros

  ```
  $ sudo -v && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sudo sh /dev/stdin
  ```

  - macOS: use [Homebrew](https://brew.sh) or download from https://calibre-ebook.com/download_osx

  ```
  $ brew install calibre
  ```

  - Windows: use [Chocolatey](https://chocolatey.org) or download from https://calibre-ebook.com/download_windows64

  ```
  # choco install calibre
  ```

- Install Python(pip) for X-Ray(optional if you only create Word Wise)

  - Arch Linux

  ```
  $ sudo pacman -Syu --needed python-pip
  ```

  - Debian based distro

  ```
  $ sudo apt install python3-pip
  ```

  - macOS

  ```
  $ brew install python

  // or install Command Line Tools
  $ xcode-select --install
  ```

  - Windows: use Chocolatey or download from https://www.python.org/downloads

  ```
  # choco install python
  ```

- Install WordDumb:

https://user-images.githubusercontent.com/21101839/124686751-39f3aa00-df06-11eb-9b07-8c8f98544683.mov

- Install [KFX Input](https://www.mobileread.com/forums/showthread.php?t=291290) plugin for KFX books(optional if you don't use this format).

- Set preferences

    - Enable "Fetch X-Ray people descriptions from Wikipedia or Fandom" option for nonfiction books and novels that have character pages on Wikipedia or Fandom. A quote from the book will be used if it's disabled or the page is not found.

    - Larger spaCy model has higher [Named-entity recognition](https://en.wikipedia.org/wiki/Named-entity_recognition) precision therefore improves X-Ray quality, more details at https://spacy.io/models/en

    - Enter a Fandom link to get X-Ray descriptions from Fandom, delete the link to search Wikipedia.

https://user-images.githubusercontent.com/21101839/124685798-90f87f80-df04-11eb-8eb6-dee012de6cab.mov

- Connect Kindle to calibre, select one book or multiple books then click the plugin icon or menu.

https://user-images.githubusercontent.com/21101839/124686791-4d067a00-df06-11eb-93c6-0dea4ee60e04.mov

- Don't add soft hyphens, it will cause the plugin to produce mediocre Word Wise and X-Ray files.

- This plugin requires access to https://files.pythonhosted.org (download X-Ray dependencies), https://raw.githubusercontent.com (download spaCy model), and https://wikipedia.org (X-Ray descriptions). These domains might be blocked in some countries([Censorship of Wikipedia](https://en.wikipedia.org/wiki/Censorship_of_Wikipedia), [Censorship of GitHub](https://en.wikipedia.org/wiki/Censorship_of_GitHub)).

- [Display Word Wise in other languages](./klld)

- For Android users:

  Currently, only KFX is supported.

  - Install Android platform tools

    - Arch Linux

    ```
    $ sudo pacman -Syu --needed android-tools
    ```

    - Debian

    ```
    $ sudo apt install android-tools-adb
    ```

    - macOS

    ```
    $ brew install android-platform-tools
    ```

    - Windows: Download from https://developer.android.com/studio/releases/platform-tools

  - Enable USB debugging, and Rooted debugging(only send Word Wise file requires this option). For more information, please read [Android Debug Bridge user guide](https://developer.android.com/studio/command-line/adb#Enabling).

  - Allow USB debugging

  - Disable USB debugging when the job is done

## I need about tree-fiddy

<a href="https://liberapay.com/xxyzz/donate"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a>

## License

This work is licensed under GPL version 3 or later.

Icon made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon">www.flaticon.com</a>.
