#!/usr/bin/env python3
# Extract just the filename for all DICOM files
# which are ORIGINAL\PRIMARY and have no overlays at all.
# Actually looks for ORIGINAL and PRIMARY anywhere in ImageType
# not specifically ORIGINAL\PRIMARY by itself.
# Imput:  extract_BIA_from_??.csv
# Output: extract_BIA_from_??.csv.origprimnoovl.csv

import csv
import sys

# Input fields: Modality,DicomFilePath,BurnedInAnnotation,RecognizableVisualFeatures,Manufacturer,ManufacturerModelName,CodeMeaning,CommentsOnRadiationDose,ImageType,ImplementationVersionName,SeriesDescription,WindowWidth,Rows,Columns,BitsStored,BitsAllocated,NumberOfFrames,OverlayRows,OverlayColumns,OverlayType,NumberOfFramesInOverlay,OverlayDescription,OverlayBitsAllocated,OverlayBitPosition,OverlayData

outfields = ['Modality', 'DicomFilePath', 'NumberOfFrames', 'ManufacturerModelName']

for file in sys.argv[1:]:
    with open(file) as fd:
        rdr = csv.DictReader(fd)
        print('Reading %s' % file)
        outfile = file + '.origprimnoovl.csv'
        with open(outfile, 'w', newline='') as outfd:
            wrt = csv.DictWriter(outfd, fieldnames=outfields, lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
            wrt.writeheader()
            print('  Writing %s' % outfile)
            for row in rdr:
                if ('ORIGINAL' in row['ImageType'] and
                    'PRIMARY' in row['ImageType'] and
                    row['OverlayType'] != ''):
                    wrt.writerow({'Modality': row['Modality'],
                        'DicomFilePath': row['DicomFilePath'],
                        'NumberOfFrames': row['NumberOfFrames'],
                        'ManufacturerModelName': row['ManufacturerModelName']})
