# dicompixelanon

Anonymisation of text burned into the pixels of DICOM images.

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

* https://sourceforge.net/projects/gdcm/files/gdcmData/gdcmData/gdcmData.tar.bz2/download (corrupt)
* https://sourceforge.net/projects/gdcm/files/gdcmData/gdcmData/gdcmData.tar.gz/download
* https://sourceforge.net/projects/gdcm/files/gdcmConformanceTests/gdcmConformanceTests/gdcmConformanceTests.tar.bz2/download

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
  - model downloaded from https://huggingface.co/flair/ner-english is:
  - `pytorch_model.bin` (downloaded from huggingface, manually installed as filename 4f4cdab26f24cb98b732b389e6cebc646c36f54cfd6e0b7d3b90b25656e4262f)
* pytesseract (v0.3.8 because of python 3.6) - to extract text from images
  - `eng.traineddata` language model (manually installed)
* numpy
* opencv-python-headless
* Pillow
* other dependencies, such as pytorch

# Installation notes

To prevent flair from trying to download models from huggingface on the internet (and crashing when it can't connect) try `export HF_HUB_OFFLINE=1`

You will need to have `SMI_ROOT` and `PACS_ROOT` in the environment.
