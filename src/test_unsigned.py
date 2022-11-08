#!/usr/bin/env python3
import pydicom
import numpy as np
from PIL import Image
f='/beegfs-hdruk/extract/v12/PACS/2010/05/20/T113H03987362/DX.2.16.840.114421.80924.9327679945.9390751945'
ds = pydicom.dcmread(f)

pix = ds.pixel_array
print(pix)
img_pix = Image.fromarray(pix)
img_pix.save('test_DX.pix.png')

pix_plus_unsigned = (pix+32768).astype(np.uint16)
print(pix_plus_unsigned)
img_pix_plus_unsigned = Image.fromarray(pix_plus_unsigned)
img_pix_plus_unsigned.save('test_DX.pix_plus_unsigned.png')

img_pix_plus_unsigned.convert('L').save('test_DX.pix_plus_unsigned_L.png')
