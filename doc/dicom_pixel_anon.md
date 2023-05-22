# Redact text regions from DICOM image files

The DICOM files will be examined by an OCR algorithm to find text burned
into the pixels of any of its image or overlay frames. All text found will
be redacted by replacing it with a black rectangle.

The location of all text can be kept in a database or exported to a CSV file
in case it is needed later.

The program calls `dicom_ocr.py` to run OCR on the image frames and overlay
frames in one or more DICOM files, saving the results in a database, and then runs
`dicom_redact.py` to actually redact the image pixels, saving the resulting images in
new DICOM files.

# Usage:

```
dicom_pixel_anon.py [-D db dir] -o output  input...
 -D database directory, optional, to persist rectangle locations
 -o output directory, optional, default same as input, or current dir
 input is one or more DICOM filenames.
```

A record of the redacted rectangles is saved in a CSV file called
`rectangles.csv` in the output directory. The columns will be
`filename,left,top,right,bottom,frame,overlay`. This file is only written
after all DICOM files have been anonymised.

When used as part of an anonymisation pipeline you should ensure that the
database directory is not part of the extracted data hierarchy because it will
contain OCR text extracted from the DICOM files and thus possibly PII.
In fact, after anonymising a set of DICOM files the database directory can be
removed.

# Requirements

This program requires `dicom_ocr.py`, `dicom_redact.py` - see their documents
for more details on their requirements.

It optionally uses the `sqlite3` command line utility to extract from the
database into a CSV file.

# References

See the [dicom_ocr.py](dicom_ocr.md) document.

See the [dicom_redact.py](dicom_redact.md) document.
