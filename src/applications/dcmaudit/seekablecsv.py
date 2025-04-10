""" SeekableCsv can be used like csv.DictReader but it also allows
you to seek into any part of the file and continue reading dicts.
Use the seekafter() method to seek into the file, which will most
likely be in the middle of a row, then the next() call will return
the following row. Can also be used as an iterator.
"""

import csv
import tempfile


# =====================================================================
class SeekableCsv():
    """ This class can be used instead of csv.DictReader because it allows
    you to issue a seek into any part of the file and continue reading dicts.
    """
    def __init__(self, filename):
        self.filename = filename
        self.fd = open(self.filename)
        self.csvr = csv.reader(self.fd)
        self.fieldnames = next(self.csvr) # first line is header row
    def seek(self, offset):
        """ naive seek into file """
        self.fd.seek(offset)
    def seekafter(self, offset):
        """ seek into file then discard the remainder of the text line """
        self.seek(offset)
        self.fd.readline() # read remainder of text line
    def __iter__(self):
        return self
    def __next__(self):
        """ iterator which returns a dict of the next line in the file """
        dd = dict(zip(self.fieldnames, next(self.csvr)))
        return dd
    def __del__(self):
        self.fd.close()


# =====================================================================

def test_SeekableCsv():
    """ Test SeekableCsv """
    fn = tempfile.NamedTemporaryFile().name
    with open(fn, 'w') as fd:
        print('col1,col2', file=fd)
        print('this is a value in row1 col1,this is a value in row1 col2', file=fd)
        print('this is a value in row2 col1,this is a value in row2 col2', file=fd)
        print('this is a value in row3 col1,this is a value in row3 col2', file=fd)
    scsv = SeekableCsv(fn)
    assert(next(scsv) == {'col1':'this is a value in row1 col1', 'col2': 'this is a value in row1 col2'})
    scsv.seekafter(99)
    assert(next(scsv) == {'col1':'this is a value in row3 col1', 'col2': 'this is a value in row3 col2'})

# =====================================================================
