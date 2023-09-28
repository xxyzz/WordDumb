Development
===========

Clone project
-------------

.. code-block:: console

   $ git clone https://github.com/xxyzz/WordDumb.git

Or use SSH:

.. code-block:: console

   $ git clone git@github.com:xxyzz/WordDumb.git

Debug
-----

.. code-block:: console

   $ calibre-customize -b . && calibre-debug -g

Add translations
----------------

You can use `Poedit <https://poedit.net>`_'s "New From POT/PO File..." option then select any .po file in the `translations` folder to create new translation file.

Run this command to compile .mo files, you don't need to do this if you're using Poedit.

.. code-block:: console

   $ calibre-debug -c "from calibre.translations.msgfmt import main; main()" translations/*.po

.. note::
   Poedit's "Update from source code" feature would comment the language name translations then move them to the end of the file. You should revert this change when commit.

Add difficulty data to more languages
-------------------------------------

Check out `Proficiency <https://github.com/xxyzz/Proficiency>`_.

Create zip file
---------------

.. code-block:: console

   $ zip -r worddumb-vx.x.x.zip * -x@exclude.lst

Library and API documents
-------------------------

- https://manual.calibre-ebook.com

- https://docs.python.org

- https://github.com/kovidgoyal/calibre

- https://wiki.mobileread.com/wiki/E-book_formats

- https://wiki.mobileread.com/wiki/PDB

- https://www.mobileread.com/forums/showthread.php?t=291290

- https://www.nltk.org

- https://flake8.pycqa.org/en/latest

- https://docs.github.com/en/free-pro-team@latest/actions/reference/workflow-syntax-for-github-actions

- https://github.com/actions/virtual-environments

- https://www.crummy.com/software/BeautifulSoup/bs4/doc

- https://www.mediawiki.org/wiki/API:Query

- https://www.mediawiki.org/wiki/API:Etiquette

- https://docs.python-requests.org

- https://lxml.de

- https://maxbachmann.github.io/RapidFuzz

- https://pip.pypa.io/en/stable/user_guide

- https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/Wikidata_Query_Help

- https://en.wikibooks.org/wiki/SPARQL

Natural language processing
---------------------------

- https://spacy.io

- https://course.fast.ai

- https://paperswithcode.com/task/word-sense-disambiguation

- https://paperswithcode.com/task/named-entity-recognition-ner

Kindle firmware
---------------

- https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW

- https://github.com/NiLuJe/KindleTool

- https://adoptium.net

- https://github.com/java-decompiler/jd-gui

- https://wiki.mobileread.com/wiki/Kindle_Touch_Hacking#Architecture
