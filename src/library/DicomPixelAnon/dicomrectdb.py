""" The DicomRectDB maintains a database of DicomRect and DicomRectText objects.
"""

import csv
import datetime
import getpass # for getuser
import json
import logging
import os
import sys
import time
from pydal import DAL, Field
from DicomPixelAnon.rect import Rect, DicomRect, DicomRectText, add_Rect_to_list
from DicomPixelAnon.ocrenum import OCREnum
from DicomPixelAnon.nerenum import NEREnum


class DicomRectDB():
    """ Persist rectangles, marks and comments about a file in a database.
    Two tables: DicomRects (holds DicomRect data, multiple per file) and
    DicomTags (holds a mark (True/False) and a text comment, one per file).
    See: http://www.web2py.com/books/default/chapter/29/06/the-database-abstraction-layer
    """
    # Class static variable holding path to database, needs trailing slash.
    # Set the value using set_db_path('dir/') or DicomRectDB.db_path = 'dir/'
    db_path = ''
    db_filename = 'dcmaudit.sqlite.db'

    @staticmethod
    def set_db_path(path):
        """ Set the class-static path to the database directory.
        Note that this affects all instances of this class.
        """
        DicomRectDB.db_path = path

    def __init__(self, filename = None):
        """ Construct a DicomRectDB in the path set by set_db_path()
        with the filename dcmaudit.sqlite.db, and open a connection to this
        database which will be kept open (not exclusively) while this object exists.
        If the filename is given then it's used instead of the class vars
        but this is not the expected way to construct this object.
        """
        # default to current directory if given path doesn't exist
        if DicomRectDB.db_path and not os.path.isdir(DicomRectDB.db_path):
            logging.warning('Database path does not exist: %s (will use current directory)' % DicomRectDB.db_path)
            DicomRectDB.db_path = ''
        if filename:
            dbdir = os.path.dirname(filename)
            dbfile = os.path.basename(filename)
        else:
            dbdir = DicomRectDB.db_path
            dbfile = DicomRectDB.db_filename
        self.db=DAL('sqlite://'+dbfile, folder = dbdir, attempts=60) # debug=True
        self.db.define_table('DicomRects',
            Field('filename'),
            Field('top', type='integer'),
            Field('bottom', type='integer'),
            Field('left', type='integer'),
            Field('right', type='integer'),
            Field('frame', type='integer', default=-1),
            Field('overlay', type='integer', default=-1),
            Field('ocrengine', type='integer', default=-1),    # one of the ocrengine enums
            Field('ocrtext'),                                  # text extracted by OCR
            Field('nerengine', type='integer', default=-1),    # one of the nerengine enums
            Field('nerpii', type='integer', default=-1),       # -1 (unknown), 0 (false), 1 (true)
            Field('last_modified', type='datetime'),
            Field('last_modified_by'))
        self.db.define_table('DicomTags',
            Field('filename', unique=True),
            Field('mark', type='boolean'),
            Field('comment'),
            Field('Modality'),
            Field('ImageType'), # must be string, with double quotes, and forward slashes
            Field('ManufacturerModelName'),
            Field('BurnedInAnnotation'),
            Field('Rows', type='integer'),
            Field('Columns', type='integer'),
            Field('last_modified', type='datetime'),
            Field('last_modified_by'))
        self.username = getpass.getuser() # os.getlogin fails when in a GUI

    def __del__(self):
        self.db.close() # this should happen when we del the object but it doesn't, it's also not documented
        del self.db

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # XXX does __del__ also get called in this case?
        pass

    def __repr__(self):
        return('<DicomRectDB(%s)>' % DicomRectDB.db_path)

    def add_rect(self, filename, dicomrect):
        """ Add a rectangle to the database, must be given a subclass of Rect,
        which can be Rect, DicomRect, or DicomRectText.
        """
        t, b, l, r = dicomrect.get_rect()
        # If the argument is a DicomRect or subclass, get the frame,overlay
        frame = dicomrect.F() if hasattr(dicomrect, 'F') else -1
        overlay = dicomrect.O() if hasattr(dicomrect, 'O') else -1
        # If the argument is a DicomRectText, get the ocr text
        # This single-line statement doesn't work
        #ocrengine, ocrtext, nerengine, nerpii = dicomrect.text_tuple() if hasattr(dicomrect, 'text_tuple') else -1, '', -1, -1
        if hasattr(dicomrect, 'text_tuple'):
            ocrengine, ocrtext, nerengine, nerpii = dicomrect.text_tuple()
        else:
            ocrengine, ocrtext, nerengine, nerpii = -1, '', -1, -1
        lastmod = datetime.datetime.now()
        # Sadly pydal does not retry this if the database is locked
        for attempts in range(99):
            try:
                self.db.DicomRects.insert(filename=filename,
                    top = t, bottom = b, left = l, right = r,
                    frame = frame, overlay = overlay,
                    ocrengine = ocrengine, ocrtext = ocrtext,
                    nerengine = nerengine, nerpii = nerpii,
                    last_modified = lastmod, last_modified_by = self.username)
                self.db.commit()
                break
            except Exception as e:
                if str(e) == 'database is locked' and attempts < 99:
                    time.sleep(0.1)
                    continue
                raise(e)
        return

    def add_tag(self, filename, mark : bool, comment = None, metadata_dict = None):
        """ Add a tag to a file in the database, being True or False,
        with an optional comment.
        Existing comment (if any) is preserved if not specified.
        """
        # Get any existing value of comment if not specified in this call
        if not comment:
            row = self.db(self.db.DicomTags.filename == filename).select()
            if row:
                comment = row[0].comment
        lastmod = datetime.datetime.now()
        self.db.DicomTags.update_or_insert(self.db.DicomTags.filename == filename,
            filename=filename,
            **metadata_dict,
            mark = mark, comment = comment,
            last_modified = lastmod, last_modified_by = self.username)
        self.db.commit()

    def toggle_tag(self, filename, metadata_dict = None):
        """ Toggle the tag for a given file in the database.
        Preserves the comment but updates the last_modified time and user.
        """
        row = self.db(self.db.DicomTags.filename == filename).select()
        if row:
            tag_val = row[0].mark
            comment_val = row[0].comment
        else:
            tag_val = False
            comment_val = None
        tag_val = not tag_val
        lastmod = datetime.datetime.now()
        self.db.DicomTags.update_or_insert(self.db.DicomTags.filename == filename,
            filename=filename,
            **metadata_dict,
            mark = tag_val, comment = comment_val,
            last_modified = lastmod, last_modified_by = self.username)
        self.db.commit()
        logging.debug('tag now %s for %s' % (tag_val, filename))

    def file_tagged(self, filename):
        """ A file is tagged (as distinct from being marked inspected)
        only if its 'mark' property is True.
        """
        tag_val = False
        row = self.db(self.db.DicomTags.filename == filename).select()
        if row:
            tag_val = row[0].mark
        return tag_val

    def mark_inspected(self, filename, metadata_dict = None):
        """ Simply add a blank entry to db showing that this file was inspected.
        If metadata_dict is passed it must contain entries named the same as
        the Fields in the Rects table. See DicomImage.get_selected_metadata.
        """
        row = self.db(self.db.DicomTags.filename == filename).select()
        if not row:
            logging.debug('tag as inspected %s' % filename)
            self.add_tag(filename, mark = False, metadata_dict = metadata_dict)

    def file_marked_done(self, filename):
        """ A file is marked as done if it contains a tag which is False
        because True means it needs to be reviewed again.
        """
        row = self.db(self.db.DicomTags.filename == filename).select()
        if row and not row[0].mark:
            return True
        return False


    def remove_file(self, filename):
        """ Remove all database entries for the given filename
        """
        self.db(self.db.DicomTags.filename == filename).delete()
        self.db.commit()
        self.db(self.db.DicomRects.filename == filename).delete()
        self.db.commit()


    def query_all_csv(self, fd = sys.stdout, query_rects = False, query_tags = False):
        """ Only for debugging, prints all rectangles and comments in the DB.
        Sorts by last_modified so most recent is at the end.
        Output is in CSV format.
        If you only want rects or tags then set the other query_X=False.
        Remember you must open the fd using open(filename, newline='')
        """
        csv_writer = csv.writer(fd)
        if query_rects:
            first = True
            for row in self.db(self.db.DicomRects).select(orderby = self.db.DicomRects.last_modified):
                rowdict = row.as_dict()
                if first:
                    csv_writer.writerow(rowdict.keys())
                csv_writer.writerow(rowdict.values())
                first = False
        if query_tags:
            first = True
            for row in self.db(self.db.DicomTags).select(orderby = self.db.DicomTags.last_modified):
                rowdict = row.as_dict()
                if first:
                    csv_writer.writerow(rowdict.keys())
                csv_writer.writerow(rowdict.values())
                first = False


    def query_all(self, fd = sys.stdout, query_rects = True, query_tags = True):
        """ Only for debugging, prints all rectangles and comments in the DB.
        Sorts by last_modified so most recent is at the end.
        Output is in JSON format, { "rects":[], "tags":[] }
        If you only want rects or tags then set the other query_X=False.
        """
        rc = '{'
        if query_rects:
            rc += '"rects":[\n'
            first = True
            for row in self.db(self.db.DicomRects).select(orderby = self.db.DicomRects.last_modified):
                rc += '%s%s\n' % (('' if first else ','), row.as_json())
                first = False
            rc += ']'
        if query_rects and query_tags:
            rc += ','
        if query_tags:
            rc += '"tags":[\n'
            first = True
            for row in self.db(self.db.DicomTags).select(orderby = self.db.DicomTags.last_modified):
                imagetype = row['ImageType']
                if imagetype:
                    # handle old-format databases where string was Python not JSON
                    row['ImageType'] = json.loads(imagetype.replace("'", '"'))
                rc += '%s%s\n' % (('' if first else ','), row.as_json())
                first = False
            rc += ']\n'
        rc += '}\n'
        print(rc, file=fd)
        return rc

    def query_rect_filenames(self):
        """ Return a list of filenames which have rectangles in the database.
        """
        rc = []
        for row in self.db(self.db.DicomRects).select('filename', distinct=True):
            rc.append(row['filename'])
        return rc

    def query_tag_filenames(self):
        """ Return a list of filenames which have tags in the database.
        """
        rc = []
        for row in self.db(self.db.DicomTags).select('filename', distinct=True):
            rc.append(row['filename'])
        return rc

    def query_rects(self, filename, frame = -1, overlay = -1, ignore_allowlisted = False, ignore_summaries = False):
        """ Return a list of DicomRectText objects for the given filename
        by reading from the database.
        Filtered to just the given frame and overlay, if specified,
        or returns all if both frame and overlay are unspecified or -1.
        """
        rc = []
        for row in self.db(self.db.DicomRects.filename == filename).select():
            if ((row.frame == frame) and (row.overlay == overlay)) or (frame == -1 and overlay == -1):
                dicomrect = DicomRectText(top = row.top, bottom = row.bottom,
                    left = row.left, right = row.right,
                    frame = row.frame, overlay = row.overlay,
                    ocrengine = row.ocrengine, ocrtext=row.ocrtext,
                    nerengine = row.nerengine, nerpii = row.nerpii)
                if ignore_summaries and row.left == -1 and row.right == -1:
                    continue
                if ignore_allowlisted and (row.nerengine == NEREnum.allowlist) and (row.nerpii == 0):
                    continue
                rc.append(dicomrect)
        return rc

    def query_tags(self, filename):
        """ Query the database for the given filename and return a tuple:
        mark, comment - where mark is whether the file has been marked,
        and comment is any manually entered comment.
        Returns False,None if the file is not in the database.
        """
        # There can only be a single row per filename because it's unique
        row = self.db(self.db.DicomTags.filename == filename).select()
        if not row:
            return False, None
        return row[0].mark, row[0].comment

    def query_similar_rects(self, filename, metadata_dict, frame = -1, overlay = -1):
        """ Look for files in the DB (which are not the given filename!) that have
        similar metadata, and return their rects.
        Note that coalesce_similar is used to reduce the number of rectangles
        returned by merging similar ones together.
        """
        assert 'Modality' in metadata_dict
        assert 'ImageType' in metadata_dict
        assert 'Rows' in metadata_dict
        assert 'Columns' in metadata_dict
        assert 'ManufacturerModelName' in metadata_dict
        rows = self.db((self.db.DicomTags.Modality == metadata_dict['Modality']) &
            (self.db.DicomTags.ImageType == metadata_dict['ImageType']) &
            (self.db.DicomTags.Rows == metadata_dict['Rows']) &
            (self.db.DicomTags.Columns == metadata_dict['Columns']) &
            (self.db.DicomTags.ManufacturerModelName == metadata_dict['ManufacturerModelName']) &
            (self.db.DicomTags.filename != filename)).select()
        rect_list = []
        for row in rows:
            for rect in self.query_rects(row.filename, frame, overlay):
                add_Rect_to_list(rect_list, rect, coalesce_similar = True)
        logging.debug('Found suggested rectangles: %s' % (rect_list))
        return rect_list


def test_DicomRectDB(tmpdir):
    logging.basicConfig(level = logging.DEBUG)
    DicomRectDB.set_db_path(tmpdir)
    db = DicomRectDB()
    db.add_rect('file1', DicomRect(10,20,10,20, 0,-1))
    db.add_rect('file2', DicomRectText(10,30,10,30, 0,-1, OCREnum.EasyOCREngine, '10/11/23', NEREnum.allowlist, 1))
    rc = db.query_rects('file1')
    assert(str(rc) == '[<DicomRectText frame=0 overlay=-1 10,10->20,20 -1="" -1=-1>]')
    metadata_dict = { "Modality": "CT",
        "ImageType": '"ORIGINAL/PRIMARY"',
        "ManufacturerModelName": "",
        "BurnedInAnnotation": "YES",
        "Rows": 1024,
        "Columns": 1024
    }
    # Add a file with one rectangle and tag=True
    db.add_rect('file3', DicomRect(10,40,10,40, 0,-1))
    db.add_tag('file3', mark = True, metadata_dict = metadata_dict)
    # A a file with one rectangle and tag=False meaning file marked as done
    db.add_rect('file4', DicomRect(10,50,10,50, 0,-1))
    db.mark_inspected('file4', metadata_dict = metadata_dict)
    # Check file3
    rc = db.query_tags('file3')
    assert(rc == (True, None))
    # Check file4
    rc = db.query_tags('file4')
    assert(rc == (False, None)) # XXX also the case if file not in DB, need to fix
    # Check that file3,file4 rects are returned coalesced
    rc = db.query_similar_rects('random_filename', metadata_dict)
    assert(str(rc) == '[<DicomRectText frame=0 overlay=-1 10,10->50,50 -1="" -1=-1>]')



if __name__ == '__main__':
    if len(sys.argv)>1:
        DicomRectDB.set_db_path(sys.argv[1])
    db = DicomRectDB()
    db.add_rect('fakerect', Rect(1,2,3,4))
    db.add_rect('fakedicomrect', DicomRect(1,2,3,4,5,6))
    db.add_rect('fakedicomrecttext', DicomRectText(1,2,3,4,5,6, 10,'Fake Text',1,1))
    db.query_all()
