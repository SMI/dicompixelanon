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

# Configuration:
num_samples = 20          # how many randomly selected lines for each combination
max_lines_per_combo = 1000000 # don't need to choose from any more than 1 million examples
debug = False

# Select the set of columns which together make up a 'primary key'
# i.e. you want combinations of the combined values of these columns.
desired_cols = ['ModelName', 'ImageType2', 'BurnedInAnnotation']

# Internal variables:
debug_fd = sys.stderr
line_addr = {} # dict has a list of file pointers for each combination of the desired columns
reached_limit_on_examples_per_combo = False

# Command-line parameters
filename = sys.argv[1]


class SizedReader:
    """ After fd=open(, 'rb') create a SizedReader(fd)
    and use that instead of fd when opening a CSV
    so that every time csv calls next() the size value is updated
    thus you can implement a tell() method which is otherwise
    not available in python3.
    """
    def __init__(self, fd, encoding='utf-8'):
        self.fd = fd
        self.size = 0
        self.encoding = encoding   # specify encoding in constructor, with utf8 as default
    def __next__(self):
        line = next(self.fd)
        self.size += len(line)
        return line.decode(self.encoding)   # returns a decoded line (a true Python 3 string)
    def __iter__(self):
        return self
    def seek(self, offset):
        self.fd.seek(offset)
    def tell(self):
        return self.size
    def readline(self):
        return self.fd.readline().decode(self.encoding)
    def close(self):
        self.fd.close()


# Open the CSV file and read the header line.
raw_fd = open(filename, 'rb') # binary mode so that filepos is accurate byte count
fd = SizedReader(raw_fd)
csvrdr = csv.DictReader(fd)
csvrdr.fieldnames # read the header

# Read the whole CSV file, one line at a time (nothing kept in memory).
# Extract the values of all the columns of interest,
# concatenate them into a single string,
# use that as a key in a dict,
# where the value is a list of file pointers.
line_num = 1
pos = fd.tell()
for row in csvrdr:
    line_num += 1
    if debug: print('At %d is %s' % (pos, row))
    unique_str = ''
    for col in desired_cols:
        unique_str += row[col] + ','
    if unique_str in line_addr:
        if len(line_addr[unique_str]) < max_lines_per_combo:
            line_addr[unique_str].append(pos)
        else:
            reached_limit_on_examples_per_combo = True
    else:
        line_addr[unique_str] = [pos]
    if line_num % 20 == 0:
        print('%s Line %d Combinations %d\r' % (filename, line_num, len(line_addr)), file=debug_fd, end='')
    pos = fd.tell()
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
for combo in line_addr:
    ll = [str(x) for x in random.choices(line_addr[combo], k=num_samples)]
    csv_fd.writerow([combo, len(line_addr[combo])] + ll)
output_fd.close()

# Ditto but output filenames instead of file pointers
output_fd = open(filename + '_filenames.csv', 'w', newline='')
csv_fd = csv.writer(output_fd, lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
csv_fd.writerow(['combination', 'filename'])
for combo in line_addr:
    for filepos in random.choices(line_addr[combo], k=num_samples):
        fd.seek(int(filepos))
        csv_row = next(csv.reader([fd.readline().rstrip()]))
        fn = csv_row[1] # DicomFilePath
        csv_fd.writerow([combo, fn])
output_fd.close()
fd.close()
