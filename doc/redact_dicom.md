# Redact DICOM images

The `redact_dicom.py` tool can redact (blank out) rectangular regions
from images in DICOM files. Unlike most redaction software, it can
target specific image frames, or overlays, or frames of overlays, and
it doesn't require overlays to be burned onto the main image.

NOTE! This is still a work in progress - the redaction functionality is
present and tested, but the interface is still being developed. Reading
a list of rectangles from the command line, or a configuration file, or
a database is intended.

Other work: CTP and pydicom-deid both allow rectangles to be redacted
based on a "script" or configuration file, which matches the values in
DICOM tags to determine which rectangles to redact. This tool can either
take on that functionality or parts of this tool can be integrated into
pydicom-deid for example.

NOTE! The utility has to decompress the image (if compressed), but it
does not (yet) recompress the image again afterwards, so the file size
may increase. Some other redaction tools have the ability to preserve
most of a lossy-JPEG-compressed image except for the redacted blocks,
but those tools do not handle overlays at all. Compression, and lossy
compression support can of course be added to this tool later.
