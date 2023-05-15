#!/usr/bin/env python3
# Reads a CSV file, groups by a set of columns, outputs
#  either the first N rows from each group,
#  or a random N rows from each group
# Output is in CSV format but with a subset of columns.
# Note that in groups which have less rows than the sample size
# you will probably get duplicated rows.

import argparse
import csv
import sys
import pandas as pd

group_by_columns = ['Manufacturer', 'ManufacturerModelName', 'Zeihm1', 'Zeihm2', 'Rows', 'Columns']
output_columns = ['DicomFilePath']

parser = argparse.ArgumentParser(description='DICOM image frames to PNG')
parser.add_argument('-d', '--debug', action="store_true", help='more verbose (show DEBUG messages)')
parser.add_argument('-c', '--csv', action="store", help='input CSV file')
parser.add_argument('-g', '--groupby', action="store", help='group by column names, comma-separated')
parser.add_argument('-p', '--print', action="store", help='output column names, comma-separated')
parser.add_argument('--random', action='store', help='Output random N rows from each group', default=None)
parser.add_argument('--head', action='store', help='Output first N rows from each group', default=None)
args = parser.parse_args()

csv_filename = args.csv
if args.random:
    output_random = True
    num_per_group = int(args.random)
if args.head:
    output_random = False
    num_per_group = int(args.head)
if args.groupby:
    group_by_columns = args.groupby.split(',')
if args.print:
    output_columns = args.print.split(',')

# Columns in CSV file
# Modality,DicomFilePath,BurnedInAnnotation,RecognizableVisualFeatures,Manufacturer,ManufacturerModelName,SoftwareVersions,SecondaryCaptureDeviceManufacturer,SecondaryCaptureDeviceManufactur
erModelName,ModelName,CodeMeaning,CommentsOnRadiationDose,ImageType2,ImageType,ImplementationVersionName,SeriesDescription,WindowWidth,Rows,Columns,BitsStored,BitsAllocated,NumberOfFrames,Ov
erlayRows,OverlayColumns,OverlayType,NumberOfFramesInOverlay,OverlayDescription,OverlayBitsAllocated,OverlayBitPosition,Zeihm1,Zeihm2

# Define some columns as 'category' to reduce memory and speed up processing
data_types = { 'Modality': 'category',
        'Manufacturer': 'category',
        'ManufacturerModelName': 'category',
        'SoftwareVersions': 'category',
        'SecondaryCaptureDeviceManufacturer': 'category',
        'SecondaryCaptureDeviceManufacturerModelName': 'category',
        'ModelName': 'category',
        'ImageType2': 'category',
        'ImageType': 'category',
        'Rows': 'category',
        'Columns': 'category',
        'Zeihm1': 'category',
        'Zeihm2': 'category',
        'ZeihmCreator': 'category',
        'ZeihmImageCaptureData': 'category'
}

# Read the CSV into memory
# NOTE must use na_filter=False to prevent empty string becoming NaN
print('Reading CSV')
df = pd.read_csv(csv_filename, dtype=data_types, na_filter=False)

# Group by columns and output CSV
print('Grouping')
for key,val in df.groupby(group_by_columns):
    if output_random:
        df_out = val.sample(n = num_per_group, replace = True)
    else:
        df_out = val.head(num_per_group)
    print(key)
    print(df_out.to_csv(header = False, columns = output_columns), end='\n\n')
