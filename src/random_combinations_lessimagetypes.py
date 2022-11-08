#!/usr/bin/env python3

import sys
import re

fd = sys.stdin
fdout = sys.stdout

hdr = next(fd) # header
print(hdr, file=fdout)

for line in fd:
  # Take everything before the last quote (") and split by ,
  # (because the bit inside quotes can contain quotes, oops)
  # eg. "YES,"MY MACHINE",ORIG\PRIM,",1,2,3
  # we remove the ,1,2,3 then split by comma.
  combo = line.rpartition('"')[0].split(',')
  # Take the penultimate part, the ORIG\PRIM above.
  imagetype = combo[len(combo)-2]
  # Get a replacement, if starts with a known good prefix
  for knowngood in ['ORIGINAL\\PRIMARY', 'ORIGINAL\\SECONDARY' 'DERIVED\\PRIMARY', 'DERIVED\\SECONDARY']:
    if imagetype.startswith(knowngood):
      #print('%s starts with %s' % (imagetype, knowngood))
      # keep just the knowngood part and remove the rest
      #print('WAS %s' % line)
      line = re.sub(knowngood.encode('unicode_escape').decode()+'.*",', knowngood+',",', line)
      #print('NOW %s' % line)
      print(line, file=fdout, end='')
