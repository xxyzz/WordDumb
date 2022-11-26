# WordDumb

A calibre plugin that generates Kindle Word Wise and X-Ray files and EPUB footnotes then send them to e-reader. Supports KFX, AZW3, AZW, MOBI and EPUB eBooks.

Supported languages: Bokmål, Català, Dansk, Deutsch, English, Español, Français, Hrvatski, Italiano, Lietuvių, Nederlands, Polski, Português, Română, Suomi, Svenska, Ελληνικά, Македонски, Русский, Українська, 中文, 日本語, 한국어.

Test plugin will be uploaded to [GitHub Actions Artifacts](https://github.com/xxyzz/WordDumb/actions/workflows/tests.yml) at each git push automatically.

![screenshot](https://user-images.githubusercontent.com/21101839/202722815-357c8cfe-703c-4e58-843f-deaf694f6fea.png)

## Contribute

Please read [CONTRIBUTING](./docs/CONTRIBUTING.md).

## How to use

- Install calibre 6

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

- Install 64bit Python and pip

  - Arch Linux

  ```
  $ sudo pacman -Syu --needed python-pip
  ```

  - Debian

  ```
  $ sudo apt install python3-pip
  ```

  - macOS

  ```
  $ brew install python

  // or install Command Line Tools, not recommended
  $ xcode-select --install
  ```

  - Windows: use Chocolatey or download from https://www.python.org/downloads

  ```
  # choco install python
  ```

- Install WordDumb:

https://user-images.githubusercontent.com/21101839/202723023-082a6147-6425-43be-9869-43293c90a306.mov

- Install [KFX Input](https://www.mobileread.com/forums/showthread.php?t=291290) plugin for KFX books(optional if you don't use this format). The installation steps are similar to the above video.

- Set preferences

    - Click "Preferred format order" button then drag your preferred format to the top.

    - Customize Word Wise requires Kindle or Android(use adb) device connected for the first time use. Lemmas have difficulty of 5 will only display when the Word Wise slider on the far right.

    - Enable "Fetch X-Ray people descriptions from Wikipedia or Fandom" option for nonfiction books and novels that have character pages on Wikipedia or Fandom. A quote from the book will be used if it's disabled or the page is not found.

    - Enable "Run spaCy with GPU" option if your machine has [CUDA](https://developer.nvidia.com/cuda-downloads). GPU will be used when creating X-Ray file if spaCy has transformer model for the book language with ner component.

    - Larger spaCy model has higher [Named-entity recognition](https://en.wikipedia.org/wiki/Named-entity_recognition) precision therefore improves X-Ray quality, more details at https://spacy.io/models/en

    - Enter a Fandom link to get X-Ray descriptions from Fandom, delete the link to search Wikipedia. This option also supports Fandom Wiki that has multiple languages by appending the language code to URL, for example https://lotr.fandom.com/fr.

    - Enable "Add locator map to EPUB footnotes" if your e-reader supports image in footnotes.

https://user-images.githubusercontent.com/21101839/202723256-36b96e53-fbf0-4a38-ba35-27fe331d7f1d.mov

- Customize X-Ray

  Add X-Ray entities that can't be recognized by spaCy model to improve NER accuracy for each selected book. It can also be used to remove entities by checking the "Omit" checkbox.

- Import Word Wise from Anki Deck Package, CSV file or Kindle Vocabulary Builder

  Words inside the imported file will be enabled.

  - Select the "Include scheduling information" option when exporting the .apkg file from Anki so the card schedule state can be used as Word Wise difficulty.

  - The CSV file should have at least one column of words and an optional column of difficulty value.

  - Kindle Vocabulary Builder database path: `system/vocabulary/vocab.db`

- Connect your e-reader, select one book or multiple books then click the plugin icon or menu. You can also run the plugin in terminal:

  ```
  $ calibre-debug -r WordDumb -- -h
  ```

https://user-images.githubusercontent.com/21101839/202723395-c84ed588-5fba-43f7-880c-70667efc9fca.mov

- Don't add soft hyphens to AZW3, AZW and MOBI books, it will cause the plugin to produce mediocre Word Wise and X-Ray files.

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

  - Enable USB debugging, and Rooted debugging(only send Word Wise file requires this option). For more information, please read [Android Debug Bridge user guide](https://developer.android.com/studio/command-line/adb#Enabling). Rooted debugging is only available on [userdebug and eng build variant](https://source.android.com/docs/setup/create/new-device#build-variants) ROMs, some custom ROMs like [LineageOS](https://lineageos.org) have this option.

  - Allow USB debugging

  - Disable USB debugging when the job is done

## I need about tree-fiddy

<a href="https://liberapay.com/xxyzz/donate"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a>

## License

This work is licensed under GPL version 3 or later.

Icon made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon">www.flaticon.com</a>.
