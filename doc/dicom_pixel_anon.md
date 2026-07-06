# Redact text regions from DICOM image files

The DICOM files will be examined by an OCR algorithm to find text burned
into the pixels of any of its image or overlay frames. All text found will
be redacted by replacing it with a black rectangle.

The location of all text can be kept in a database or exported to a CSV file
in case it is needed later.

There are two programs:
* `dicom_ocr.py` - runs OCR on the image frames and overlay frames in one or
more DICOM files, saving the results in a database,
* `dicom_redact.py` - redact the image pixels, saving the resulting images in
new DICOM files.

Rather than call both programs separately there are two options to perform
OCR and redaction in a single step:
* `dicom_pixel_anon.py` - a single Python program which uses the above
two modules internally,
* `dicom_pixel_anon.sh` - a shell script that calls the two Python programs
consecutively.

# Usage:

```
dicom_pixel_anon.py [-h] [-v] [-d] [--ocr OCR] [--db DB] [--pii PII] [--use-ultrasound-regions]
   [--except-ultrasound-regions] [--rects] [--forms] [--no-overlays] [--review] [--deid]
   [--deid-rules DEID_RULES] [-o OUTPUT] [--relative-path RELATIVE] [--rename RENAME]
   [--compress] [--write-csv CSVOUT] input...
```

The input can be one or more DICOM files or it can be a directory
which will be searched recursively for DICOM files.

The output, for a single input file, can be a file or directory,
otherwise should be a directory. If it is the same as the input then
files will be overwritten.

The write-csv option should be used to preserve a CSV file of the
rectangles which were redacted. It is a subset of the database as it
has no PII.  The columns will be
`filename,left,top,right,bottom,frame,overlay`.
This file is only written after all DICOM files have been anonymised.

The relative option should be used to strip a given prefix from the
path when writing the CSV so that full path names are not visible.

There are additional options to assist the detection of PII, as described
in the references:
* The use of tagged regions in Ultrasound images (`--use-ultrasound-regions`)
* The use of deid files which indicate well-known regions to redact (`--deid`)
* The detection of scanned forms (`--forms`)

The database directory could be in a temporary location only used for this
particular invocation, or it could be preserved for multiple jobs. The
benefit of a temporary location is that PII will be detected and files will be
redacted before no prior information exists. This might be important if
filenames are not unique or you are running it multiple times on files with
the same filenmes. The benefit of preserving the database would be that
detection is skipped if a filename is already in the database, which saves
time as long as the filename matches exactly. If you reference files by
Study/Series/Instance then this will be useful but if you reference files by
ExtractionJob then you may not get the benefit.

When used as part of an anonymisation pipeline you should ensure that the
database directory is not part of the extracted data hierarchy because it will
contain OCR text extracted from the DICOM files and thus possibly PII.
In fact, after anonymising a set of DICOM files the database directory can be
removed if you do not need it for future redactions.

The shell script version of this program has slightly different options
and works very slightly differently, for example when writing the rectangles CSV.

# Requirements

This program requires `dicom_ocr.py`, `dicom_redact.py` - see their documents
for more details on their requirements.

# References

See the [dicom_ocr.py](dicom_ocr.md) document.

See the [dicom_redact.py](dicom_redact.md) document.
