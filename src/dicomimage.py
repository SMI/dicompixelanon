import json
import logging
import pydicom
import numpy as np
from PIL import Image

class DicomImage:
    """ Holds the data for a single DICOM file.
    Frame and overlay numbers start at 0, so use -1 for unset/not applicable.
    """
    # Class static constants:
    elem_OverlayBitPosition = 0x0102
    elem_OverlayData = 0x3000
    elem_OverlayRows = 0x0010
    elem_OverlayCols = 0x0011
    elem_OverlayNumFrames = 0x0015
    elem_OverlayOrigin = 0x0050

    def __init__(self, filename):
        self.filename = filename
        self.ds = pydicom.dcmread(filename)
        self.pixel_data = self.ds.pixel_array # this can raise an exception in some files

        # Check for multiple frames
        self.num_frames = self.ds['NumberOfFrames'].value if 'NumberOfFrames' in self.ds else 1

        # Check which bits in PixelData are actually used:
        # bits_allocated is the physical space used, 1 or a multiple of 8.
        # bits_stored is the number of meaningful bits within those allocated.
        self.bits_stored = self.ds['BitsStored'].value if 'BitsStored' in self.ds else -1
        self.bits_allocated = self.ds['BitsAllocated'].value if 'BitsAllocated' in self.ds else -1
        self.bit_mask = (~((~0) << self.bits_stored))

        # Check for signed integers
        self.signed = self.ds['PixelRepresentation'].value if 'PixelRepresentation' in self.ds else 0

        logging.info('%s is %s using %d/%d bits with %d frames' % (filename, str(self.pixel_data.shape), self.bits_stored, self.bits_allocated, self.num_frames))

        self.overlay_group_list = [ii for ii in range(0x6000, 0x6020, 2)]
        self.overlay_group_used = [False] * len(self.overlay_group_list)
        self.overlay_group_num_frames = [0] * len(self.overlay_group_list)
        self.num_overlays = 0
        for overlay_group_idx in range(len(self.overlay_group_list)):
            overlay_group = self.overlay_group_list[overlay_group_idx]
            # See if an overlay exists in the high bits of the image data
            if [overlay_group, DicomImage.elem_OverlayBitPosition] in self.ds:
                overlay_bit_pos = self.ds[overlay_group, DicomImage.elem_OverlayBitPosition].value
                if not overlay_bit_pos: overlay_bit_pos = 0 # sometimes it is None!
                if overlay_bit_pos > 0:
                    self.overlay_group_used[overlay_group_idx] = True
                    self.overlay_group_num_frames[overlay_group_idx] = 1
                    logging.debug('overlay %d is present in bit pos %d' % (overlay_group_idx, overlay_bit_pos))
                    self.num_overlays += 1
            # See if an overlay exists independently
            if [overlay_group, DicomImage.elem_OverlayData] in self.ds:
                overlay_num_frames = self.ds[overlay_group, DicomImage.elem_OverlayNumFrames].value if [overlay_group, DicomImage.elem_OverlayNumFrames] in self.ds else 1
                self.overlay_group_used[overlay_group_idx] = True
                self.overlay_group_num_frames[overlay_group_idx] = overlay_num_frames
                logging.debug('overlay %d is present with %d frames' % (overlay_group_idx, overlay_num_frames))
                self.num_overlays += 1
        self.image_idx = -1


    def get_filename(self):
        return self.filename

    def is_secondary_capture(self):
        """ Return True if the DICOM looks like it was a secondary capture
        based on tags other than the ImageType tag.
        Warning: just a hueristic.
        """
        # Secondary Capture Image Storage = 1.2.840.10008.5.1.4.1.1.7[.*]
        sopclass = self.ds.get('SOPClassUID', '')
        is_SC = (sopclass.startswith('1.2.840.10008.5.1.4.1.1.7') or
            self.ds.get('SecondaryCaptureDeviceManufacturer', '') or
            self.ds.get('SecondaryCaptureDeviceManufacturerModelName', '') or
            self.ds.get('DateOfSecondaryCapture', ''))
        return is_SC

    def get_tag_imagetype_list(self):
        """ Return ImageType as a list, eg. ['ORIGINAL','PRIMARY'].
        If no ImageType then it tries to guess.
        Result might be a single element "NoImageType" if it can't guess.
        """
        image_type = self.ds.get('ImageType', None)
        # If it's not present, but the image looks like a secondary capture then fake it
        if not image_type:
            if self.is_secondary_capture():
                image_type = ['DERIVED', 'SECONDARY']
            else:
                image_type = ['NoImageType']
        return image_type

    def get_tag_imagetype(self):
        """ Return ImageType as a string with / separators.
        """
        return '/'.join(self.get_tag_imagetype_list()) #  or, import simplejson then add iterable_as_array=True

    def get_tag_manufacturer_model(self):
        """ Get a useful string representing the model of machine.
        This should be ModelName but sometimes it's empty so try version.
        Complicated by the fact that some secondary captures don't have it.
        """
        manuf = self.ds.get('Manufacturer', '')
        if not manuf:
            manuf = self.ds.get('SecondaryCaptureDeviceManufacturer', '')
        model = self.ds.get('ManufacturerModelName', None)
        if not model:
            model = self.ds.get('SecondaryCaptureDeviceManufacturerModelName', '')
        swver = self.ds.get('SoftwareVersions', '')
        if not model:
            model = manuf + ' ' + swver
        if not model or model == ' ':
            model = 'NoModel'
        return model.lstrip().rstrip()

    def get_selected_metadata(self):
        """ Return a dict containing some DICOM metadata.
        Return ONLY the tag values which are defined as Fields in
        the DicomRectDB 'Rects' table, as updated by the mark_inspected method.
        If a tag is missing then a special string is returned (NoBIA or NoModel).
        ImageType is returned as a list in JSON format.
        NB. ManufacturerModelName is now Manufacturer + SoftwareVersions
          if the ModelName is missing, or NoModel if both those are missing
          (changed 2022-08-28).
        """
        return {
            "Modality": self.ds.get('Modality', 'NoModality'),
            "ImageType": json.dumps(self.get_tag_imagetype(), default=list),
            "Rows": int(self.ds.get('Rows', 0)),
            "Columns": int(self.ds.get('Columns', 0)),
            "ManufacturerModelName": self.get_tag_manufacturer_model(),
            "BurnedInAnnotation": self.ds.get('BurnedInAnnotation','NoBIA'),
        }

    def debug_tags(self):
        """ For debugging, called by dcmaudit
        """
        print(self.ds)

    def get_tag(self, tag):
        """ Return the tag or None if it doesn't exist
        """
        return self.ds.get(tag, None)

    def get_tag_overview(self):
        """ Return a string summary of the useful tags.
        Shortens the ImageType words to take less space.
        Truncates brutally.
        """
        tag_data = self.get_selected_metadata()
        str = "%s" % tag_data['Modality']
        str += ", BIA=" + tag_data['BurnedInAnnotation']
        image_type = '\\'.join(json.loads(tag_data['ImageType'])).replace('ORIGINAL', 'ORIG').replace('PRIMARY', 'PRIM').replace('SECONDARY','SEC').replace('DERIVED','DER')[:11]
        str += ", ImType=" + image_type
        str += ", Model=" + tag_data['ManufacturerModelName'][:16]
        return str

    def get_num_frames(self):
        """ Return the number of normal image frames in this file
        not counting any in overlays.
        """
        return self.num_frames

    def get_num_overlays(self):
        """ Return the number of overlays in this file.
        """
        return self.num_overlays

    def get_num_frames_in_overlays(self, overlay = -1):
        """ Return the total number of image frames in all overlays
        or just in the specified overlay.
        """
        if overlay == -1:
            return sum(self.overlay_group_num_frames)
        else:
            return self.overlay_group_num_frames[overlay]

    def get_total_frames(self):
        """ Return the total number of image frames including all the
        frames of all the overlays.
        """
        return self.get_num_frames() + self.get_num_frames_in_overlays()

    def image(self, frame = -1, overlay = -1):
        """ Return a PIL image from the requested frame or overlay.
        frame and overlay count from zero, or None if error occurs.
        If you specify both frame and overlay you get that frame
        from that overlay, it doesn't overlay the overlay onto the
        normal frame.
        The returned image is scaled to 8-bit (but not equalised).
        XXX should raise exceptions rather than returning None.
        """
        def rescale_np(arr, invert = False):
            """ Rescale a numpy array to use the full 8-bit range of pixel values.
            Input can be 8 or 16 bit and may only use a subset of that range.
            Also optionally inverts the pixel values (black<->white).
            """
            minval = arr.min()
            maxval = arr.max()
            if minval == maxval:
                return arr
            scale = 255.0 / (maxval - minval)
            srctype = np.uint16 if (maxval - minval > 255) else np.uint8
            if invert:
                arr = ((maxval - arr.astype(srctype)) * scale).astype(np.uint8)
            else:
                arr = ((arr.astype(srctype) - minval) * scale).astype(np.uint8)
            return arr

        if frame > self.num_frames-1:
            logging.error('ERROR: frame %d > %d' % (frame, self.num_frames-1))
            return None
        if overlay >=0 and not self.overlay_group_used[overlay]:
            logging.error('ERROR: overlay %d not found' % overlay)
            return None
        if overlay >=0 and frame >=0 and frame > self.overlay_group_num_frames[overlay]:
            logging.error('ERROR: frame %d of overlay %d not found' % (frame, overlay))
            return None

        inverted = self.get_tag('PhotometricInterpretation') == 'MONOCHROME1'

        if frame >= 0 and overlay < 0:
            if self.num_frames == 1:
                pix_extracted = (self.pixel_data & self.bit_mask)
            else:
                if self.pixel_data.ndim == 3:
                    pix_extracted = (self.pixel_data[frame,:,:] & self.bit_mask)
                else:
                    pix_extracted = (self.pixel_data[frame,:,:,:] & self.bit_mask)
            # If signed integers [-N,N) then map to unsigned [0,N)
            if self.signed:
                if self.bits_stored > 8:
                    # XXX assuming 16-bit, not larger
                    pix_extracted = (pix_extracted + 32768).astype(np.uint16)
                else:
                    pix_extracted = (pix_extracted + 128).astype(np.uint8)
            # Equalise it before returning
            return Image.fromarray(rescale_np(pix_extracted, inverted))
        if overlay >= 0:
            overlay_group = self.overlay_group_list[overlay]
            # See if the overlay is stored in the high bits of the pixel data
            overlay_bit_pos = 0
            if [overlay_group, DicomImage.elem_OverlayBitPosition] in self.ds:
                overlay_bit_pos = self.ds[overlay_group, DicomImage.elem_OverlayBitPosition].value
            if not overlay_bit_pos:
                overlay_bit_pos = 0 # sometimes .value is None!
            if overlay_bit_pos > 0:
                pixdata = self.pixel_data
                if pixdata.ndim == 2:
                    return Image.fromarray(rescale_np(pixdata & (1<<overlay_bit_pos), False))
                if pixdata.ndim == 3:
                    return Image.fromarray(rescale_np(pixdata[frame,:,:] & (1<<overlay_bit_pos), False))
                else:
                    return Image.fromarray(rescale_np(pixdata[frame,:,:,:] & (1<<overlay_bit_pos), False))
            # If the requested overlay group exists
            if ([overlay_group, DicomImage.elem_OverlayData] in self.ds and
                    [overlay_group, DicomImage.elem_OverlayData] in self.ds and
                    [overlay_group, DicomImage.elem_OverlayCols] in self.ds and
                    self.ds[overlay_group, DicomImage.elem_OverlayCols].value):
                overlay_width = self.ds[overlay_group, DicomImage.elem_OverlayCols].value
                overlay_height = self.ds[overlay_group, DicomImage.elem_OverlayRows].value
                overlay_origin = self.ds[overlay_group, DicomImage.elem_OverlayOrigin].value # seems to be origin [1,1] not [0,0]
                # handle broken DICOMs where origin is an integer 1 not a list [1,1]
                if not isinstance(overlay_origin, list):
                    overlay_origin = [overlay_origin, overlay_origin]
                overlay_x = overlay_origin[0] if overlay_origin[0] else 1
                overlay_y = overlay_origin[1] if overlay_origin[1] else 1
                overlay_data = self.ds.overlay_array(overlay_group) # might raise an exception
            else:
                return None
            # Check for multiple frames in overlay
            overlay_num_frames = self.ds[overlay_group, DicomImage.elem_OverlayNumFrames].value if [overlay_group, DicomImage.elem_OverlayNumFrames] in self.ds else 1
            if overlay_num_frames == 1:
                return Image.fromarray(rescale_np(overlay_data, False))
            else:
                if overlay_data.ndim == 3:
                    # the first dimension is the frame
                    return Image.fromarray(rescale_np(overlay_data[frame_num,:,:], False))
                else:
                    # assume the fourth dimension is RGB
                    return Image.fromarray(rescale_np(overlay_data[frame_num,:,:,:], False))

    def idx_to_tuple(self, n = -1):
        """ Sequential index into the image frames,
        Counts from zero, first N are the real image frames,
        then the frames from overlay 0, then the frames from overlay 1, etc.
        """
        orig_n = n
        frame = overlay = -1
        if n == -1:
            n = self.image_idx
        if n < self.get_num_frames():
            frame = n
        else:
            n -= self.get_num_frames()
            for overlay_num in range(len(self.overlay_group_num_frames)):
                if not self.overlay_group_used[overlay_num]:
                    continue
                if n < self.overlay_group_num_frames[overlay_num]:
                    overlay = overlay_num
                    frame = n
                    break
                else:
                    n -= self.overlay_group_num_frames[overlay_num]
        logging.debug('idx %d (%d) -> %d %d' % (orig_n, self.image_idx, frame, overlay))
        return frame, overlay

    def get_current_idx(self):
        """ Returns index of current image (counting from zero).
        """
        return self.image_idx

    def get_current_frame_overlay(self):
        """ Returns frame,overlay tuple (counting from zero, -1 if not applicable).
        """
        return self.idx_to_tuple(self.get_current_idx())

    def next_image(self, n = -1):
        """ Returns the next PIL image from the DICOM.
        You can pass n as the index of the image required,
        or omit it (-1) to get the next image in sequence.
        """
        if n == -1:
            if self.image_idx+1 < self.get_total_frames():
                self.image_idx += 1
            n = self.image_idx
        frame, overlay = self.idx_to_tuple(n)
        if overlay == -1:
            logging.debug('Returning frame %d' % n)
            return self.image(frame = n)
        else:
            logging.debug('Returning frame %d from overlay %d' % (frame, overlay))
            return self.image(overlay = overlay, frame = frame)
        return None

    def prev_idx(self):
        """ Change the image_idx pointer to the previous frame or overlay
        """
        if self.image_idx < 1:
            self.image_idx = -1
            return
        self.image_idx -= 2
        return

    def ffwd_idx(self):
        """ Change the image_idx pointer to skip over the remaining frames
        in the current overlay to get to the next overlay.
        """
        curr_frame, curr_overlay = self.idx_to_tuple(self.image_idx)
        if curr_frame == -1 and curr_overlay == -1:
            return
        while True:
            next_idx =  self.image_idx + 1
            frame, overlay = self.idx_to_tuple(next_idx)
            if frame == -1 and overlay == -1:
                # Can't change idx, nothing newer
                return
            if overlay == curr_overlay:
                # still in same frame or overlay
                continue
            # Step back one, because the caller will automatically increment
            self.image_idx = next_idx - 1
            break
        return

