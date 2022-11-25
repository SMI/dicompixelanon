#!/usr/bin/env python3

# Usage: -i file.dcm... # identify frames and overlays
#        -x file.dcm... # extracts frames and overlays
#
# Note that the images will be converted to 8-bit using contrast stretching
# so you can't extract the raw image pixels with this utility
# (see the version prior to 24 Aug 2022 if you need that ability).
#
# Requirements are: pydicom numpy matplotlib pylibjpeg pylibjpeg-libjpeg Pillow
# dependencies: cycler fonttools kiwisolver packaging pyparsing python-dateutil six

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
def find_file(filename):
    """ Look for file as given or in $PACS_ROOT
    """
    if os.path.isfile(filename):
        return filename
    # See if file is in $PACS_DIR
    tmp = os.path.join(os.environ.get('PACS_ROOT','.'), filename)
    if os.path.isfile(tmp):
        return tmp
    err('Cannot find file %s' % filename)
    return None


def process_image(img, filename=None, output_dir=None,
        frame=-1, overlay=-1,
        ocr_engine=None, nlp_engine=None,
        to_save=False, output_format='png', output_rects=False,
        imagetype='', manufacturer='', bia=''):
    """ Do something useful with an image (numpy array) extracted from a DICOM.
    either save it in a file, or run OCR, or both, or just display info.
    """
    ocr_engine_name = ocr_engine.engine_name() if ocr_engine else 'NOOCR'
    nlp_engine_name = nlp_engine.engine_name() if nlp_engine else 'NONLP'
    # Run OCR and output text to stdout
    if ocr_engine:
        debug('OCR(%s,%s) %s (%d,%d)' % (ocr_engine_name, nlp_engine_name, filename, frame, overlay))
        ocr_rectlist = []
        ocr_text = ''
        if output_rects:
            # Get a list of rectangles and construct text string
            ocr_data = ocr_engine.image_to_data(img)
            for item in ocr_data:
                if item['conf'] > OCR.confidence_threshold:
                    ocr_text += item['text'] + ' '
                    ocr_rectlist.append( (item['rect'], item['text']) )
        else:
            ocr_text = ocr_engine.image_to_text(img)
        # Output in CSV format, first each rectangle then the full text string
        csv_writer = csv.writer(sys.stdout)
        ocr_rectlist.append( (Rect(), ocr_text) )
        for rect,text in ocr_rectlist:
            # Try using NER (eg. SpaCy) to check for PII
            is_sensitive = -1
            if nlp_engine and len(text):
                entities = nlp_engine.detect(text)
                for ent in entities:
                    if ent['label'] in ['PER', 'ORG', 'LOC']:
                        is_sensitive = 1
                # If no PII found then mark as checked
                if is_sensitive == -1:
                    is_sensitive = 0
            # Output in CSV format
            csv_writer.writerow([
                filename, frame, overlay,
                imagetype, manufacturer, bia,
                ocr_engine.engine_name(),
                rect.L(), rect.T(), rect.R(), rect.B(),
                text,
                nlp_engine_name,
                is_sensitive
            ])
    # Extract image to a file
    if to_save:
        filename = os.path.join(output_dir, os.path.basename(filename))
        if overlay == -1:
            filename += '_frame%02d' % frame
        elif frame == -1:
            filename += '_overlay%02x' % overlay
        else:
            filename += '_overlay%02x_frame%02d' % (overlay, frame)
        filename += '.' + output_format
        debug('Saving %s' % filename)
        if overlay == -1:
            #equalize(Image.fromarray(img)).save(filename+'.histeq.'+output_format)
            #Image.fromarray(img).convert('L').save(filename+'.L.'+output_format)
            Image.fromarray(img).save(filename)
        else:
            Image.fromarray(img).save(filename)
    return

# Examine or extract a DICOM file
def process_dicom(filename, to_save = False, output_format = 'png', ocr_engine = None, nlp_engine = None, output_rects = False, ignore_overlays = False):

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

    # Check if we can write to same directory, otherwise use current dir
    output_dir = os.path.dirname(filename)
    try:
        tmpfile = os.path.join(output_dir, 'tmp.XXX')
        fd = open(tmpfile, 'w')
        fd.close()
        os.remove(tmpfile)
    except:
        output_dir = '.'

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
        'to_save':       to_save,
        'output_format': output_format,
        'output_rects':  output_rects,
        'bia':           ds.get('BurnedInAnnotation', ''),
        'manufacturer':  manuf,
        'imagetype':     image_type
    }

    # Save all the frames
    for idx in range(dicomimg.get_total_frames()):
        img = dicomimg.next_image()
        frame, overlay = dicomimg.get_current_frame_overlay()
        if ignore_overlays and overlay != -1:
            continue
        process_image(np.asarray(img), filename=filename, output_dir=output_dir, frame=frame, overlay=overlay, **meta)
    return


if __name__ == "__main__":
    to_save = False
    parser = argparse.ArgumentParser(description='DICOM image frames to PNG')
    parser.add_argument('-v', '--verbose', action="store_true", help='more verbose (show INFO messages)')
    parser.add_argument('-d', '--debug', action="store_true", help='more verbose (show DEBUG messages)')
    parser.add_argument('-x', '--extract', action="store_true", help='extract PNG/TIFF files to input dir (or current dir)')
    parser.add_argument('-i', '--identify', action="store_true", help='identify only')
    parser.add_argument('--ocr', action='store', help='OCR using "tesseract" or "easyocr", output to stdout', default=None)
    parser.add_argument('--csv', action="store_true", help='output CSV header when using --ocr', default=False)
    parser.add_argument('--pii', action='store', help='Check OCR output for PII using "spacy" or "flair" (add ,model if needed)', default=None)
    parser.add_argument('--rects', action="store_true", help='Output each OCR rectangle separately with coordinates', default=False)
    parser.add_argument('--no-overlays', action="store_true", help='Do not process any DICOM overlays', default=False)
    parser.add_argument('-f', '--format', action="store", help='image format png or tiff (default %(default)s)', default='tiff')
    parser.add_argument('files', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.extract: to_save = True
    if args.identify: to_save = False

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
    if args.ocr:
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
        if args.csv:
            csv_writer = csv.writer(sys.stdout)
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

    # Process files
    for file in args.files:
        file = find_file(file)
        process_dicom(file, to_save = to_save, output_format = args.format, ocr_engine = ocr_engine, nlp_engine = nlp_engine, output_rects = args.rects, ignore_overlays = args.no_overlays)
