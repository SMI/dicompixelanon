# dicom_ocr.py

Run OCR on all the image frames, overlays and overlay frames in one or more DICOM files.
Optionally also run a NER algorithm on the text to check for PII.
Save the results to CSV format or to a database.

## Usage

```
usage: dicom_ocr.py [-v] [-d] [--ocr OCR] [--pii PII]
                         [--csv filename.csv or "stdout"]
                         [--db database_dir or "default"]
                         [--csv-header/--no-csv-header]
                         [--rects] [--no-overlays]
                         files...

 -v, --verbose         more verbose (show INFO messages)
 -d, --debug           more verbose (show DEBUG messages)
 --ocr OCR             OCR using "tesseract" or "easyocr", output to stdout
 --pii PII             Check OCR output for PII using "spacy" or "flair"
                       (add ,model if needed)
 --db database_dir     output to database in directory, or use "default" for the default directory
 --csv file.csv        output to CSV filename, or use "stdout" for stdout
 --rects               Output each OCR rectangle separately with coordinates
 --no-overlays         Do not process any DICOM overlays (default processes overlays)
```

* ocr options: easyocr / tesseract
* pii options: spacy / flair / stanford / stanza
* database filename: will be dcmaudit.sqlite
* default directory: $SMI_ROOT/data/dicompixelanon

This program can be run on a CPU but it is much faster with a GPU.
To run on a CPU you should install the CPU version of PyTorch
(for `pip` use `--extra-index-url https://download.pytorch.org/whl/cpu`).
When run on a GPU it is configured to use a maximum of 40% of available
GPU memory so that two processes can be run in parallel.

## Example

```
dicom_ocr.py --ocr easyocr --pii flair --db dbdir --rect file*.dcm 
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

## Output Database

See the documentation of the `DicomRects` table in the [dcmaudit](dcmaudit.md) document.
