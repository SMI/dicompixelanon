# dicompixelanon

Anonymisation of text burned into the pixels of DICOM images.

Contents:
* [dcmaudit](doc/dcmaudit.md) - view DICOM images, annotate regions to redact
* [dicom_ocr](doc/dicom_ocr.md) - run OCR on the images and overlays in one or more DICOM files
* [dicom_redact](doc/dicom_redact.md) - redact regions from DICOM images
* [dicom_pixel_anon](doc/dicom_pixel_anon.md) - run OCR and redact regions from DICOM images
* [pydicom_images](doc/pydicom_images.md) - extract DICOM images and overlays, run OCR and NLP/NER to find PII
* [dicom rect db](doc/dicomrectdb.md) - the database about DICOM files which have been examined

Utilities:
* `dcmaudit.py` - interactive GUI to mark rectangles for redaction in DICOM image frames and overlays
* `dicom_redact_db.py` - redact every file in the database which has rectangles
* `extract_all.py` - extract as JSON every document from every image modality in MongoDB
* `extract_BIA.py` - extract all the DICOM tags relevant to annotations, overlays, frames from every document from every image modality in MongoDB
* `csv_groupby_filter.py` - group CSV rows and output a selection from each group
* `summary.py` - report a count of the unique values in each column of the CSV
* `summary_overlay.py` - print the overlay-related columns from the CSV
* `random_combinations.sh` - run `random_combinations.py` for every image modality CSV file
* `random_combinations.py` - read a CSV file and output a randomly-selected set of lines for each of every combination of values in a given set of columns
* `random_combinations_files.py` - convert the output from `random_combinations.py` into a set of filenames
* `ocr_files_parallel.sh` - run two OCR on output of random_combinations.sh
* `pydicom_images.py` - extract all the image frames, overlays, overlay frames as PNG format from a DICOM file, optionally run through OCR to get text, optionally run that through NER to get PII
* `dbrects.sh` - display the rectangles in the database (simple sqlite3 wrapper)
* `dbtext.sh` - display the OCR text in the database (simple sqlite3 wrapper)
* `dbtags.sh` - display the table of files marked as Done in the database (simple sqlite3 wrapper)
* `dbtagged.sh` - display the filenames marked as Done in the database (simple sqlite3 wrapper)
* `dbtext_for_tagged.sh` - display OCR details of files marked as Done
* `dbrects_for_tagged.sh` - display rectangles of files marked as Done
* `dbrects_to_deid_rules.py` - convert rectangles from files marked as Done into deid rules
* `dicomls.py` - simply list all DICOM tags and values from a file
* `dicom_pixel_anon.sh` - anonymise a DICOM by running OCR and redacting all rectangles
* `build_allowlist.py` - create list of regex rules for allowlisting OCR output and write to file, optionally reduce the number of rules by 20 percent (leading to more redactions of non-PII data, but significantly shorter runtime)

# Usage


Environment variables

* `$SMI_ROOT` - this will be used to find data and configuration files
* `$PACS_ROOT` - this will be used to find DICOM files (e.g. if a path to a
DICOM file is relative, and the file cannot be found, then PACS_ROOT will be
prepended)
* `export HF_HUB_OFFLINE=1` if using `flair` inside a safe haven without
internet access, to prevent it from trying to download models from huggingface
(and crashing when it can't connect).
* export `PYTHONPATH=../../library/` if you want to try any of the applications
from their directory without building and installing the library

Setup

* Create a Python virtual environment and activate it
* Create a config file directory `$SMI_ROOT/data` (you can set `$SMI_ROOT` anywhere)
* Install all of the Python requirements (see below)
* Copy `data/ocr_allowlist_regex.txt` into `$SMI_ROOT/data/dicompixelanon/ocr_allowlist_regex.txt` if required for dicom_redact
* Copy `src/library/DicomPixelAnon/data/deid.dicom.smi` into `$SMI_ROOT/data/deid/deid.dicom.smi`
* Build the DicomPixelAnon library, see the instructions in the `src/library` directory
* Install the DicomPixelAnon wheel into the virtual environment

Now you can run the applications:
 * dcmaudit, if you want to view a DICOM file and manually curate a database of rectangles
 * dicom_ocr, if you want to run OCR on a DICOM file and store the results in a database
 * dicom_redact, if you want to redact the DICOM file based on the rectangles in the database
 * dicom_pixel_anon, to run both ocr and redact together

See below for a suggested workflow.

# Sample data

Some sample data is provided as part of the GDCM repo:

* See https://gdcm.sourceforge.net/wiki/index.php/Sample_DataSet (list of sample datasets)
* https://sourceforge.net/projects/gdcm/files/gdcmConformanceTests/gdcmConformanceTests/gdcmConformanceTests.tar.bz2/download (gdcm Conformance tests)
* https://sourceforge.net/projects/gdcm/files/gdcmData/gdcmData/gdcmData.tar.gz/download (gdcm Data)
* https://sourceforge.net/projects/gdcm/files/gdcmData/gdcmData/gdcmData.tar.bz2/download (corrupt version of gdcm Data)

Useful sample files:

* `gdcm-US-ALOKA-16.dcm` - has Sequence of Ultrasound Regions (3) plus text within the image regions
* `CT_OSIRIX_OddOverlay.dcm` - has 1 overlay
* `XA_GE_JPEG_02_with_Overlays.dcm` - has 8 overlays in high bits
* `PHILIPS_Brilliance_ExtraBytesInOverlay.dcm` - has 1 overlay


# Requirements

Before installing these requirements please read the Installation Notes below.

Python requirements

* pytorch CPU version (if no GPU available), see the pytorch website
NOTE install this separately first before installing any others.
* pydicom - for reading DICOM format
* pydal - for database access (the db is typically `sqlite` format)
* easyocr - to extract text from images
* numpy
* opencv_python_headless
* Pillow
* other dependencies of the above

Optional Python requirements

* pymongo - to extract metadata from MongoDB (optional)
* spacy - to detect named entities in text
* flair - to detect named entities in text
* pytesseract (v0.3.8 because of python 3.6) - to extract text from images
* stanford CoreNLP - to detect named entities in text
* stanza - to detect named entities in text

OS packages

* sqlite3
* python3-tk (for dcmaudit), this will install tk8.6 and libtk8.6
* tesseract-ocr (optional)

# Installation notes

## pytorch

Before installing the requirements from `requirements.txt` you must install the CPU version of PyTorch if you don't have a GPU available:
```
pip3 install torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu
```

## pydicom

pydicom has some additional packages which need to be installed.
To handle compressed images you need to install `pylibjpeg` and `pylibjpeg_libjpeg`.
See the tables in the `pydicom` documentation:
https://pydicom.github.io/pydicom/stable/old/image_data_handlers.html#supported-transfer-syntaxes

## pytesseract

PyTesseract must be pinned to version 0.3.8 if you are stuck with Python 3.6 (as found in CentOS-7).
See also tesseract below.

## Stanford NER

Stanford NER (the original CoreNLP, not Stanza) requires Java 1.8. It can be made to work with Java 9 and Java 10 but will not work with Java 11 because a dependency has been removed from the JRE.

## easyocr

The easyocr model hub is https://www.jaided.ai/easyocr/modelhub/
Download the English model from https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/english_g2.zip
and the text detection model from https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip
Unpack the zip files and copy the `.pth` files into `$SMI_ROOT/data/easyocr`

## spacy

Inside your virtual environment run `python -m spacy download en_core_web_trf`

## tesseract

Download the file `eng.traineddata` from
https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata
and copy it to `$SMI_ROOT/data/tessdata`

## flair

Download the file `pytorch_model.bin` from https://huggingface.co/flair/ner-english,
copy it to `$SMI_ROOT/data/flair/models/ner-english/`
and make a symlink from `4f4cdab26f24cb98b732b389e6cebc646c36f54cfd6e0b7d3b90b25656e4262f`
and/or from `4f4cdab26f24cb98b732b389e6cebc646c36f54cfd6e0b7d3b90b25656e4262f.8baa8ae8795f4df80b28e7f7b61d788ecbb057d1dc85aacb316f1bd02837a4a4`

## stanford

Download the repo https://github.com/philipperemy/Stanford-NER-Python
and run `init.sh` to unpack the zip to the `stanford-ner` directory.
Copy the contents of the `stanford-ner` directory into `$SMI_ROOT/data/stanford_ner/`
Note that this includes the CoreNLP Java software which needs Java 1.8
(possibly also 9 and 10 but it is not compatible with Java 11).

## stanza

Download the models from https://huggingface.co/stanfordnlp/stanza-en/resolve/v1.4.1/models/default.zip
Unpack `default.zip` into `$SMI_ROOT/data/stanza/en/`


# Workflow

A suggested workflow might be:
* Get a list of filenames to examine
  - extract_BIA to extract a modality from MongoDB
  - randomly sample from the output file
* dicom_ocr.py to create a database from
  - OCR
  - Ultrasound tags
* dcmaudit.py to review the results
* dbtagged.sh to go back over the ones you tagged in dcmaudit
* dicom_redact.py to actually redact images
