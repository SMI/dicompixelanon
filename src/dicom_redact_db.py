#!/usr/bin/env python3
# Read the filename of every file in the database which has got
# some rectangles, and actually redact the DICOM file.
# Usage: dicom_redact_db.py [db_path]

import logging
import os
import sys
from dicomrectdb import DicomRectDB

destdir = '/beegfs-hdruk/extract/v12/PACS/projects/abrooks_test5'

if __name__ == '__main__':

    # set database path
    if len(sys.argv)>1:
        DicomRectDB.db_path = sys.argv[1]

    db = DicomRectDB()

    # Get list of all files which have rectangles in the database
    files = db.query_rect_filenames()

    for file in files:
        # output goes into destdir
        # XXX no subdirectories so it might get very large
        destname = os.path.basename(file)
        destfile = os.path.join(destdir, destname)

        # Ignore if output file already exists
        if os.path.isfile(destfile):
            logging.debug('ALREADY EXISTS: %s' % destname)
            continue

        # Redact
        # XXX uses current directory not $PATH
        cmd = ['./dicom_redact.py', '--db', DicomRectDB.db_path,
            '--dicom', file,
            '--output', destfile
            ]
        logging.info('RUN %s' % ' '.join(cmd))
        os.system(' '.join(cmd)) # XXX should use subprocess instead
        # XXX no errors are reported nor does it stop upon error
