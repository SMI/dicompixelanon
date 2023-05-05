#!/usr/bin/env python3
# Allow pydicom/deid rules to be used in DicomPixelAnon
# Use the function deid_dataset_to_DicomRectList()
# on a pydicom Dataset object to get a list of DicomRect
# rectangles to redact (or an empty list if no filters match
# the metadata in this file).

import glob
import os
import sys
import pydicom
from deid.dicom import DicomCleaner
from DicomPixelAnon.rect import Rect, DicomRect, rect_exclusive_list, add_Rect_to_list


def coord_str_to_DicomRect(coord_str : str, width = None, height = None):
    """ Decode a string containing the coordinates of a rectangle
    in the format "l,t,w,h" or "(l,t,r,b)" or the string "all".
    Width and height are needed only if 'all' is passed.
    Returns a DicomRect object (which will be initialised with frame,overlay=-1)
    """
    if 'all' in coord_str:
        if width and height:
            return DicomRect(top = 0, bottom = height-1, left = 0, right = width-1)
        else:
            raise Exception('undefined image dimensions, cannot return "all"')
    #print('decode coord_str "%s"' % coord_str)
    # WAS: assuming ctp (relative) coords unless inside brackets:
    #if '(' in coord_str:
    #    left, top, right, bottom = [int(ii) for ii in coord_str.replace('(','').replace(')','').split(',')]
    #else:
    #    left, top, width, height = [int(ii) for ii in coord_str.split(',')]
    #    right = left + width
    #    bottom = top + height
    # NOW: coordinates are always absolute
    left, top, right, bottom = [int(ii) for ii in coord_str.replace('(','').replace(')','').split(',')]
    #print('"%s" -> %d %d %d %d' % (coord_str, left, top, right, bottom))
    return DicomRect(top = top, bottom = bottom, left = left, right = right)


def result_coords_to_DicomRectList(result_coords, width = None, height = None):
    """
    Create a list of DicomRect objects from a list of coordinate strings
    that have been returned from deid's detect() function.
    result_coords is a list of coordinates from result['coordinates'].
    Each coordinate can be a tuple (type, coord_str) or
    it can be a tuple(type, list_of_coord_str).
    coord_str can be "l,t,w,h" or "(l,t,r,b)" or the string "all".
    type 0 is a rectangle to redact,
    type 1 is a rectangle to keep, need to invert these.
    It processes all the 'keep' rectangles first then inverts them to
    get a set of rectangles to redact, then appends all the 'redact' ones.
    Returns a DicomRect list where frame,overlay=-1 mean apply to all.
    """
    #print('Processing %s' % result_coords)
    rectlist = []
    keep_coord_list = []
    redact_coord_list = []
    for coord in result_coords:
        coord_type, coords = coord
        if not isinstance(coords, list):
            coords = [coords]
        for coord_str in coords:
            #print('type %d coord %s' % (coord_type, coord_str))
            if coord_type == 0:
                if coord_str == 'all':
                    # ignore a request to redact the whole image
                    # (an artefact of how deid handles ultrasound regions)
                    #print('ignored: redact all')
                    continue
                redact_coord_list.append(coord_str_to_DicomRect(coord_str, width, height))
            elif coord_type == 1:
                keep_coord_list.append(coord_str_to_DicomRect(coord_str, width, height))
    rectlist = rect_exclusive_list(keep_coord_list, width, height)
    for rect in redact_coord_list:
        add_Rect_to_list(rectlist, rect)
    return rectlist


def find_deid_rules_files():
    """ Find a list of deid recipe filenames, first looking in
    $SMI_ROOT/data/deid
    then in the data subdirectory relative to this file.
    """
    datadir = os.path.join(os.path.dirname(__file__), 'data')
    files = []
    if 'SMI_ROOT' in os.environ:
        dirname = os.path.join(os.environ['SMI_ROOT'], 'data', 'deid')
        if os.path.isdir(dirname):
            datadir = dirname
    if os.path.isdir(datadir):
        files = glob.glob(os.path.join(datadir, 'deid.dicom.*'))
    return files


def deid_dataset_to_DicomRectList(pydicom_dataset):
    """ Run the pydicom Dataset through a set of filters
    to determine any static rectangles which need to be redacted.
    Returns a list of DicomRect objects (but frame,overlay will
    both be -1 meaning apply to all frames/overlays because the
    rules don't specify any particular frame or overlay).
    Returns [] if this file's metadata matches no rules.
    """
    rectlist = []
    print('deid using rules files %s' % find_deid_rules_files())
    rc = DicomCleaner(deid=find_deid_rules_files()).detect(pydicom_dataset)
    if rc['results']:
        result_list = []
        for result in rc['results']:
            result_list.extend(result['coordinates'])
        rectlist = result_coords_to_DicomRectList(result_list, pydicom_dataset.Columns, pydicom_dataset.Rows)
    return rectlist


def test_deid_result_rectangles():
    # Example taken from gdcmData/gdcm-US-ALOKA-16.dcm
    # with two extra coords added to test the code.
    rc = {
        'flagged': True,
        'results': [
            {
                'reason': ' SequenceOfUltrasoundRegions present ',
                'group': 'graylist',
                'coordinates': [
                    [0, '(33,34,35,36)'],
                    [1, ['32,24,335,415', '336,24,639,415', '32,40,63,103']]
                ]
            },
            {
                'reason': ' Fake test ',
                'group': 'blacklist',
                'coordinates': [ [0, '41,42,43,44']]
            }
        ]
    }
    result_list = rc['results'][0]['coordinates']
    if len(rc['results'])>1:
        result_list.extend(rc['results'][1]['coordinates'])
    rectlist = result_coords_to_DicomRectList(result_list, 640, 480)
    rectlist_str = str(rectlist)
    # We are expected 3 rectangles which cover the inverse
    # of the regions listed in the results because they are
    # type 1 (meaning keep) from Ultrasound.
    assert(len(rectlist) == 6)
    assert('<DicomRect frame=-1 overlay=-1 0,0->639,24>' in rectlist_str)
    assert('<DicomRect frame=-1 overlay=-1 0,24->32,415>' in rectlist_str)
    assert('<DicomRect frame=-1 overlay=-1 335,24->336,415>' in rectlist_str)
    assert('<DicomRect frame=-1 overlay=-1 0,415->639,479>' in rectlist_str)
    assert('<DicomRect frame=-1 overlay=-1 33,34->35,36>' in rectlist_str)
    assert('<DicomRect frame=-1 overlay=-1 41,42->43,44>' in rectlist_str)

# ---------------------------------------------------------------------

def detect(pydicom_dataset):
    return deid_dataset_to_DicomRectList(pydicom_dataset)


# ---------------------------------------------------------------------
if __name__ == '__main__':

    filenames = [ '/home/arb/src/pydicom/deid/examples/dicom/header-manipulation/func-sequence-replace/MR.dcm',
        '/home/arb/data/gdcm/gdcmData/gdcm-US-ALOKA-16.dcm' ]
    if len(sys.argv) > 1:
        filenames = sys.argv[1:]

    for filename in filenames:
        print('Loading %s' % filename)
        ds = pydicom.dcmread(filename)

        # Use the function
        rectlist = deid_dataset_to_DicomRectList(ds)
        for rect in rectlist:
            print('  Has rectangle: %s' % (rect))

        # Do it manually
        rc = DicomCleaner(deid=find_deid_rules_files()).detect(ds)

        print('Is flagged? %s' % rc['flagged'])
        if rc['results']:
            result_list = []
            for result in rc['results']:
                print(' Because of: %s' % result['reason'])
                result_list.extend(result['coordinates'])
            rectlist = result_coords_to_DicomRectList(result_list, ds.Columns, ds.Rows)
            for rect in rectlist:
                print('  Has rectangle: %s' % (rect))
