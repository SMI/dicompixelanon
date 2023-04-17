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
 --use-ultrasound-regions
                       collect rectangles from Ultrasound region tags
 --db database_dir     output to database in directory, or use "default" for the default directory
 --csv file.csv        output to CSV filename, or use "stdout" for stdout
 --rects               Output each OCR rectangle separately with coordinates
 --no-overlays         Do not process any DICOM overlays (default processes overlays)
```

* OCR options: `easyocr` / `tesseract`
* PII options: `spacy` / `flair` / `stanford` / `stanza` / `ocr_allowlist`
* database filename: will be dcmaudit.sqlite
* default directory: $SMI_ROOT/data/dicompixelanon

This program can be run on a CPU but it is much faster with a GPU.
To run on a CPU you should install the CPU version of PyTorch
(for `pip` use `--extra-index-url https://download.pytorch.org/whl/cpu`).
When run on a GPU it is configured to use a maximum of 40% of available
GPU memory so that two processes can be run in parallel.

Besides (or instead of) using OCR to find text, this program can also use
metadata inside Ultrasound DICOM files that indicate image regions.
The tag `SequenceOfUltrasoundRegions` contains a set of rectangles defining
the image content so this program can invert those to get a set of rectangles
surrounding the image content. Such rectangles can be treated the same way
as rectangles found using OCR; stored in a database or CSV file for future
redaction.

PII can be detected using one of a number of algorithms; SpaCy and Flair
also have several language models to choose from, although none are highly
accurate on short text fragments without context. A check for PII will set
a flag 0 if no named entities are found and 1 if some are found.

An OCR allowlist is also available in the PII option, which operates slightly
differently. If the whole exact string is in the allowlist it marks the
rectangle as non-PII as determined by a allowlist, otherwise it marks the
rectangle as PII because it was not on a allowlist. The text may still be
safe without PII but the allowlist alone cannot determine this so it errs on
the side of caution.

## Examples

To run OCR and then detect PII in the resulting text, and save the
details of each individual rectangle into a database in dbdir directory:
```
dicom_ocr.py --ocr easyocr --pii flair --db dbdir --rects  file*.dcm
```

To test one of the Ultrasound examples, output CSV to stdout,
you should expect to see the three Ultrasound regions converted into
four redaction rectangles, then the rectangles from the easyocr OCR.
Note how each text string appears separately with its coordinates and
then all of the text concatenated appears with a null rectangle.
```
PYTHONPATH=../library/ ./dicom_ocr.py --rects --csv /dev/tty --use-ultrasound-regions ~/data/gdcm/gdcmData/gdcm-US-ALOKA-16.dcm
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,ultrasoundregions,0,0,639,24,,,-1
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,ultrasoundregions,0,24,32,415,,,-1
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,ultrasoundregions,335,24,336,415,,,-1
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,ultrasoundregions,0,415,639,479,,,-1
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,easyocr,246,0,340,64,8s79 127/2884},,-1
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,easyocr,559,31,640,67,1103 2812,,-1
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,easyocr,19,429,241,471,9123 5.0 R15 066 c6 8e,,-1
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,easyocr,259,431,281,447,Az,,-1
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,easyocr,339,431,381,447,9123,,-1
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,easyocr,399,429,633,471,"5,0 R15 063 c6 Az  no",,-1
gdcm-US-ALOKA-16.dcm,0,-1,ORIGINAL/PRIMARY/ABDOM/RAD/0001,SSD-4000,,easyocr,-1,-1,-1,-1,"8s79 127/2884} 1103 2812 9123 5.0 R15 066 c6 8e Az 9123 5,0 R15 063 c6 Az  no ",,-1
```

To do the same and also filter out text which is safe (not PII) using an allowlist.
Note that the output will still include all the text rectangles but those which
are safe will have `ner_engine=allowlist` and `is_sensitive=0`
```
cp data/ocr_allowlist_regex.txt $SMI_ROOT/data/dicompixelanon
dicom_ocr.py --pii ocr_allowlist ...etc as above...
filename.dcm, ... ,allowlist,0
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

Database output is better than CSV as the information can be shared between programs.
For example `dcmaudit.py` and `dicom_redact.py` can both read from a database.
The database location is specified by a directory (the filename inside is fixed).

See the documentation of the `DicomRects` table in the [dicomrectdb](dicomrectdb.md) document.
