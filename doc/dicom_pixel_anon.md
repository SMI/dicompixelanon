# Redact text regions from DICOM image files

The DICOM files will be examined by an OCR algorithm to find text burned
into the pixels of any of its image or overlay frames. All text found will
be redacted by replacing it with a black rectangle.

The location of all text can be kept in a database in case it is needed later.

Usage:
```
dicom_pixel_anon.py [-D db dir] -o output  input...
 -D database directory, optional, to persist rectangle locations
 -o output directory, optional, default same as input, or current dir
 input is one or more DICOM filenames.
```

The program simply calls `dicom_ocr.py` to run OCR on the image frames and overlay
frames in one or more DICOM files, saving the results in a database, and then runs
`dicom_redact.py` to actually redact the image pixels, saving the resulting image in
a new DICOM file.

See the [dicom_ocr.py](dicom_ocr.md) document.

See the [dicom_redact.py](dicom_redact.md) document.
