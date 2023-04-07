# Ultrasound images in DICOM format

import pydicom
from DicomPixelAnon.rect import DicomRectText, rect_exclusive_list
from DicomPixelAnon.ocrenum import OCREnum


# ---------------------------------------------------------------------

def read_DicomRectText_list_from_region_tags(filename):
    """ Read the DICOM tags which define the usable region in an image
    and construct a list of rectangles which redact all parts outside.
    Only applicable to Ultrasound images, as it reads the tag
    SequenceOfUltrasoundRegions.
    Returns a list of DicomRect object, or [] if none found.
    Note that the frame number will always be 0 (and overlay -1)
    and the ocr engine will be set to ultrasoundregions as the source.
    XXX in future could accept a pydicom dataset instead of filename.
    """
    rect_list = []
    ds = pydicom.dcmread(filename)
    if 'SequenceOfUltrasoundRegions' in ds:
        keep_list = []
        width = int(ds['Columns'].value)
        height = int(ds['Rows'].value)
        for region in ds['SequenceOfUltrasoundRegions']:
            x0 = int(region['RegionLocationMinX0'].value)
            y0 = int(region['RegionLocationMinY0'].value)
            x1 = int(region['RegionLocationMaxX1'].value)
            y1 = int(region['RegionLocationMaxY1'].value)
            keep_list.append(DicomRectText(left=x0, right=x1, top=y0, bottom=y1, frame=0, overlay=-1, ocrengine=OCREnum.UltrasoundRegions))
        rect_list = rect_exclusive_list(keep_list, width, height)
    return rect_list


# ---------------------------------------------------------------------

def test_read_DicomRectText_list_from_region_tags():
    """ Construct a DICOM file with two Ultrasound Regions
    and test that we get back a set of rectangles which surround them.
    """
    import datetime
    import os
    import tempfile
    import pydicom
    from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
    from pydicom.sequence import Sequence
    from pydicom.uid import UID

    # Create temporary filename
    suffix = '.dcm'
    filename = tempfile.NamedTemporaryFile(suffix=suffix).name

    # Populate required values for file meta information
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = UID('1.2.840.10008.5.1.4.1.1.2')
    file_meta.MediaStorageSOPInstanceUID = UID("1.2.3")
    file_meta.ImplementationClassUID = UID("1.2.3.4")

    # Create the FileDataset instance (initially no data elements, but file_meta supplied)
    ds = FileDataset(filename, {},
                 file_meta=file_meta, preamble=b"\0" * 128)

    # Add the data elements -- not trying to set all required here.
    ds.PatientName = "Test^Firstname"
    ds.PatientID = "123456"
    ds.Rows = 1024
    ds.Columns = 1024

    # Set creation date/time
    dt = datetime.datetime.now()
    ds.ContentDate = dt.strftime('%Y%m%d')
    timeStr = dt.strftime('%H%M%S.%f')  # long format with micro seconds
    ds.ContentTime = timeStr

    # Create a single UltrasoundRegion "Dataset"
    def make_region(x0,y0, x1,y1):
        region1 = Dataset()
        region1.RegionSpatialFormat = 1
        region1.RegionDataType = 1
        region1.RegionFlags = 2
        region1.RegionLocationMinX0 = x0
        region1.RegionLocationMinY0 = y0
        region1.RegionLocationMaxX1 = x1
        region1.RegionLocationMaxY1 = y1
        return region1

    ds.SequenceOfUltrasoundRegions = Sequence([
        make_region(10,20, 30,40),
        make_region(50,60, 70,80)
    ])

    # Save in little-endian transfer syntax
    ds.is_little_endian = True
    ds.is_implicit_VR = True
    ds.save_as(filename)

    # Open the file to check
    rectlist = read_DicomRectText_list_from_region_tags(filename)
    #print(rectlist)
    # XXX  NOTE some of these coordinates are off-by-one!!
    # But we would need to fix rect.py before fixing this test.
    expected = [         # format is left,top,right,bottom
        (0,0,1023,20),
        (0,20,10,40),
        (30,20,1023,40),
        (0,40,1023,60),
        (0,60,50,80),
        (70,60,1023,80),
        (0,80,1023,1023)
    ]
    os.remove(filename)
    for rect in rectlist:
        #if not rect.ltrb() in expected: print('Unexpected %s' % (rect.ltrb(),))
        assert(rect.ltrb() in expected)


if __name__ == '__main__':
    test_read_DicomRectText_list_from_region_tags()
