""" The FileList class maintains a simple list of filenames
allowing you to step forwards and backwards through the list.
It was intended to do more than this, but it's quite simple right now.
"""

import glob
import os

class FileList:
    """ A list of filenames to process.
    Was going to do clever stuff but at the moment is basically a list.
    """
    def __init__(self, filelist):
        self.files = []
        self.prefixes = ['']
        if os.environ.get('PACS_ROOT', None):
            self.set_prefix(os.environ.get('PACS_ROOT'))
        self.set_list(filelist)

    def set_prefix(self, prefix):
        """ Adds a path to be used as a prefix to find files
        """
        self.prefixes.append(prefix)

    def set_list(self, filenames):
        """ Record a list of filenames. Each entry can be a wildcard
        which is expanded to include all the matching files.
        """
        for file in filenames:
            if os.path.isabs(file):
                self.files.extend(glob.glob(file))
            else:
                for prefix in self.prefixes:
                    self.files.extend(glob.glob(os.path.join(prefix, file)))
        self.idx = -1

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
