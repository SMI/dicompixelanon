# DICOM Tag and Rectangle Database

## Introduction

The database has two tables, one for DicomTags and one for DicomRects.
See the `dcmaudit` document and the `dicom_ocr` and `dicom_redact`
documents for more details.

## Installation

Ensure the `SMI_ROOT` variable is set so that the database can be
written to `$SMI_ROOT/data/dicompixelanon/` This directory can be
overridden with the `--db` option in various applications.

## Usage

To display the database contents
```
dcmaudit.py --dump-database
```
The output is in JSON format with an array of rects and an array of tags.

List the completed images:
```
./dcmaudit.py --dump-database | jq -r '.tags[].filename'
```

List the images with a redaction in an overlay plane:
```
./dcmaudit.py --dump-database | jq -r '.rects[] | select(.overlay > 0) | .filename'
```

You can examine the database using:
```
% sqlite3 dcmaudit.sqlite.db
sqlite> select * from DicomTags;
```

Some utilities are provided to make this slightly easier, see `dbrects.sh`, `dbtags.sh` and `dbtext.sh`

## Database schema

The database is held in `dcmaudit.sqlite.db` but despite sqlite being a 
single-file format it creates two other files with names like:
```
952e4562cd3ebdf5205ee934be4b20f9_DicomRects.table
952e4562cd3ebdf5205ee934be4b20f9_DicomTags.table
```
These files are simply table descriptions created by the python database layer `pydal` and can be ignored.


The tables are defined as below.
Rectangles are defined by top, bottom, left, right, and the number of the overlay frame if applicable. There can be many rectangles defined for any one file.
The DicomTags table holds a mark (if an image has been tagged for closer inspection) or a comment.
Note that the imagetype column holds the string value of the DICOM tag, which includes start and end double quotes, and separators with forward slashes, e.g. "ORIGINAL/PRIMARY" where the quotes are actually included in the table.

```
CREATE TABLE "DicomRects"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "filename" CHAR(512),  -- NB. not UNIQUE
    "top" INTEGER,         -- coordinates all -1 for whole image
    "bottom" INTEGER,
    "left" INTEGER,
    "right" INTEGER,
    "frame" INTEGER,       -- default to -1
    "overlay" INTEGER,     -- default to -1
    "source" INTEGER,      -- deprecated
    "ocr" CHAR(512),       -- deprecated
    "ispii" INTEGER,       -- deprecated
    "sourcepii" INTEGER,   -- deprecated
    "last_modified" TIMESTAMP,
    "last_modified_by" CHAR(512),
    "ocrengine" INTEGER,   -- name of OCR algorithm
    "ocrtext" CHAR(512),   -- found text
    "nerengine" INTEGER,   -- name of NER algorithm
    "nerpii" INTEGER);     -- -1 (unknown), 0 (not), 1 (PII)
);

CREATE TABLE "DicomTags"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "filename" CHAR(512) UNIQUE,
    "mark" CHAR(1),        -- actually boolean
    "comment" CHAR(512),
    "modality" CHAR(512),  -- DICOM tag
    "imagetype" CHAR(512), -- DICOM tag
    "manufacturermodelname" CHAR(512),
    "burnedinannotation" CHAR(512),
    "rows" CHAR(512),
    "columns" CHAR(512),
    "last_modified" TIMESTAMP,
    "last_modified_by" CHAR(512)
);
```
