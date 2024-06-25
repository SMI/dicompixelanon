#!/usr/bin/env python3
# Convert all DICOM files recursively under the input directory
# into the same file hierarchy under the output directory
# such that all pixel data is replaced by zero bytes
# (and compressed using RLE which compresses zeros very well)
# and the UIDs replaced by hashed values.
# This make a totally anonymous dataset which could be used as
# synthetic data.
# If you want a different set of UIDs then use the salt option.

import argparse
import hashlib
import logging
import os
import sys
import numpy as np
import pydicom
from pydicom.uid import RLELossless
from pydicom.valuerep import VR as VR_

logger = logging.getLogger(__name__)
compression = False


def hasher(id, salt=None):
    """ Given an id (encoded str) it returns a str which is
    a hashed value of the id. Gets the hex string of the digest
    but then converts to decimal to meet DICOM standards which
    only allow 0-9 and dot, and max 64 chars. If salt is given
    then it's used to randomise the hashing. """
    if not salt:
        salt = b''
    hashobj = hashlib.blake2s(digest_size=16, salt=salt)
    hashobj.update(id)
    return str(int(hashobj.hexdigest(), base=16))


def process_file(infile, outfile, salt=None):
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
    logger.debug('BPP %s Frames %sx%s %s BitsAlloc %s BitsStored %s SignedInts %s ArrayShape %s Type %s' % (
        ds.SamplesPerPixel,
        ds.get('NumberOfFrames', 'ERR_NumberOfFrames),
        ds.Rows, ds.Columns, ds.BitsAllocated, ds.BitsStored, ds.PixelRepresentation, (pixel_data.shape,), pixel_data.dtype))
    # Create an empty array exactly same dimensions as pixel_data
    zero_data =  np.zeros_like(pixel_data)
    # Replace the pixel data in the DICOM, using compression
    if compression:
        ds.compress(transfer_syntax_uid = RLELossless, arr = zero_data)
        ds['PixelData'].VR = VR_.OB
    else:
        ds.PixelData = zero_data.tobytes()

    # Hash all the UIDs, including the one in the header
    mappings={}
    # The salt should be bytes not str
    if salt:
        salt = salt.encode()
    file_metas = getattr(ds, 'file_meta', pydicom.Dataset())
    if hasattr(file_metas, 'MediaStorageSOPInstanceUID'):
        mssop = file_metas['MediaStorageSOPInstanceUID'].value
        mappings[mssop] = hasher(mssop.encode(), salt=salt)
        file_metas.MediaStorageSOPInstanceUID = mappings[mssop]
        ds.file_meta = file_metas
    mappings[ds.SOPInstanceUID] = hasher(ds.SOPInstanceUID.encode(), salt=salt)
    mappings[ds.StudyInstanceUID] = hasher(ds.StudyInstanceUID.encode(), salt=salt)
    mappings[ds.SeriesInstanceUID] = hasher(ds.SeriesInstanceUID.encode(), salt=salt)
    ds.SOPInstanceUID = mappings[ds.SOPInstanceUID]
    ds.StudyInstanceUID = mappings[ds.StudyInstanceUID]
    ds.SeriesInstanceUID = mappings[ds.SeriesInstanceUID]

    # Replace any directory names which are actual UIDs
    for map in mappings:
        # XXX this might fail if map is a prefix for multiple mappings
        # but can't put trailing slash as need to replace in filename.
        outfile = outfile.replace(f'/{map}', f'/{mappings[map]}')

    # Save the new image
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    ds.save_as(outfile)

# ---------------------------------------------------------------------
parser = argparse.ArgumentParser(description='DICOM Image Remover')
parser.add_argument('-d', '--debug', action="store_true", help='debug')
parser.add_argument('-c', '--compress', action="store_true", help='compress using RLE (lossless)')
parser.add_argument('-i', '--inputdir', action="store", help='input directory (will be searched recursively)')
parser.add_argument('-o', '--outputdir', action="store", help='output directory (will mirror input hierarchy)')
parser.add_argument('--salt', action="store", help="salt to randomise hash (max 8 chars)')
args = parser.parse_args()
if args.debug:
    logging.basicConfig(level = logging.DEBUG)
if args.compress:
    compression = True

for root, dirs, files in os.walk(args.inputdir):
    for filename in files:
        infile = os.path.join(root, filename)
        outfile = infile.replace(args.inputdir, args.outputdir)
        process_file(infile, outfile, args.salt)
