Usage
=====

Set preferences
---------------

- Click "Preferred format order" button then drag your preferred format to the top.

- The "Use POS type to find Word Wise definition" option should be disabled for languages that spaCy's lemmatizer doesn't work well, like Korean and stressed Russian.

- Enable "Fetch X-Ray people descriptions from Wikipedia or other MediaWiki server" option for nonfiction books and novels that have character pages on Wikipedia or any other MediaWiki server. A quote from the book will be used if it's disabled or the page is not found.

- Enable "Run spaCy with GPU" option if your machine has `CUDA <https://developer.nvidia.com/cuda-toolkit-archive>`_. GPU will be used when creating X-Ray file if spaCy has transformer model for the book language with ner component.

- Larger spaCy model has higher `Named-entity recognition <https://en.wikipedia.org/wiki/Named-entity_recognition>`_ precision therefore improves X-Ray quality, more details at https://spacy.io/models/en

- Enter a `MediaWiki Action API <https://www.mediawiki.org/wiki/API:Main_page>`_ link to get X-Ray descriptions from a MediaWiki server, delete the link to search Wikipedia. Most MediaWiki Action API endpoint is ``https://wiki.domain/w/api.php`` but some servers don't have the ``/w`` part, you can check the API URL in a browser.

- Enable "Add locator map to EPUB footnotes" if your e-reader supports image in footnotes.

.. raw:: html

   <video controls width="100%" src="https://user-images.githubusercontent.com/21101839/202723256-36b96e53-fbf0-4a38-ba35-27fe331d7f1d.mov"></video>

Customize Word Wise
-------------------

- The default gloss language is English. If you want to use another gloss language, choose the language then click the "OK" button and wait for the download job to finish.

- Lemmas have difficulty of 5 will only display when the Kindle Word Wise slider on the far right.

.. attention::
   If the "Use Wiktionary definition" option is enabled, you have to change Word Wise language to **Chinese** on your Kindle device to view the correct gloss data, and the original Chinese Word Wise database file on Kindle will be replaced.

Customize X-Ray
---------------

Add X-Ray entities that can't be recognized by spaCy model to improve NER accuracy for each selected book. It can also be used to remove entities by checking the "Omit" checkbox.

Create files
------------

Connect your e-reader, select one book or multiple books then click the plugin icon or menu. Then the selected books and the generated files will be sent to your e-reader.

.. raw:: html

   <video controls width="100%" src="https://user-images.githubusercontent.com/21101839/202723395-c84ed588-5fba-43f7-880c-70667efc9fca.mov"></video>

.. attention::
   - Click calibre's "Send to device" menu won't send created files to e-reader. Always use the WordDumb plugin to send books to your device.

   - Word Wise file created from this plugin is not supported for Kindle devices login with amazon.cn account.

.. tip::
   If you forget to connect your device before generating files, connect your device then click the plugin icon or menu again and the created files will be moved to your e-reader.

You can also run the plugin in terminal:

.. code-block:: console

   $ calibre-debug -r WordDumb -- -h

.. note::
   - Don't add soft hyphens to AZW3, AZW and MOBI books, it will cause the plugin to produce mediocre Word Wise and X-Ray files.

   - WordDumb adds random ASIN metadata to Kindle books if the book don't have this data.

   - Non-English Kindle book's language metadata will be changed to English when creating Word Wise file, the original book's metadata in calibre library won't be changed.

   - English and Chinese Kindle Word Wise definitions require a database file downloaded from Amazon, use Wiktionary definitions if your device can't download this file.

Import Word Wise
----------------

Update difficulty levels from Anki Deck Package, CSV file or Kindle Vocabulary Builder. Words inside the imported file will be enabled.

- Select the "Include scheduling information" option when exporting the .apkg file from Anki so the card schedule state can be used as Word Wise difficulty.

- The CSV file should have at least one column of words and an optional column of difficulty value.

- Kindle Vocabulary Builder database path: `system/vocabulary/vocab.db`

Setting correct KOReader settings
---------------------------------

By default KOReader shows footnotes on the page, which takes up too much space when WordWise is enabled.

To change this, open the menu (click somewhere at the top area), then in the upper menu choose the "reader with lines" symbol (second from left).
Here, select "Style tweaks" -> "In-page footnotes" and remove all checkmarks. (By default, In-Page EPUB footnotes (smaller) is checked.)

For an even better footnote experience, enable pop-up footnotes. Do this by opening the top menu again, clicking on the "gear" symbol (third from left).
Then select "Taps and gestures" -> "Links" and then check "Show footnotes in popup"

HTTP proxy
----------

HTTP proxy can be configured by setting the `http_proxy`, and `https_proxy` environment variables:

.. code-block:: console

    $ export HTTP_PROXY="http://host:port"
    $ export HTTPS_PROXY="http://host:port"

Notice the value of `HTTPS_PROXY` starts with `http://`. For more information, check out `requests documentation <https://requests.readthedocs.io/en/latest/user/advanced/#proxies>`_ and `calibre manual <https://manual.calibre-ebook.com/faq.html#how-do-i-get-calibre-to-use-my-http-proxy>`_.
