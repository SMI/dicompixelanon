# deid rules

The rules used for redacting DICOM images are based on pydicom deid's
rules which in turn are based on CTP's rules.

These rules can be created manually or by using `dcmaudit.py` (or even
`dicom_ocr.py`). Save the rectangles to a database and then use the utility
`dbrects_to_deid_rules.py` to create rules.

Rules specify a set of DICOM metadata tags, all of which must match,
and then a set of rectangles to be redacted.

Rules can also be used to derive a set of rectangles from Ultrasound
images if they contain the DICOM tag SequenceOfUltrasoundRegions.

Note that rule-based redaction has to be applied to every frame and every
overlay in a file because the rules have no way to specify individual frames.

## Redaction rules

This example redacts XA images of size 1024x1024 if they have two
private tags which are known to be used by Ziehm Vision machines.
This requires the latest verision of pydicom/deid that has support
for private tags. Note how the `contains` rule can be a regular expression.

```
LABEL Ziehm X-Rays 1024
  contains Modality XA
  + contains 0x00190010 ZIEHM_1.0
  + contains 0x00191201 Fluoro|LowDose|Snapshot|HiQ|LPK|HLC
  + equals Rows 1024
  + equals Columns 1024
  coordinates 0,0,196,148
  coordinates 0,940,189,1006
  coordinates 706,0,1023,66
```

## Ultrasound regions

This example will return rectangles if present in SequenceOfUltrasoundRegions tag.
Note that it uses `keepcoordinates` so that the deid library function knows to
invert them before returning rectangles to be redacted.

Note one difference from the `pydicom/deid` rules is that there is no need
for an inverse mask to be specified using `coordinates all` when using Ultrasound
regions because all coordinates specified using `keepcoordinates` will be
inverted automatically.

```
LABEL Clean Areas Outside Ultrasound Regions
    present SequenceOfUltrasoundRegions
    keepcoordinates from:SequenceOfUltrasoundRegions
```


# References

* CTP metadata anonymiser
  - rules https://github.com/SMI/SmiServices/blob/master/data/ctp/ctp-whitelist.script
* CTP pixel anonymiser
  - docs   https://mircwiki.rsna.org/index.php?title=The_CTP_DICOM_Pixel_Anonymizer
  - rules  https://github.com/johnperry/CTP/blob/master/source/files/scripts/DicomPixelAnonymizer.script
* pydicom deid
  - docs   https://pydicom.github.io/deid/user-docs/recipe-filters/
  - and https://pydicom.github.io/deid/getting-started/dicom-pixels/
  - rules  https://github.com/pydicom/deid/tree/master/deid/data
