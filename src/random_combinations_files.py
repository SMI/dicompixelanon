#!/usr/bin/env python3

# Read the output from random_combinations.py,
# given a filename like extract_BIA_from_XX.csv_filepos.csv
# and convert the file offsets into filenames
# by reading the original CSV file.
# Assumes the original CSV is the same filename with _filepos.csv removed.
# Usage: [-d] [-c] [-1] [-n N] [-F filter] extract_BIA_from_XX.csv_filepos.csv
# Use -C to print the combination it came from as well as the filename.
# Use -1 to get only the first filename from each combination, or
# use -n to get only the first N filenames from each combination.
# Use -F to filter to only the combinations which match the given string.
# Output is filenames, one per line, written to stdout.

import argparse
import csv
import os
import sys

parser = argparse.ArgumentParser()
parser.add_argument('-1', '--one', action="store_true", help='only print the first filename from each combination')
parser.add_argument('-n', '--number', action="store", help='only print the first N filenames from each combination')
parser.add_argument('-c', '--show-combination', action="store_true", help='show the combination string')
parser.add_argument('-F', '--filter', action="store", help='only output those where combination contains the given string')
parser.add_argument('-d', '--debug', action="store_true", help='debug')
parser.add_argument('file', nargs=argparse.REMAINDER)
args = parser.parse_args()

filename = args.file[0]
if args.one:
    max_files_to_print = 1
elif args.number:
    max_files_to_print = int(args.number)
else:
    max_files_to_print = 999999999999
if args.show_combination:
    show_combination = True
else:
    show_combination = False
debug = args.debug
filter = args.filter

orig_csv_filename = filename.replace('_filepos.csv', '')
pacs_root = os.getenv('PACS_ROOT')

fd = open(filename)
rdr = csv.reader(fd)
next(rdr) # skip header row

# columns should be: combination,total,fp,fp,fp,fp,fp...
rownum=0
for row in rdr:
    rownum += 1
    combo = row.pop(0)
    total = row.pop(0)

    if filter and not filter in combo:
        continue

    fp_set = set(row) # a set makes them unique
    if debug: print('Set of fp: %s' % fp_set)
    csv_fd = open(orig_csv_filename)
    num_files_printed = 0
    for fp in fp_set:
        csv_fd.seek(int(fp))
        csv_row = next(csv.reader([csv_fd.readline().rstrip()]))
        DicomFilePath = csv_row[1]
        if show_combination:
            print('"%s",%s/%s ' % (combo, pacs_root, DicomFilePath))
        else:
            print('%s/%s ' % (pacs_root, DicomFilePath))
        num_files_printed += 1
        if num_files_printed == max_files_to_print:
            break
