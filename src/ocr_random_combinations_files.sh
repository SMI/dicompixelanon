#!/bin/bash
# Run OCR on a random selection of 3 files taken from each combination.
# Also runs a NER algorithm.
# Splits file list into batches of 10 so
# Usage: list of modalities, e.g.  DX CR
# Input:  extract_BIA_from_${modality}.csv_filepos.csv
# Output: ocr_random_combinations_files.sh_${modality}.csv
# Configuration:
#    choose OCR and NLP algorithms
#    use --rects if you want every OCR rectangle in the output
#    use --no-overlays to ignore all overlay frames
# NOTE: picks 20 files from each combination.
# NOTE: runs in batches of 20 in case OCR has memory leak(?)
# which means the CSV header will be inserted every 20 images :-(

modality="CR"
OCR="easyocr"           # tesseract or easyocr
NLP="flair"             # spacy or flair
FILTER="ORIGINAL/PRIMARY"
prog=$(basename $0)
# Where to look for input CSV files and write output log:
#root=$SMI_ROOT/MongoDbQueries/BurnedInAnnotations
root=$(pwd)

if [ "$1" == "" ]; then modality="CR"; fi

for modality; do

  log=${prog}_${modality}.csv

  touch $log

  ./random_combinations_files.py -n 20 -F "${FILTER}" $root/extract_BIA_from_${modality}.csv_filepos.csv | \
      xargs -n 20 ./pydicom_images.py -v --ocr ${OCR} --pii ${NER} --rects -i   >> $log

done
