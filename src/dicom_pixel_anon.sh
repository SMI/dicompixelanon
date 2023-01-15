#!/bin/bash
# Run OCR on a DICOM file, save the rectangles to a database, then
# produce a redacted DICOM file by redacting the rectangles from the database.
# Usage: input.dcm output.dcm
# XXX the startup time for pydicom_images is long so it would be better if we
# could OCR many files at once in which case we would have to generate output filenames.
# XXX need to implement an allowlist for safe words found by OCR, e.g. "AP ERECT"

# Options
input="$1"
output="$2"

# Configuration
ocr_tool="easyocr"

export PATH=${PATH}:. # temporary for testing from current directory

# Temporary files
tmpdir="/tmp/dicom_pixel_anon.$$"
mkdir -p "${tmpdir}"
csv="${tmpdir}/rects.csv"
dbdir="${tmpdir}"

# exit straight away if any commands fail
set -e

# Get a list of all rectangles into the database
#pydicom_images.py --no-overlays --csv --rects --ocr easyocr $input > $csv
#pydicom_images.py --csv --rects --ocr "${ocr_tool}" "${input}"  >  "${csv}"
dicom_ocr.py --db "${dbdir}" --review --rects "${input}"

# Redact by reading the database
dicom_redact.py --db "${dbdir}" --dicom "${input}" --output "${output}"

rm -fr "${tmpdir}"
