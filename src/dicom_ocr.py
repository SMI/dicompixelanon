#!/usr/bin/env python3
# Run OCR on DICOM images and optionally also NER to detect PII
# Output to CSV file or database

import argparse
import csv
import glob
import logging
import numpy as np
import os
import pydicom
import sys
from PIL import Image
from ocrengine import OCR
from nerengine import NER
from dicomimage import DicomImage
from dicomrectdb import DicomRectDB
from rect import Rect


# Reporting functions
def err(msg):
    logging.error(msg)

def msg(msg):
    logging.info(msg)

def warn(msg):
    logging.warning(msg)

def debug(msg):
    logging.debug(msg)


# Return a filename as given or with $PACS_ROOT prefix if needed
def find_file(filename : str) -> str:
    """ Look for file as given or in $PACS_ROOT
    """
    if os.path.isfile(filename):
        return filename
    # See if file is in $PACS_ROOT
    tmp = os.path.join(os.environ.get('PACS_ROOT','.'), filename)
    if os.path.isfile(tmp):
        return tmp
    err('Cannot find file %s' % filename)
    return None


def check_for_pii(nlp_engine : NER, text) -> int:
    """ Use NER (e.g. SpaCy) to check for PII in some text.
    nlp_engine must be an instance of NER()
    Returns -1 if it's None, 0 if no PII found, or
    1 if any of the entities were PER, ORG or LOC.
    """
    is_sensitive = -1
    if nlp_engine and len(text):
        entities = nlp_engine.detect(text)
        for ent in entities:
            if ent['label'] in ['PER', 'ORG', 'LOC']:
                is_sensitive = 1
        # If no PII found then mark as checked
        if is_sensitive == -1:
            is_sensitive = 0
    return is_sensitive


def process_image(img, filename = None,
        frame = -1, overlay = -1,
        ocr_engine: OCR = None, nlp_engine: NER = None,
        output_rects = False,
        imagetype = '', manufacturer = '', bia = '',
        csv_writer = None, db_writer: DicomRectDB = None):
    """ OCR the image (numpy array) extracted from a DICOM
    and optionally run NLP. Store the results in CSV and/or database.
    ocr_engine must be an instance of OCR().
    nlp_engine must be an instance of NER() or None.
    csv_writer must be an instance of csv.writer() or None.
    db_writer must be an instance of DicomRectDB() or None.
    frame, overlay are integers (-1 if NA).
    output_rects=True will output each OCR rectangle individually.
    imagetype, manufacturer, bia are the dicom tag string,
    although manufacturer may be specially crafted (see elsewhere).
    """
    assert(ocr_engine)
    ocr_engine_name = ocr_engine.engine_name() if ocr_engine else 'NOOCR'
    nlp_engine_name = nlp_engine.engine_name() if nlp_engine else 'NONLP'

    # Run OCR
    debug('OCR(%s,%s) %s (%d,%d)' % (ocr_engine_name, nlp_engine_name, filename, frame, overlay))
    ocr_rectlist = []   # array of tuple(Rect, text, is_sensitive)
    ocr_text = ''
    if output_rects:
        # Get a list of rectangles and construct text string
        ocr_data = ocr_engine.image_to_data(img)
        for item in ocr_data:
            if item['conf'] > OCR.confidence_threshold:
                ocr_text += item['text'] + ' '
                is_sensitive = check_for_pii(nlp_engine, item['text'])
                ocr_rectlist.append( (item['rect'], item['text']) )
        # Now append the whole string with a null rectangle
        ocr_rectlist.append( (Rect(), ocr_text, check_for_pii(ocr_text)) )
    else:
        ocr_text = ocr_engine.image_to_text(img)
        is_sensitive = check_for_pii(nlp_engine, item['text'])
        ocr_rectlist.append( (Rect(), ocr_text, is_sensitive) )

    # Output in CSV format
    if csv_writer:
        for rect,text,is_sensitive in ocr_rectlist:
            csv_writer.writerow([
                filename, frame, overlay,
                imagetype, manufacturer, bia,
                ocr_engine.engine_name(),
                rect.L(), rect.T(), rect.R(), rect.B(),
                text,
                nlp_engine_name,
                is_sensitive
            ])

    # Output to database
    if db_writer:
        for rect,text,is_sensitive in ocr_rectlist:
            dicomrect = DicomRect(top = rect.T(), bottom = rect.B(),
                left = rect.L(), right = rect.R(),
                frame = frame, overlay = overlay)
            db_writer.add_rect(filename, dicomrect)

    return


# OCR every image and overlay in a DICOM file
def process_dicom(filename, ocr_engine: OCR = None, nlp_engine: NER = None, output_rects = False, ignore_overlays = False, csv_writer = None, db_writer: DicomRectDB = None):

    # Attempt to read and parse as DICOM
    try:
        ds = pydicom.dcmread(filename)
        dicomimg = DicomImage(filename)
    except Exception as e:
        err('ERROR reading DICOM file %s (%s)' % (filename, e))
        return

    # Check that it's an image file
    if not 'PixelData' in ds:
        warn('No pixel data in %s' % filename)
        return
    try:
        pixel_data = ds.pixel_array
    except Exception as e:
        err('ERROR decoding pixel data from DICOM file %s (%s)' % (filename, e))
        return

    # Check for multiple frames
    num_frames = ds['NumberOfFrames'].value if 'NumberOfFrames' in ds else 1

    # Check which bits in PixelData are actually used
    bits_stored = ds['BitsStored'].value if 'BitsStored' in ds else -1
    bits_allocated = ds['BitsAllocated'].value if 'BitsAllocated' in ds else -1
    msg('%s is %s using %d/%d bits with %d frames' % (filename, str(pixel_data.shape), bits_stored, bits_allocated, num_frames))

    # Get some tag values massaged to return proper values
    image_type = dicomimg.get_tag_imagetype()
    manuf = dicomimg.get_tag_manufacturer_model()

    # Additional parameters passes to process_image()
    meta = {
        'ocr_engine':    ocr_engine,
        'nlp_engine':    nlp_engine,
        'output_rects':  output_rects,
        'bia':           ds.get('BurnedInAnnotation', ''),
        'manufacturer':  manuf,
        'imagetype':     image_type,
        'csv_writer':    csv_writer,
        'db_writer':     db_writer
    }

    # Save all the frames
    for idx in range(dicomimg.get_total_frames()):
        img = dicomimg.next_image()
        frame, overlay = dicomimg.get_current_frame_overlay()
        if ignore_overlays and overlay != -1:
            continue
        process_image(np.asarray(img), filename=filename, frame=frame, overlay=overlay, **meta)
    return


# ---------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DICOM image OCR and NER')
    parser.add_argument('-v', '--verbose', action="store_true", help='more verbose (show INFO messages)')
    parser.add_argument('-d', '--debug', action="store_true", help='more verbose (show DEBUG messages)')
    parser.add_argument('--ocr', action='store', help='OCR using "tesseract" or "easyocr"', default='easyocr')
    parser.add_argument('--db',  action="store", help='output to database directory (or specify "default")', default=False)
    parser.add_argument('--csv', action="store", help='output to CSV file', default=False)
    parser.add_argument('--csv-header', action="store_true", help='output CSV header when using --csv', default=True)
    parser.add_argument('--no-csv-header', action="store_true", help='do not output CSV header when using --csv', default=False)
    parser.add_argument('--pii', action='store', help='Check OCR output for PII using "spacy" or "flair" or "stanford" or "stanza" (add ,model if needed)', default=None)
    parser.add_argument('--rects', action="store_true", help='Output each OCR rectangle separately with coordinates', default=False)
    parser.add_argument('--no-overlays', action="store_true", help='Do not process any DICOM overlays', default=False)
    parser.add_argument('files', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    # Logging or debug (in order error,warning,info,debug)
    if args.debug:
        logging.basicConfig(level = logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level = logging.INFO)
    else:
        logging.basicConfig(level = logging.WARNING)

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
            warn('Cannot run NLP on the OCR output because %s is not installed' % pii_params[0])
            nlp_engine = None

    # Output header for CSV format
    csv_writer = None
    if args.csv:
        if args.csv in ['-', 'stdout']:
            csv_writer = csv.writer(sys.stdout)
        else:
            csv_fd = open(args.csv, 'w', newline='') # implicit close on exit
            csv_writer = csv.writer(csv_fd)
        if args.csv_header or not args.no_csv_header:
            csv_writer.writerow([
                'filename',
                'frame',
                'overlay',
                'imagetype',
                'manufacturer',
                'burnedinannotation',
                'ocr_engine',
                'left', 'top', 'right', 'bottom',
                'ocr_text',
                'ner_engine',
                'is_sensitive'
            ])

    # Initialise database
    db_writer = None
    if args.db:
        if args.db not in ['', None, '-', 'default']:
            DicomRectDB.db_path = args.db
            db_writer = DicomRectDB()

    # Process files
    for file in args.files:
        file = find_file(file)
        process_dicom(file, ocr_engine = ocr_engine, nlp_engine = nlp_engine,
            output_rects = args.rects, ignore_overlays = args.no_overlays,
            csv_writer = csv_writer, db_writer = db_writer)