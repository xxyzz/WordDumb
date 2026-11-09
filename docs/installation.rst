Installation
============

Install calibre (>=7.1)
-----------------------

- Arch Linux:

.. code:: console

   sudo pacman -Syu --needed calibre

- Other Linux distros:

.. code:: console

   sudo -v && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sudo sh /dev/stdin

- macOS: use `Homebrew <https://brew.sh>`_ or download from https://calibre-ebook.com/download_osx.

.. code:: console

   brew install calibre

- Windows: download from https://calibre-ebook.com/download_windows

Install uv
----------

- Arch Linux:

.. code:: console

   sudo pacman -Syu --needed uv

- Debian:

.. code:: console

   curl -LsSf https://astral.sh/uv/install.sh | sh

- macOS:

.. code:: console

   brew install uv

- Windows:

.. code:: console

   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

Install WordDumb plugin
-----------------------

.. raw:: html

   <video controls width="100%" src="https://user-images.githubusercontent.com/21101839/202723023-082a6147-6425-43be-9869-43293c90a306.mov"></video>

Install `KFX Input <https://www.mobileread.com/forums/showthread.php?t=291290>`_ plugin(optional)
-------------------------------------------------------------------------------------------------

This step is optional if you don't use the KFX format. The installation steps are similar to the above video.

.. attention::
   "Create book (EBOK) instead of personal document (PDOC)" option must be selected when converting book to KFX format.
