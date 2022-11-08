# review_SR_report.py

A simple program to load a report created by the CohortPackager
(as a result of running IsIdentifiable)
which contains a list of instances of PII found in DICOM files.

It allows a word or phrase to be chosen and displays a list of files
which contained that text.

Each file can be viewed and marked as a False Positive or as PII.

Upon exit the lists are written to files.

![Screenshot](review_SR_report.png)

## Usage

```
review_SR_report.py -r report.csv
```

## Input report format

Currently the input report is expected to be in the format produced by
IsIdentifiable (although it can be created by other programs if required).

The CSV file should have fields `Word, Classification, ProblemValueWindow, Offset,Resource`.

The `Word` is the fragment of text which is suspected to be PII.
The `Classification`, `ProblemValueWindow` and `Offset` are not used.
The `Resource` is the filename of the SR.

## Results

The results are saved into files in the `../data` directory relative to the program directory:
* reviewed_as_false_positives.csv - the particular word highlighted is not PII, it's a false positive
* reviewed_as_PII.csv - the particular word highlighted is definitely PII
* reviewed.csv - marked as "reviewed" but no indication of whether words were PII or not. May be just used to indicate "don't show me this file again"?

Note that the same document can be reported multiple times,
where some words may be found to be PII and other words may be found to be false positives,
so the filename can appear in both output files.
When considering whether to release or quarantine the file the PII results should be given priority.
