#!/usr/bin/env python3
# Redact a DICOM image to deidentify it:
#  * can remove the overlay planes stored in the high bits of the image data
#  * can redact rectangles from any of the image frames or overlay frames

# TODO: change all errors to raise exceptions
# NOTE:
#   overlays may be smaller than their images. Rectangle coordinates
#     are within the overlay, not relative to the original image, so
#     if you want to use image coordinates you'll need to subtract
#     the overlay origin coordinate.

import csv
import argparse
import logging
import numpy as np
import os
import pydicom
from pydicom.pixel_data_handlers.numpy_handler import pack_bits
from rect import DicomRect
import sys
try:
    from dicomrectdb import DicomRectDB
    dbEnabled = True
except:
    dbEnabled = False

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Need examples of:
#  high-bit overlays (and multiple of them)
#  separate overlays (and multiple of them)
#  multiple frames in separate overlays
#  multiple frames of images
#  mono, inverted mono, signed ints, RGB, Palette, etc
#  various compression
filename = 'XA_GE_JPEG_02_with_Overlays.dcm'   # has high-bit overlays
filename = 'MR-SIEMENS-DICOM-WithOverlays.dcm' # has separate overlays
filename = 'GE_DLX-8-MONO2-Multiframe.dcm'     # has multiple frames

elem_OverlayBitPosition = 0x0102
elem_OverlayData = 0x3000
elem_OverlayRows = 0x0010
elem_OverlayCols = 0x0011
elem_OverlayNumFrames = 0x0015
elem_OverlayOrigin = 0x0050


# ---------------------------------------------------------------------

def mark_as_uncompressed(ds):
    """ Call this after you've uncompressed the PixelData
    and written it back into the dataset using tobytes()
    """
    if sys.byteorder == 'little':
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    else:
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRBigEndian


# ---------------------------------------------------------------------

def overlay_tag_group_from_index(overlay):
    """ Convert an overlay index 0..15 into a DICOM tag group
    They start at 0x6000 and go up in twos.
    """
    return 0x6000 + 2 * overlay


def overlay_bit_position(ds, overlay):
    """ Return the bit index of the overlay, if it's hidden
    inside the high bits of the image data, or 0 if it's a
    standalone overlay, i.e. given overlay number N,
    returns the actual number of the bit inside the byte
    for that overlay, e.g. overlay 0 is bit 8.
    """
    overlay_group_num = overlay_tag_group_from_index(overlay)
    if [overlay_group_num, elem_OverlayBitPosition] in ds:
        overlay_bit = ds[overlay_group_num, elem_OverlayBitPosition].value
        # Sometimes it is prevent but value is None!
        if not overlay_bit:
            overlay_bit = 0
        # Bit position must be >0 for a high-bit overlay
        if overlay_bit > 0:
            logger.debug('Found overlay %d in high-bit %d' % (overlay, overlay_bit))
            return overlay_bit
    return 0


# ---------------------------------------------------------------------

def remove_overlays_in_high_bits(ds):
    """ Mask off the high-bits of all the pixel values
    just in case there are overlays hidden in there
    which we want to remove (simply removing the 60xx tags
    does not actually remove the overlay pixels).
    """

    # Sanity check that image has pixels
    if not 'PixelData' in ds:
        logger.error('no pixel data present')
        return

    # bits_allocated is the physical space used, 1 or a multiple of 8.
    # bits_stored is the number of meaningful bits within those allocated.
    bits_stored = ds['BitsStored'].value if 'BitsStored' in ds else -1
    bits_allocated = ds['BitsAllocated'].value if 'BitsAllocated' in ds else -1
    bit_mask = (~((~0) << bits_stored))
    samples = ds['SamplesPerPixel'].value if 'SamplesPerPixel' in ds else -1
    photometric = ds['PhotometricInterpretation'].value if 'PhotometricInterpretation' in ds else 'MONOCHROME2'

    # This code calculates a bit mask from the actual overlays in use.
    # It is not used.
    # Instead we simply mask off everything outside the bits_stored bits.
    overlay_bitmask = 0
    for overlay_num in range(16):
        overlay_bit = overlay_bit_position(ds, overlay_num)
        if overlay_bit > 0:
            logger.debug('found overlay %d in high-bit %d' % (overlay_num, overlay_bit))
            overlay_bitmask |= (1 << overlay_bit)
    logger.debug('bits_stored = %d (image bits used)' % bits_stored)
    logger.debug('bits_allocated = %d (physical space needed)' % bits_allocated)
    logger.debug('bit_mask = %x (use & to get only image data)' % bit_mask)
    logger.debug('overlay_bitmask = %x (for overlays in use)' % overlay_bitmask)
    logger.debug('samples = %d' % samples)

    # Can only handle greyscale or palette images
    # XXX would an overlay every be present in an RGB image? Doesn't make sense?
    if photometric not in ['MONOCHROME1', 'MONOCHROME2', 'PALETTE COLOR']:
        logger.error('cannot remove overlays from %s' % photometric)
        return

    # Can only handle 1 sample per pixel
    # XXX would an overlay be present if multiple samples per pixel? Doesn't make sense?
    if samples > 1:
        logger.error('cannot remove overlays from %d samples per pixel' % samples)
        return

    pixel_data = ds.pixel_array # this can raise an exception in some files
    logger.debug('ndim = %d' % pixel_data.ndim)

    # Use numpy to mask the bits, handles both 8 and 16 bits per pixel.
    masked = (pixel_data & bit_mask)
    # Could also do this?
    #if pixel_data.ndim == 3:
    #    masked = (pixel_data[frame,:,:] & bit_mask)
    #else:
    #    masked = (pixel_data[frame,:,:,:] & bit_mask)
    ds.PixelData = masked.tobytes()

    # XXX does not re-compress
    mark_as_uncompressed(ds)
    # No need to handle ICC Profile, Colour Space, Palette Lookup Table, etc
    # No need to handle 2's complement Pixel Representation.
    return


# ---------------------------------------------------------------------

def redact_rectangles_from_high_bit_overlay(ds, overlay=0, rect_list=[]):
    """ Redact a list of rectangles (x0,y0,w,h) from the given overlay
    which is stored in the high bits of the image data, by setting the
    enclosed bits to zero.
    """

    # bits_allocated is the physical space used, 1 or a multiple of 8.
    # bits_stored is the number of meaningful bits within those allocated.
    bits_stored = ds['BitsStored'].value if 'BitsStored' in ds else -1
    bits_allocated = ds['BitsAllocated'].value if 'BitsAllocated' in ds else -1
    overlay_bit = overlay_bit_position(ds, overlay)
    bit_mask = ~(1 << overlay_bit)
    samples = ds['SamplesPerPixel'].value if 'SamplesPerPixel' in ds else -1
    photometric = ds['PhotometricInterpretation'].value if 'PhotometricInterpretation' in ds else 'MONOCHROME2'

    # Can only handle greyscale or palette images
    # XXX would an overlay every be present in an RGB image? Doesn't make sense?
    if photometric not in ['MONOCHROME1', 'MONOCHROME2', 'PALETTE COLOR']:
        logger.error('cannot remove overlays from %s' % photometric)
        return

    # Can only handle 1 sample per pixel
    # XXX would an overlay be present if multiple samples per pixel? Doesn't make sense?
    if samples > 1:
        logger.error('cannot remove overlays from %d samples per pixel' % samples)
        return

    pixel_data = ds.pixel_array # this can raise an exception in some files
    #logger.debug('ndim = %d' % pixel_data.ndim)

    # Use numpy to mask the bits, handles both 8 and 16 bits per pixel.
    # Can't simply &=bit_mask if dtype differs so use 1-elem array.
    bit_mask_arr = np.array([bit_mask], dtype=pixel_data.dtype)

    for rect in rect_list:
        x0, y0, w, h = rect
        x1 = x0 + w
        y1 = y0 + h
        pixel_data[y0:y1, x0:x1] &= bit_mask_arr

    ds.PixelData = pixel_data.tobytes()
    # XXX does not re-compress
    mark_as_uncompressed(ds)
    return


def redact_rectangles_from_image_frame(ds, frame=0, rect_list=[]):
    """ Redact a list of rectangles (x0,y0,w,h) from a specific image frame,
    counting from zero.
    """

    samples = ds['SamplesPerPixel'].value if 'SamplesPerPixel' in ds else -1
    photometric = ds['PhotometricInterpretation'].value if 'PhotometricInterpretation' in ds else 'MONOCHROME2'
    num_frames = ds['NumberOfFrames'].value if 'NumberOfFrames' in ds else 1
    bits_stored = ds['BitsStored'].value if 'BitsStored' in ds else -1
    bit_mask = ((~0) << bits_stored)

    if frame >= num_frames:
        logger.error('cannot redact frame %d, max is %d' % (frame, num_frames-1))
        return

    pixel_data = ds.pixel_array # this can raise an exception in some files
    #logger.debug('ndim = %d (should be the same as samples)' % pixel_data.ndim)

    # Use numpy to mask the bits, handles both 8 and 16 bits per pixel.
    # Can't simply &=bit_mask if dtype differs so use 1-elem array.
    bit_mask_arr = np.array([bit_mask], dtype=pixel_data.dtype)

    for rect in rect_list:
        x0, y0, w, h = rect
        x1 = x0 + w
        y1 = y0 + h
        if pixel_data.ndim == 2:
            pixel_data[y0:y1, x0:x1] &= bit_mask_arr
        elif pixel_data.ndim == 3:
            pixel_data[frame, y0:y1, x0:x1] &= bit_mask_arr
        elif pixel_data.ndim == 4:
            pixel_data[frame, :, y0:y1, x0:x1] &= bit_mask_arr

    ds.PixelData = pixel_data.tobytes()
    # XXX does not re-compress
    mark_as_uncompressed(ds)
    return


def redact_rectangles_from_overlay_frame(ds, frame=0, overlay=0, rect_list=[]):
    """ Redact a list of rectangles from a specific frame of an overlay.
    Frame and overlay count from zero.
    """

    redacted_colour = 0

    overlay_group_num = overlay_tag_group_from_index(overlay)
    if not [overlay_group_num, elem_OverlayData] in ds:
        logger.error('no overlay data found for overlay %d' % overlay)
        return

    pixel_data = ds.overlay_array(overlay_group_num)

    for rect in rect_list:
        x0, y0, w, h = rect
        x1 = x0 + w
        y1 = y0 + h
        if pixel_data.ndim == 2:
            pixel_data[y0:y1, x0:x1] = redacted_colour
        else:
            pixel_data[frame, y0:y1, x0:x1] = redacted_colour

    packed_bytes = pack_bits(pixel_data)

    ds[overlay_group_num, elem_OverlayData].value = packed_bytes
    # XXX not sure if there's a transfer syntax for overlaydata
    return


def redact_rectangles(ds, frame=-1, overlay=-1, rect_list=[]):
    """ Redact a list of rectangles from:
    * the given image frame (if overlay == -1)
    * or the given overlay (if frame == -1)
    * or the given frame of the given overlay (if both >= 0)
    * The rectangles are (x,y,width,height) where
      x,y are from 0,0 top-left
    """

    if not rect_list:
        logger.debug('no rectangles to redact')
        return None

    if not 'PixelData' in ds:
        logger.error('no pixel data present')
        return None

    if overlay == -1:
        return redact_rectangles_from_image_frame(ds, frame, rect_list)

    if overlay < 0 or overlay > 15:
        logger.error('invalid overlay requested %d' % overlay)
        return None

    if overlay_bit_position(ds, overlay) > 0:
        if frame > 0:
            logger.error('cannot specify an overlay frame %d when overlay %d is in image high bits' % (frame, overlay))
            return None
        return redact_rectangles_from_high_bit_overlay(ds, overlay, rect_list)
    else:
        return redact_rectangles_from_overlay_frame(ds, frame, overlay, rect_list)


# ---------------------------------------------------------------------

def redact_DicomRect_rectangles(ds, dicomrect_list):
    """ Split the list by frame/overlay and call redact_rectangles.
    """
    for dr in dicomrect_list:
        print(dr)
    frameoverlay_list = [(dr.F(), dr.O()) for dr in dicomrect_list]
    frameoverlay_set = set(frameoverlay_list) # to get unique values
    for (frame,overlay) in frameoverlay_set:
        rect_list = [ (dr.L(), dr.T(), 1+dr.R()-dr.L(), 1+dr.B()-dr.T())
            for dr in dicomrect_list if dr.F() == frame and dr.O() == overlay]
        #print('calling redact_rectangles(%d, %d) with %s' % (frame,overlay,rect_list))
        redact_rectangles(ds, frame=frame, overlay=overlay, rect_list=rect_list)


# ---------------------------------------------------------------------

def read_DicomRect_listmap_from_csv(csv_filename, filename=None, frame=-1, overlay=-1):
    """ Read left,top,right,bottom from CSV and turn into rectangle list.
    Ignores coordinates which are all negative -1,-1,-1,-1.
    Can filter by filename, frame, overlay if desired.
    Returns a map of filenames, where each filename entry is
    a list of DicomRect objects, or [].
    If you asked for an explicit filename it will be the only entry in the map.
    e.g.
    mapping['filename1'] = [ DicomRect(..), DicomRect(..) ]
    """
    dicom_rectlist = {}
    with open(csv_filename) as csv_fd:
        csv_reader = csv.DictReader(csv_fd)
        for row in csv_reader:
            # If a filename has been given then ignore any other files
            if filename and ('filename' in row) and (filename != row['filename']):
                continue
            # Ignore entries which don't have a valid rectangle
            # (these will be OCR summaries for the whole frame)
            (row_left, row_top, row_right, row_bottom) = (int(row['left']), int(row['top']), int(row['right']), int(row['bottom']))
            (row_frame, row_overlay) = (int(row.get('frame', -1)), int(row.get('overlay', -1)))
            if row_left < 0:
                continue
            # If a frame has been given then ignore any other frames
            if (frame != -1) and (frame != row_frame):
                continue
            # If an overlay has been given then ignore any other overlays
            if (overlay != -1) and (overlay != row_overlay):
                continue
            dicomrect = DicomRect(left=row_left, top=row_top,
                right=row_right, bottom=row_bottom,
                frame=row_frame, overlay=row_overlay)
            if row['filename'] in dicom_rectlist:
                dicom_rectlist[row['filename']].append( dicomrect )
            else:
                dicom_rectlist[row['filename']] = [ dicomrect ]
    return dicom_rectlist


# ---------------------------------------------------------------------

def read_DicomRect_list_from_database(db_dir=None, filename=None, frame=-1, overlay=-1):
    """ Read left,top,right,bottom from CSV and turn into rectangle list.
    Ignores coordinates which are all negative -1,-1,-1,-1.
    Can filter by filename, frame, overlay if desired.
    Returns a list of DicomRect objects, or [].
    """
    #database_path = os.path.join(os.getenv('SMI_ROOT'), "data", "dicompixelanon/") # needs trailing slash
    if db_dir:
        DicomRectDB.db_path = db_dir
    db = DicomRectDB()
    rect_list = db.query_rects(filename, frame=frame, overlay=overlay)
    return rect_list


# ---------------------------------------------------------------------

def decode_rect_list_string(rect_str):
    """
    x0,y0,x1,y1
    x0,y0,+w,+h
     with frame,overlay appended
     separated by ; with optional brackets for clarity
    eg. (10,10,30,30,0,-1);10,10,+20,+20
    """
    print(rect_str)
    rect_list = []
    rect_str = rect_str.replace('(', '')
    rect_str = rect_str.replace(')', '')
    rect_str = rect_str.replace(' ', '')
    rect_arr = rect_str.split(';')
    for rect in rect_arr:
        frame = -1
        overlay = -1
        rect_elems = rect.split(',')
        x0 = int(rect_elems[0])
        y0 = int(rect_elems[1])
        if '+' in rect_elems[2]:
            x1 = int(rect_elems[2]) + x0
        else:
            x1 = int(rect_elems[2])
        if '+' in rect_elems[3]:
            y1 = int(rect_elems[3]) + y0
        else:
            y1 = int(rect_elems[3])
        if len(rect_elems) > 4:
            frame = int(rect_elems[4])
        if len(rect_elems) > 5:
            overlay = int(rect_elems[5])
        dr = DicomRect(left = x0, top = y0, right = x1, bottom = y1, frame = frame, overlay = overlay)
        rect_list.append(dr)
    return rect_list

# ---------------------------------------------------------------------

def is_directory_writable(dirname):
    """ Test if a directory is writable by trying to write a file
    """
    tmpfile = os.path.join(dirname, 'tmp.XXX')
    try:
        with open(tmpfile, 'w') as fd:
            pass
        os.remove(tmpfile)
        return True
    except:
        return False


def create_output_filename(infilename, outfilename = None):
    """ Return a suitable output filename given an input filename
    and an optional output file name or directory.
    If outfilename is specified (and is not a directory) then use it.
    If outfilename is specified and is a directory then use
    that directory.
    If outfilename is not specified then use the the same directory
    as the input unless it's read-only in which case use current dir.
    Output filename (if not specified) will be the infilename but
    with .dcm extension removed and .redacted.dcm added.
    """
    infile = os.path.basename(infilename)
    if outfilename:
        if is_directory_writable(outfilename):
            return os.path.join(outfilename, infile.replace('.dcm', '') + '.redacted.dcm')
    dirname = os.path.dirname(infilename)
    if not is_directory_writable(dirname):
        dirname = '.'
    return os.path.join(dirname, infile.replace('.dcm', '') + '.redacted.dcm')


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Redact DICOM')
    parser.add_argument('-v', '--verbose', action="store_true", help='Verbose')
    parser.add_argument('--db', dest='db', action="store", help='database directory to read rectangles (needs --dicom)')
    parser.add_argument('--csv', dest='csv', action="store", help='CSV path to read rectangles (redacts all files in csv if --dicom not used)')
    parser.add_argument('--dicom', dest='dicom', action="store", help='DICOM filename to be redacted', default=None)
    parser.add_argument('-o', '--output', dest='output', action="store", help='Output DICOM dir or filename (created automatically if not specified)', default=None)
    parser.add_argument('--remove-high-bit-overlays', action="store_true", help='remove overlays in high-bits of image pixels', default=False)
    parser.add_argument('-r', '--rect', dest='rects', nargs='*', default=[], help='rectangles x0,y0,x1,y1 or x0,y0,+w,+h;...')
    args = parser.parse_args()

    # Will be a map from filename to a list of DicomRect
    rect_list_map = {}
    if args.dicom:
        rect_list_map[args.dicom] = []

    # If we only want to remove the high bit overlays
    if args.dicom and args.remove_high_bit_overlays:
        if args.rects:
            logger.error('Sorry, cannot redact rectangles at the same time as removing high bit overlays (yet)')
            sys.exit(2)
        infile = args.dicom
        outfile = os.path.basename(infile) + ".nooverlays.dcm"
        ds = pydicom.dcmread(infile)
        remove_overlays_in_high_bits(ds)
        ds.save_as(outfile)
        sys.exit(0)

    # If given a list of rectangles explicitly then it must be for a given filename
    if args.rects:
        if not args.dicom:
            logger.error('Must specify a DICOM file to go with the rectangles')
            sys.exit(1)
        for rect_str in args.rects:
            rect_list_map[args.dicom] += decode_rect_list_string(rect_str)

    # If given a database then we need a filename to search for
    if args.db:
        if not args.dicom:
            logger.error('Must specify a DICOM file to find in the database')
            sys.exit(1)
        rect_list_map[args.dicom] += read_DicomRect_list_from_database(db_dir = args.db, filename = args.dicom)

    # If given a CSV file then we can process every DICOM in the file
    # or just the single filename provided
    if args.csv:
        if args.dicom:
            rect_list_map = read_DicomRect_listmap_from_csv(csv_filename = args.csv, filename = args.dicom)
        else:
            rect_list_map = read_DicomRect_listmap_from_csv(csv_filename = args.csv)

    # Redact 
    for infilename in rect_list_map.keys():
        rect_list = rect_list_map[infilename]
        outfilename = create_output_filename(infilename, args.output)
        ds = pydicom.dcmread(infilename)
        redact_DicomRect_rectangles(ds, rect_list)
        ds.save_as(outfilename)
