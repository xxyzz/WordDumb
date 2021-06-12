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

- Install Python3(pip3)

  - macOS

  ```
  // recommended
  $ brew install python

  // or install outdated pip3 from Apple's developer tools
  $ xcode-select --install
  ```

  - Arch Linux

  ```
  # pacman -S python
  ```

  - Ubuntu

  ```
  $ sudo apt update
  $ sudo apt install python3-pip
  ```

  - Windows: https://www.python.org/downloads

    If you've installed 64-bit calibre, you should install 64-bit Python. If you have 32-bit calibre then download 32-bit Python. Select "Install Now".

- Install WordDumb plugin:

https://user-images.githubusercontent.com/21101839/120099000-b1962280-c16b-11eb-87e7-b2e1d6e02f9f.mov

- Install jhowell's [KFX Input](https://www.mobileread.com/forums/showthread.php?t=291290) plugin for KFX books(optional), the installtion method is the same as the above video.

- Select one book or multiple books, right click then click the WordDumb plugin menu. If your Kindle is connected, WordDumb will send the book and created files to your device.

https://user-images.githubusercontent.com/21101839/120099125-629cbd00-c16c-11eb-8c18-b0059ec64c6a.mov

- Disable X-Ray(optional)

    The X-Ray feature doesn't support macOS, because macOS prohibits calibre from loading unsigned numpy library.

https://user-images.githubusercontent.com/21101839/120099114-4ef15680-c16c-11eb-9192-1e443e01c5e6.mov

- Never add ASIN to your book, that will cause Kindle to replace Word Wise and X-Ray files.

- This plugin requires access to https://files.pythonhosted.org (download dependencies) and https://raw.githubusercontent.com (download NLTK data) at first run, and https://en.wikipedia.org every time if X-Ray is enabled. These domains might be blocked in some countries.

## I need about tree-fiddy

<a href="https://liberapay.com/xxyzz/donate"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a>

## License

This work is licensed under GPL version 3 or later.

Icon made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon">www.flaticon.com</a>.
