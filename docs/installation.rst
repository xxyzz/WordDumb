Installation
============

Install calibre 6.9.0+
----------------------

- Arch Linux:

.. code-block:: console

   $ sudo pacman -Syu --needed calibre

- Other Linux distros:

.. code-block:: console

   $ sudo -v && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sudo sh /dev/stdin

- macOS:

Use `Homebrew <https://brew.sh>`_ or download from https://calibre-ebook.com/download_osx.

.. code-block:: console

   $ brew install calibre

.. attention::
   Don't use Rosetta 2.

- Windows:

Use `Chocolatey <https://chocolatey.org>`_ or download from https://calibre-ebook.com/download_windows64

.. code-block:: console

   # choco install calibre

Install Python 3.10+ and pip
----------------------------

- Arch Linux:

.. code-block:: console

   $ sudo pacman -Syu --needed python-pip

- Debian:

.. code-block:: console

   $ sudo apt install python3-pip

- macOS:

.. code-block:: console

   $ brew install python

.. attention::
   Don't use Rosetta 2.

- Windows:

Use Chocolatey or download from https://www.python.org/downloads

.. code-block:: console

   # choco install python

.. attention::
   Do not change the default installtion settings in the Python installer.

Install CUDA(optional)
----------------------

`CUDA <https://en.wikipedia.org/wiki/CUDA>`_ is required for the "Run spaCy with GPU" feature, you can download CUDA from https://developer.nvidia.com/cuda-downloads

.. attention::

   - PyTorch currently doesn't support CUDA 12(`GitHub issue <https://github.com/pytorch/pytorch/issues/91122>`_), download older version from https://developer.nvidia.com/cuda-toolkit-archive

   - C/C++ compiler is needed for Windows, download from https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022

   - Read the installation guide on the CUDA download page for more information.

Install WordDumb plugin
-----------------------

.. raw:: html

   <video controls width="100%" src="https://user-images.githubusercontent.com/21101839/202723023-082a6147-6425-43be-9869-43293c90a306.mov"></video>

Install `KFX Input <https://www.mobileread.com/forums/showthread.php?t=291290>`_ plugin(optional)
-------------------------------------------------------------------------------------------------

This step is optional if you don't use the KFX format. The installation steps are similar to the above video.


Install adb(optional)
---------------------

This step is for Android users. Only KFX books are supported.

- Arch Linux:

.. code-block:: console

   $ sudo pacman -Syu --needed android-tools

- Debian:

.. code-block:: console

   $ sudo apt install android-tools-adb

- macOS:

.. code-block:: console

   $ brew install android-platform-tools

- Windows: download from https://developer.android.com/studio/releases/platform-tools

Enable USB debugging, and Rooted debugging(only send Word Wise file requires this option). For more information, please read `Android Debug Bridge user guide <https://developer.android.com/studio/command-line/adb#Enabling>`_. Rooted debugging is only available on `userdebug and eng build variant <https://source.android.com/docs/setup/create/new-device#build-variants>`_ ROMs, some custom ROMs like `LineageOS <https://lineageos.org>`_ have this option. Don't forget to diable USB debugging after the files are sent.
