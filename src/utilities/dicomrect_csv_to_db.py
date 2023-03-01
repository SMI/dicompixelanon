#!/usr/bin/env python3
# Read the CSV produced by pydicom_images.py
# containing a list of rectangles in DICOM files
# and add them to the DicomRectDB database.

import argparse
import csv
from DicomPixelAnon.rect import DicomRect
from DicomPixelAnon.dicomrectdb import DicomRectDB


def add_to_db(filename, frame=-1, overlay=-1, top=-1, bottom=-1, left=-1, right=-1):
    dicomrect = DicomRect(top = top,
        bottom = bottom,
        left = left,
        right = right,
        frame = frame, overlay = overlay)
    # Add to database
    db = DicomRectDB()
    db.add_rect(filename, dicomrect)


def row_filter(row, imagetype=None, manufacturer=None):
    """ Return True if the row passes the filter and should be
    added to the database. The filter is for valid rectangles
    i.e. not the ones with -1,-1,-1,-1, and
    the imagetype/manufacturer can be a regex """
    # Ignore invalid rectangles
    if -1 in [row['left'], row['right'], row['top'], row['bottom']]:
        return False
    if imagetype and not re.match(imagetype, row['imagetype']):
            return False
    if manufacturer and not re.match(manufacturer, row['manufacturer']):
            return False
    return True


def read_csv(filename):
    # Rows are as follows (see pydicom_images.py):
    #   'filename',
    #   'frame',
    #   'overlay',
    #   'imagetype', 'manufacturer', 'burnedinannotation',
    #   'ocr_engine',
    #   'left', 'top', 'right', 'bottom',
    #   'ocr_text', 'ner_engine', 'is_sensitive'
    fp = open(filename, newline='')
    reader = csv.DictReader(fp)
    for row in reader:
        if row_filter(row):
            add_to_db(row['filename'],
                frame = row['frame'],
                overlay = row['overlay'],
                top = row['top'],
                bottom = row['bottom'],
                left = row['left'],
                right = row['right'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Add rect to database')
    parser.add_argument('-v', '--verbose', action="store_true", help='verbose')
    parser.add_argument('-d', '--debug', action="store_true", help='debug')
    parser.add_argument('-c', '--csv', dest='csv', action="store", help='input CSV file having filename,left,right,top,bottom,frame,overlay', required=True)
    parser.add_argument('--db', dest='db', action="store", help='output database directory')
    args = parser.parse_args()
    if args.db:
        DicomRectDB.set_db_path(args.db)

    read_csv(args.csv)
