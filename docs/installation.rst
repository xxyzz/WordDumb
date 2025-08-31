Installation
============

Install calibre 7.1.0+
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

Use `Chocolatey <https://chocolatey.org>`_ or download from https://calibre-ebook.com/download_windows

.. code-block:: console

   # choco install calibre

Install Python 3.11+ and pip
----------------------------

You could set the Python interpreter path in the plugin preferences window if you don't use the following methods to install Python.

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
   - Do not change the default installation settings in the Python installer.
   - `PyTorch <https://pytorch.org/get-started/locally>`_ may not support the latest Python and CUDA version.

Install CUDA or ROCm(optional)
------------------------------

`CUDA <https://en.wikipedia.org/wiki/CUDA>`_ or `ROCm <https://en.wikipedia.org/wiki/ROCm>`_ can be installed to shorten `WSD <https://en.wikipedia.org/wiki/Word-sense_disambiguation>`_ processing time if you have supported GPU. You can download CUDA from https://developer.nvidia.com/cuda-toolkit-archive and ROCm from https://rocm.docs.amd.com/projects/install-on-linux/en/latest/install/quick-start.html

- CUDA supported GPUs: https://developer.nvidia.com/cuda-gpus
- ROCm supported GPUs: https://rocm.docs.amd.com/projects/install-on-linux/en/latest/reference/system-requirements.html

.. attention::
   - The latest CUDA and ROCm release usually is not supported by PyTorch, read https://pytorch.org/get-started/locally to find the supported versions.
   - C/C++ compiler is needed for Windows, download from https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
   - Read the installation guide on the CUDA download page for more information.

Install WordDumb plugin
-----------------------

.. raw:: html

   <video controls width="100%" src="https://user-images.githubusercontent.com/21101839/202723023-082a6147-6425-43be-9869-43293c90a306.mov"></video>

Install `KFX Input <https://www.mobileread.com/forums/showthread.php?t=291290>`_ plugin(optional)
-------------------------------------------------------------------------------------------------

This step is optional if you don't use the KFX format. The installation steps are similar to the above video.

.. attention::
   "Create book (EBOK) instead of personal document (PDOC)" option must be selected when converting book to KFX format.
