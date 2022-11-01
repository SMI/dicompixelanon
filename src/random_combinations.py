#!/usr/bin/env python3
# Read a CSV file and output a randomly-selected set of lines
# for each of every combination of values in a given set of columns.
# eg. if you are interested in columns 'year', 'model, 'status'
# and you want to find N lines (selected at random) for each
# combination of year+model+status. The output is actually the
# file pointers not line numbers so you can more easily find the line.

import csv
import random
import sys

filename = sys.argv[1]
num_samples = 20          # how many randomly selected lines for each combination
max_lines_per_combo = 1000000 # don't need to choose from any more than 1 million examples
debug = False
debug_fd = sys.stderr

desired_cols = ['ModelName', 'ImageType2', 'BurnedInAnnotation'] # names of columns (as defined in header row) which you want
desired_cols_index = []        # will be filled in with the index of those columns

line_addr = {} # dict has a list of file pointers for each combination of the desired columns
reached_limit_on_examples_per_combo = False

# Read the header line of a CSV file,
# look for a given set of column names,
# and record which array index they appear at,
# so if you want C and E from A,B,C,D,E
# you get desired_cols_index = [2,4] (counting from zero).
fd = open(filename)
header_line = fd.readline().rstrip()
header_row = next(csv.reader([header_line]))
num_cols = len(header_row)
if debug: print('columns in file: %s' % header_row)
for idx in range(len(header_row)):
    if header_row[idx] in desired_cols:
        desired_cols_index.append(idx)
if debug: print('indexes of desired columns: %s' % desired_cols_index)

# Read the whole CSV file, one line at a time (nothing kept in memory).
# Extract the values of all the columns of interest,
# concatenate them into a single string,
# use that as a key in a dict,
# where the value is a list of file pointers.
# This code looks complicated because we can't get a file pointer from the
# python csv reader so we have to read the CSV manually :-(
line_num = 1
while True:
    pos = fd.tell()
    line = ''
    line_cols = 0
    row = []
    # One CSV row may span multiple lines so read until num_cols read.
    while line_cols < num_cols:
        line_part = fd.readline()
        if not line_part:
            break
        line += line_part
        line_cols = len(next(csv.reader([line])))
    if line_cols < num_cols:
        break
    line_num += 1
    row = next(csv.reader([line]))
    if debug: print('At %d is %s' % (pos, row))
    unique_str = ''
    for col_idx in desired_cols_index:
        if debug: print('%d is %s' % (col_idx, row[col_idx]))
        try:
            unique_str += row[col_idx] + ','
        except:
            print('\nCannot access idx %s in %s' % (col_idx, row))
            print('\nDesired cols is %s' % (desired_cols_index))
            print('\nLine %d' % line_num)
            exit(1)
    if debug: print(unique_str)
    if unique_str in line_addr:
        if len(line_addr[unique_str]) < max_lines_per_combo:
            line_addr[unique_str].append(pos)
        else:
            reached_limit_on_examples_per_combo = True
    else:
        line_addr[unique_str] = [pos]
    if line_num % 20 == 0:
        print('%s Line %d Combinations %d\r' % (filename, line_num, len(line_addr)), file=debug_fd, end='')
print(file=debug_fd)
if reached_limit_on_examples_per_combo:
    print('WARNING: reached limit at least once on number of samples per combination of variables', file=debug_fd)

# Make a random selection from the list of file pointers
# for every combination of the values in the columns of interest
# and output in a CSV-style file.
# Columns are: the combination of variables,
#  the number of rows in original CSV having that combination,
#  then num_samples columns of file pointers.
# To use this output you can read each file pointer from the columns
# seek in the original CSV file and read the line directly.
output_fd = open(filename + '_filepos.csv', 'w', newline='')
csv_fd = csv.writer(output_fd, lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
csv_fd.writerow(['combination', 'total'] + [str(x) for x in range(num_samples)])
for entry in line_addr:
    ll = [str(x) for x in random.choices(line_addr[entry], k=num_samples)]
    csv_fd.writerow([entry, len(line_addr[entry])] + ll)
output_fd.close()
fd.close()
