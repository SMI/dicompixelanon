# pydicom_images.py

Parse a DICOM file or files to find all image frames, overlays, and frames in overlays.
Optionally run OCR on each frame, and then optionally run NER on the text to check for PII.

## Usage

```
usage: pydicom_images.py [-v] [-d] [-x] [-i] [--ocr OCR] [--pii PII]
                         [--rects] [--no-overlays] [-f FORMAT]
                         files...

 -v, --verbose         more verbose (show INFO messages)
 -d, --debug           more verbose (show DEBUG messages)
 -x, --extract         extract PNG/TIFF files to input dir
                       (or current dir if input dir not writable)
 -i, --identify        identify only
 --ocr OCR             OCR using "tesseract" or "easyocr", output to stdout
 --pii PII             Check OCR output for PII using "spacy" or "flair"
                       (add ,model if needed)
 --rects               Output each OCR rectangle separately with coordinates
 --no-overlays         Do not process any DICOM overlays (default processes overlays)
 -f FORMAT, --format FORMAT  image format png or tiff for -x (default tiff)
```

## Output CSV format

OCR results are written out in CSV format.
Multiple rectangles will be written out using one line for each rectangle,
then an additional line will be written with the whole concatenated text string,
and this will be marked with coordinates -1,-1,-1,-1.

```
filename,frame,overlay,imagetype,manufacturer,burnedinannotation,ocr_engine,left,top,right,bottom,ocr_text,ner_engine,is_sensitive
```

* frame, overlay - counts from zero, will be -1 if not applicable
* imagetype - the full content of the ImageType tag
* manufacturer - actually the ManufacturerModelName tag or if that is empty then the Manufacturer + SoftwareVersions
* burnedinannotation- the BurnedInAnnotation tag
* ocr_engine - name of the engine used to perform OCR, blank if none
* left,top,right,bottom - rectangle, or -1,-1,-1,-1 for the whole image OCR string
* ocr_text - text found by OCR, blank if none or not checked
* ner_engine - name of the engine used to check for NER, blank if none
* is_sensitive - 0 if no PII, 1 if PII, -1 if not checked
