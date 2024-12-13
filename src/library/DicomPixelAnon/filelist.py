""" The FileList class maintains a simple list of filenames
allowing you to step forwards and backwards through the list.
It was intended to do more than this, but it's quite simple right now.
"""

import csv
import glob
import logging
import os
from DicomPixelAnon.s3url import s3url_is


class FileList:
    """ A list of filenames to process.
    Was going to do clever stuff but at the moment is basically a list.
    Can be initialised from:
    * a list of filenames,
    * filenames can include wildcards that are expanded,
    * filenames can include a CSV file which is read for filename or DicomFilePath column
    * filenames which are relative to current directory or to $PACS_ROOT
    """
    def __init__(self, filelist):
        self.files = []
        self.prefixes = ['']
        if os.environ.get('PACS_ROOT', None):
            self.set_prefix(os.environ.get('PACS_ROOT'))
        self.set_list(filelist)

    def __repr__(self):
        return '<FileList at %d %s>' % (self.idx, self.files)

    def set_prefix(self, prefix):
        """ Adds a path to be used as a prefix to find files
        """
        self.prefixes.append(prefix)

    def set_list(self, filenames):
        """ Record a list of filenames. Each entry can be a wildcard
        which is expanded to include all the matching files.
        If an entry in the list is a filename *.csv or *.CSV then the
        CSV file is read and the list of filenames is taken from the
        'filename' or 'DicomFilePath' column.
        If an entry in the list is a s3:// URL then it is appended as given.
        """
        for file in filenames:
            # Read filenames from a CSV file
            if file.endswith('.csv') or file.endswith('.CSV'):
                with open(file, newline='') as fd:
                    rdr = csv.DictReader(fd)
                    for row in rdr:
                        if 'filename' in row:
                            cfile = row['filename']
                        elif 'DicomFilePath' in row:
                            cfile = row['DicomFilePath']
                        else:
                            logging.getLogger(__name__).error('set_list(%s) is not sure which column in CSV holds filename' % file)
                            break
                        if os.path.isabs(cfile):
                            self.files.extend(glob.glob(cfile))
                        else:
                            for prefix in self.prefixes:
                                # XXX should use realpath to check this file not already added
                                self.files.extend(glob.glob(os.path.join(prefix, cfile)))
            elif s3url_is(file):
                self.files.append(file)
            elif os.path.isabs(file):
                self.files.extend(glob.glob(file))
            else:
                for prefix in self.prefixes:
                    # XXX should use realpath to check this file not already added
                    self.files.extend(glob.glob(os.path.join(prefix, file)))
        self.idx = -1

    def is_exhausted(self):
        if (self.idx+1) >= len(self.files):
            return True
        return False

    def next(self):
        """ Return the next filename, or None
        """
        self.idx += 1
        if self.idx >= len(self.files):
            return None
        return self.files[self.idx]

    def prev(self):
        """ Return the previous filename, or None
        """
        self.idx -= 1
        if self.idx < -1:
            self.idx = -1
            return None
        return self.files[self.idx]

    def get_current_index(self):
        return self.idx, len(self.files)
