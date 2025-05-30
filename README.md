# dicompixelanon

Anonymisation of text burned into the pixels of DICOM images. This software
has been used on the complete archive of a whole national population across
a variety of modalities (CT, MR, CR, DX, etc) and has proven highly effective.

This repo contains a full suite of software for
* viewing DICOM files in a GUI, including every frame, and every frame of every overlay
* marking up regions which need to be redacted
* maintaining databases of regions to be redacted
* maintaining redaction rules to be applied to DICOM files
* automatically finding text within DICOM images (checking every every frame and overlay)
* automatically redacting DICOM files based on the finding text, rules, or regions
* verifying that a redaction process has taken place correctly
(including GUI tools for quickly accepting/rejecting images)
* training Machine Learning models to identify particular image types
(used to spot scanned documents and forms which aren't clinical images)
* replacing all image frames with blank images (to produce dummy/synthetic data)
* a reusable library of code for reading and manipulating DICOM images

It also contains software which can be used to create dummy or synthetic DICOM files
based on originals, changing only the content of the image frames not the metadata.

What it does not do: anonymise the metadata in the DICOM tags;
this is best left to other tools (see CTP for example).

Contents:
* [dcmaudit](doc/dcmaudit.md) - view DICOM images, annotate regions to redact
* [dicom_pixel_anon](doc/dicom_pixel_anon.md) - run OCR and redact regions from DICOM images
   * [dicom_ocr](doc/dicom_ocr.md) - run OCR on the images and overlays in one or more DICOM files
   * [dicom_redact](doc/dicom_redact.md) - redact regions from DICOM images
* [pydicom_images](doc/pydicom_images.md) - extract DICOM images and overlays, run OCR and NLP/NER to find PII
* [dicom rect db](doc/dicomrectdb.md) - the database about DICOM files which have been examined
* [deidrules](doc/deidrules.md) - redaction using rules
* [dicom_pixel_remover](doc/dicom_pixel_remover.md) - replace DICOM images with blanks

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


## Environment variables

* `$SMI_ROOT` - this will be used to find data and configuration files
* `$PACS_ROOT` - this will be used to find DICOM files (e.g. if a path to a
DICOM file is relative, and the file cannot be found, then PACS_ROOT will be
prepended)
* `export HF_HUB_OFFLINE=1` if using `flair` inside a safe haven without
internet access, to prevent it from trying to download models from huggingface
(and crashing when it can't connect).
* export `PYTHONPATH=../../library/` if you want to try any of the applications
from their directory without building and installing the library

## Setup

* Create a Python virtual environment and activate it
* Create a config file directory `$SMI_ROOT/data` (you can set `$SMI_ROOT` anywhere)
* Install all of the Python requirements (see below)
* Copy `data/ocr_allowlist_regex.txt` into `$SMI_ROOT/data/dicompixelanon/ocr_allowlist_regex.txt` if required for dicom_redact
* Copy `data/deid.dicom.smi` into `$SMI_ROOT/data/deid/deid.dicom.smi`
* Copy `scannedforms_model.pth` into `$SMI_ROOT/data/dicompixelanon`
* Build the DicomPixelAnon library, see the instructions in the `src/library` directory
* Install the DicomPixelAnon wheel into the virtual environment

## Update

```
git pull
cp data/ocr_allowlist_regex.txt $SMI_ROOT/data/dicompixelanon/
cp data/deid.dicom.smi $SMI_ROOT/data/deid/
cd src/library
python3 ./setup.py bdist_wheel
pip install $(ls dist/*whl|tail -1)
```

## Run

Now you can run the applications:
 * dcmaudit.py, if you want to view a DICOM file and manually curate a database of rectangles
 * dicom_ocr.py, if you want to run OCR on a DICOM file and store the results in a database
 * dicom_redact.py, if you want to redact the DICOM file based on the rectangles in the database
 * dicom_pixel_anon.sh, to run both OCR and redaction together

See below for a suggested workflow.

# Sample data

Some sample data is provided as part of the GDCM repo:

* See https://gdcm.sourceforge.net/wiki/index.php/Sample_DataSet (list of sample datasets)
* https://sourceforge.net/projects/gdcm/files/gdcmConformanceTests/gdcmConformanceTests/gdcmConformanceTests.tar.bz2/download (gdcm Conformance tests)
* https://sourceforge.net/projects/gdcm/files/gdcmData/gdcmData/gdcmData.tar.gz/download (gdcm Data)
* https://sourceforge.net/projects/gdcm/files/gdcmData/gdcmData/gdcmData.tar.bz2/download (corrupt version of gdcm Data)

Useful sample files:

* `gdcm-US-ALOKA-16.dcm` - has Sequence of Ultrasound Regions (3) plus text within the image regions
* `US-GE-4AICL142.dcm` - has SequenceOfUltrasoundRegions
* `CT_OSIRIX_OddOverlay.dcm` - has 1 overlay
* `XA_GE_JPEG_02_with_Overlays.dcm` - has 8 overlays in high bits
* `PHILIPS_Brilliance_ExtraBytesInOverlay.dcm` - has 1 overlay
* `MR-SIEMENS-DICOM-WithOverlays.dcm` - has separate overlays
* `GE_DLX-8-MONO2-Multiframe.dcm` - has multiple frames



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

You might need to specify a version when installing spacy because the most
recent version on pypi (a dev version of 4.0.0) does not have the language
models available yet. For example `pip install spacy==3.6.0`

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

## Windows installation

Notes:
* you need a recent version of Python (3.6 probably too old)
* some packages are not yet available for Python 3.12 in binary form,
so if you don't have a compiler you might need to install Python 3.10,
which you can install alongside other versions if you wish, or install
into your personal AppData directory
* if you get an error about module skbuild not found, try `pip install scikit-build`
* if pip tries to install spacy v4 then `pip install spacy==3.6.0`
* if pip tries to install source-code packages then you could install a compiler
from https://visualstudio.microsoft.com/visual-cpp-build-tools/
* if you don't have a compiler then 
use the `--prefer-binary` option (or `--only-binary :all:`)
* if you get an error about matplotlib please try to install it
separately first, i.e. `pip install --prefer-binary matplotlib`
This is caused by an old binary version of deid asking for an old version of matplotlib.
* we need to force sentencepiece to be binary because it needs a compiler
* we need to force deid to be source to get the latest version
because older binary versions require an old matplotlib
but deid does not need to be compiled so it's safe to force a source version
* if you get an error about fastDamerauLevenshtein ("Microsoft Visual C++ is required")
please delete that line from `dicompixelanon\src\library\requirements.txt`
* Note that the keyboard shortcuts might not work on Windows
(I don't know why) so please use the menu instead (sorry).

Create the virtual environment (venv) using your preferred version of Python,
for example use *one* of these:
```
python -m venv c:\tmp\venv
C:\Program Files\Python310\python.exe -m venv c:\tmp\venv
C:\Users\Guneet\AppData\Local\Programs\Python\Python310\python.exe -m venv c:\tmp\venv
```

```
c:\tmp\venv\Scripts\activate.bat
pip install torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu
pip install --prefer-binary pydicom pydal easyocr numpy Pillow spacy flair pylibjpeg pylibjpeg_libjpeg --only-binary=sentencepiece
python -m spacy download en_core_web_trf
cd c:\tmp
git clone https://github.com/SMI/SmiServices
git clone https://github.com/SMI/StructuredReports
git clone https://github.com/SMI/dicompixelanon
pip install --prefer-binary -r c:\tmp\StructuredReports\src\library\requirements.txt
pip install --prefer-binary --no-binary=deid -r c:\tmp\dicompixelanon\src\library\requirements.txt --no-binary=deid
cd c:\tmp\StructuredReports\src\library
python .\setup.py install
cd c:\tmp\dicompixelanon\src\library
python .\setup.py install
cd c:\tmp\dicompixelanon\src\applications
set SMI_ROOT=c:\tmp\SmiServices
python dcmaudit.py -i C:\tmp\SmiServices\tests\common\Smi.Common.Tests\TestData\*.dcm
```

# Workflow

A suggested workflow for producing rules to anonymise a consistent set of DICOM files:
* identify all your DICOM files
* optionally sort into different directories by Manufacturer, SoftwareVersions, dimensions, etc.
* run `dcm_audit.py` and redact the PII in one of the images, it will be saved in the database
* visually check all the others - that rectangle should be suggested on all similar DICOMs,
check that it's correct, adjust it (reset the file and draw it again if necessary), or add others
* run `dbrects_to_deid_rules.py` to create deid rules which will automatically redact all DICOM
files which match the Manufacturer etc rules.
* put the deid file in the correct place to be used by `dicom_redact.py`, you won't need the database.

A suggested workflow for testing OCR on a whole Modality:
* Get a list of filenames to examine
  - extract_BIA to extract a modality from MongoDB
  - randomly sample from the output file
* dicom_ocr.py to create a database from
  - OCR
  - Ultrasound tags
* dcmaudit.py to review the results
* dbtagged.sh to go back over the ones you tagged in dcmaudit
* dicom_redact.py to actually redact images
* dicom_pixel_anon.sh to perform OCR and redaction together for checking
