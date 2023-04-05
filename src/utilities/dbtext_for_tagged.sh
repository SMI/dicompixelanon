#!/bin/bash
# Display the rectangles from DicomRects for files tagged in the DicomTags table
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

# To get the OCR text from files which you tagged:
sql='SELECT DicomTags.ocrtext FROM DicomTags
     INNER JOIN DicomRects ON DicomTags.filename = DicomRects.filename'

# To get the filename of tagged files where the rectangle is
#  very large but the detected text is small:
sql='SELECT DicomRects.filename FROM DicomTags 
     INNER JOIN DicomRects ON DicomTags.filename = DicomRects.filename 
     WHERE DicomRects.ocrtext != "" 
       AND DicomRects.left != -1 
       AND (DicomRects.right-DicomRects.left)*(DicomRects.bottom-DicomRects.top) > 3000 * LENGTH(DicomRects.ocrtext)'

# Run the SQL
sqlite3 -csv -header -separator , -cmd "$sql"  "$db" < /dev/null
