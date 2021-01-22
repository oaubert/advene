===============================
Windows Installer Build Scripts
===============================

All the Windows Installer build files are adapted from the great work
done by Christoph Reiter for Quodlibet.

We use `msys2 <https://msys2.github.io/>`__ for creating the Windows installer
and development on Windows.

Setting Up the MSYS2 Environment
--------------------------------

* Download msys2 64-bit from https://msys2.github.io/
* Follow instructions on https://msys2.github.io/
* Execute ``C:\msys64\mingw64.exe``
* Run ``pacman -S git`` to install git
* Run ``git clone https://github.com/oaubert/advene.git``
* Run ``cd advene/dev/win_installer`` to end up where this README exists.
* Execute ``./bootstrap.sh`` to install all the needed dependencies.
* Now go to the application source code ``cd ../..``
* To run Quod Libet execute ``./bin/advene``

Creating an Installer
---------------------

Simply run ``./build.sh [git-tag]`` and both the installer and the portable
installer should appear in this directory.

You can pass a git tag ``./build.sh release-3.8.0`` to build a specific tag or
pass nothing to build master. Note that it will clone from this repository and
not from github so any commits present locally will be cloned as well.


Updating an Existing Installer
------------------------------

We directly follow msys2 upstream so building the installer two weeks later
might result in newer versions of dependencies being used. To reduce the risk
of stable release breakage you can use an existing installer and just install
a newer Advene version into it and then repack it.

``./rebuild.sh advene-3.8.0-installer.exe [git-tag]``
