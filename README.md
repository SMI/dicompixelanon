# dicompixelanon

Anonymisation of text burned into the pixels of DICOM images.

Contents:
* [dcmaudit](doc/dcmaudit.md) - view DICOM images, annotate regions to redact
* [pydicom_images](doc/pydicom_images.md) - extract DICOM images and overlays, run OCR and NLP/NER to find PII
* [redact_dicom](doc/redact_dicom.md) - redact regions from DICOM images
* [review_SR_report](doc/review_SR_report.md) - view DICOM Structured Reports, review possible PII from IsIdentifiable report

Summary of procedure:
* extract all the potentially useful information from MongoDB and store in CSV files (quicker than querying MongoDB every time)
* extract a random sample of DICOM filenames from the CSV files, eg. 20 for every combination of modality + ImageType + Manufacturer
* use pydicom_images to view the DICOMs and visually inspect for PII in the pixels

Utilities:
* `dcmaudit.py` - interactive GUI to mark rectangles for redaction in DICOM image frames and overlays
* `extract_all.py` - extract as JSON every document from every image modality in MongoDB
* `extract_BIA.py` - extract all the DICOM tags relevant to annotations, overlays, frames from every document from every image modality in MongoDB
* `summary.py` - report a count of the unique values in each column of the CSV
* `summary_overlay.py` - print the overlay-related columns from the CSV
* `random_combinations.sh` - run `random_combinations.py` for every image modality CSV file
* `random_combinations.py` - read a CSV file and output a randomly-selected set of lines for each of every combination of values in a given set of columns
* `random_combinations_files.py` - convert the output from `random_combinations.py` into a set of filenames
* `pydicom_images.py` - extract all the image frames, overlays, overlay frames as PNG format from a DICOM file, optionally run through OCR to get text, optionally run that through NER to get PII

# Sample data

Some sample data is provided as part of the GDCM repo:

* See https://gdcm.sourceforge.net/wiki/index.php/Sample_DataSet (list of sample datasets)
* https://sourceforge.net/projects/gdcm/files/gdcmConformanceTests/gdcmConformanceTests/gdcmConformanceTests.tar.bz2/download (gdcm Conformance tests)
* https://sourceforge.net/projects/gdcm/files/gdcmData/gdcmData/gdcmData.tar.gz/download (gdcm Data)
* https://sourceforge.net/projects/gdcm/files/gdcmData/gdcmData/gdcmData.tar.bz2/download (corrupt version of gdcm Data)

# Requirements

Python requirements

* pydicom - for reading DICOM format
  - To handle compressed images you need to install `pylibjpeg` (and `pylibjpeg-libjpeg`). See the tables in the `pydicom` documentation:
https://pydicom.github.io/pydicom/stable/old/image_data_handlers.html#supported-transfer-syntaxes
* pydal - for database access (typically `sqlite` format)
* pymongo - to extract metadata from MongoDB
* easyocr - to extract text from images
  - models downloaded from https://www.jaided.ai/easyocr/modelhub/ are:
  - `craft_mlt_25k.pth` text detection model (manually installed)
  - `english_g2.pth` 2nd generation language model (manually installed)
* spacy - to detect named entities in text
  - `en_core_web_trf` language model (installed from pip or wheel)
* flair - to detect named entities in text
  - model downloaded from https://huggingface.co/flair/ner-english is: `pytorch_model.bin`
* pytesseract (v0.3.8 because of python 3.6) - to extract text from images
  - `eng.traineddata` language model (manually installed)
* stanford CoreNLP - to detect named entities in text
  - https://github.com/philipperemy/Stanford-NER-Python
  - includes the CoreNLP Java software (for Java 1.8 not Java 11)
* stanza - to detect named entities in text
* numpy
* opencv-python-headless
* Pillow
* pytorch CPU version (if no GPU available)
* other dependencies of the above

# Installation notes

Before installing the requirements from `requirements.txt` you must install the CPU version of PyTorch if you don't have a GPU available:
```
pip3 install torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu
```

PyTesseract must be pinned to version 0.3.8 if you are stuck with Python 3.6 (as found in CentOs-7).

Stanford NER (the original CoreNLP, not Stanza) requires Java 1.8. It can be made to work with Java 9 and Java 10 but will not work with Java 11 because a dependency has been removed from the JRE.

## easyocr

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

Download the file `pytorch_model.bin` from https://huggingface.co/flair/ner-english, copy it to `$SMI_ROOT/data/flair/models/ner-english/` and make a symlink from `4f4cdab26f24cb98b732b389e6cebc646c36f54cfd6e0b7d3b90b25656e4262f`

## stanford

Download the repo https://github.com/philipperemy/Stanford-NER-Python
and run `init.sh` to unpack the zip to the `stanford-ner` directory.
Copy the contents of the `stanford-ner` directory into `$SMI_ROOT/data/stanford_ner/`

## stanza

Download the models from https://huggingface.co/stanfordnlp/stanza-en/resolve/v1.4.1/models/default.zip
Unpack `default.zip` into `$SMI_ROOT/data/stanza/en/`

# Usage

You will need to have `SMI_ROOT` and `PACS_ROOT` in the environment.

To prevent flair from trying to download models from huggingface
on the internet (and crashing when it can't connect) try:
`export HF_HUB_OFFLINE=1`
