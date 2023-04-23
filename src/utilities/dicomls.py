#!/usr/bin/env python3

import sys
import pydicom

ds = pydicom.dcmread(sys.argv[1])
print(ds)
