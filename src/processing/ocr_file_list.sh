#!/bin/bash
# Run OCR on a list of filenames.
# Also runs a NER algorithm.
# Splits file list into batches of 20 so
# Usage: filename where file contains a list of DICOM filenames
# Configuration:
#    choose OCR and NLP algorithms
#    use --rects if you want every OCR rectangle in the output
#    use --no-overlays to ignore all overlay frames
# NOTE: runs in batches of 20 in case OCR has memory leak(?)

OCR="easyocr"           # tesseract or easyocr
NER="flair"             # spacy or flair
prog=$(basename $0)

for file; do

  log=${prog}_$$.csv

  touch $log

  cat "$file" | \
      xargs -n 20 ./pydicom_images.py -v --ocr ${OCR} --pii ${NER} --rects -i  >> $log

done
