#!/usr/bin/env python3
# Simple program to review the report produced by CohortPackager
#  - displays a list of words found by IsIdentifiable
#  - displays a list of files containing a chosen word
#  - displays the content of a StructuredReport from a chosen file
#  - allows the file to be marked as safe or not
# Requires SmiServices installed in your python path.
# TODO: load report faster (don't use DictReader?).
# TODO: run NER on the text and highlight PII which may have been missed.
# TODO: allow undo if user clicks wrong button.
# TODO: Use a database?

import argparse
import csv
import datetime
import getpass # for getuser
import logging
import os
import re
import sys
sys.path.append('../../SmiServices/src/common/Smi_Common_Python/')
from SmiServices import DicomText
from pydal import DAL, Field
try:
    import PySimpleGUI as gui
except:
    try:
        import PySimpleGUIQt as gui
    except:
        raise Exception('No version of PySimpleGUI is installed')

# Default values of parameters
report_filename = 'verification_failures_TextValue.csv.orig.noCR'
root_dir = '/nimble/2021-0063/2021-0063-StudyInstanceUID/dicom'
good_button_colour = ('white', 'green')    # Mark as False Positive
bad_button_colour = ('white', 'red')       # Mark as PII
other_button_colour = ('black', 'yellow')  # Reviewed
bad_text_colour = 'red'                    # Highlighted PII in text body
default_button_colour = ('white', 'grey') #gui.COLOR_SYSTEM_DEFAULT doesn't work
good_list_filename = 'reviewed_as_false_positives.csv'
other_list_filename = 'reviewed.csv'
bad_list_filename = 'reviewed_as_PII.csv'

# Write to scriptpath/../data/progname/
csv_directory = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', 'data', os.path.basename(__file__).replace('.py','')))
try:
    os.makedirs(csv_directory, exist_ok=True)
except:
    csv_directory = '.'
db_directory = csv_directory

class SRReviewDB():
    db_path = db_directory

    def __init__(self):
        self.db=DAL('sqlite://review_SR_report.sqlite.db', folder = SRReviewDB.db_path) # debug=True
        self.db.define_table('ReviewedSRs', Field('filename', required=True, notnull=True), # unique=True
            Field('word'), Field('review'),
            Field('last_modified', type='datetime'),
            Field('last_modified_by'))
        self.db.executesql('CREATE INDEX IF NOT EXISTS filenameidx ON ReviewedSRs (filename);')
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
        return('<SRReviewDB(%s)>' % SRReviewDB.db_path)

    def get_review(self, filename, word):
        review = ''
        for row in self.db(
                (self.db.ReviewedSRs.filename == filename) &
                (self.db.ReviewedSRs.word == word)
                ).select():
            review = row['review']
        return review

    def mark_as_reviewed(self, filename, word, review):
        # If db already contains filename then only overwrite the old value if
        # it is safe, i.e. a true positive (PII) takes priority and can't be
        # replaced by a false positive
        # otherwise you'd lose the fact that it contains PII.
        lastmod = datetime.datetime.now()
        already_reviewed = self.get_review(filename, word)
        if already_reviewed == 'TP':
            logging.debug('ignore "%s" update to %s as already "TP"' % (review, filename))
            return
        if already_reviewed:
            self.db((self.db.ReviewedSRs.filename == filename) & (self.db.ReviewedSRs.word == word)).update(
                review = review,
                last_modified = lastmod, last_modified_by = self.username)
        else:
            self.db.ReviewedSRs.update_or_insert(filename=filename,
                word = word,
                review = review,
                last_modified = lastmod, last_modified_by = self.username)
        self.db.commit()

    def mark_as_false_positive(self, filename, word):
        self.mark_as_reviewed(filename, word, 'FP')

    def mark_as_PII(self, filename, word):
        self.mark_as_reviewed(filename, word, 'TP')

    def mark_as_other(self, filename, word):
        self.mark_as_reviewed(filename, word, 'reviewed')

    def dump_db(self):
        print('{"files":[')
        first = True
        for row in self.db(self.db.ReviewedSRs).select(orderby = self.db.ReviewedSRs.last_modified):
            print('%s%s' % (('' if first else ','), row.as_json()))
            first = False
        print(']\n}')


def test_SRReviewDB():
    db = SRReviewDB()
    print('test1 word1 = %s' % db.get_review('test1', 'word1'))
    print('test1 word2 = %s' % db.get_review('test1', 'word2'))
    print('test2 word4 = %s' % db.get_review('test2', 'word4'))
    db.mark_as_false_positive('test1', 'word1')
    db.mark_as_PII('test1', 'word2')
    db.mark_as_false_positive('test1', 'word2') # should not overwrite PII
    db.mark_as_PII('test2', 'word4')
    print('test1 word1 = %s' % db.get_review('test1', 'word1'))
    print('test1 word2 = %s' % db.get_review('test1', 'word2'))
    print('test2 word4 = %s' % db.get_review('test2', 'word4'))
    db.dump_db()
    assert(db.get_review('test1', 'word1') == 'FP')
    assert(db.get_review('test1', 'word2') == 'TP')
    assert(db.get_review('test2', 'word4') == 'TP')
    assert(1==2)


def write_db_false_positive(word, filename):
    db = SRReviewDB()
    db.mark_as_false_positive(filename, word)

def write_db_PII(word, filename):
    db = SRReviewDB()
    db.mark_as_PII(filename, word)

def write_db_reviewed(word, filename):
    db = SRReviewDB()
    db.mark_as_other(filename, word)


def write_csv(filename, word_filename_list):
    """ Write a CSV filename in the csv_directory which contains
    all rows in word_filename_list. Columns assumed to be in the order
    as specified in the writerow() call below (word,filename).
    Appends to the CSV file if it already exists.
    """
    filename = os.path.join(csv_directory, filename)
    append = os.path.isfile(filename)
    if append:
        fd = open(filename, 'a', newline='')
    else:
        fd = open(filename, 'w', newline='')
    writer = csv.writer(fd)
    if not append:
        writer.writerow(['word', 'filename'])
    writer.writerows(word_filename_list)
    fd.close()


def load_report(report_filename, root_dir = ''):
    """ Read the report into a dictionary indexed by the Word
    Word,Classification,ProblemValueWindow,Offset,Resource
    If root_dir is given it is prepended onto all paths in the report.
    """
    # Count number of lines in file
    csv_fd = open(report_filename)
    csv_numlines = sum(1 for i in csv_fd)
    csv_fd.close()
    # Read in as a CSV
    csv_fd = open(report_filename)
    csv_reader = csv.DictReader(csv_fd)
    csv_words = {}
    rownum = 0
    for csv_row in csv_reader:
        rownum += 1
        if not gui.one_line_progress_meter('Loading report', rownum, csv_numlines, key='progress'):
            break
        word = csv_row['Word']
        classif = csv_row['Classification']
        context = csv_row['ProblemValueWindow']
        offset = csv_row['Offset']
        filename = csv_row['Resource']
        word_dict = { 'word': word,
            'classif': classif,
            'context': context,
            'offset': offset,
            'filename': os.path.join(root_dir, filename) }
        if word not in csv_words:
            csv_words[word] = [ word_dict ]
        else:
            csv_words[word].append(word_dict)
    csv_fd.close()
    gui.one_line_progress_meter_cancel(key='progress')
    return csv_words


def load_SR(path):
    """ Load a DICOM SR and extract the text.
    Removes any tag strings inside [[Tag]] lines.
    """
    sr = DicomText.DicomText(path)
    sr.parse()
    text = sr.text()
    text = re.sub(r'\[\[.*\]\].*\n', '', text)
    logging.debug('Loaded %s to get "%s"' % (path, text))
    return text


def word_to_gui_label(word):
    """ Given a word return a string for the combo box,
    which includes a count of how many documents contained that word.
    """
    return '%6d: %s' % (len(csv_words[word]), word)

def gui_label_to_word(word):
    """ Given the word as displayed in the combo box,
    convert it back to the raw word.
    """
    return re.sub('^ *[0-9]*: ', '', word)

def find_path_given_filename(word, filename):
    """ Given a word and a filename, return the full file path.
    XXX uses [0] because the generator returns a list but there should only be one result.
    """
    for f in csv_words[word]:
        if os.path.basename(f['filename']) == filename:
            return f['filename']
    # SLOWER: return [f['filename'] for f in csv_words[word] if os.path.basename(f['filename']) == filename][0]

def find_index_of_path_given_filename(word, filename):
    """ Given a word and a filename, return the index in the list of the full file path.
    """
    idx = -1
    for f in csv_words[word]:
        idx += 1
        if os.path.basename(f['filename']) == filename:
            break
    return idx

def create_gui(csv_words):
    """ Create the GUI window and return the window object
    """
    list_of_words_with_counts = sorted([
        word_to_gui_label(word)
        for word in list(csv_words.keys())
    ])
    gui_layout = [
        [gui.Text("Review SR Reports")],
        [gui.Combo(list_of_words_with_counts, size=(80,1), key='Word', enable_events=True)],
        [gui.Combo([''], size=(80,1), key='Files', enable_events=True)],
        [gui.Multiline("", size=(80,15), key='Output')],
        #[gui.Button('Select word'), gui.Button('Load')], # not needed
        [gui.Button('Mark as False Positive', button_color=good_button_colour),
            gui.Button('Reviewed', button_color=other_button_colour),
            gui.Button('Mark as PII', button_color=bad_button_colour)],
        [gui.Button('Quit', button_color=default_button_colour)]
    ]

    gui_window = gui.Window('Reviewer', gui_layout)
    return gui_window


def run_gui(gui_window):
    """ Run the GUI given the main window object
    """
    good_list = []
    other_list = []
    bad_list = []
    try:
        while True:
            event, values = gui_window.read()
            if event == gui.WINDOW_CLOSED or event == 'Quit':
                break
            if event == 'Select word' or event == 'Word':
                logging.debug('load: %s' % gui_window['Word'])
                word = gui_label_to_word(values['Word'])
                if word not in csv_words:
                    gui.Popup('ERROR: word not found in input file: %s' % word)
                gui_window['Files'].update(values=[os.path.basename(f['filename']) for f in csv_words[word]])
            if event == 'Load' or event == 'Files':
                word = gui_label_to_word(values['Word'])
                filepath = find_path_given_filename(word, values['Files'])
                text = filepath + '\n\n' + load_SR(filepath)
                parts = re.split(word, text)
                gui_window['Output'].update('')
                for part in parts[:-1]:
                    gui_window['Output'].update(part, append=True)
                    gui_window['Output'].update(word, append=True, text_color_for_value=bad_text_colour) # no need to set background_color_for_value
                gui_window['Output'].update(parts[-1], append=True)
                # restore button colours
                gui_window['Mark as False Positive'].update(button_color=good_button_colour)
                gui_window['Mark as PII'].update(button_color=bad_button_colour)
            if event == 'Mark as False Positive':
                word = gui_label_to_word(values['Word'])
                filepath = find_path_given_filename(word, values['Files'])
                good_list.append((word,filepath))
                write_csv(good_list_filename, [(word,filepath)])
                gui_window['Mark as False Positive'].update(button_color=default_button_colour)
            if event == 'Mark as PII':
                word = gui_label_to_word(values['Word'])
                filepath = find_path_given_filename(word, values['Files'])
                bad_list.append((word,filepath))
                write_csv(bad_list_filename, [(word,filepath)])
                gui_window['Mark as PII'].update(button_color=default_button_colour)
            if event == 'Reviewed':
                word = gui_label_to_word(values['Word'])
                filepath = find_path_given_filename(word, values['Files'])
                other_list.append((word,filepath))
                write_csv(other_list_filename, [(word,filepath)])
                gui_window['Reviewed'].update(button_color=default_button_colour)
            logging.debug('event: %s' % event)
            logging.debug('values: %s' % values)
    except Exception as e:
        if 'popup_error_with_traceback' in dir(gui):
            # This doesn't exist in the Qt version
            gui.popup_error_with_traceback('ERROR: exception:', e)
        else:
            raise
    # Write marked files just before exit?
    #if len(good_list):
    #    write_csv(good_list_filename, good_list)
    #if len(other_list):
    #    write_csv(other_list_filename, other_list)
    #if len(bad_list):
    #    write_csv(bad_list_filename, bad_list)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reviewer')
    parser.add_argument('-d', '--debug', action="store_true", help='Debug')
    parser.add_argument('-r', '--report', action="store", help="Report filename (default %s)" % report_filename)
    parser.add_argument('-f', '--files', action="store", help="Directory containing DICOM files (default %s)" % root_dir)
    args = parser.parse_args()
    if args.report:
        report_filename = args.report
    if args.files:
        root_dir = args.files
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    csv_words = load_report(report_filename, root_dir = root_dir)
    win = create_gui(csv_words)
    run_gui(win)
