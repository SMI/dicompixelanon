# Redact regions in DICOM images

The `dicom_redact.py` tool can redact (blank out) rectangular regions
from images in DICOM files. Unlike most redaction software, it can
target specific image frames, or overlays, or frames of overlays, and
it doesn't require overlays to be burned onto the main image.

Other tools: CTP and pydicom-deid both allow rectangles to be redacted
based on a "script" or configuration file, which matches the values in
DICOM tags to determine which rectangles to redact. Both have limitations
on which image frames can be redacted, and how well the DICOM tags match
those in the configuration file.

This tool can redact rectangles in five ways:
* from a list specified on the command line
* from a list provided in a CSV file, for example the output from
 `pydicom_images.py` running OCR on DICOM files
* from a list stored in a database, for example the output from
 `dcmaudit.py` with manually marked-up DICOM files, or from `dicom_ocr.py`
* from a set of regions defined in the metadata of an UltraSound DICOM
* from rules which define rectangles for files whose metadata tags
match specific criteria.

It should be noted that all of these tools can be used standalone or
in conjunction with other tools, for example you can use CTP and/or
pydicom-deid as well.

## Preserving non-PII text

The purpose of redaction is to remove PII, but some text rectangles
may contain no PII and in fact may be worth keeping, so this tool
has an allow-list to preserve specific fragments of text. The allow-
list is currently a set of regular expressions which is read from a
text file in `$SMI_ROOT/data/dicompixelanon/ocr_allowlist_regex.txt`
If the text in a rectangle exactly matches the regex then the
rectangle is not redacted.

## High-bit overlays

This tool also has the ability to remove any overlays which are
embedded in the high-bits of the image pixels. The normal CTP anonymisation
process can remove overlays but it only removes the 60xx group of DICOM
tags which in most cases is sufficient, but it doesn't remove high-bit
overlays. This tool can do that job to fully clean a DICOM file.

## NOTE!

The utility has to decompress the image (if compressed), but it
does not recompress the image again afterwards using the same
compression scheme so the file size may increase.
Some other redaction tools have the ability to preserve
most of a lossy-JPEG-compressed image except for the redacted blocks,
but those tools do not handle overlays at all. Lossless compression is
an option but the only scheme supported is JPEG2000Lossless.

## Usage:

```
  -v, --verbose         Verbose
  --db DB               database directory to read rectangles (needs --dicom)
  --csv CSV             CSV path to read rectangles (redacts all files in csv if --dicom not used)
  --compress            Compress the output using lossless JPEG2000
  --dicom DICOM         DICOM path to be redacted
  -o OUTPUT, --output O Output DICOM dir or filename (created automatically if not specified)
  --relative-path RELATIVE
                        Output DICOM dir will be relative to input but with this prefix removed from input path
  --remove-high-bit-overlays
                        remove overlays in high-bits of image pixels
  --remove-ultrasound-regions
                        remove around the stored ultrasound regions
  --deid                Use deid-recipe rules to redact
  --deid-rules          Path to file or directory containing deid recipe files (deid.dicom.*)
  -r [RECTS ...], --rect [RECTS ...]
                        rectangles x0,y0,x1,y1 or x0,y0,+w,+h; ...
```

Use `--db` to read rectangles from a database, e.g. from `dcmaudit`,
or `--csv` to read rectangles from a CSV file, e.g. from `pydicom_images`,
or specify the rectangles directly with `--rect`. In all cases you can
specify `--dicom` to find only that path in the database/CSV.

### Rectangles

The `--rect` option can have multiple rectangle arguments after it
(if it's specified last on the command line) or you can specify multiple
rectangles in a single argument by separating them with a semicolon.
The format is either `x0,y0,x1,y1` (left,top,right,bottom) or
`x0,y0,+w,+h` (left,top and width,height). Brackets around the whole
set are optional. Example: `(10,10,20,20);(30,30,+10,+10)`

### Ultrasound Regions

If the image is an UltraSound and has a set of regions defined within
its metadata ("SequenceOfUltrasoundRegions") then the `--remove-ultrasound-regions`
option will redact all of the areas outside of those regions (the regions
are assumed to be defining the useful parts of the image).

### Rule-based redaction

To redact based on rules which match DICOM metadata tags give the `--deid`
option which by default will read rules from `$SMI_ROOT/data/deid/deid.dicom.*`
files. The `--deid-rules` option can be used to specify different files.
See the [deidrules](deidrules.md) document for more details.

Note that rule-based redaction has to be applied to every frame and every
overlay in a file because the rules have no way to specify individual frames.

Rules can also be used for redacting around Ultrasound Regions, or you can use the
`--remove-ultrasound-regions` option instead.

### Rectangles from a CSV file

If reading from a CSV and no DICOM has been specified then all filenames listed in
the CSV will be redacted.

The CSV file is expected to have (at least) these columns, in any order:
```
filename,frame,overlay,left,top,right,bottom
```
Other columns in the CSV file are ignored.

The database directory is typically `$SMI_ROOT/data/dicompixelanon` and the
filename is `dcmaudit.sqlite.db` as it is currently in sqlite format.
The database has a table called `DicomRects` having columns with
the same names as for CSV files above.
Other columns and tables in the database are ignored.

### Output filename

The output filename can be specified for a single input file.
If not specified then the output filename is the same as the input
filename but with `.dcm` removed and `.redacted.dcm` appended.
If that directory is not writable then the current directory is used.
The `--output` option can also refer to a directory in which case
the output files are written there, again with `.dcm` replaced with
`.redacted.dcm`. A relative path can be specified with the `--relative`
option which is best explained with an example:
```
input:     /beegfs/path/study/series/file.dcm
--output   /path/to/output
--relative /beegfs/path
will create:
/path/to/output/study/series/file.dcm
```

### Removing only the high-bit overlays

If you only want to remove high-bit overlays (not redact rectangles),
then only use the `--remove-high-bit-overlays` and `--dicom` options.
This may be useful when you've already asked CTP to remove the overlay
tags and just want to clear out the high bits of the pixel data.

## Troubleshooting

Use the `-v` option for more information on what is happening.

If the OCR is finding rectangles but the output image is not redacted
then check if the DICOM is colour (RGB photometric) or if the DICOM has
multiple image frames. If so then then choice of array slice might be
incorrect in the function `redact_rectangles_from_image_frame`.

If the output is corrupt or the DICOM tags are misrepresenting the content
then check the code in `dicom_redact.py` especially the function
`mark_as_uncompressed`. There may be other tags that need to be altered,
besides the Transfer Syntax.
