import datetime
import getpass # for getuser
import json
import logging
import os
import sys
from pydal import DAL, Field
from rect import Rect, DicomRect, add_Rect_to_list


class DicomRectDB():
    """ Persist rectangles, marks and comments about a file in a database.
    Two tables: DicomRects (holds DicomRect data, multiple per file) and
    DicomTags (holds a mark (True/False) and a text comment, one per file).
    See: http://www.web2py.com/books/default/chapter/29/06/the-database-abstraction-layer
    """
    # Class static variable holding path to database, needs trailing slash.
    # Set the value using DicomRectDB.db_path = 'dir/'
    db_path = ''

    def __init__(self):
        # default to current directory if given path doesn't exist
        if DicomRectDB.db_path and not os.path.isdir(DicomRectDB.db_path):
            logging.error('Database path does not exist: %s' % DicomRectDB.db_path)
            DicomRectDB.db_path = ''
        self.db=DAL('sqlite://dcmaudit.sqlite.db', folder = DicomRectDB.db_path) # debug=True
        self.db.define_table('DicomRects', Field('filename'),
            Field('top', type='integer'), Field('bottom', type='integer'),
            Field('left', type='integer'), Field('right', type='integer'),
            Field('frame', type='integer'), Field('overlay', type='integer'),
            Field('last_modified', type='datetime'),
            Field('last_modified_by'))
        self.db.define_table('DicomTags', Field('filename', unique=True),
            Field('mark', type='boolean'), Field('comment'),
            Field('Modality'), Field('ImageType'),
            Field('ManufacturerModelName'),
            Field('BurnedInAnnotation'),
            Field('Rows', type='integer'), Field('Columns', type='integer'),
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
        t, b, l, r = dicomrect.get_rect()
        frame = dicomrect.F()
        overlay = dicomrect.O()
        lastmod = datetime.datetime.now()
        self.db.DicomRects.insert(filename=filename,
            top = t, bottom = b, left = l, right = r,
            frame = frame, overlay = overlay,
            last_modified = lastmod, last_modified_by = self.username)
        self.db.commit()
        return

    def add_tag(self, filename, mark, comment = None):
        # XXX need to select to get any existing value of comment if not specified in this call
        lastmod = datetime.datetime.now()
        self.db.DicomTags.insert(filename=filename,
            mark = mark, comment = comment,
            last_modified = lastmod, last_modified_by = self.username)
        self.db.commit()

    def toggle_tag(self, filename):
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
            mark = tag_val, comment = comment_val,
            last_modified = lastmod, last_modified_by = self.username)
        self.db.commit()
        logging.debug('tag now %s for %s' % (tag_val, filename))

    def mark_inspected(self, filename, metadata_dict = None):
        """ Simply add a blank entry to db showing that this file was inspected.
        If metadata_dict is passed it must contain entries named the same as
        the Fields in the Rects table. See DicomImage.get_selected_metadata.
        """
        row = self.db(self.db.DicomTags.filename == filename).select()
        if not row:
            logging.debug('tag as inspected %s' % filename)
            self.add_tag(filename, False)
        # Ensure full DICOM metadata is now stored
        # (no point doing this earlier as it wastes space unless image will be useful)
        if metadata_dict:
            lastmod = datetime.datetime.now()
            self.db.DicomTags.update_or_insert(self.db.DicomTags.filename == filename,
                **metadata_dict,
                last_modified = lastmod, last_modified_by = self.username)
            self.db.commit()
            #logging.debug(self.db._timings)

    def file_marked_done(self, filename):
        """ A file is marked as done if it contains a tag which is False
        because True means it needs to be reviewed again.
        """
        row = self.db(self.db.DicomTags.filename == filename).select()
        if row and row[0].mark == False:
            return True
        return False


    def remove_file(self, filename):
        """ Remove all database entries for the given filename
        """
        self.db(self.db.DicomTags.filename == filename).delete()
        self.db.commit()
        self.db(self.db.DicomRects.filename == filename).delete()
        self.db.commit()


    def query_all(self):
        """ Only for debugging, prints all rectangles and comments in the DB.
        Sorts by last_modified so most recent is at the end.
        Output is in JSON format, { "rects":[], "tags":[] }
        """
        print('{"rects":[')
        first = True
        for row in self.db(self.db.DicomRects).select(orderby = self.db.DicomRects.last_modified):
            print('%s%s' % (('' if first else ','), row.as_json()))
            first = False
        print('],"tags":[')
        first = True
        for row in self.db(self.db.DicomTags).select(orderby = self.db.DicomTags.last_modified):
            imagetype = row['ImageType']
            if imagetype:
                # handle old-format databases where string was Python not JSON
                row['ImageType'] = json.loads(imagetype.replace("'", '"'))
            print('%s%s' % (('' if first else ','), row.as_json()))
            first = False
        print(']\n}')

    def query_rects(self, filename, frame = -1, overlay = -1):
        """ Return a list of DicomRect objects for the given filename
        by reading from the database.
        Filtered to just the given frame and overlay, if specified,
        or returns all if both frame and overlay are unspecified or -1.
        """
        rc = []
        for row in self.db(self.db.DicomRects.filename == filename).select():
            if ((row.frame == frame) and (row.overlay == overlay)) or (frame == -1 and overlay == -1):
                dicomrect = DicomRect(top = row.top, bottom = row.bottom,
                    left = row.left, right = row.right,
                    frame = row.frame, overlay = row.overlay)
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
        similar metadata, and return their rects
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
                add_Rect_to_list(rect_list, rect)
        logging.debug('Found suggested rectangles: %s' % (rect_list))
        return rect_list


if __name__ == '__main__':
    if len(sys.argv)>1:
        DicomRectDB.db_path = sys.argv[1]
    db = DicomRectDB()
    db.query_all()
