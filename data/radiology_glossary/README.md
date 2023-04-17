# Radiology Glossary Data

Glossary of medical abbreviations and acronyms used in radiology. Source: [radiopaedia.org](https://radiopaedia.org/articles/medical-abbreviations-and-acronyms-a?lang=gb).

Datafiles in this directory:
- [`glossary.json`](glossary.json): Dictionary of abbreviations and their meanings, parsed from radiopeadia.org. Currently only the keys of the dictionary are used for defining allowlisting rules for OCR redaction (see [`build_allowlist.py`](../../src/utilities/build_allowlist.py)). Could be used in the future to recogise abbreviations in OCR analysis and add them (and potentially their meaning) as metadata. Note that there is often more than one meaning for an abbreviation.
- [`raw/glossary_LETTER.html`](raw/): Not tracked as it would only be needed to build [`glossary.json`](glossary.json) from scratch which shouldn't be necessary. Running [`build_allowlist.py`](../../src/utilities/build_allowlist.py) with option `--fetchbuild` fills the `raw/` directory with HTML files, one for each page of the glossary on radiopaedia.org.
  
