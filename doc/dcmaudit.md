# DICOM Audit

## Introduction

The DICOM Audit tool helps to visualise all of the image frames contained
within a DICOM file to assist with finding text burned into the pixel data.
If particularly sensitive text is found it can be redacted, and the
coordinates of a redaction rectangle can be stored in a database.

One important feature of this tool is that it can display all of the frames
in a file, all of the overlays separately, and all of the frames of each overlay.
Some tools apply overlays onto an image frame, but this is not ideal.

There are already tools to do redaction but they are cumbersome to use,
and they often do not work on an individual frame level.

Note that only raster graphic overlays are supported.

## Installation

See requirements.txt, `pip install -r requirements.txt`

Note that on CentOS-7 the maximum version of pytesseract is 0.3.8
because after that it needs python 3.7 and Pillow 8. Ensure you are
installing into a python3 environment.

Ensure the `SMI_ROOT` variable is set so that the database can be
written to `$SMI_ROOT/data/dicompixelanon/` This directory can be
overridden with the `--db` option.

If necessary ensure the `TESSDATA_PREFIX` variable is set so that
Tesseract can find `tessdata/eng.traineddata`, for example
`TESSDATA_PREFIX=$SMI_ROOT/data/tessdata`

Also ensure that the `PATH` variable contains the path to the `tesseract`
program.  Try installing `tesseract-ocr` if not, or download from
https://github.com/second-state/OCR-tesseract-on-Centos7/raw/main/tesseract.tar.gz


## Usage

Files to be redacted are specified on the command line:

```
usage: dcmaudit.py [-h] [-d] [-q] [--db dir] [--dump-database] [--review]
                   [-i [INFILES [INFILES ...]]]
optional arguments:
  -h, --help            show this help message and exit
  -d, --debug           debug
  -q, --quiet           quiet
  --db directory        database directory
  --dump-database       show database content in JSON format
  --review              review files already marked as done
  -i [INFILES [INFILES ...]] list of DICOM filenames, or a
     CSV filename to get the filenames from the DicomFilePath column
```

A rectangle is displayed and can be dragged around the image.
If you drag from the middle of the rectangle it will stick inside the image.
When the rectangle covers the area where text might be found it can be
marked as such and the information stored in a database.

Files can be tagged, meaning that this image needs further investigation.
The tag is stored in a database so all tagged images can be reviewed later.
Tags are shown as `[X]` before the filename.

Files can be marked as "done" when they have been fully inspected.
You can mark rectangles, which are saved instantly in the database, but
only when you explicitly mark the whole file as inspected will that
flag be saved.  This allows you to come back later and review a file.
Once a file has been marked as done then it won't be shown again
(unless the `--review` option is used).
Only files marked as done should be considered when making use of
the redaction rectangles. Likewise only rectangles from images marked
as done will be suggested as possible rectangles as the metadata
for comparison is not written until images are marked as done.

Display of frame/overlay:
Images have multiple frames, but then after all the frames come the overlays, and
each overlay can have multiple frames.
The overlay number is not shown until you have stepped through all the frames first.

![screenshot](../resources/images/dcmaudit.png)

To ease the process of defining redaction rectangles, when an image is
displayed the database is queried to find other images with similar metadata.
If they have redaction rectangles then they are displayed on the current image
using a rectangle with a cross through it. These suggested rectangles can be
applied to the current image one at a time by right-clicking on the rectangle
or all at once use the 'A' key.

### Keyboard shortcuts

```
n - move to Next frame (or Next overlay frame)
p - move to Previous frame (or Previous overlay frame)
f - Fast-forward to next overlay (skip rest of current overlay frames)
N - mark the current image as 'done' in the database then move to the Next image
Esc - move to next image, do not mark current image as done
P - move to the previous image, do not mark current image as done
i - Display some DICOM tag information
o - Display the result of running OCR on the image
r - redact the image within the rectangle and store this rectangle in the database
A - apply all suggested rectangles to the current frame
t - tag this image as needing further investigation and store the tag in the database.
q - quit
 N.B. if you quit, but haven't marked done with N, then any rectangles
 will be saved but the image itself will not be marked as done so will
 be shown again for editing next time.
```

## Workflow

* Select a set of images, keep their filenames
* Start `dcmaudit.py -i $(cat filenames)`
* Use `n` to step through all the frames
* If you see any PII then move the redaction rectangle to cover it and press `r`
* If you see any crossed rectangles which cover possible PII then right-click on them (or use `A` if there's a lot)
* At the last frame, if you are happy with all redactions, press `N` to finish this image
* If you have any concerns about this image then press `t` to tag it for future inspection
* If there are hundreds of frames and no possibility of PII then use `f` to fast-forward
* When you reach the last image press `q` to quit.

## Debugging

To see the database use the `--dump-database` option. The output is in JSON format
with an array of rects and an array of tags.

List the completed images:
```
./dcmaudit.py --dump-database | jq -r '.tags[].filename'
```

List the images with a redaction in an overlay plane:
```
./dcmaudit.py --dump-database | jq -r '.rects[] | select(.overlay > 0) | .filename'
```

To see debugging info add the `-d` option.

To manually extract and check the image frames and overlay frames:

```
usage: pydicom_images.py [-v] [-x] [-i] [-f FORMAT] files...
  -v, --verbose         more verbose
  -x, --extract         extract PNG files
  -i, --identify        identify only
  -f FORMAT, --format FORMAT
                        output format png or tiff
```

## Database schema

See the `dicomrectdb.md` document.

## Future work

Add way to review all tagged images (i.e. find all those in the database which have been tagged as needing further review).

Add UI for entering comments.

The system should learn which image types have text in specific locations
and suggest redaction rectangles based on previously taught images.
It does this for images where the metadata is identical but could be improved.
At the moment it only suggests rectangles where the frame and overlay are the same.
Maybe it could overlay all of them?
