#!/bin/bash
# Run OCR on a DICOM file, save the rectangles to a database, then
# produce a redacted DICOM file by redacting the rectangles from the database.
# Usage: -o output input...
# XXX need to implement an allowlist for safe words found by OCR, e.g. "AP ERECT"

# Options
output=""
dbdir=""
prog=$(basename $0)
options="o:D:"
usage="usage: $prog [-D db dir] -o output  input..."
# Configuration, choose which OCR algorithm
ocr_tool="easyocr"

while getopts "$options" var; do
    case $var in
        o) output="$OPTARG";;
        D) dbdir="$OPTARG";;
        ?) echo "$usage"; exit 1;;
	esac
done
shift $(($OPTIND - 1))
if [ "$output" == "" ]; then
	echo "$usage - the -o option is mandatory" >&2
	exit 1
fi

# Temporary! PATH for testing from current directory
export PATH=${PATH}:.

# Temporary directory for database if needed
if [ "$dbdir" == "" ]; then
	tmpdir="/tmp/dicom_pixel_anon.$$"
	mkdir -p "${tmpdir}"
	dbdir="${tmpdir}"
fi

# exit straight away if any commands fail
set -e

# Get a list of all rectangles into the database
echo "$(date) ${prog} Running OCR on $@"
dicom_ocr.py --db "${dbdir}" --review --rects "$@"

# Redact by reading the database
for input in "$@"; do
	echo "$(date) ${prog} Redacting $input"
    dicom_redact.py --db "${dbdir}" --dicom "${input}" --output "${output}"
done

# Tidy up if necessary
if [ "${tmpdir}" != "" ]; then
	rm -fr "${tmpdir}"
fi

exit 0
