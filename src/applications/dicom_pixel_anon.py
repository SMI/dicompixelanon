#!/usr/bin/env python3
# Run OCR on DICOM images and optionally also NER to detect PII,
# save the rectangles to a database,
# then redact those rectangles from the DICOM files.
# Finally a CSV file listing the rectangles is written to the
# output directory, but without the actual PII text.
# If an output file already exists then it is first renamed,
# and then deleted if the redacted file is saved successfully.
# This means the output directory could be the same as the input.
# Note that you probably also want to use the relative option so
# that the CSV file does not contain full paths.
# e.g. PYTHONPATH=../library/ \
# ./dicom_pixel_anon.py --db . --use-ultrasound-regions --rects --deid \
#   -o ./output/ --relative --write-csv ./output/rectangles.csv \
#   ../../data/sample_dicom/US-GE-4AICL142.dcm
# 
# TODO: change all errors to raise exceptions
# TODO: use allowlist from database?
# NOTE:
#   overlays may be smaller than their images. Rectangle coordinates
#     are within the overlay, not relative to the original image, so
#     if you want to use image coordinates you'll need to subtract
#     the overlay origin coordinate.

import argparse
import csv
import logging
import os
import pydicom
from DicomPixelAnon.ocrengine import OCR
from DicomPixelAnon.nerengine import NER
from DicomPixelAnon.dicomrectdb import DicomRectDB
from DicomPixelAnon import deidrules
import dicom_ocr
import dicom_redact

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='DICOM image OCR and NER')
    parser.add_argument('-v', '--verbose', action="store_true", help='more verbose (show INFO messages)')
    parser.add_argument('-d', '--debug', action="store_true", help='more verbose (show DEBUG messages)')
    parser.add_argument('--ocr', action='store', help='OCR using "tesseract" or "easyocr"', default='easyocr')
    parser.add_argument('--db',  action="store", help='output to database directory (or specify "default")', default=False)
    parser.add_argument('--pii', action='store', help='Check OCR output for PII using "spacy" or "flair" or "stanford" or "stanza" (add ,model if needed)', default=None)
    parser.add_argument('--use-ultrasound-regions', action='store_true', help='collect rectangles from Ultrasound region tags', default=False)
    parser.add_argument('--except-ultrasound-regions', action='store_true', help='ignore OCR inside rectangles from Ultrasound region tags', default=False)
    parser.add_argument('--rects', action="store_true", help='Output each OCR rectangle separately with coordinates', default=False)
    parser.add_argument('--forms', action="store_true", help='Detect scanned forms and redact the whole image', default=False)
    parser.add_argument('--no-overlays', action="store_true", help='Do not process any DICOM overlays', default=False)
    parser.add_argument('--review', action="store_true", help='Ignore database and perform OCR again', default=False)
    parser.add_argument('--deid', action="store_true", help='Use deid-recipe rules to redact', default=False)
    parser.add_argument('--deid-rules', action="store", help='Path to file or directory containing deid recipe files (deid.dicom.*)', default=None)
    parser.add_argument('-o', '--output', dest='output', action="store", help='Output DICOM dir or filename (created automatically if not specified)', default=[])
    parser.add_argument('--relative-path', dest='relative', action="store", help='Output DICOM dir will be relative to input but with this prefix removed from input path', default=None)
    parser.add_argument('--rename', dest='rename', action="store", help='Output DICOM filename suffix, e.g. _redacted.dcm', default=None)
    parser.add_argument('--compress', dest='compress', action="store_true", help='Use lossless compression (JPEG2000)')
    parser.add_argument('--write-csv', dest='csvout', action="store", help='CSV path to write rectangles.csv')
    parser.add_argument('files', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    # Logging or debug (in order error,warning,info,debug)
    if args.debug:
        logging.basicConfig(level = logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level = logging.INFO)
    else:
        logging.basicConfig(level = logging.WARNING)

    # Sanity checks
    if args.deid and args.deid_rules:
        logger.error('Sorry, specifying a deid rules file/directory is not yet implemented')

    # Initialise the OCR functions
    ocr_engine = None
    nlp_engine = None

    # Initialise the OCR for detecting text
    ocr_engine = OCR(args.ocr)

    # Initialise the NLP for detecting PII
    if args.pii:
        pii_params = args.pii.split(',')
        nlp_engine = NER(pii_params[0], model = pii_params[1] if len(pii_params)>1 else None)
        if not nlp_engine.isValid():
            logger.warning('Cannot run NLP on the OCR output because %s is not installed' % pii_params[0])
            nlp_engine = None

    # Initialise database
    db_writer = None
    if args.db:
        if args.db not in ['', None, '-', 'default']:
            DicomRectDB.set_db_path(args.db)
            db_writer = DicomRectDB()

    # Detect text in DICOM files
    for file in dicom_ocr.file_list(args.files):
        # If already in database then ignore
        if db_writer and not args.review:
            if db_writer.query_rects(file):
                logger.debug("ignore (already in db) %s" % file)
                continue
        # Find full path if given relative to PACS_ROOT
        file = dicom_ocr.find_file(file)
        # Test database again with full pathname
        if db_writer and not args.review:
            if db_writer.query_rects(file):
                logger.debug("ignore (already in db) %s" % file)
                continue
        # Run the OCR
        options = {
            'ocr_engine' : ocr_engine,
            'nlp_engine' : nlp_engine,
            'csv_writer' : None,
            'db_writer' : db_writer,
            'output_rects' : args.rects,
            'ignore_overlays' : args.no_overlays,
            'redact_forms' : args.forms,
            'us_regions' : args.use_ultrasound_regions,
            'except_us_regions' : args.except_ultrasound_regions,
        }
        logger.debug('OCR %s' % file)
        dicom_ocr.process_dicom(file, options = options)

    # Open CSV file for rectangles
    if args.csvout:
        fieldnames = ['filename', 'left', 'top', 'right', 'bottom', 'frame', 'overlay']
        csvfd = open(args.csvout, 'w', newline='')
        csvw = csv.DictWriter(csvfd, fieldnames=fieldnames, lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
        csvw.writeheader()


    # Redact DICOM files
    for infilename in dicom_ocr.file_list(args.files):
        logger.debug('REDACT %s' % infilename)
        rect_list = db_writer.query_rects(infilename,
            ignore_allowlisted = True, ignore_summaries = True)
        if args.deid:
            rect_list += deidrules.detect(infilename)
        outfilename = dicom_redact.create_output_filename(infilename, args.output, args.relative, args.rename)
        print('%s -> %s' % (infilename, outfilename))
        ds = pydicom.dcmread(infilename)
        dicom_redact.redact_DicomRect_rectangles(ds, rect_list)
        if args.compress:
            dicom_redact.compress_dataset(ds)
        # Some of the sample DICOMs have curves which are deprecated and cause a crash
        if pydicom.tag.Tag(0x5004, 0x3000) in ds:
            del ds[(0x5004, 0x3000)]
        # If the output file already exists then rename it temporarily
        output_already_exists = os.path.isfile(outfilename)
        if output_already_exists:
            logger.debug('Output file %s already exists, renaming to %s.bak' % (outfilename, outfilename))
            os.rename(outfilename, outfilename+'.bak')
        # Save the new DICOM file, any error during this should raise an exception
        logger.debug('Saving redacted DICOM file to %s' % outfilename)
        ds.save_as(outfilename)
        # If no error then remove the backup
        if output_already_exists:
            logger.debug('Removing backup file %s.bak' % (outfilename))
            os.remove(outfilename+'.bak')

        # Append to CSV
        if args.csvout:
            relative = args.relative
            if relative:
                if len(relative) > 1 and relative[-1] != '/':
                    relative += '/'
            else:
                relative = ''
            for rect in rect_list:
                if rect.L() != -1:
                    csvw.writerow({'filename': outfilename.replace(relative, ''),
                        'left': rect.L(),
                        'right': rect.R(),
                        'top': rect.T(),
                        'bottom': rect.B(),
                        'frame': rect.F(),
                        'overlay': rect.O()})




# ---------------------------------------------------------------------
if __name__ == '__main__':
    main()
