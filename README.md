# WordDumb

A calibre plugin that generates Word Wise and X-Ray files then sends them to Kindle. Supports KFX, AZW3 and MOBI eBooks.

Languages X-Ray supports: Català, Dansk, Deutsch, English, Español, Français, Italiano, Lietuvių, Nederlands, Norsk bokmål, Polski, Português, Română, Ελληνικά, Русский, 中文, 日本語.

X-Ray doesn't support macOS, because macOS prohibits calibre from loading unsigned library.

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
  # pacman -Syu --needed calibre
  ```

  - Other Linux distros

  ```
  $ sudo -v && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sudo sh /dev/stdin
  ```

  - Windows: https://calibre-ebook.com/download_windows64

- Install Python 3(pip3)

  - macOS

  ```
  // recommended
  $ brew install python

  // or install outdated pip3 from Apple's developer tools
  $ xcode-select --install
  ```

  - Arch Linux

    pip module is installed in the last step.

  - Ubuntu

  ```
  $ sudo apt update
  $ sudo apt install python3-pip
  ```

  - Windows: https://www.python.org/downloads

    If you've installed 64-bit calibre, you should install 64-bit Python. If you have 32-bit calibre then download 32-bit Python. Select "Install Now".

- Install WordDumb:

https://user-images.githubusercontent.com/21101839/124686751-39f3aa00-df06-11eb-9b07-8c8f98544683.mov

- Install [KFX Input](https://www.mobileread.com/forums/showthread.php?t=291290) plugin for KFX books(optional).

- Set preferences

    - Enable "search people" option for nonfiction books and novels that have character pages on Wikipedia to add people descriptions in X-Ray.
    
    - Larger spaCy model has higher [NER](https://en.wikipedia.org/wiki/Named-entity_recognition) precision, more details at https://spacy.io/models/en

https://user-images.githubusercontent.com/21101839/124685798-90f87f80-df04-11eb-8eb6-dee012de6cab.mov

- Connect Kindle to calibre, select one book or multiple books then click the plugin icon or menu.

https://user-images.githubusercontent.com/21101839/124686791-4d067a00-df06-11eb-93c6-0dea4ee60e04.mov

- Never add ASIN to your book, that will cause Kindle to replace Word Wise and X-Ray files.

- Don't add soft hyphens, it will cause the plugin to produce a mediocre X-Ray file.

- This plugin requires access to https://files.pythonhosted.org (download dependencies) and https://raw.githubusercontent.com (download NLTK and spaCy model) at first run, and https://wikipedia.org every time if X-Ray is enabled. These domains might be blocked in some countries.

## I need about tree-fiddy

<a href="https://liberapay.com/xxyzz/donate"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a>

## License

This work is licensed under GPL version 3 or later.

Icon made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon">www.flaticon.com</a>.
