# Redact text regions from DICOM image files

This program simply calls `dicom_ocr.py` to run OCR on the image frames and overlay
frames in one or more DICOM files, saving the results in a database, and then runs
`dicom_redact.py` to actually redact the image pixels, saving the resulting image in
a new DICOM file.

See the [dicom_ocr.py](dicom_ocr.md) document.

See the [dicom_redact.py](dicom_redact.md) document.
