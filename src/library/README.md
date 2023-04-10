# DicomPixelAnon Python library

Some useful functions in Python for performing anonymisation of text burned into the pixels of image frames in DICOM files.

## Requirements

See `requirements.txt`

Note that you must first install either the CPU or GPU version of PyTorch
before installing requirements.txt otherwise you will get the default
(probably GPU).

## Installation

Run `python3 ./setup.py bdist_wheel` to create `dist/DicomPixelAnon-1.0.0-py3-none-any.whl`

Run `python3 ./setup.py install` to install (including dependencies) into your python site-packages
(whether that be global or inside a current virtualenv).

Note that the version number is read from version.txt in the current directory.

## Testing

Test all modules:

```
pytest DicomPixelAnon/*.py
```

Test each module individually, for example:
```
python3 -m pytest DicomPixelAnon/ocrengine.py
python3 -m pytest DicomPixelAnon/nerengine.py
```

## Usage

For example:

```
from DicomPixelAnon import ocrengine
from DicomPixelAnon import nerengine
```

## dicomimage.py

Defines the class DicomImage for holding image frames from a DICOM file.

## dicomrectdb.py

Defines the class DicomRectDB for storing DICOM rectangles in a database.

## filelist.py

Defines the class FileList for storing a list of filenames.

## nerengine.py

Defines the class NER as a wrapper around multiple NLP/NER libraries.

## ocrengine.py

Defines the class OCR as a wrapper around multiple OCR libraries.

## rect.py

Defines classes `Rect`, `DicomRect` and `DicomRectText`
to hold rectangles, rectangles in DICOM image frames, and
rectangles in DICOM image frames with OCR text.

## stanford_ner.py

A wrapper around the Stanford NER library.

## torchmem.py

A utility to import the torch library and set the amount of memory used.

