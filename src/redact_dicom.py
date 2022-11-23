#!/usr/bin/env python3

import logging
import pydicom
from pydicom.pixel_data_handlers.numpy_handler import pack_bits
from dicomimage import DicomImage
import sys

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

elem_OverlayBitPosition = 0x0102
elem_OverlayData = 0x3000
elem_OverlayRows = 0x0010
elem_OverlayCols = 0x0011
elem_OverlayNumFrames = 0x0015
elem_OverlayOrigin = 0x0050


def mark_as_uncompressed(ds):
    """ Call this after you've uncompressed the PixelData
    and written it back into the dataset using tobytes()
    """
    if sys.byteorder == 'little':
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    else:
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRBigEndian


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


def remove_overlays_in_high_bits(ds):
    """ Mask off the high-bits of all the pixel values
    just in case there are overlays hidden in there
    which we want to remove (simply removing the 60xx tags
    does not actually remove the overlay pixels).
    """

    # Sanity check that image has pixels
    if not 'PixelData' in ds:
        logger.debug('no pixel data present')
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
        overlay_bit = overlay_bit_position(overlay_num)
        if overlay_bit > 0:
            logger.debug('Found overlay %d in high-bit %d' % (overlay_num, overlay_bit))
            overlay_bitmask |= (1 << overlay_bit)
    logger.debug('bits_stored = %d (image bits used)' % bits_stored)
    logger.debug('bits_allocated = %d (physical space needed)' % bits_allocated)
    logger.debug('bit_mask = %x (use & to get only image data)' % bit_mask)
    logger.debug('overlay_bitmask = %x (for overlays in use)' % overlay_bitmask)
    logger.debug('samples = %d' % samples)

    # Can only handle greyscale or palette images
    # XXX would an overlay every be present in an RGB image? Doesn't make sense?
    if photometric not in ['MONOCHROME1', 'MONOCHROME2', 'PALETTE COLOR']:
        logger.debug('cannot remove overlays from %s' % photometric)
        return

    # Can only handle 1 sample per pixel
    # XXX would an overlay be present if multiple samples per pixel? Doesn't make sense?
    if samples > 1:
        logger.debug('cannot remove overlays from %d samples per pixel' % samples)
        return

    pixel_data = ds.pixel_array # this can raise an exception in some files
    logger.debug('ndim = %d (should be the same as samples)' % pixel_data.ndim)

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


def redact_rectangles_from_high_bit_overlay(ds, overlay, rect_list):
    """
    """
    # bits_allocated is the physical space used, 1 or a multiple of 8.
    # bits_stored is the number of meaningful bits within those allocated.
    bits_stored = ds['BitsStored'].value if 'BitsStored' in ds else -1
    bits_allocated = ds['BitsAllocated'].value if 'BitsAllocated' in ds else -1
    overlay_bit = overlay_bit_position(overlay)
    bit_mask = ~(1 << overlay_bit)
    samples = ds['SamplesPerPixel'].value if 'SamplesPerPixel' in ds else -1
    photometric = ds['PhotometricInterpretation'].value if 'PhotometricInterpretation' in ds else 'MONOCHROME2'

    # Can only handle greyscale or palette images
    # XXX would an overlay every be present in an RGB image? Doesn't make sense?
    if photometric not in ['MONOCHROME1', 'MONOCHROME2', 'PALETTE COLOR']:
        logger.debug('cannot remove overlays from %s' % photometric)
        return

    # Can only handle 1 sample per pixel
    # XXX would an overlay be present if multiple samples per pixel? Doesn't make sense?
    if samples > 1:
        logger.debug('cannot remove overlays from %d samples per pixel' % samples)
        return

    pixel_data = ds.pixel_array # this can raise an exception in some files
    logger.debug('ndim = %d (should be the same as samples)' % pixel_data.ndim)

    for rect in rect_list:
        x0, y0, w, h = rect
        x1 = x0 + w
        y1 = y0 + h
        # Use numpy to mask the bits, handles both 8 and 16 bits per pixel.
        pixel_data[y0:y1, x0:x1] &= bit_mask

    ds.PixelData = pixel_data.tobytes()
    # XXX does not re-compress
    mark_as_uncompressed(ds)
    return


def redact_rectangles_from_image_frame(ds, frame, rect_list):
    """ Redact a list of rectangles from a specific image frame
    counting from zero.
    """
    redacted_colour = 0

    samples = ds['SamplesPerPixel'].value if 'SamplesPerPixel' in ds else -1
    photometric = ds['PhotometricInterpretation'].value if 'PhotometricInterpretation' in ds else 'MONOCHROME2'
    num_frames = ds['NumberOfFrames'].value if 'NumberOfFrames' in ds else 1
    bits_stored = ds['BitsStored'].value if 'BitsStored' in ds else -1
    bit_mask = (~((~0) << bits_stored))

    pixel_data = ds.pixel_array # this can raise an exception in some files
    logger.debug('ndim = %d (should be the same as samples)' % pixel_data.ndim)

    for rect in rect_list:
        x0, y0, w, h = rect
        x1 = x0 + w
        y1 = y0 + h
        if pixel_data.ndim == 2:
            pixel_data[y0:y1, x0:x1] = redacted_colour
        elif pixel_data.ndim == 3:
            pixel_data[frame, y0:y1, x0:x1] = redacted_colour
        elif pixel_data.ndim == 4:
            pixel_data[frame, :, y0:y1, x0:x1] = redacted_colour

    ds.PixelData = pixel_data.tobytes()
    # XXX does not re-compress
    mark_as_uncompressed(ds)
    return


def redact_rectangles_from_overlay_frame(ds, frame, overlay, rect_list):
    """ Redact a list of rectangles from a specific frame of an overlay.
    Frame and overlay count from zero.
    """
    redacted_colour = 0

    overlay_group_num = overlay_tag_group_from_index(overlay)
    if not [overlay_group_num, DicomImage.elem_OverlayData] in ds:
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

    ds[overlay_group_num, DicomImage.elem_OverlayData] = packed_bytes
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
        return

    if not 'PixelData' in ds:
        logger.debug('no pixel data present')
        return

    if overlay == -1:
        return redact_rectangles_from_image_frame(ds, frame, rect_list)

    if overlay < 0 or overlay > 15:
        logger.debug('invalid overlay requested %d' % overlay)
        return

    if overlay_bit_index(ds, overlay) > 0:
        if frame > -1:
            logger.error('cannot specify an overlay frame %d when overlay %d is in image high bits' % (frame, overlay))
            return
        return redact_rectangles_from_high_bit_overlay(ds, overlay, rect_list)
    else:
        return redact_rectangles_from_overlay_frame(ds, frame, overlay, rect_list)
    return


if __name__ == '__main__':
    if len(sys.argv)>1:
        filename = sys.argv[1]

    ds = pydicom.dcmread(filename)
    remove_overlays_in_high_bits(ds)
    ds.save_as(filename + ".nooverlays.dcm")

    ds = pydicom.dcmread(filename)
    redact_rectangle(ds, frame=0, overlay=-1, rect_list=[(100, 100, 75, 50)])
    ds.save_as(filename + ".redactedframe.dcm")

    ds = pydicom.dcmread(filename)
    redact_rectangle(ds, frame=0, overlay=0, rect_list=[(100, 100, 75, 50)])
    ds.save_as(filename + ".redactedoverlay.dcm")
