#!/usr/bin/env python3
# Convert all DICOM files recursively under the input directory
# into the same file hierarchy under the output directory
# such that all pixel data is replaced by zero bytes
# (and compressed using RLE which compresses zeros very well)
# and the UIDs replaced by hashed values.
# This make a totally anonymous dataset which could be used as
# synthetic data.

import argparse
import hashlib
import logging
import os
import sys
import numpy as np
import pydicom
from pydicom.uid import RLELossless

logger = logging.getLogger(__name__)


def hasher(id):
    """ Given an id (str) it returns another str which is
    a hashed value of the id. Gets the hex string of the digest
    but then converts to decimal to meet DICOM standards which
    only allow 0-9 and dot, and max 64 chars. """
    hashobj = hashlib.blake2s(digest_size=16)
    hashobj.update(id)
    return str(int(hashobj.hexdigest(), base=16))


def process_file(infile, outfile):
    logger.debug('convert %s to %s' % (infile, outfile))
    try:
        ds = pydicom.dcmread(infile)
    except:
        logger.error('Cannot parse as DICOM: %s' % infile)
        return
    try:
        pixel_data = ds.pixel_array
    except:
        logger.error('Cannot find image pixels in DICOM: %s' % infile)
        return
    # Create an empty array exactly same dimensions as pixel_data
    zero_data =  np.zeros_like(pixel_data)
    # Replace the pixel data in the DICOM, using compression
    ds.compress(RLELossless, zero_data)

    # Hash all the UIDs, including the one in the header
    file_metas = getattr(ds, 'file_meta', pydicom.Dataset())
    if hasattr(file_metas, 'MediaStorageSOPInstanceUID'):
        file_metas.MediaStorageSOPInstanceUID = hasher(str(file_metas['MediaStorageSOPInstanceUID']).encode())
        ds.file_meta = file_metas
    ds.SOPInstanceUID = hasher(ds.SOPInstanceUID.encode())
    ds.StudyInstanceUID = hasher(ds.StudyInstanceUID.encode())
    ds.SeriesInstanceUID = hasher(ds.SeriesInstanceUID.encode())

    # Save the new image
    ds.save_as(outfile)

parser = argparse.ArgumentParser(description='DICOM Image Remover')
parser.add_argument('-d', '--debug', action="store_true", help='debug')
parser.add_argument('-i', '--inputdir', action="store", help='input directory (will be searched recursively)')
parser.add_argument('-o', '--outputdir', action="store", help='output directory (will mirror input hierarchy)')
args = parser.parse_args()
if args.debug:
    logging.basicConfig(level = logging.DEBUG)

for root, dirs, files in os.walk(args.inputdir):
    for filename in files:
        infile = os.path.join(root, filename)
        outfile = infile.replace(args.inputdir, args.outputdir)
        os.makedirs(os.path.dirname(outfile), exist_ok=True)
        process_file(infile, outfile)
