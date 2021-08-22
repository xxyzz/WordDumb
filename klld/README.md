# Create klld in other languages

- Download Kindle default dictionary:

  - *Progressive English-Japanese Dictionary(プログレッシブ英和中辞典)*

  - *Oxford English - German Dictionary*

  - *Oxford English - Spanish Dictionary*

  - *Oxford Hachette English - French Dictionary*

  - *Oxford Paravia English - Italian Dictionary*

- Install or build [mobitool](https://github.com/bfabiszewski/libmobi)

```
$ brew install libmobi
```

- Dump dictionary rawml text record

```
$ mobitool -d -o output_folder -P device_serival_number path_of_dict_azw
```

- Create klld

```
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install lxml
$ python create_klld.py path_of_en_klld path_of_dict_rawml dict_lang
$ deactivate
```

- Rename klld file to `kll.en.zh.klld`

- Move klld to Kindle folder `/system/kll/`

- Select "Chinese(China)" in the Kindle Word Wise language settings
