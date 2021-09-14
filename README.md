# WordDumb

A calibre plugin that generates Word Wise and X-Ray files then sends them to Kindle. Supports KFX, AZW3 and MOBI eBooks.

Languages X-Ray supports: Català, Dansk, Deutsch, English, Español, Français, Italiano, Lietuvių, Nederlands, Norsk bokmål, Polski, Português, Română, Ελληνικά, Македонски, Русский, 中文, 日本語.

X-Ray doesn't support macOS, because macOS prohibits calibre from loading unsigned library.

![screenshot](https://user-images.githubusercontent.com/21101839/130245435-b874f19a-7785-4093-9975-81596efc42bb.png)

## Contribute

Please read [CONTRIBUTING](./docs/CONTRIBUTING.md).

## How to use

- Install calibre

  - Arch Linux

  ```
  # pacman -Syu --needed calibre
  ```

  - Other Linux distros

  ```
  $ sudo -v && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sudo sh /dev/stdin
  ```

  - macOS: use [Homebrew](https://brew.sh) or download from https://calibre-ebook.com/download_osx

  ```
  $ brew install calibre
  ```

  - Windows: install 64bit calibre with [Chocolatey](https://chocolatey.org) or download from https://calibre-ebook.com/download_windows64

  ```
  $ choco install calibre
  ```

- Install Python(pip) for X-Ray

  - Arch Linux

    pip module is included in python.

  - Debian or Ubuntu based distro

  ```
  $ sudo apt install python3-pip
  ```

  - Windows: use Chocolatey or download from https://www.python.org/downloads

  ```
  $ choco install python
  ```

- Install WordDumb:

https://user-images.githubusercontent.com/21101839/124686751-39f3aa00-df06-11eb-9b07-8c8f98544683.mov

- Install [KFX Input](https://www.mobileread.com/forums/showthread.php?t=291290) plugin for KFX books(optional).

- Set preferences

    - Enable "search people" option for nonfiction books and novels that have character pages on Wikipedia to add people descriptions in X-Ray.
    
    - Larger spaCy model has higher [NER](https://en.wikipedia.org/wiki/Named-entity_recognition) precision therefore improves X-Ray quality, more details at https://spacy.io/models/en

https://user-images.githubusercontent.com/21101839/124685798-90f87f80-df04-11eb-8eb6-dee012de6cab.mov

- Connect Kindle to calibre, select one book or multiple books then click the plugin icon or menu.

https://user-images.githubusercontent.com/21101839/124686791-4d067a00-df06-11eb-93c6-0dea4ee60e04.mov

- Don't add soft hyphens, it will cause the plugin to produce mediocre Word Wise and X-Ray files.

- This plugin requires access to https://files.pythonhosted.org (download dependencies) and https://raw.githubusercontent.com (download spaCy model) at first run, and https://wikipedia.org every time if X-Ray is enabled. These domains might be blocked in some countries([Censorship of Wikipedia](https://en.wikipedia.org/wiki/Censorship_of_Wikipedia), [Censorship of GitHub](https://en.wikipedia.org/wiki/Censorship_of_GitHub)).

- [Display Word Wise in other languages](./klld)

## I need about tree-fiddy

<a href="https://liberapay.com/xxyzz/donate"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a>

## License

This work is licensed under GPL version 3 or later.

Icon made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon">www.flaticon.com</a>.
