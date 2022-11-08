#!/bin/bash
# Filter the output from the OCR step
# to get only the files where NO text was detected by OCR
# in any of the image frames (ignoring any text in overlays).
# We already know from the ocr script that these are 
# ORIGINAL/PRIMARY because we filtered on that before doing OCR.

modality="$1" # eg. CR or DX

in="ocr_random_combinations_files.sh_${modality}.csv"
out="ocr_random_combinations_files.sh_${modality}.csv.no_ocr_text.csv"

# Header only once
grep '^filename' $in | head -1 > $out

# 1. filter out only genuine rows (those with filenames)
# 2. filter any frame number,no overlay,ORIGINAL/PRIMARY,no OCR text,flair
grep /beegfs $in | \
    grep ',[0-9]*,-1,ORIG.*-1,-1,-1,-1,,flair' >> $out
