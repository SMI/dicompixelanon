#!/usr/bin/env python3
# Find all of the common machine/modality/etc combinations
# and list all of the rectangles for that combination.
# Create rules like:
# LABEL Ziehm X-Rays
#   contains Modality XA
#   + contains 0x00190010 ZIEHM_1.0 DeviceConfigData
#   + contains 0x00191201 Fluoro
#   coordinates 0,0,196,148

import os
import sys
import pydicom
from DicomPixelAnon.dicomrectdb import DicomRectDB


def read_Manufacturer_tags(filename):
    ds = pydicom.dcmread(filename)
    Manufacturer = ds.get('Manufacturer', None)
    ManufacturerModelName = ds.get('ManufacturerModelName', None)
    SecondaryCaptureDeviceManufacturer = ds.get('SecondaryCaptureDeviceManufacturer', None)
    SecondaryCaptureDeviceManufacturerModelName = ds.get('SecondaryCaptureDeviceManufacturerModelName', None)
    return Manufacturer, ManufacturerModelName, SecondaryCaptureDeviceManufacturer, SecondaryCaptureDeviceManufacturerModelName


# First parameter can be a filename or directory containing a database
db_path = sys.argv[1]
if os.path.isdir(db_path):
    DicomRectDB.set_db_path(db_path)
else:
    DicomRectDB.set_db_path(os.path.dirname(db_path))

drdb = DicomRectDB()

# Read the database and build a dictionary indexed by
# the tags with which we can group similar images,
# having the value being a list of rectangles (l,t,r,b)
prev_group_by = ()
rectlist_dict = {}
for row in drdb.db(drdb.db.DicomRects.filename == drdb.db.DicomTags.filename).select(
        # select() takes: orderby=, groupby=, limitby=(0,9)
        drdb.db.DicomTags.ALL, drdb.db.DicomRects.ALL,
        orderby = drdb.db.DicomTags.Modality | drdb.db.DicomTags.ManufacturerModelName | drdb.db.DicomTags.Rows | drdb.db.DicomTags.Columns,
    ):
    # Read real Manufacturer etc from the file
    if os.path.isfile(row.DicomTags.filename):
        Manufacturer, ManufacturerModelName, SecondaryCaptureDeviceManufacturer, SecondaryCaptureDeviceManufacturerModelName = read_Manufacturer_tags(row.DicomTags.filename)
    # Create dictionary key
    bits_to_group_by = (row.DicomTags.Modality, row.DicomTags.Rows, row.DicomTags.Columns, Manufacturer, ManufacturerModelName, SecondaryCaptureDeviceManufacturer, SecondaryCaptureDeviceManufacturerModelName)
    # Construct a rectangle tuple
    rect = (row.DicomRects.left, row.DicomRects.top, row.DicomRects.right, row.DicomRects.bottom)
    # Add the rectangle to a set (ensures no duplicates)
    if not bits_to_group_by in rectlist_dict:
        rectlist_dict[bits_to_group_by] = set()
    rectlist_dict[bits_to_group_by].add(rect)
    # Not needed
    prev_group_by = bits_to_group_by

# Dump the dictionary as a set of rules
for key in rectlist_dict:
    Modality, Rows, Columns, Manufacturer, ManufacturerModelName, SecondaryCaptureDeviceManufacturer, SecondaryCaptureDeviceManufacturerModelName = key
    print('\nLABEL test')
    print('  contains Modality %s' % Modality)
    if Manufacturer:
        print('  + contains Manufacturer %s' % Manufacturer)
    if ManufacturerModelName:
        print('  + contains ManufacturerModelName %s' % ManufacturerModelName)
    if SecondaryCaptureDeviceManufacturer:
        print('  + contains SecondaryCaptureDeviceManufacturer %s' % SecondaryCaptureDeviceManufacturer)
    if SecondaryCaptureDeviceManufacturerModelName:
        print('  + contains SecondaryCaptureDeviceManufacturerModelName %s' % SecondaryCaptureDeviceManufacturerModelName)
    print('  + equals Rows %s' % Rows)
    print('  + equals Columns %s' % Columns)
    for rect in rectlist_dict[key]:
        print('  coordinates %s' % ','.join([str(c) for c in rect]))
