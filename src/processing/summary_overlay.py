#!/usr/bin/env python3

import csv
import sys

for file in sys.argv[1:]:
  fd = open(file)
  rdr = csv.DictReader(fd)
  for row in rdr:
    print('%s,%s,%s,%s,%s' % (row['OverlayType'],row['NumberOfFramesInOverlay'],row['OverlayDescription'],row['OverlayBitsAllocated'],row['OverlayBitPosition']))
