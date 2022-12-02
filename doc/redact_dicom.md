# Redact DICOM images

The `redact_dicom.py` tool can redact (blank out) rectangular regions
from images in DICOM files. Unlike most redaction software, it can
target specific image frames, or overlays, or frames of overlays, and
it doesn't require overlays to be burned onto the main image.

Other tools: CTP and pydicom-deid both allow rectangles to be redacted
based on a "script" or configuration file, which matches the values in
DICOM tags to determine which rectangles to redact. Both have limitations
on which image frames can be redacted, and how well the DICOM tags match
those in the configuration file.

This tool can redact rectangles in three ways:
* from a list specified on the command line
* from a list provided in a CSV file, for example the output from
 `pydicom_images.py` running OCR on DICOM files
* from a list stored in a database, for example the output from
 `dcmaudio.py` with manually marked-up DICOM files

It should be noted that all of these tools can be used standalone or
in conjunction with other tools, for example you can use CTP and/or
pydicom-deid as well.

This tool also has the ability to remove any overlays which are
embedded in the high-bits of the image pixels. The normal CTP anonymisation
process can remove overlays but it only removes the 60xx group of DICOM
tags which in most cases is sufficient, but it doesn't remove high-bit
overlays. This tool can do that job to fully clean a DICOM file.

NOTE! The utility has to decompress the image (if compressed), but it
does not (yet) recompress the image again afterwards, so the file size
may increase. Some other redaction tools have the ability to preserve
most of a lossy-JPEG-compressed image except for the redacted blocks,
but those tools do not handle overlays at all. Compression, and lossy
compression support can of course be added to this tool later.
