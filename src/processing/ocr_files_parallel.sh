#!/bin/bash
# Read extract_BIA_from_XX.csv_filepos.csv  having a list of filename-pointers,
# get a random N filenames from the corresponding extract_BIA_from_XX.csv
# split into two lists,
# start two OCR processes in parallel, writing to a temporary DB directory
# extract the resulting DB into a CSV file.
# You can actually run dcmaudit.py on the database directory to check detection.

modality="PX"
numPerCombo=3

if [ "$1" != "" ]; then
    modality="$1"
fi
inputfile="extract_BIA_from_${modality}.csv_filepos.csv"

# Use a different database each time
now=$(date +%Y%m%d_%H%M)
dbdir=db.${modality}.${now}
mkdir -p $dbdir
echo "Database is in $dbdir"

# Find programs
export PATH=${PATH}:.:../applications:../utilities
# Use latest devel library
export PYTHONPATH=../library/

# Get a selection of filenames from the random list of filename positions
echo "Getting $numPerCombo filenames per combination"
random_combinations_files.py -n $numPerCombo "$inputfile" > $dbdir/files.txt

# Split list into two
numlines=$(wc -l < $dbdir/files.txt)
halfnum=$(expr $numlines / 2)
plusone=$(expr $halfnum + 1)
head -$halfnum $dbdir/files.txt > $dbdir/filesA.txt
tail -n +$plusone $dbdir/files.txt > $dbdir/filesB.txt

# Run OCR in parallel
echo "Starting OCR of $numlines files..."
dicom_ocr.py -d --db $dbdir --rects $(cat $dbdir/filesA.txt) > $dbdir/logA 2>&1 &
sleep 2
dicom_ocr.py -d --db $dbdir --rects $(cat $dbdir/filesB.txt) > $dbdir/logB 2>&1 &
wait
echo "Check $dbdir/logA,B for errors"

# Create CSV file from database (not necessary but might be useful)
echo "Creating $dbdir/db.csv"
dbrects.sh $dbdir > $dbdir/db.csv
