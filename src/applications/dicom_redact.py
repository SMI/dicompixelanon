#!/usr/bin/env python3
# Redact a DICOM image to deidentify it:
#  * can remove the overlay planes stored in the high bits of the image data
#  * can redact rectangles from any of the image frames or overlay frames

# TODO: change all errors to raise exceptions
# TODO: read ocrtext from CSV files (like is already done from database)
# TODO: use allowlist from database?
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
import re
import pydicom
# pack_bits moved from pixel_data_handlers to pixels.utils in pydicom v3
try:
    from pydicom.pixels.utils import pack_bits
else:
    from pydicom.pixel_data_handlers.numpy_handler import pack_bits
from DicomPixelAnon.rect import Rect, DicomRect, DicomRectText, rect_exclusive_list
from DicomPixelAnon.nerengine import NER
from DicomPixelAnon.ocrenum import OCREnum
from DicomPixelAnon.nerenum import NEREnum
from DicomPixelAnon import ultrasound
from DicomPixelAnon import deidrules
import sys
try:
    from DicomPixelAnon.dicomrectdb import DicomRectDB
    dbEnabled = True
except:
    dbEnabled = False

logger = logging.getLogger(__name__)

# Need examples of:
#  high-bit overlays (and multiple of them)
#  separate overlays (and multiple of them)
#  multiple frames in separate overlays
#  multiple frames of images
#  mono, inverted mono, signed ints, RGB, Palette, etc
#  various compression
filename = 'US-GE-4AICL142.dcm'                # has SequenceOfUltrasoundRegions
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
    """ Mark a DICOM file as containing uncompressed image data.
    Call this after you've uncompressed the PixelData
    and written it back into the dataset using tobytes().
    It only changes the TransferSyntaxUID, to either
    ExplicitVRLittleEndian or ExplicitVRBigEndian as appropriate.
    XXX not sure about this.
    """
    if sys.byteorder == 'little':
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    else:
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRBigEndian


# ---------------------------------------------------------------------

def overlay_tag_group_from_index(overlay):
    """ Convert an overlay index 0..15 into a DICOM tag group
    They start at 0x6000 and go up in twos, e.g. 0=0x6000, 1=0x6002.
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
    samples = ds['SamplesPerPixel'].value if 'SamplesPerPixel' in ds else -1
    photometric = ds['PhotometricInterpretation'].value if 'PhotometricInterpretation' in ds else 'MONOCHROME2'

    # Calculate bit mask to keep only the bits in use not the overlays
    bit_mask = np.array((1<<bits_stored)-1).astype(np.uint16)

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
    logger.debug('photometric = %s' % photometric)

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
    # Set the pixel data from the numpy array
    # XXX Should use set_pixel_data() ?
    # XXX See https://github.com/pydicom/pydicom/pull/2082
    ds.PixelData = masked.tobytes()

    # XXX does not re-compress
    mark_as_uncompressed(ds)
    # No need to handle ICC Profile, Colour Space, Palette Lookup Table, etc
    # No need to handle 2's complement Pixel Representation.
    return


# ---------------------------------------------------------------------

def redact_rectangles_from_high_bit_overlay(ds, overlay=0, rect_list=None):
    """ Redact a list of rectangles (x0,y0,w,h) from the given overlay
    which is stored in the high bits of the image data, by setting the
    enclosed bits to zero.
    """
    if not rect_list:
        rect_list = []

    # bits_allocated is the physical space used, 1 or a multiple of 8.
    # bits_stored is the number of meaningful bits within those allocated.
    bits_stored = ds['BitsStored'].value if 'BitsStored' in ds else -1
    bits_allocated = ds['BitsAllocated'].value if 'BitsAllocated' in ds else -1
    overlay_bit = overlay_bit_position(ds, overlay)
    samples = ds['SamplesPerPixel'].value if 'SamplesPerPixel' in ds else -1
    photometric = ds['PhotometricInterpretation'].value if 'PhotometricInterpretation' in ds else 'MONOCHROME2'

    # Calculate mask to remove only the bit used by this particular overlay
    bit_mask = np.array(0xffff ^ ( 1 << overlay_bit)).astype(np.uint16)

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
        if x0 < 0 or y0 < 0 or w < 1 or h < 1:
            continue
        x1 = x0 + w
        y1 = y0 + h
        pixel_data[y0:y1, x0:x1] &= bit_mask_arr

    # Set the pixel data from the numpy array
    # XXX Should use set_pixel_data() ?
    # XXX See https://github.com/pydicom/pydicom/pull/2082
    ds.PixelData = pixel_data.tobytes()
    # XXX does not re-compress
    mark_as_uncompressed(ds)
    return


def redact_rectangles_from_image_frame(ds, frame=0, rect_list=None):
    """ Redact a list of rectangles (x0,y0,w,h) from a specific image frame,
    counting from zero.
    """
    if not rect_list:
        rect_list = []

    samples = ds['SamplesPerPixel'].value if 'SamplesPerPixel' in ds else -1
    photometric = ds['PhotometricInterpretation'].value if 'PhotometricInterpretation' in ds else 'MONOCHROME2'
    num_frames = ds['NumberOfFrames'].value if 'NumberOfFrames' in ds else 1
    bits_stored = ds['BitsStored'].value if 'BitsStored' in ds else -1

    # Calculate mask to set pixel to black without breaking high bit overlays
    bit_mask = np.array(0xffff << bits_stored).astype(np.uint16)

    if frame >= num_frames:
        logger.error('cannot redact frame %d, max is %d' % (frame, num_frames-1))
        return

    pixel_data = ds.pixel_array # this can raise an exception in some files
    if photometric not in ['MONOCHROME1', 'MONOCHROME2', 'PALETTE COLOR', 'RGB']:
        # Typically one of HSV,ARGB,CMYK,YBR_FULL,YBR_FULL_422,YBR_PARTIAL_422,YBR_PARTIAL_420,YBR_ICT,YBR_RCT
        # Must be converted to RGB simply because it would confuse the TransferSyntax otherwise
        # (e.g. jpeg colour in an uncompressed transfersyntax) ?
        pixel_data = pydicom.pixel_data_handlers.convert_color_space(ds.pixel_array, photometric, "RGB", per_frame=True)
        ds.PhotometricInterpretation = 'RGB'
    #logger.debug('ndim = %d (should be the same as samples)' % pixel_data.ndim)

    # Use numpy to mask the bits, handles both 8 and 16 bits per pixel.
    # Can't simply &=bit_mask if dtype differs so use 1-elem array.
    bit_mask_arr = np.array([bit_mask], dtype=pixel_data.dtype)

    for rect in rect_list:
        x0, y0, w, h = rect
        if x0 < 0 or y0 < 0 or w < 1 or h < 1:
            continue
        x1 = x0 + w
        y1 = y0 + h
        if pixel_data.ndim == 2:
            pixel_data[y0:y1, x0:x1] &= bit_mask_arr
        elif pixel_data.ndim == 3 and (samples == 3 or photometric == 'RGB'):
            # XXX assumes the colour channel is the last element
            pixel_data[y0:y1, x0:x1, :] &= bit_mask_arr
        elif pixel_data.ndim == 3:
            # XXX assumes the frame channel is the first element
            pixel_data[frame, y0:y1, x0:x1] &= bit_mask_arr
        elif pixel_data.ndim == 4:
            # XXX assumes the frame channel is the first element
            # XXX assumes the colour channel is the last element
            pixel_data[frame, y0:y1, x0:x1, :] &= bit_mask_arr

    # Set the pixel data from the numpy array
    # XXX Should use set_pixel_data() ?
    # XXX See https://github.com/pydicom/pydicom/pull/2082
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
        if x0 < 0 or y0 < 0 or w < 1 or h < 1:
            continue
        if pixel_data.ndim == 2:
            pixel_data[y0:y1, x0:x1] = redacted_colour
        else:
            pixel_data[frame, y0:y1, x0:x1] = redacted_colour

    packed_bytes = pack_bits(pixel_data)

    ds[overlay_group_num, elem_OverlayData].value = packed_bytes
    # XXX not sure if there's a transfer syntax for overlaydata
    return


def redact_rectangles(ds, frame=-1, overlay=-1, rect_list=None):
    """ Redact a list of rectangles from:
    * the given image frame (if overlay not given or == -1)
    * or the given overlay (if frame not given or == -1)
    * or the given frame of the given overlay (if both >= 0)
    * The rectangles are (x,y,width,height) where
      x,y are from 0,0 top-left
    ds is the pydicom Dataset object.
    """

    if not rect_list:
        rect_list = []

    if not rect_list:
        logger.debug('no rectangles to redact')
        return None

    if not 'PixelData' in ds:
        logger.error('no pixel data present')
        return None

    # Redact all frames, all overlays, all frames in overlays
    if overlay == -1 and frame == -1:
        num_frames = ds['NumberOfFrames'].value if 'NumberOfFrames' in ds else 1
        # Redact all the frames
        for frame in range(num_frames):
            redact_rectangles_from_image_frame(ds, frame, rect_list)
        # Redact all the high-bit overlays (if any)
        for overlay_num in range(16):
            overlay_bit = overlay_bit_position(ds, overlay_num)
            if overlay_bit_position(ds, overlay_num) > 0:
                redact_rectangles_from_high_bit_overlay(ds, overlay_num, rect_list)
        # Redact all the frames in all the overlays
        for overlay_num in range(16):
            overlay_group_num = overlay_tag_group_from_index(overlay_num)
            if [overlay_group_num, elem_OverlayData] in ds:
                # Redact the first frame in this overlay
                redact_rectangles_from_overlay_frame(ds, 0, overlay_num, rect_list)
                # XXX not yet implemented - does not redact ALL frames in this overlay
        return

    # Only a single frame
    if overlay == -1:
        return redact_rectangles_from_image_frame(ds, frame, rect_list)

    # A single overlay
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
# Functions to implement an allow-list for letting through rectangles
# whose text exactly matches a pattern.

def load_allowlist(filename = None):
    """ Initialise the allow-list (allowlist) by constructing a NER
    object and keeping it in a global variable.
    XXX this is a hacky way of making a singleton.
    Returns the NER object on which you can call the detect() method.
    You only need to call this function once but it's safe to call it
    every time you need to use detect().
    """
    global ocr_allowlist
    try:
        return ocr_allowlist
    except:
        ocr_allowlist = NER('ocr_allowlist')
    return ocr_allowlist

def test_load_allowlist():
    allowlist = load_allowlist()
    assert(allowlist)
    

def rect_in_allowlist(rect):
    """ Return True if the text contained in the rectangle is safe
    and doesn't need to be redacted. By default, return False, unless
    the text is on a known allowlist. rect should be a DicomRectText
    but if it's a DicomRect or Rect then it simply returns False.
    """
    allowlist = load_allowlist()
    # If the rect is a DicomRectText object it has a text_tuple method
    if hasattr(rect, 'text_tuple'):
        ocrengine,ocrtext,nerengine,nerpii = rect.text_tuple()
    else:
        ocrtext = ''
    # Check if rectangle already tested against allowlist
    if ocrtext and (nerengine == NEREnum.allowlist) and (nerpii == 0):
        return True
    # Check allowlist
    if ocrtext and allowlist.detect(ocrtext) == []:
        return True
    return False

def test_rect_in_allowlist():
    assert(rect_in_allowlist(DicomRectText(ocrtext='ERECT')))
    assert(rect_in_allowlist(DicomRectText(ocrtext='AP ERECT')))
    assert(rect_in_allowlist(DicomRectText(ocrtext='PA ERECT')))
    assert(not rect_in_allowlist(DicomRectText(ocrtext='NOT ERECT', top=0)))
    

def filter_rect_list(rect_list):
    """ Filter the DicomRectText list to remove all items which are "safe"
    based on an allow-list. The list should be a list of DicomRectText objects
    so we can test the ocrtext but if it's not (because it's a DicomRect,
    or the text is empty) then it's assumed unsafe so is kept in the list.
    Filters in-place and also returns list.
    """
    rect_list[:] = [rect for rect in rect_list if not rect_in_allowlist(rect)]
    return rect_list

def test_filter_rect_list():
    rect1 = DicomRectText(ocrtext = 'ERECT')
    rect2 = DicomRectText(ocrtext = 'NOT ERECT')
    rect3 = DicomRectText(ocrtext = 'AP ERECT')
    rect_list = [rect1, rect2, rect3]
    filtered_rect_list = filter_rect_list(rect_list)
    assert(len(filtered_rect_list) == 1) # one bad rect remains
    assert(filtered_rect_list[0].text_tuple()[1] == 'NOT ERECT')

# ---------------------------------------------------------------------

def redact_DicomRect_rectangles(ds, dicomrect_list):
    """ Redact all the rectangles in the given DicomRectText list
    from the image in the DICOM file which has been read into a
    pydicom.dataset.Dataset object (from dcmread).
    The list may contain rectangles from any frame,overlay, so it
    splits the list by frame/overlay and call redact_rectangles
    on each grouping.
    """
    frameoverlay_list = [(dr.F(), dr.O()) for dr in dicomrect_list]
    frameoverlay_set = set(frameoverlay_list) # to get unique values
    for (frame,overlay) in frameoverlay_set:
        # convert from corner coord to width,height
        rect_list = [ (dr.L(), dr.T(), 1+dr.R()-dr.L(), 1+dr.B()-dr.T())
            for dr in dicomrect_list if dr.F() == frame and dr.O() == overlay]
        # Remove rect which are safe (in the allowlist)
        rect_list = filter_rect_list(rect_list)
        # Perform the redaction on the pydicom dataset
        redact_rectangles(ds, frame=frame, overlay=overlay, rect_list=rect_list)


# ---------------------------------------------------------------------

def read_DicomRectText_listmap_from_csv(csv_filename, filename=None, frame=-1, overlay=-1):
    """ Read left,top,right,bottom from CSV and turn into rectangle list.
    Ignores coordinates which are all negative -1,-1,-1,-1.
    Can filter by filename, frame, overlay if desired.
    Returns a map/dict of filenames, where each filename entry is
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
            (row_left, row_top, row_right, row_bottom) = (int(row['left']), int(row['top']), int(row['right']), int(row['bottom']))
            (row_frame, row_overlay) = (int(row.get('frame', -1)), int(row.get('overlay', -1)))
            row_ocrenginename = row.get('ocr_engine', '')
            row_ocrtext = row.get('ocr_text', '')
            row_nerenginename = row.get('ner_engine', '')
            row_nerpii = row.get('is_sensitive', -1)
            row_ocrengine = OCREnum().enum(row_ocrenginename)
            row_nerengine = NEREnum().enum(row_nerenginename)

            # Ignore entries which don't have a valid rectangle
            # (these will be OCR summaries for the whole frame)
            if row_left < 0:
                continue
            # If a frame has been given then ignore any other frames
            if (frame != -1) and (frame != row_frame):
                continue
            # If an overlay has been given then ignore any other overlays
            if (overlay != -1) and (overlay != row_overlay):
                continue
            dicomrect = DicomRectText(left=row_left, top=row_top,
                right=row_right, bottom=row_bottom,
                frame=row_frame, overlay=row_overlay,
                ocrengine = row_ocrengine, ocrtext = row_ocrtext,
                nerengine = row_nerengine, nerpii = row_nerpii)
            if row['filename'] in dicom_rectlist:
                dicom_rectlist[row['filename']].append( dicomrect )
            else:
                dicom_rectlist[row['filename']] = [ dicomrect ]
    return dicom_rectlist


# ---------------------------------------------------------------------
def read_DicomRectText_list_from_database(db_dir=None, filename=None, frame=-1, overlay=-1):
    """ Read left,top,right,bottom from CSV and turn into rectangle list.
    Ignores coordinates which are all negative -1,-1,-1,-1.
    Can filter by filename, frame, overlay if desired.
    Returns a list of DicomRect objects, or [].
    """
    #database_path = os.path.join(os.getenv('SMI_ROOT'), "data", "dicompixelanon/") # needs trailing slash
    if db_dir:
        DicomRectDB.set_db_path(db_dir)
    db = DicomRectDB()
    rect_list = db.query_rects(filename, frame=frame, overlay=overlay,
        ignore_allowlisted = True, ignore_summaries = True)
    return rect_list


# ---------------------------------------------------------------------

def decode_rect_list_string(rect_str):
    """
    Decode a string containing one or more rectangles
    and return a list of DicomRect objects, or [].
    x0,y0,x1,y1 - one rectangle given by corner coordinates.
    x0,y0,+w,+h - one rectangle given by top-left,width,height.
    frame,overlay can also be appended; use -1 for either if
    not applicable, e.g. first and only image frame is 0,-1.
    Multiple rectangles separated by ; semi-colon.
    Can use optional brackets for clarity, e.g.
    eg. (10,10,30,30,0,-1);10,10,+20,+20
    """
    rect_list = []
    rect_str = rect_str.replace('(', '')
    rect_str = rect_str.replace(')', '')
    rect_str = rect_str.replace(' ', '')
    rect_arr = rect_str.split(';')
    for rect in rect_arr:
        frame = -1
        overlay = -1
        rect_elems = rect.split(',')
        if len(rect_elems) < 4:
            raise ValueError("A rectangle must have at least 4 comma-separated values")
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

def test_decode_rect_list_string():
    assert(decode_rect_list_string('1,2,3,4') == [DicomRect(2,4,1,3)])
    assert(decode_rect_list_string('1,2,+3,+4') == [DicomRect(2,6,1,4)])
    assert(decode_rect_list_string('1,2,+3,+4,5,6') == [DicomRect(2,6,1,4,5,6)])
    assert(decode_rect_list_string('1,2,3,4;5,6,7,8') == [DicomRect(2,4,1,3), DicomRect(6,8,5,7)])
    assert(decode_rect_list_string('(1,2,3,4) ; (5,6,7,8)') == [DicomRect(2,4,1,3), DicomRect(6,8,5,7)])


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


def create_output_filename(infilename, outfilename = None, relative = None):
    """ Return a suitable output filename given an input filename
    and an optional output file name or directory.
    If outfilename is specified (and is not a directory) then use it.
    If outfilename is specified and is a directory then use
    that directory. If relative is specified then that part of the input
    path will be removed and the output will be the same as the rest of
    the input path but relative to the output directory. Intermediate
    directories will be created as required.
    If outfilename is not specified then use the the same directory
    as the input unless it's read-only in which case use current dir.
    Output filename (if not specified) will be the infilename but
    with .dcm extension removed and .redacted.dcm added.
    """
    infile = os.path.basename(infilename)
    if outfilename:
        if is_directory_writable(outfilename):
            if relative:
                outfilename = os.path.join(outfilename, os.path.relpath(infilename, relative))
                os.makedirs(os.path.dirname(outfilename), exist_ok = True)
                return outfilename
            else:
                return os.path.join(outfilename, infile.replace('.dcm', '') + '.redacted.dcm')
        else:
            return outfilename
    dirname = os.path.dirname(infilename)
    if not is_directory_writable(dirname):
        dirname = '.'
    return os.path.join(dirname, infile.replace('.dcm', '') + '.redacted.dcm')


def test_create_output_filename():
    assert(create_output_filename('file') == 'file.redacted.dcm')
    assert(create_output_filename('file.dcm') == 'file.redacted.dcm')
    assert(create_output_filename('no_such_dir/file.dcm') == './file.redacted.dcm')
    assert(create_output_filename('/tmp/file.dcm') == '/tmp/file.redacted.dcm')
    assert(create_output_filename('file.dcm', 'newfile.dcm') == 'newfile.dcm')
    assert(create_output_filename('file.dcm', '/tmp') == '/tmp/file.redacted.dcm')
    assert(create_output_filename('file.dcm', '/bin') == '/bin') # XXX !!!
    assert(create_output_filename('/path/to/my/file.dcm', '.', '/path/to') == './my/file.dcm')
    assert(create_output_filename('/path/to/my/file.dcm', '/tmp', '/path/to') == '/tmp/my/file.dcm')


# ---------------------------------------------------------------------

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Redact DICOM')
    parser.add_argument('-v', '--verbose', action="store_true", help='Verbose')
    parser.add_argument('--db', dest='db', action="store", help='database directory to read rectangles (needs --dicom)')
    parser.add_argument('--csv', dest='csv', action="store", help='CSV path to read rectangles (redacts all files in csv if --dicom not used)')
    parser.add_argument('--dicom', dest='dicom', nargs='*', action="store", help='DICOM filename(s) to be redacted', default=None)
    parser.add_argument('-o', '--output', dest='output', action="store", help='Output DICOM dir or filename (created automatically if not specified)', default=[])
    parser.add_argument('--relative-path', dest='relative', action="store", help='Output DICOM dir will be relative to input but with this prefix removed from input path', default=None)
    parser.add_argument('--remove-high-bit-overlays', action="store_true", help='remove overlays in high-bits of image pixels', default=False)
    parser.add_argument('--remove-ultrasound-regions', action="store_true", help='remove around the stored ultrasound regions', default=False)
    parser.add_argument('--deid', action="store_true", help='Use deid-recipe rules to redact', default=False)
    parser.add_argument('--deid-rules', action="store", help='Path to file or directory containing deid recipe files (deid.dicom.*)', default=None)
    parser.add_argument('-r', '--rect', dest='rects', default=None, help='rectangles x0,y0,x1,y1 or x0,y0,+w,+h;...')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    # Will be a map from filename to a list of DicomRect
    rect_list_map = {}
    for filename in args.dicom:
        rect_list_map[filename] = []

    # If we only want to remove the high bit overlays
    if args.dicom and args.remove_high_bit_overlays:
        if args.rects:
            logger.error('Sorry, cannot redact rectangles at the same time as removing high bit overlays (yet)')
            sys.exit(2)
        for infilename in args.dicom:
            outfile = os.path.basename(infile) + ".nooverlays.dcm" # XXX should use create_output_filename(infilename, args.output, args.relative)
            ds = pydicom.dcmread(infilename)
            remove_overlays_in_high_bits(ds)
            ds.save_as(outfile)
            sys.exit(0)

    # If given a list of rectangles explicitly then it must be for a given filename
    if args.rects:
        if not args.dicom:
            logger.error('Must specify a DICOM file to go with the rectangles')
            sys.exit(1)
        for filename in args.dicom:
            rect_list_map[filename] += decode_rect_list_string(args.rects)

    # Get a list of rectangles surrounding the UltrasoundRegions
    if args.dicom and args.remove_ultrasound_regions:
        for filename in args.dicom:
            rect_list_map[filename] += ultrasound.read_DicomRectText_list_from_region_tags(filename = filename)

    # If given a database then we need a filename to search for
    if args.db:
        if not dbEnabled:
            logger.error('Database support is not available')
            sys.exit(1)
        if not args.dicom:
            logger.error('Must specify a DICOM file to find in the database')
            sys.exit(1)
        for filename in args.dicom:
            rect_list_map[filename] += read_DicomRectText_list_from_database(db_dir = args.db, filename = filename)

    # If using deid recipes then find the recipe files and use them to add rectangles
    if args.deid:
        if args.deid_rules:
            logger.error('Sorry, specifying a deid rules file/directory is not yet implemented')
        for filename in args.dicom:
            rect_list_map[filename] += deidrules.detect(filename)

    # If given a CSV file then we can process every DICOM in the file
    # or just the filename(s) provided
    if args.csv:
        if args.dicom:
            for filename in args.dicom:
                rect_list_map = read_DicomRectText_listmap_from_csv(csv_filename = args.csv, filename = filename)
        else:
            rect_list_map = read_DicomRectText_listmap_from_csv(csv_filename = args.csv)

    # Redact 
    for infilename in rect_list_map.keys():
        rect_list = rect_list_map[infilename]
        outfilename = create_output_filename(infilename, args.output, args.relative)
        ds = pydicom.dcmread(infilename)
        redact_DicomRect_rectangles(ds, rect_list)
        ds.save_as(outfilename)
