pdf-quench
==========

Pdf-Quench is a visual tool for cropping pdf files. It's made in pure python.

Install on Debian/Ubuntu

$ sudo dpkg -i pdf-quench_1.0.0_all.deb

To make sure all dependants are met:

$ sudo apt-get install python-pygoocanvas python-poppler python-pypdf

Shortcut can be found at Start > Office > Pdf-Quench.

Download links:

https://drive.google.com/#folders/0BwrTqzph0i12VDY4R0ZxSTdPTFE

Change Log

v1.0.3

- Change to use PyPdf2. Since PyPdf2 has not been available in ubuntu package repository, a latest PyPdf2 source code was included.

v1.0.2

- Enable specifing a pdf file to open in command line (patch from Antonio Sánchez)

- Minor fixes: a) fix package maintainer; b) use #!/usr/bin/python2
