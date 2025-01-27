#!/bin/bash
# Run OCR on a DICOM file, save the rectangles to a database, then
# produce a redacted DICOM file by redacting the rectangles from the database.
# Usage: -o output input...
# XXX need to implement an allowlist for safe words found by OCR, e.g. "AP ERECT"

# Options
output=""
relative=""
dbdir=""
prog=$(basename $0)
options="cfo:r:D:"
usage="usage: $prog [-D db_dir] [-c] [-f] [-r relative_dir] -o output  input..."

# Configuration, choose which OCR algorithm
ocr_tool="easyocr"
keep_rects=1
opt_forms=""
opt_compression=""

while getopts "$options" var; do
    case $var in
        c) opt_compression="--compress";;
        f) opt_forms="--forms";;
        o) output="$OPTARG";;
        r) relative="--relative $OPTARG";;
        D) dbdir="$OPTARG";;
        ?) echo "$usage";
            echo "-D is the path to the database directory"
            echo "-c to compress the output files"
            echo "-f to detect scanned forms"
            echo "-o is the path to the output directory"
            exit 1;;
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

# Get a list of all rectangles of text into the database,
# but ignore any text on an allowlist. Detect scanned forms
# and add a rectangle the size of the whole image to the database.
# People might need to know all regions that are redacted so
# add UltraSound regions (and any text found within them) to the db.
# (i.e. use --use-ultrasound-regions not --except-ultrasound-regions).
echo "$(date) ${prog} Running OCR on $@"
dicom_ocr.py --db "${dbdir}" --review $opt_forms --pii ocr_allowlist --use-ultrasound-regions --rects "$@"

# Redact by reading the database, and using UltraSound regions.
# Use the deid rules to pick up any other redaction rules
# (these rules may also include UltraSound regions).
echo "$(date) ${prog} Redacting $input"
dicom_redact.py --db "${dbdir}" \
    --remove-ultrasound-regions \
    --deid $opt_compression \
    --output "${output}" $relative \
    --dicom "$@"

# Append to a record of all rectangles
# Only outputs limited columns (esp. not the ocrtext!)
if [ $keep_rects -eq 1 -a -d "$output" ]; then
    rects_file="$output/rectangles.csv"
    rects_cols="filename,left,top,right,bottom,frame,overlay"
    if [ ! -f "$rects_file" ]; then
        echo "$rects_cols" > "$rects_file"
    fi
    filename_arr=( "$@" )
    join_with_sep() { local d=$1 s=$2; shift 2 && printf %s "$s${@/#/$d}"; }
    filenames=$(join_with_sep "','" "${filename_arr[@]}")
    sqlite3 -csv -separator , \
        -cmd "select $rects_cols from DicomRects where left != -1 and filename in ('$filenames')" \
        "$dbdir/dcmaudit.sqlite.db" >> "$rects_file" < /dev/null
fi

# Tidy up if necessary
if [ "${tmpdir}" != "" ]; then
    rm -fr "${tmpdir}"
fi

exit 0
