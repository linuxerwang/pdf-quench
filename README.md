# pdf-quench

Pdf-Quench is a visual tool for cropping pdf files. It's made in pure python.

## Install on Debian/Ubuntu 16.04

The master branch of pdf-quench has changed to use gobject introspections
bindings. This work is contributed by
[thrasibule](https://github.com/thrasibule). Thanks, thrasibule.

$ sudo dpkg -i pdf-quench_1.0.5_all.deb

To make sure all dependants are met:

$ sudo apt install gir1.2-goocanvas-2.0 gir1.2-poppler-0.18 python-pygoocanvas \
  python-poppler python-pypdf

Shortcut can be found at Start > Office > Pdf-Quench.

Download links:

https://drive.google.com/#folders/0BwrTqzph0i12VDY4R0ZxSTdPTFE

## Install on Debian/Ubuntu 14.04

Please checkout commit a36c50eedd1647e442fa1202e422526a6199b0aa.

$ sudo dpkg -i pdf-quench_1.0.4_all.deb

To make sure all dependants are met:

$ sudo apt-get install python-pygoocanvas python-poppler python-pypdf

Shortcut can be found at Start > Office > Pdf-Quench.

Download links:

https://drive.google.com/#folders/0BwrTqzph0i12VDY4R0ZxSTdPTFE

## Change Log

v1.0.5

- Set pdf crop box to the same position as meda box, thus fix the issue with cropping the 2nd time.

v1.0.4

- Add support for cropping with correct rotation.

v1.0.3

- Change to use PyPdf2. Since PyPdf2 has not been available in ubuntu package repository, a latest PyPdf2 source code was included.

v1.0.2

- Enable specifing a pdf file to open in command line (patch from Antonio Sánchez)

- Minor fixes: a) fix package maintainer; b) use #!/usr/bin/python2

