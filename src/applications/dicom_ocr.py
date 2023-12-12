#!/usr/bin/env python3
# Run OCR on DICOM images and optionally also NER to detect PII
# Output to CSV file or database
# e.g. PYTHONPATH=../library/ ./dicom_ocr.py --rects --csv /dev/tty --use-ultrasound-regions ~/data/gdcm/gdcmData/gdcm-US-ALOKA-16.dcm

import argparse
import csv
import logging
import os
import sys
import pydicom
import numpy as np
from DicomPixelAnon.ocrengine import OCR
from DicomPixelAnon.ocrenum import OCREnum
from DicomPixelAnon.nerengine import NER
from DicomPixelAnon.nerenum import NEREnum
from DicomPixelAnon.dicomimage import DicomImage
from DicomPixelAnon.dicomrectdb import DicomRectDB
from DicomPixelAnon.rect import DicomRectText
from DicomPixelAnon.rect import filter_DicomRectText_list_by_fontsize
from DicomPixelAnon.torchdicom import ScannedFormDetector
from DicomPixelAnon.ultrasound import read_DicomRectText_list_from_region_tags
import DicomPixelAnon.torchmem # ignore W0611 unused-import


# ---------------------------------------------------------------------
# Reporting functions
def err(msg):
    logging.error(msg)

def msg(msg):
    logging.info(msg)

def warn(msg):
    logging.warning(msg)

def debug(msg):
    logging.debug(msg)


# ---------------------------------------------------------------------
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


# ---------------------------------------------------------------------
def check_for_pii(nlp_engine : NER, text) -> int:
    """ Use NER (e.g. SpaCy) to check for PII in some text,
    or use a allowlist to check if text is safe.
    nlp_engine must be an instance of NER()
    Returns -1 if it's None (could not check for PII),
    0 if no PII found,
      or allowlist was used and text was on list,
    1 if any of the entities were PER, ORG or LOC,
      or allowlist was used but text was not on list.
    """
    is_sensitive = -1
    if nlp_engine and len(text):
        entities = nlp_engine.detect(text)
        for ent in entities:
            if ent['label'] in ['PER', 'ORG', 'LOC']:
                is_sensitive = 1
            elif nlp_engine.engine_enum() == NEREnum.allowlist:
                is_sensitive = 1
        # If no PII found then mark as checked
        if is_sensitive == -1:
            is_sensitive = 0
    return is_sensitive


# ---------------------------------------------------------------------

def check_for_scanned_form(img):
    """ Use a PyTorch model to see if this image is a scanned form.
    """
    det = ScannedFormDetector()
    rc = det.test_Image(img)
    return (rc[0]['class'] == 1)


# ---------------------------------------------------------------------
def save_rects(filename, frame, overlay, meta, ocr_rectlist : list, csv_writer = None, db_writer: DicomRectDB = None):
    """ Save the list of rectangles to the CSV file and/or database.
    """
    # Output in CSV format
    if csv_writer:
        for rect in ocr_rectlist:
            ocrenum, ocrtext, nerenum, is_sensitive = rect.text_tuple()
            csv_writer.writerow([
                filename, frame, overlay,
                meta.get('ImageType', ''),
                meta.get('ManufacturerModelName'),
                meta.get('BurnedInAnnotation', ''),
                OCREnum().name(ocrenum),
                rect.L(), rect.T(), rect.R(), rect.B(),
                ocrtext,
                NEREnum().name(nerenum),
                is_sensitive
            ])

    # Output to database
    if db_writer:
        for dicomrect in ocr_rectlist:
            db_writer.add_rect(filename, dicomrect)
    return


# ---------------------------------------------------------------------
def process_image(img, filename = None,
        frame = -1, overlay = -1,
        options : dict = None,
        meta : dict = None):
    """ OCR the image (PIL image) extracted from a DICOM
    and optionally run NLP. Store the results in CSV and/or database.
    frame, overlay are integers (-1 if NA).
    options dict must contain:
      ocr_engine must be an instance of OCR().
      nlp_engine must be an instance of NER() or None.
      csv_writer must be an instance of csv.writer() or None.
      db_writer must be an instance of DicomRectDB() or None.
      us_regions=True will add rectangles from Ultrasound tags.
      except_us_regions=True will ignore text found within
      rectangles from Ultrasound tags (so there's no duplication,
      if you're redacting US regions anyway, and so you can check
      if the US regions are sufficient by looking for text outside).
      output_rects=True will output each OCR rectangle individually.
    meta dict must contain keys taken from DICOM tag values:
      ImageType
      ManufacturerModelName
      BurnedInAnnotation
    """
    ocr_engine = options.get('ocr_engine', None)
    nlp_engine = options.get('nlp_engine', None)
    output_rects = options.get('output_rects', False)
    us_regions = options.get('us_regions', False)
    except_us_regions = options.get('except_us_regions', False)
    csv_writer = options.get('csv_writer', None)
    db_writer = options.get('db_writer', None)

    # Convert from PIL Image to numpy array
    img = np.asarray(img)

    assert(ocr_engine)
    ocr_engine_name = ocr_engine.engine_name() if ocr_engine else 'NOOCR'
    ocr_engine_enum = ocr_engine.engine_enum() if ocr_engine else -1
    nlp_engine_name = nlp_engine.engine_name() if nlp_engine else 'NONLP'
    nlp_engine_enum = nlp_engine.engine_enum() if nlp_engine else -1

    ocr_rectlist = []   # array of DicomRectText (was tuple(Rect, text, is_sensitive))

    # Try Ultrasound regions
    # XXX we should only call this if frame==0 and overlay==-1
    # to avoid adding rectangles with every other frame/overlay?
    if us_regions:
        ocr_rectlist = read_DicomRectText_list_from_region_tags(filename = filename)

    if except_us_regions:
        us_rectlist = read_DicomRectText_list_from_region_tags(filename = filename)

    # Run OCR
    debug('OCR(%s,%s) %s (%d,%d)' % (ocr_engine_name, nlp_engine_name, filename, frame, overlay))
    ocr_text = ''
    if output_rects:
        # Get a list of rectangles and construct text string
        # image_to_data returns dict with text,conf,rect keys.
        # XXX regardless of frame,overlay supplied the US regions are always attributed to frame=0
        ocr_data = ocr_engine.image_to_data(img)
        for item in ocr_data:
            if item['conf'] > OCR.confidence_threshold:
                ocr_text += item['text'] + ' '
                is_sensitive = check_for_pii(nlp_engine, item['text'])
                ocr_rectlist.append( DicomRectText(arect = item['rect'],
                    frame=frame, overlay=overlay,
                    ocrengine=ocr_engine_enum, ocrtext=item['text'],
                    nerengine=nlp_engine_enum, nerpii=is_sensitive) )
        # Now append the whole string with a null rectangle
        is_sensitive = check_for_pii(nlp_engine, ocr_text)
        ocr_rectlist.append( DicomRectText(ocrengine=ocr_engine_enum, ocrtext=ocr_text,
            nerengine=nlp_engine_enum, nerpii=is_sensitive) )
    else:
        ocr_text = ocr_engine.image_to_text(img)
        is_sensitive = check_for_pii(nlp_engine, ocr_text)
        ocr_rectlist.append( DicomRectText(ocrengine=ocr_engine_enum, ocrtext=ocr_text,
            nerengine=nlp_engine_enum, nerpii=is_sensitive) )

    # Filter out huge rectangles
    ocr_rectlist = filter_DicomRectText_list_by_fontsize(ocr_rectlist)

    # Filter out text inside US regions if required
    if except_us_regions:
        def rect_within_rectlist(rect, rectlist):
            return any([r.contains_rect(rect) for r in rectlist])
        ocr_rectlist = [ rect for rect in ocr_rectlist if not rect_within_rectlist(rect, us_rectlist) ]

    save_rects(filename, frame, overlay, meta, ocr_rectlist,
        csv_writer = csv_writer, db_writer = db_writer)

    return


# ---------------------------------------------------------------------
# OCR every image and overlay in a DICOM file

def process_dicom(filename, options : dict):
    """ Examine every frame in the DICOM file and run OCR.
    Add rectangles to database or CSV.
    options should contain:
    ocr_engine: OCR = None, nlp_engine: NER = None,
    csv_writer = None, db_writer: DicomRectDB = None, options : dict):
    output_rects = False, redact_forms = False, ignore_overlays = False,
    us_regions = False, except_us_regions = False
    """

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

    # Additional parameters passes to process_image()
    # Get some tag values massaged to return proper values
    meta = dicomimg.get_selected_metadata()

    # Save all the frames
    for idx in range(dicomimg.get_total_frames()):
        msg(" extracting frame %d from %s" % (idx, filename))
        try:
            img = dicomimg.next_image()
        except Exception as e:
            err('Cannot extract frame %d from %s (%s)' % (idx, filename, e))
            continue
        frame, overlay = dicomimg.get_current_frame_overlay()
        if idx == 0 and options.get('redact_forms', None):
            is_scanned_form = False
            det = ScannedFormDetector()
            rc = det.test_Image(img)
            if rc and len(rc)>0 and 'class' in rc[0]:
                is_scanned_form = (rc[0]['class'] == 1)
            if is_scanned_form:
                max_rectlist = [
                    DicomRectText(0, meta['Rows']-1, 0, meta['Columns']-1,
                    frame=frame, overlay=overlay,
                    ocrengine=OCREnum.ScannedForm, ocrtext='SCANNED_FORM',
                    nerengine=NEREnum.scannedform, nerpii=True)
                ]
                save_rects(filename, frame, overlay, meta, max_rectlist, options['csv_writer'], options['db_writer'])
                break # no need for other frames
        if options['ignore_overlays'] and overlay != -1:
            continue
        if not img:
            err('Cannot extract frame %d overlay %d from %s' % (frame, overlay, filename))
            continue
        process_image(img, filename=filename, frame=frame, overlay=overlay, options = options, meta = meta)
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
    parser.add_argument('--use-ultrasound-regions', action='store_true', help='collect rectangles from Ultrasound region tags', default=False)
    parser.add_argument('--except-ultrasound-regions', action='store_true', help='ignore OCR inside rectangles from Ultrasound region tags', default=False)
    parser.add_argument('--rects', action="store_true", help='Output each OCR rectangle separately with coordinates', default=False)
    parser.add_argument('--forms', action="store_true", help='Detect scanned forms and redact the whole image', default=False)
    parser.add_argument('--no-overlays', action="store_true", help='Do not process any DICOM overlays', default=False)
    parser.add_argument('--review', action="store_true", help='Ignore database and perform OCR again', default=False)
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
            DicomRectDB.set_db_path(args.db)
            db_writer = DicomRectDB()

    # Process files
    for file in args.files:
        # If already in database then ignore
        if db_writer and not args.review:
            if db_writer.query_rects(file):
                debug("ignore (already in db) %s" % file)
                continue
        # Find full path if given relative to PACS_ROOT
        file = find_file(file)
        # Test database again with full pathname
        if db_writer and not args.review:
            if db_writer.query_rects(file):
                debug("ignore (already in db) %s" % file)
                continue
        # Run the OCR
        options = {
            'ocr_engine' : ocr_engine,
            'nlp_engine' : nlp_engine,
            'csv_writer' : csv_writer,
            'db_writer' : db_writer,
            'output_rects' : args.rects,
            'ignore_overlays' : args.no_overlays,
            'redact_forms' : args.forms,
            'us_regions' : args.use_ultrasound_regions,
            'except_us_regions' : args.except_ultrasound_regions,
        }
        process_dicom(file, options = options)
