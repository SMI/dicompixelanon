#!/usr/bin/env python3
# Usage: summary.py file.csv...
# Report a count of the unique values in each column
# BurnedInAnnotation,Manufacturer,ManufacturerModelName,ModelName,SoftwareVersions,CodeMeaning,CommentsOnRadiationDose,ImageType2,ImageType,ImplementationVersionName,SeriesDescription,WindowWidth,Rows,Columns,OverlayRows,OverlayColumns,OverlayType,NumberOfFramesInOverlay,OverlayDescription,OverlayBitsAllocated,OverlayBitPosition
# and report more detailed stats about some of the interesting columns.

import csv
import sys

def stats(num_dict):
  # Summarise a dict where the keys are actually numbers.
  # eg. { ' ': 3, '256': 4, '512': 6, 'X': 9 }
  # we want to know:
  #  the minimum value (256) and maximum value (512) of the keys,
  #  the average value, which is calculated as:
  #  ((256*4) + (512*6)) / (4+6)
  # so it's the average width, not (256+512)/2, but taking into
  # account how many times 256 occurs (4) and 512 occurs (6).
  # Returns a tuple:
  #  total_NA is the sum of the values of non-numeric keys,
  #  num_vals is the sum of the values of the numeric keys,
  #  min, max, mean  as described above (for numeric keys),
  #  total is the keys multipled by their values
  #    (256*4 + 512*6) in this case, which doesn't make sense
  #    for width, but is useful for number of frames. 
  min = 99999999999
  max = mean = num_vals = total = total_NA = 0
  for key in num_dict:
    try:
      n = int(key.replace('[','').replace(']','')) # remove [] around numbers
      num_vals += num_dict[key]
      total += n * num_dict[key]
      if n < min: min = n
      if n > max: max = n
    except:
      total_NA += num_dict[key]
  if num_vals:
    mean = total / num_vals
  return total_NA,num_vals,min,max,mean,total


def summarise_file(file):
  BurnedInAnnotation = {}
  RecognizableVisualFeatures = {}
  Manufacturer = {}
  ManufacturerModelName = {}
  ModelName = {}
  SoftwareVersions = {}
  CodeMeaning = {}
  CommentsOnRadiationDose = {}
  ImageType2 = {}
  ImageType = {}
  ImageTypeShort = {}
  ImplementationVersionName = {}
  SeriesDescription = {}
  WindowWidth = {}
  Rows = {}
  Columns = {}
  BitsStored = {}
  BitsAllocated = {}
  NumberOfFrames = {}
  OverlayRows = {}
  OverlayColumns = {}
  OverlayType = {}
  NumberOfFramesInOverlay = {}
  OverlayDescription = {}
  OverlayBitsAllocated = {}
  OverlayBitPosition = {}

  fd = open(file)
  rdr = csv.DictReader(fd)
  for row in rdr:
    count = BurnedInAnnotation.get(row['BurnedInAnnotation'], 0)
    BurnedInAnnotation[row['BurnedInAnnotation']] = count+1

    count = RecognizableVisualFeatures.get(row['RecognizableVisualFeatures'], 0)
    RecognizableVisualFeatures[row['RecognizableVisualFeatures']] = count+1

    count = Manufacturer.get(row['Manufacturer'], 0)
    Manufacturer[row['Manufacturer']] = count+1

    count = ManufacturerModelName.get(row['ManufacturerModelName'], 0)
    ManufacturerModelName[row['ManufacturerModelName']] = count+1

    count = ModelName.get(row['ModelName'], 0)
    ModelName[row['ModelName']] = count+1

    count = SoftwareVersions.get(row['SoftwareVersions'], 0)
    SoftwareVersions[row['SoftwareVersions']] = count+1

    count = CodeMeaning.get(row['CodeMeaning'], 0)
    CodeMeaning[row['CodeMeaning']] = count+1

    count = CommentsOnRadiationDose.get(row['CommentsOnRadiationDose'], 0)
    CommentsOnRadiationDose[row['CommentsOnRadiationDose']] = count+1

    count = ImageType2.get(row['ImageType2'], 0)
    ImageType2[row['ImageType2']] = count+1
    count = ImageType.get(row['ImageType'], 0)
    ImageType[row['ImageType']] = count+1
    # Now count only the first two words of ImageType, ignore trailing junk
    imagetype_short = row['ImageType'].split('\\')
    if ((len(imagetype_short)>1) and
        (imagetype_short[0] == 'ORIGINAL' or imagetype_short[0] == 'DERIVED') and
        (imagetype_short[1] == 'PRIMARY' or imagetype_short[1] == 'SECONDARY')):
      imagetype_short = '\\'.join(imagetype_short[0:2])
      count = ImageTypeShort.get(imagetype_short, 0)
      ImageTypeShort[imagetype_short] = count+1
    else:
      # All the badly-formatted values are counted together
      count = ImageTypeShort.get('BAD', 0)
      ImageTypeShort['BAD'] = count+1

    count = ImplementationVersionName.get(row['ImplementationVersionName'], 0)
    ImplementationVersionName[row['ImplementationVersionName']] = count+1

    count = SeriesDescription.get(row['SeriesDescription'], 0)
    SeriesDescription[row['SeriesDescription']] = count+1

    count = WindowWidth.get(row['WindowWidth'], 0)
    WindowWidth[row['WindowWidth']] = count+1

    count = Rows.get(row['Rows'], 0)
    Rows[row['Rows']] = count+1

    count = Columns.get(row['Columns'], 0)
    Columns[row['Columns']] = count+1

    count = BitsStored.get(row['BitsStored'], 0)
    BitsStored[row['BitsStored']] = count+1

    count = BitsAllocated.get(row['BitsAllocated'], 0)
    BitsAllocated[row['BitsAllocated']] = count+1

    count = NumberOfFrames.get(row['NumberOfFrames'], 0)
    NumberOfFrames[row['NumberOfFrames']] = count+1

    count = OverlayRows.get(row['OverlayRows'], 0)
    OverlayRows[row['OverlayRows']] = count+1

    count = OverlayColumns.get(row['OverlayColumns'], 0)
    OverlayColumns[row['OverlayColumns']] = count+1

    count = OverlayType.get(row['OverlayType'], 0)
    OverlayType[row['OverlayType']] = count+1

    count = NumberOfFramesInOverlay.get(row['NumberOfFramesInOverlay'], 0)
    NumberOfFramesInOverlay[row['NumberOfFramesInOverlay']] = count+1

    count = OverlayDescription.get(row['OverlayDescription'], 0)
    OverlayDescription[row['OverlayDescription']] = count+1

    count = OverlayBitsAllocated.get(row['OverlayBitsAllocated'], 0)
    OverlayBitsAllocated[row['OverlayBitsAllocated']] = count+1

    count = OverlayBitPosition.get(row['OverlayBitPosition'], 0)
    OverlayBitPosition[row['OverlayBitPosition']] = count+1

  print('%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d' % (
    file,
    len(BurnedInAnnotation),
    len(RecognizableVisualFeatures),
    len(Manufacturer),
    len(ManufacturerModelName),
    len(ModelName),
    len(SoftwareVersions),
    len(CodeMeaning),
    len(CommentsOnRadiationDose),
    len(ImageType2),
    len(ImageType),
    len(ImplementationVersionName),
    len(SeriesDescription),
    len(WindowWidth),
    len(Rows),
    len(Columns),
    len(BitsStored),
    len(BitsAllocated),
    len(NumberOfFrames),
    len(OverlayRows),
    len(OverlayColumns),
    len(OverlayType),
    len(NumberOfFramesInOverlay),
    len(OverlayDescription),
    len(OverlayBitsAllocated),
    len(OverlayBitPosition)
    ))

  print('BurnedInAnnotation',BurnedInAnnotation)
  print('RecognizableVisualFeatures',RecognizableVisualFeatures)
  print('ImageType',ImageTypeShort)
  print('ImageType2',ImageType2)
  print('OverlayType',OverlayType)
  print('Rows    stats = NA %s count %s min %s max %s avg %s total %s' % (stats(Rows)))
  print('Columns stats = NA %s count %s min %s max %s avg %s total %s' % (stats(Columns)))
  print('NumberOfFrames stats = NA %s count %s min %s max %s avg %s total %s' % (stats(NumberOfFrames)))
  print('OverlayRows    stats = NA %s count %s min %s max %s avg %s total %s' % (stats(OverlayRows)))
  print('OverlayColumns stats = NA %s count %s min %s max %s avg %s total %s' % (stats(OverlayColumns)))
  print('NumberOfFramesInOverlay stats = NA %s count %s min %s max %s avg %s total %s' % (stats(NumberOfFramesInOverlay)))

print('file,'
    'BurnedInAnnotation,',
    'RecognizableVisualFeatures,',
    'Manufacturer,'
    'ManufacturerModelName,'
    'ModelName,'
    'SoftwareVersions,'
    'CodeMeaning,'
    'CommentsOnRadiationDose,'
    'ImageType2,'
    'ImageType,'
    'ImplementationVersionName,'
    'SeriesDescription,'
    'WindowWidth,'
    'Rows,'
    'Columns,'
    'BitsStored',
    'BitsAllocated',
    'NumberOfFrames',
    'OverlayRows,'
    'OverlayColumns,'
    'OverlayType,'
    'NumberOfFramesInOverlay,'
    'OverlayDescription,'
    'OverlayBitsAllocated,'
    'OverlayBitPosition'
    )

# ---------------------------------------------------------------------
if __name__ == "__main__":
    for file in sys.argv[1:]:
        summarise_file(file)

