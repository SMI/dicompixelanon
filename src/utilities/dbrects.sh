#!/bin/bash
# Display the DicomRects table
# Usage: [-r|-a|-s] database
#  where database may be:
#    path to database directory
#    database file itself
# -a = extract all rows
# -r = extract only valid rectangles
# -s = extract only summary rows

param="all"
while getopts ars var; do
    case $var in
    a) param="all";;
    r) param="rects";;
    s) param="summary";;
    ?) echo "usage: $0 [-a|-r|-s] dbdir" >&2; exit 1;;
    esac
done
shift $(($OPTIND - 1))

db="$1"
if [ "$db" == "" ]; then
    db=$SMI_ROOT/data/dicompixelanon
fi
if [ -d "$db" ]; then
    db="$db"/dcmaudit.sqlite.db
fi

case $param in
    "all")     sql="select * from DicomRects";;
    "rects")   sql="select * from DicomRects where left != -1";;
    "summary") sql="select * from DicomRects where left = -1";;
esac

sqlite3 -csv -header -separator , -cmd "$sql" "$db" < /dev/null
