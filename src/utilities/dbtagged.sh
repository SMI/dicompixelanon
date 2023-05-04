#!/bin/bash
# Display the filenames from the DicomTags table
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
sqlite3 -cmd 'select filename from DicomTags' "$db" < /dev/null
