#!/bin/bash
# Display the DicomRects table
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
sqlite3 -separator , -cmd 'select * from DicomRects' "$db" < /dev/null
