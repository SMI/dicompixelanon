# Dicom Pixel Remover

Replaces the pixel data in a set of DICOM files with blank images.

Convert all DICOM files recursively under the input directory
into the same file hierarchy under the output directory
such that all pixel data is replaced by zero bytes
(and compressed using RLE which compresses zeros very well)
and the UIDs replaced by hashed values. The directory names
and file names are also replaced by their hashed values.
This make a totally anonymous dataset which could be used as
synthetic data.

Notes:
* images are replaced with blank images of exactly the same
shape and size (dimensions and number of frames)
* does not change any overlay frames
* input files should already have passed through the CTP
anonymiser to remove tags with possible PII

## Usage

```
-d = debug
-c = compress using RLE (lossless) otherwise uncompressed
-i inputdir (will be searched recursively)
-o outputdir (will be searched recursively)
```
