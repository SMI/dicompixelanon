#!/bin/bash
# Run OCR on a DICOM file, save the rectangles to a database, then
# produce a redacted DICOM file by redacting the rectangles from the database.
# Usage: input.dcm output.dcm
# XXX the startup time for pydicom_images is long so it would be better if we
# could OCR many files at once in which case we would have to generate output filenames.
# XXX need to implement an allowlist for safe words found by OCR, e.g. "AP ERECT"

input="$1"
output="$2"

export PATH=${PATH}:. # temporary for testing from current directory

csv=tmp.$$

# exit straight away if any commands fail
set -e

# Cannot redact the input file directly so copy it first
cp "$input" "$output"

# Get a list of all rectangles
pydicom_images.py --no-overlays --csv --rects --ocr easyocr $input > $csv

# Convert the CSV into the database (not yet implemented into the previous step)
dicomrect_csv_to_db.py --csv $csv

# Redact by reading the database
redact_dicom.py --db --dicom $output

rm -f $csv
