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

This tool can redact rectangles in four ways:
* from a list specified on the command line
* from a list provided in a CSV file, for example the output from
 `pydicom_images.py` running OCR on DICOM files
* from a list stored in a database, for example the output from
 `dcmaudio.py` with manually marked-up DICOM files
* from a set of regions defined in an UltraSound DICOM

It should be noted that all of these tools can be used standalone or
in conjunction with other tools, for example you can use CTP and/or
pydicom-deid as well.

This tool also has the ability to remove any overlays which are
embedded in the high-bits of the image pixels. The normal CTP anonymisation
process can remove overlays but it only removes the 60xx group of DICOM
tags which in most cases is sufficient, but it doesn't remove high-bit
overlays. This tool can do that job to fully clean a DICOM file.

NOTE! The utility has to decompress the image (if compressed), but it
does not (yet) recompress the image again afterwards, so the file size
may increase. Some other redaction tools have the ability to preserve
most of a lossy-JPEG-compressed image except for the redacted blocks,
but those tools do not handle overlays at all. Compression, and lossy
compression support can of course be added to this tool later.

## Usage:

```
  -v, --verbose         Verbose
  --db DB               database directory to read rectangles (needs --dicom)
  --csv CSV             CSV path to read rectangles (redacts all files in csv if --dicom not used)
  --dicom DICOM         DICOM path to be redacted
  -o OUTPUT, --output O Output DICOM dir or filename (created automatically if not specified)
  --remove-high-bit-overlays
                        remove overlays in high-bits of image pixels
  --remove-ultrasound-regions
                        remove around the stored ultrasound regions
  -r [RECTS ...], --rect [RECTS ...]
                        rectangles x0,y0,x1,y1 or x0,y0,+w,+h; ...
```

Use `--db` to read rectangles from a database, e.g. from `dcmaudit`,
or `--csv` to read rectangles from a CSV file, e.g. from `pydicom_images`,
or specify the rectangles directly with `--rect`. In all cases you can
specify `--dicom` to find only that path in the database/CSV. If reading
from a CSV and no DICOM has been specified then all filenames listed in
the CSV will be redacted.

If the image is an UltraSound and has a set of regions defined within
its metadata ("SequenceOfUltrasoundRegions") then the `--remove-ultrasound-regions`
option will redact all of the areas outside of those regions (the regions
are assumed to be defining the useful parts of the image).

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

The output filename can be specified for a single input file.
If not specified then the output filename is the same as the input
filename but with `.dcm` removed and `.redacted.dcm` appended.
If that directory is not writable then the current directory is used.
The `--output` option can also refer to a directory.

## Rectangles

The `--rect` option can have multiple rectangle arguments after it
(if it's specified last on the command line) or you can specify multiple
rectangles in a single argument by separating them with a semicolon.
The format is either `x0,y0,x1,y1` (left,top,right,bottom) or
`x0,y0,+w,+h` (left,top and width,height). Brackets around the whole
set are optional. Example: `(10,10,20,20);(30,30,+10,+10)`

## Removing only the high-bit overlays

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
