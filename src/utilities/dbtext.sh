#!/bin/bash
# Display the OCR text from the DicomRects table
# Usage: database
#  where database may be:
#    path to database directory
#    database file itself
db="$1"
if [ "$db" == "" ]; then
    db=$SMI_ROOT/data/dicompixelanon
fi
if [ -d "$db" ]; then
    db="$db"/dcmaudit.sqlite.db
fi
sqlite3 -separator , -cmd 'select ocrtext from DicomRects where ocrtext != "" and left != -1' "$db" < /dev/null
