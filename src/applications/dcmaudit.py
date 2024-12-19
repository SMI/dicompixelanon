#!/usr/bin/env python3
#
# Simple GUI to assist in looking for text (especially PII) in DICOM images
# and drawing rectangles to redact regions.
#
# sample files in src/SmiServices/tests/common/Smi.Common.Tests/TestData/
# gdcmConformanceTests:
#  ~/src/dicom/gdcm/gdcmConformanceTests/CT_OSIRIX_OddOverlay.dcm (1 overlay)
#  ~/src/dicom/gdcm/gdcmConformanceTests/XA_GE_JPEG_02_with_Overlays.dcm (8 overlays in high bits)
#  ~/src/dicom/gdcm/gdcmData/PHILIPS_Brilliance_ExtraBytesInOverlay.dcm (1 overlay)

# Requirements:
#   pydal pydicom pylibjpeg pylibjpeg-libjpeg Pillow tkinter # python3-tk.deb
#   pytesseract
# Dependencies:
#   numpy
#   maptplotlib cycler fonttools kiwisolver packaging pyparsing python-dateutil six
#   tesseract-ocr

from PIL import Image
from PIL import ImageTk
from PIL import ImageDraw
from PIL.ImageOps import equalize, invert
import argparse
import boto3
import csv
import logging
import random
import numpy as np
import os
import sys
import traceback
from threading import Thread
import tkinter
import tkinter.filedialog
import tkinter.messagebox
import tkinter.simpledialog
from tkinter.ttk import Progressbar
from tktooltip import ToolTip
import pytesseract
from DicomPixelAnon.filelist import FileList
from DicomPixelAnon.dicomrectdb import DicomRectDB
from DicomPixelAnon.rect import Rect, DicomRect, add_Rect_to_list
from DicomPixelAnon.ocrengine import OCR
from DicomPixelAnon.dicomimage import DicomImage
from DicomPixelAnon import deidrules
from DicomPixelAnon import ultrasound
from DicomPixelAnon.s3url import s3url_create, s3url_is, s3url_sanitise
from dcmaudit_s3 import S3CredentialStore


# Configuration:
DEFAULT_S3_ENDPOINT = 'http://127.0.0.1:7070/' # nsh-fs02:7070
NUM_RANDOM_S3_IMAGES = 10
MAX_S3_LOAD = 10000    # max to load from S3 if not limited by study/series
TTD=0.4                # delay in seconds before ToolTip is shown


# =====================================================================
# Allow a thread to return a value. Use like this:
# thr = ThreadWithReturn(target=my_func, args=(None,))
# thr.start()
# rc = thr.join()
class ThreadWithReturn(Thread):
    """ A Thread class which returns a value.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._return = None
    
    def run(self):
        target = getattr(self, '_target')
        if target is not None:
            self._return = target(
                *getattr(self, '_args'),
                **getattr(self, '_kwargs')
            )
    
    def join(self, *args, **kwargs):
        super().join(*args, **kwargs)
        return self._return


# =====================================================================
class GridEntryDialog(tkinter.simpledialog.Dialog):
    """ A custom Tkinter dialog box to display a set of items in a grid
    as rows of label: text where text is editable, not so the user can
    edit the text but so that they can scroll inside and copy/paste out.
    itemlist should be a list of (label,text) tuples or dicts.
    """
    def __init__(self, parent, itemlist):
        self.itemlist = itemlist
        super().__init__(parent)

    def body(self, parent):
        for idx in range(len(self.itemlist)):
            item = self.itemlist[idx]
            if isinstance(item, dict):
                label = item['label']
                text  = item['text']
            else:
                label = item[0]
                text  = item[1]
            tkinter.Label(parent, text=label).grid(row=idx, column=0)
            e = tkinter.Entry(parent)
            e.insert(0, text)
            e.grid(row=idx, column=1)

    def apply(self):
        pass


# =====================================================================
class S3CredentialsDialog:
    """ Pop up a dialogue box for managing S3 credentials
    cached in a hidden file in the home directory:
    ~/.s3cred.csv contains 3 columns name,access,secret.
    """

    def __init__(self, parent):
        # Initialise class variables
        self.access = self.secret = None
        self.endpoint = DEFAULT_S3_ENDPOINT
        # Read the stored credentials
        # Add an empty one so there's at least one item
        cred_store = S3CredentialStore()
        cred_list = cred_store.read_creds()
        cred_names = list(cred_list.keys())
        options = cred_names if len(cred_names) else ['---']
        # Construct GUI
        top = self.top = tkinter.Toplevel(parent)
        top.geometry(f'+{max(0,parent.winfo_rootx()-20)}+{parent.winfo_rooty()}')
        tkinter.Label(top, text='Saved credentials:').grid(row=0, column=0)
        #self.myLabel.pack() instead of pack()ing every widget we use grid(row,column)
        self.bucket_dropdown = tkinter.StringVar()
        def pick(xx):
            chose = self.bucket_dropdown.get()
            if chose == '---':
                return
            (acc,sec,srv) = cred_store.read_cred(chose)
            self.serverEntry.delete(0, tkinter.END)
            self.serverEntry.insert(0, srv)
            self.accessEntry.delete(0, tkinter.END)
            self.accessEntry.insert(0, acc)
            self.secretEntry.delete(0, tkinter.END)
            self.secretEntry.insert(0, sec)
            self.bucketEntry.delete(0, tkinter.END)
            self.bucketEntry.insert(0, chose)
        self.bucketMenu = tkinter.OptionMenu(top, self.bucket_dropdown, *options, command = pick)
        ToolTip(self.bucketMenu, msg="Select from a set of saved credentials", delay=TTD)
        self.bucketMenu.grid(row=0, column=1)
        tkinter.Label(top, text='Server:').grid(row=1, column=0)
        self.serverEntry = tkinter.Entry(top)
        self.serverEntry.insert(0, DEFAULT_S3_ENDPOINT)
        ToolTip(self.serverEntry, msg="Enter the web address of the bucket server", delay=TTD)
        self.serverEntry.grid(row=1, column=1)
        tkinter.Label(top, text='Access key:').grid(row=2, column=0)
        self.accessEntry = tkinter.Entry(top)
        ToolTip(self.accessEntry, msg="Enter the access key you were given for the bucket. An empty key will remove the named bucket from the list.", delay=TTD)
        self.accessEntry.grid(row=2, column=1)
        tkinter.Label(top, text='Secret key:').grid(row=3, column=0)
        self.secretEntry = tkinter.Entry(top)
        ToolTip(self.secretEntry, msg="Enter the secret key you were given for the bucket", delay=TTD)
        self.secretEntry.grid(row=3, column=1)
        tkinter.Label(top, text='Bucket name:').grid(row=4, column=0)
        self.bucketEntry = tkinter.Entry(top)
        ToolTip(self.bucketEntry, msg="Enter the name of the bucket exactly as given when you were provided access", delay=TTD)
        self.bucketEntry.grid(row=4, column=1)
        self.mySubmitButton = tkinter.Button(top, text='Save', command=self.save)
        ToolTip(self.mySubmitButton, msg="The credentials will be saved under the name you have selected for the bucket", delay=TTD)
        self.mySubmitButton.grid(row=5, column=1)

    def save(self):
        self.access = self.accessEntry.get()
        self.secret = self.secretEntry.get()
        self.bucketname = self.bucketEntry.get()
        self.endpoint = self.serverEntry.get()
        if self.bucketname:
            cred_store = S3CredentialStore()
            cred_store.add_cred(self.bucketname, self.access, self.secret, self.endpoint)
            if self.access and self.secret and self.bucketname:
                try:
                    logging.debug('Logging into S3 at %s with %s:%s' % (self.endpoint, self.access, self.secret))
                    s3 = boto3.resource('s3',
                        endpoint_url=self.endpoint,
                        aws_access_key_id=self.access, aws_secret_access_key=self.secret)
                    s3.meta.client.head_bucket(Bucket = self.bucketname)
                except:
                    tkinter.messagebox.showerror(title="Error", message="Cannot connect to the S3 server, check the bucket name, endpoint URL and the credentials")
                    return
        self.top.destroy()


# =====================================================================

class S3LoadDialog:
    def __init__(self, parent, s3loadprefs = None):
        # Initialise class variables
        self.bucket = None
        self.access = self.secret = None
        self.random = False
        self.csv_file = None
        self.study_list = []
        self.series_list = []
        self.output_dir = None
        self.path_list = []
        if s3loadprefs:
            self.output_dir = s3loadprefs.output_dir
            self.csv_file_dir = s3loadprefs.csv_file_dir
        else:
            self.csv_file_dir = '.'
        # Read the stored credentials
        cred_store = S3CredentialStore()
        cred_list = cred_store.read_creds()
        cred_names = list(cred_list.keys())
        if not cred_names:
            tkinter.messagebox.showerror(title="No credentials",
                message='Please use the credential manager to save some credentials')
            return
        # Construct GUI
        top = self.top = tkinter.Toplevel(parent)
        top.geometry(f'+{max(0,parent.winfo_rootx()-20)}+{parent.winfo_rooty()}')
        tkinter.Label(top, text='Saved credentials:').grid(row=0, column=0)
        self.bucket_dropdown = tkinter.StringVar()
        def pick(xx):
            self.bucket = self.bucket_dropdown.get()
            (self.access, self.secret, self.endpoint) = cred_store.read_cred(self.bucket)
        self.bucketMenu = tkinter.OptionMenu(top, self.bucket_dropdown, *cred_names, command = pick)
        ToolTip(self.bucketMenu, msg="Select the name of the bucket where the files are stored", delay=TTD)
        self.bucketMenu.grid(row=0, column=1)
        # Random sample
        tkinter.Label(top, text='Random sample:').grid(row=1, column=0)
        self.randomVar = tkinter.IntVar()
        self.randomCheck = tkinter.Checkbutton(top, text='Random',variable=self.randomVar, onvalue=1, offvalue=0) # command=<func>
        ToolTip(self.randomCheck, msg=f"If selected then {NUM_RANDOM_S3_IMAGES} will be selected randomly from the CSV file", delay=TTD)
        self.randomCheck.grid(row=1, column=1)
        # CSV file
        #tkinter.Label(top, text='CSV file (optional):').grid(row=2, column=0)
        def showFileChooser():
            self.csv_file = tkinter.filedialog.askopenfilename(parent=top, title='CSV file (optional)',
                initialdir=self.csv_file_dir,
                #initialfile='',
                filetypes=[('csv','*.csv'), ('CSV', '*.CSV')]
                )
            if not self.csv_file:
                return
            self.csvEntry.delete(0, tkinter.END)
            self.csvEntry.insert(0, self.csv_file)
            self.csv_file_dir = os.path.dirname(self.csv_file)
        tkinter.Button(top, text='CSV file (optional)', command=showFileChooser).grid(row=2, column=0)
        self.csvEntry = tkinter.Entry(top)
        ToolTip(self.csvEntry, msg="A CSV file can be used to lookup Study numbers given Series numbers, or for random sampling", delay=TTD)
        self.csvEntry.grid(row=2, column=1)
        tkinter.Label(top, text='Study Ids:').grid(row=3, column=0)
        self.studyEntry = tkinter.Entry(top)
        ToolTip(self.studyEntry, msg="Enter one (or more, comma separated) Study numbers, or leave blank if random sampling", delay=TTD)
        self.studyEntry.grid(row=3, column=1)
        tkinter.Label(top, text='Series Ids:').grid(row=4, column=0)
        self.seriesEntry = tkinter.Entry(top)
        ToolTip(self.seriesEntry, msg="Enter one (or more, comma separated) Series numbers, or leave blank for all Series in a Study", delay=TTD)
        self.seriesEntry.grid(row=4, column=1)
        tkinter.Label(top, text='Output directory:').grid(row=5, column=0)
        self.outputEntry = tkinter.Entry(top)
        ToolTip(self.outputEntry, msg="Leave blank to load the images straight into the viewer without saving as a file, or enter an output directory. You can add {study} and {series} to directory names. Directories will be created as necessary.", delay=TTD)
        self.outputEntry.grid(row=5, column=1)
        self.mySubmitButton = tkinter.Button(top, text='Load', command=self.load)
        self.mySubmitButton.grid(row=6, column=1)
        ToolTip(self.mySubmitButton, msg="Download the images (and save as files, if output directory specified) and load into the viewer", delay=TTD)

    def load(self):
        # Save preferences for next time XXX needs s3loadprefs passed
        #if s3loadprefs:
        #    s3loadprefs.output_dir = self.output_dir
        #    s3loadprefs.csv_file_dir = self.csv_file_dir
        if not self.access or not self.secret:
            tkinter.messagebox.showerror(title="Error", message='Please select some credentials')
            return
        self.random = True if self.randomVar.get() else False
        self.study_list = self.studyEntry.get().split(',') if self.studyEntry.get() else []
        self.series_list = self.seriesEntry.get().split(',') if self.seriesEntry.get() else []
        self.output_dir = self.outputEntry.get()
        self.csv_file = self.csvEntry.get()
        # Sanity checks
        if self.random and not self.csv_file:
            tkinter.messagebox.showerror(title="Error", message="Please supply a CSV to use random sampling")
            return
        if self.series_list and not self.study_list and not self.csv_file:
            tkinter.messagebox.showerror(title="Error", message="Cannot download a Series without a Study unless a CSV file is given")
            return
        if not self.study_list and not self.series_list and not self.csv_file:
            tkinter.messagebox.showerror(title="Error", message="Cannot download all Studies unless a CSV file is given")
            return
        if len(self.study_list)>1 and (len(self.study_list) != len(self.series_list)):
            tkinter.messagebox.showerror(title="Error", message="Not sure what you mean by multiple Study AND multiple Series")
            return
        # If a study but no series then either (a) look in csv, or (b) load all series by doing S3 ls
        # If a series but not study then need CSV to find study
        # If a study and series are supplied then load it
        # If output directory given then write there, else load direct into memory
        #
        s3prefix_list = set()

        # If same number of study and series then combine them
        if len(self.study_list)>1 and (len(self.study_list) == len(self.series_list)):
            s3prefix_list.update([ f'{stu}/{ser}' for (stu,ser) in zip(self.study_list, self.series_list)])

        # Open CSV file
        csvr = None
        if self.csv_file:
            print('Opening CSV file %s' % self.csv_file)
            fd = open(self.csv_file)
            csvr = csv.DictReader(fd)
            if 'StudyInstanceUID' not in csvr.fieldnames or 'SeriesInstanceUID' not in csvr.fieldnames:
                tkinter.messagebox.showerror(title="Error", message="The CSV file does not have columns called StudyInstanceUID and SeriesInstanceUID")
                return
            #if 'SOPInstanceUID' in csvr.fieldnames:
            #    tkinter.messagebox.showerror(title="Error", message="The CSV file has a column called SOPInstanceUID which means multiple instances of Study+Series so queries may not work well; please try a CSV file reduced to only Study and Series")
            csvr.fd = fd # keep for later

        # Random: read CSV and select random rows
        if self.random:
            print('Reading CSV file')
            numrows = 0
            for row in csvr:
                numrows += 1
            # Rewind and skip header row
            csvr.fd.seek(0)
            next(csvr.fd)
            # Pick ten random rows
            rownum_list = [random.randint(0,numrows-1) for n in range(NUM_RANDOM_S3_IMAGES)]
            while numrows > 0:
                row = next(csvr)
                if numrows in rownum_list:
                    s3prefix_list.add('%s/%s/' % (row['StudyInstanceUID'], row['SeriesInstanceUID']))
                numrows -= 1

        # If we don't have Study or Series then read all
        if not self.study_list and not self.series_list:
            numrows = 0
            for row in csvr:
                s3prefix_list.add('%s/%s/' % (row['StudyInstanceUID'], row['SeriesInstanceUID']))
                numrows += 1
                if numrows > MAX_S3_LOAD:
                    tkinter.messagebox.showerror(title="Error", message=f"Limited to {MAX_S3_LOAD}")
                    break

        # If we only have series we need CSV to get study
        if self.series_list and not self.study_list:
            numrows = 0
            for row in csvr:
                if row['SeriesInstanceUID'] in self.series_list:
                    s3prefix_list.add('%s/%s/' % (row['StudyInstanceUID'], row['SeriesInstanceUID']))
                    numrows += 1
                    if numrows > MAX_S3_LOAD:
                        tkinter.messagebox.showerror(title="Error", message=f"Limited to {MAX_S3_LOAD}")
                        break

        # If we only have study we need to iterate, or we can use CSV to get series
        if self.study_list and not self.series_list:
            if csvr:
                numrows = 0
                for row in csvr:
                    if row['StudyInstanceUID'] in self.study_list:
                        s3prefix_list.add('%s/%s/' % (row['StudyInstanceUID'], row['SeriesInstanceUID']))
                        numrows += 1
                        if numrows > MAX_S3_LOAD:
                            tkinter.messagebox.showerror(title="Error", message=f"Limited to {MAX_S3_LOAD}")
                            break
            else:
                s3prefix_list.update(['%s/'%s for s in self.study_list])

        print('Try a list of prefix:')
        for pfx in s3prefix_list:
            print('  %s' % pfx)

        # Finished with CSV file now
        if csvr:
            csvr.fd.close()

        # Connect to S3 service
        logging.debug('Logging into S3 at %s with %s:%s' % (self.endpoint, self.access, self.secret))
        try:
            s3 = boto3.resource('s3',
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access, aws_secret_access_key=self.secret)
        except:
            tkinter.messagebox.showerror(title="Error", message="Cannot connect to the S3 server, check the endpoint URL and the credentials in the credential manager")
            return

        # Select the bucket given by the credential name
        s3bucket = s3.Bucket(name=self.bucket)

        # Format output path which can include {study} {series}
        # If a relative path is given then prefix it with our HOME directory
        if self.output_dir:
            if not (self.output_dir[0]=='/' or self.output_dir=='~' or self.output_dir=='$'):
                self.output_dir = os.environ.get('HOME','.')
            if not '{' in self.output_dir:
                self.output_dir += '/{study}/{series}/{file}'
            #if not '{file}' in self.output_dir:
            #    self.output_dir += '/{file}'
            logging.debug('Files will be saved in\n%s' % self.output_dir)

        # List bucket and download files, creating directories as necessary
        self.path_list = []
        def get_obj(obj):
            (stu,ser,sop) = obj.key.split('/')
            path = self.output_dir.format(study=stu, series=ser, file=sop)
            logging.debug(f"{obj.key}\t{obj.size}\t{obj.last_modified}\t->\t{path}")
            if self.output_dir:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                s3bucket.download_file(obj.key, path)
                self.path_list.append(path)
            else:
                self.path_list.append(s3url_create(self.access, self.secret, self.endpoint, self.bucket, obj.key))
        for s3prefix in s3prefix_list:
            for obj in s3bucket.objects.filter(Prefix = s3prefix):
                # Expecting Study/Series/SOP but if we only get Study/Series
                # then need to do an additional 'ls' inside the Series
                # (typically if Series is a symlink):
                key_parts = obj.key.split('/')
                if len(key_parts)==2:
                    for obj2 in s3bucket.objects.filter(Prefix = '%s/' % obj.key):
                        get_obj(obj2)
                else:
                    get_obj(obj)

        self.top.destroy()


# =====================================================================
class App:
    """ The class responsible for the Tk GUI
    """
    # Class members and enums
    (
        DRAG_NONE,
        DRAG_TL, DRAG_T, DRAG_TR,
        DRAG_L,  DRAG_C, DRAG_R,
        DRAG_BL, DRAG_B, DRAG_BR
    ) = list(range(10))
    (
        RC_QUIT,
        RC_NEXTFRAME,
        RC_FFWD,
        RC_NEXTIMAGE,
        RC_DONEIMAGE,
        RC_PREVIMAGE,
    ) = list(range(6))
    cursor_map = {
        DRAG_TL: 'top_left_corner',
        DRAG_L:  'left_side',
        DRAG_BL: 'bottom_left_corner',
        DRAG_TR: 'top_right_corner',
        DRAG_R:  'right_side',
        DRAG_BR: 'bottom_right_corner',
        DRAG_T:  'top_side',
        DRAG_B:  'bottom_side',
        DRAG_C:  'fleur'}
    redact_colour = 0xff # white
    outline_colour = 0xff # white
    deid_rect_colour = 'green' # deid rules
    us_rect_colour = 'yellow'  # ultrasound regions


    def __init__(self):
        """ GUI constructor
        """

        # GUI
        self.tk_app = tkinter.Tk()
        self.tk_app.wm_title(("dcmaudit"))
        self.tk_app.wm_iconname(("dcmaudit"))
        self.tk_app.wm_protocol('WM_DELETE_WINDOW', self.quit)

        # Settings (have to be set after creating root window)
        self.skip_marked_files = tkinter.BooleanVar(value = True)
        self.skip_untagged_files = tkinter.BooleanVar(value = False)
        self.highlight_rects = tkinter.BooleanVar(value = False)
        self.highlight_suggested_rects = tkinter.BooleanVar(value = True)
        self.highlight_deid_rects = tkinter.BooleanVar(value = False)
        self.highlight_ultrasound_rects = tkinter.BooleanVar(value = False)
        self.redact_deid_rects = tkinter.BooleanVar(value = True)
        self.redact_us_rects = tkinter.BooleanVar(value = False)
        self.starting_directory = os.environ.get('PACS_ROOT', '.')

        # Main window contains an image
        self.app_image = tkinter.Label(self.tk_app)
        self.app_image.pack(side="bottom")
        self.app_image.bind("<Button-1>", self.press_event)
        self.app_image.bind("<Button1-Motion>", self.motion_event)
        self.app_image.bind("<Motion>", self.idle_motion_event)
        self.app_image.bind("<ButtonRelease-1>", self.release_event)
        self.app_image.bind("<Enter>", self.enter_event)
        self.app_image.bind("<Leave>", self.leave_event)
        self.app_image.bind("<Button1-Enter>", "#nothing")
        self.app_image.bind("<Button1-Leave>", "#nothing")
        self.app_image.bind("<ButtonRelease-2>", self.apply_possible_rect_event)
        self.app_image.bind("<ButtonRelease-3>", self.apply_possible_rect_event)
        #self.app_image.bind("<Configure>", self.on_resize)

        # Main window keyboard shortcuts
        #  Grab keyboard focus if needed
        #self.tk_app.focus_force()
        #self.tk_app.bind("<Return>", self.done_file_event)
        self.tk_app.bind("<Escape>", self.escape_file_event)
        self.tk_app.bind("<Shift-Escape>", self.prev_file_event)
        self.tk_app.bind("<t>", self.tag_file_event)
        self.tk_app.bind("<c>", self.text_entry_event)
        self.tk_app.bind("<n>", self.next_frame_event)
        self.tk_app.bind("<N>", self.done_file_event)
        self.tk_app.bind("<p>", self.prev_frame_event)
        self.tk_app.bind("<P>", self.prev_file_event)
        self.tk_app.bind("<f>", self.ffwd_frame_event)
        self.tk_app.bind("<i>", self.info_file_event)
        self.tk_app.bind("<minus>", self.display_without_rects)
        self.tk_app.bind("<plus>", self.display_with_rects)
        self.tk_app.bind("<o>", self.ocr_frame_event)
        self.tk_app.bind("<r>", self.redact_event)
        self.tk_app.bind("<A>", self.apply_all_possible_rects_event)
        self.tk_app.bind("<q>", self.quit_event)
        self.tk_app.bind("<Z>", self.undo_file_event)
        self.tk_app.bind("?", self.help_button_pressed)
        self.tk_app.bind("<Control-o>", self.open_files_event)
        self.tk_app.bind("<Control-d>", self.open_directory_event)
        self.tk_app.bind("<Control-3>", self.manage_s3_event)
        self.tk_app.bind("<Control-s>", self.open_s3_event)

        # Internal settings
        self.render_flag = False # indicate that window should be rendered at next idle time
        self.wait_flag = tkinter.IntVar(self.tk_app) # effectively the return code -1=exit 0=cancel 1=done image

        # Add buttons (can have multiple, exactly like this)
        self.menu_button = tkinter.Menubutton(self.tk_app, text="Menu")
        self.menu_button.pack(side="left")
        self.menu = tkinter.Menu(self.menu_button)
        self.menu_button.config(menu=self.menu)
        # Add a help option as the first menu item
        self.menu.add_command(label='Help [?]', command=lambda: self.help_button_pressed(None))
        # Create the Open menu as the second menu item
        self.openmenu = tkinter.Menu(self.menu)
        self.menu.add_cascade(label = 'File', menu = self.openmenu)
        self.openmenu.add_command(label='Open files', accelerator='Ctrl+O', command=lambda: self.open_files_event(None))
        self.openmenu.add_command(label='Open directory', accelerator='Ctrl+D', command=lambda: self.open_directory_event(None, False))
        self.openmenu.add_command(label='Open directory recursive', command=lambda: self.open_directory_event(None, True))
        self.openmenu.add_separator()
        self.openmenu.add_command(label='Manage S3 credentials', accelerator='Ctrl+3', command=lambda: self.manage_s3_event(None))
        self.openmenu.add_command(label='Open files from S3', accelerator='Ctrl+S', command=lambda: self.open_s3_event(None))
        self.openmenu.add_separator()
        self.openmenu.add_command(label='Choose database directory', command=lambda: self.open_db_directory_event(None))
        self.openmenu.add_command(label='Export database of rectangles as CSV', command=lambda: self.save_db_csv_event(None, rects=True, tags=False))
        self.openmenu.add_command(label='Export database of tagged files as CSV', command=lambda: self.save_db_csv_event(None, rects=False, tags=True))
        # Create an Options menu
        self.optmenu = tkinter.Menu(self.menu)
        self.menu.add_cascade(label = 'Options', menu = self.optmenu)
        self.optmenu.add_checkbutton(label = 'Ignore files already marked as done', variable = self.skip_marked_files, onvalue = True, offvalue = False)
        self.optmenu.add_checkbutton(label = 'Only view files which have been tagged', variable = self.skip_untagged_files, onvalue = True, offvalue = False)
        self.optmenu.add_separator()
        self.optmenu.add_checkbutton(label = 'Redact deid-rules regions', variable = self.redact_deid_rects, onvalue = True, offvalue = False)
        self.optmenu.add_checkbutton(label = 'Redact ultrasound regions (DICOM tags)', variable = self.redact_us_rects, onvalue = True, offvalue = False)
        self.optmenu.add_separator()
        self.optmenu.add_checkbutton(label = 'Highlight redacted rectangles (database)', variable = self.highlight_rects, onvalue = True, offvalue = False)
        self.optmenu.add_checkbutton(label = 'Highlight suggested rectangles (similar images)', variable = self.highlight_suggested_rects, onvalue = True, offvalue = False)
        self.optmenu.add_checkbutton(label = 'Highlight deid-rules rectangles', variable = self.highlight_deid_rects, onvalue = True, offvalue = False)
        self.optmenu.add_checkbutton(label = 'Highlight ultrasound rectangles (DICOM tags)', variable = self.highlight_ultrasound_rects, onvalue = True, offvalue = False)
        # Add other top-level menu items
        self.menu.add_command(label='Redact [r] the chosen rect', command=lambda: self.redact_event(None))
        self.menu.add_command(label='Info [i]', command=lambda: self.info_file_event(None))
        self.menu.add_command(label='OCR frame [o]', command=lambda: self.ocr_frame_event(None))
        self.menu.add_command(label='Display redacted [+]', command=lambda: self.display_with_rects(None))
        self.menu.add_command(label='Display unredacted [-]', command=lambda: self.display_without_rects(None))
        self.menu.add_command(label='Apply all suggested rects [A]', command=lambda: self.apply_all_possible_rects_event(None))
        self.menu.add_command(label='Next frame [n]', command=lambda: self.next_frame_event(None))
        self.menu.add_command(label='Fast forward frames [f]', command=lambda: self.ffwd_frame_event(None))
        self.menu.add_command(label='Previous frame [p]', command=lambda: self.prev_frame_event(None))
        self.menu.add_command(label='Mark done; Next file [N]', command=lambda: self.done_file_event(None))
        self.menu.add_command(label='Next file [Esc]', command=lambda: self.escape_file_event(None))
        self.menu.add_command(label='Prev file [P]', command=lambda: self.prev_file_event(None))
        self.menu.add_command(label='Tag file [t]', command=lambda: self.tag_file_event(None))
        self.menu.add_command(label='Comment on file [c]', command=lambda: self.text_entry_event(None))
        self.menu.add_command(label='Undo file [Z]', command=lambda: self.undo_file_event(None))
        self.menu.add_command(label='Quit [q]', command=lambda: self.quit_event(None))

        self.info_label = tkinter.Label(self.tk_app, justify="left")
        self.info_label.pack(side="left")

        # Screen size
        self.screen_height_max = self.tk_app.winfo_screenheight() - 64 - 32 - 32
        self.screen_width_max  = self.tk_app.winfo_screenwidth() - 64
        # Image
        self.image = None    # the full-size image
        self.image_scale = 1 # if larger than screen then scale down 
        # Active rectangle
        self.rect_l = self.rect_r = self.rect_t = self.rect_b = 0
        self.show_handles = True
        # Engines
        self.ocr_easy_loader_thread = ThreadWithReturn(target = self.ocr_easy_loader, args=())
        self.ocr_tess_loader_thread = ThreadWithReturn(target = self.ocr_tess_loader, args=())
        self.ocr_easy_loader_thread.start()
        self.ocr_tess_loader_thread.start()
        # Make initial window bigger
        self.tkimage = ImageTk.PhotoImage(Image.new('L', (640,480)))
        self.app_image.configure(image=self.tkimage)



    def ocr_easy_loader(self):
        """ This is called in a thread """
        return OCR(engine = 'easyocr')

    def ocr_tess_loader(self):
        """ This is called in a thread """
        return OCR(engine = 'tesseract')

    # Properties
    @property
    def image(self):
        return self._image
    @image.setter
    def image(self, value):
        self._image = value

    # Properties which return the value of the Thread when it's finished.
    @property
    def ocr_easy(self):
        return self.ocr_easy_loader_thread.join()
    @property
    def ocr_tess(self):
        return self.ocr_tess_loader_thread.join()

    def set_skip_marked_files(self, newval):
        """ Manully set this option.
        NB this is not called when menu is used. """
        self.skip_marked_files.set(newval)
        logging.debug('skip_marked_files = %s' % self.skip_marked_files.get())

    def set_skip_untagged_files(self, newval):
        """ Manully set this option.
        NB this is not called when menu is used. """
        self.skip_untagged_files.set(newval)
        logging.debug('skip_untagged_files = %s' % self.skip_untagged_files.get())

    # User interface events

    def open_files_event(self, event):
        """ Pop up a file dialog box asking for one or more files.
        Start in same directory as last time it was used.
        Clears the existing list and adds these file to list.
        Can be a CSV file, or even a database (not the same database
        as the one which will be used to record new tags/rectangles).
        """
        filenames = tkinter.filedialog.askopenfilenames(title='Select files', initialdir=self.starting_directory, multiple=True)
        if not filenames:
            return
        self.starting_directory = os.path.dirname(os.path.abspath(filenames[0]))
        dicomfilelist = self.construct_FileList(list(filenames))
        # Any of the selected files can be a CSV file which will be read
        # and the filename or DicomFilePath column will be added to the list
        self.set_image_list(dicomfilelist)
        self.load_next_file()

    def open_directory_event(self, event, recursive = False):
        """ Pop up a file dialog box asking for a directory.
        Start in same directory as last time it was used.
        Clears the existing list and add all these files to list.
        Option to add all files recursively.
        """
        directory = tkinter.filedialog.askdirectory(title='Select directory', initialdir=self.starting_directory)
        if not directory:
            return
        self.starting_directory = directory
        if recursive:
            filenames = [os.path.join(dirpath,f) for (dirpath, dirnames, filenames) in os.walk(directory) for f in filenames]
        else:
            filenames = [os.path.join(directory,f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        self.set_image_list(FileList(filenames))
        self.load_next_file()

    def open_db_directory_event(self, event):
        """ Pop up a file dialog box asking for a directory.
        Use this as the new database directory.
        """
        directory = tkinter.filedialog.askdirectory(title='Select directory containing '+DicomRectDB.db_filename, initialdir=self.starting_directory)
        if not directory:
            return
        if not os.path.isfile(os.path.join(directory, DicomRectDB.db_filename)):
            rc = tkinter.messagebox.showerror(title="No database",
                message='That directory does not contain '+DicomRectDB.db_filename+'. '
                    'Do you want to create a new database in this directory?',
                type=tkinter.messagebox.OKCANCEL)
            if rc == 'cancel':
                return
        DicomRectDB.set_db_path(directory)



    def manage_s3_event(self, event):
        """ Only display dialogue box to edit credential store """
        root = self.tk_app
        s3cred = S3CredentialsDialog(root)
        root.wait_window(s3cred.top)

    def open_s3_event(self, event):
        """ Display dialogue box to pick a series to load,
        copies from S3, then loads them.
        """
        root = self.tk_app
        s3load = S3LoadDialog(root)
        # If dialogue box never got constructed due to error then
        # it won't have a 'top' so doesn't need to be destroyed.
        if hasattr(s3load, 'top'):
            root.wait_window(s3load.top)
        self.set_image_list(FileList(s3load.path_list))
        self.load_next_file()


    def save_db_csv_event(self, event, rects = False, tags = False):
        """ Pop up a file dialog box asking for a CSV filename.
        Start in same directory as last time it was used.
        Saves the database to the CSV file.
        """
        filename = tkinter.filedialog.asksaveasfilename(title='Select CSV filename', initialdir=self.starting_directory)
        if not filename:
            return
        self.starting_directory = os.path.dirname(os.path.abspath(filename))
        fd = open(filename, 'w', newline='')
        db = DicomRectDB()
        db.query_all_csv(fd = fd, query_rects = rects, query_tags = tags)
        fd.close()


    def tag_file_event(self, event):
        """ Toggle the tag for a file
        """
        logging.debug('Tag file')
        # Add to database
        filename = self.dcm.get_filename()
        db = DicomRectDB()
        db.toggle_tag(filename,
            metadata_dict = self.dcm.get_selected_metadata())
        self.update_info_label()

    def next_frame_event(self, event):
        logging.debug('Next Frame')
        # Simply indicate to GUI loop that user has finished this frame.
        # The image index will be incremented elsewhere.
        self.cancel()
        return

    def prev_frame_event(self, event):
        logging.debug('Prev Frame')
        # Simply indicate to GUI loop that user has finished this frame.
        # Rewind by 2 because image index will be incremented elsewhere.
        self.dcm.prev_idx()
        self.cancel()
        return

    def ffwd_frame_event(self, event):
        logging.debug('Fast-forward Frame')
        # Simply indicate to GUI loop that user has finished this frame.
        # Index will be incremented elsewhere so set up ready for that.
        self.dcm.ffwd_idx()
        self.cancel()
        return

    def ocr_frame_event(self, event):
        """ Run two types of OCR, display the results in a window, and
        add the rectangles as suggested rects onto the image.
        """
        logging.debug('OCR frame')
        # Create a popup window and put a progress bar inside it
        popup = tkinter.Toplevel()
        progressbar = Progressbar(popup, mode='determinate')
        toplevel_x = self.tk_app.winfo_x()
        toplevel_y = self.tk_app.winfo_y()
        popup.geometry("+%d+%d" % (toplevel_x + 200, toplevel_y + 200))
        progressbar.pack()
        # Start at 15% and run OCR using tesseract
        # NB. we OCR the raw_image not the displayed image, which means
        # it will always have text even after you've redacted rectangles.
        progressbar['value'] = 15
        self.tk_app.update_idletasks() # refresh progressbar
        ocr_input_image = np.array(self.raw_image.convert('L'))
        #Image.fromarray(ocr_input_image).save('text.png')
        ocr_tess_text = self.ocr_tess.image_to_text(ocr_input_image)
        # Start at 50% and run OCR using EasyOCR
        progressbar['value'] = 50
        self.tk_app.update_idletasks() # refresh progressbar
        # Could use image_to_text, but want rectangles so use _to_data
        #ocr_easy_text = self.ocr_easy.image_to_text(ocr_input_image)
        ocr_easy_data = self.ocr_easy.image_to_data(ocr_input_image)
        easy_rectlist = []
        ocr_easy_text = ''
        for item in ocr_easy_data:
            if item['conf'] > OCR.confidence_threshold:
                ocr_easy_text += item['text'] + ' '
                easy_rectlist.append(item['rect'])
                logging.debug('OCR adding %s from %s' % (item['rect'], item['text']))
        # Close the popup window and show both Tesseract and EasyOCR texts
        popup.destroy()
        msg = "Tesseract\n\n" + ocr_tess_text + "\n\nEasyOCR\n\n" + ocr_easy_text
        tkinter.messagebox.showinfo(title="Text from OCR", message=msg)
        frame, overlay = self.dcm.get_current_frame_overlay()
        for rect in easy_rectlist:
            # Convert Rect to DicomRect
            t, b, l, r = rect.get_rect()
            dicomrect = DicomRect(t, b, l, r, frame=frame, overlay=overlay)
            add_Rect_to_list(self.possible_rects, dicomrect, coalesce_similar = True)
        self.update_image(dicomrectlist = self.redacted_rects, dicomtransrectlist = self.possible_rects)
        return

    def text_entry_event(self, event=None):
        """ Ask for a comment to be added to the database for this image
        """
        filename = self.dcm.get_filename()
        db = DicomRectDB()
        marked, comment = db.query_tags(filename)
        comment = tkinter.simpledialog.askstring("Input",
            "Enter comment for this image:",
            initialvalue=comment,
            parent=self.tk_app)
        if comment:
            logging.debug('Comment file %s = \"%s\"' % (filename, comment))
            db.add_tag(filename, marked, comment,
                metadata_dict = self.dcm.get_selected_metadata())
            self.update_info_label()

    def redact_dicomrect(self, dicomrect):
        """ Add a white rectangle to the displayed image
        and call render() to show it on screen.
        """
        draw = ImageDraw.Draw(self.image)
        onscreen_rect = tuple(i // self.image_scale for i in dicomrect.ltrb())
        draw.rectangle(onscreen_rect, fill=App.redact_colour)
        self.render()

    def redact_event(self, event):
        """ Redact the currently displayed rectangle
        """
        frame, overlay = self.dcm.get_current_frame_overlay()
        filename = self.dcm.get_filename()
        dicomrect = DicomRect(top = self.rect_t,
            bottom = self.rect_b,
            left = self.rect_l,
            right = self.rect_r,
            frame = frame, overlay = overlay)
        # Add to database
        db = DicomRectDB()
        db.add_rect(filename, dicomrect)
        # Redact on image
        self.redact_dicomrect(dicomrect)

    def apply_possible_rect_event(self, event):
        """ Redact any rectangle from the list possible_rects if
        it contains the mouse coordinate in event.x,y (right-click)
        by adding the rect to the database and redacting on-screen.
        """
        # Find which rectangle contains the mouse
        mouse_x = event.x * int(self.image_scale)
        mouse_y = event.y * int(self.image_scale)
        logging.debug('Right-click at %d,%d' % (mouse_x, mouse_y))
        for dicomrect in self.possible_rects:
            if dicomrect.contains(mouse_x, mouse_y):
                # Add to database
                filename = self.dcm.get_filename()
                db = DicomRectDB()
                db.add_rect(filename, dicomrect)
                # Redact on image
                self.redact_dicomrect(dicomrect)

    def apply_all_possible_rects_event(self, event):
        """ Redact all rectangles from the list possible_rects
        by adding the rects to the database and redacting on-screen.
        """
        frame, overlay = self.dcm.get_current_frame_overlay()
        filename = self.dcm.get_filename()
        for dicomrect in self.possible_rects:
            # Add to database
            db = DicomRectDB()
            db.add_rect(filename, dicomrect)
            # Redact on image
            # (this test will always be true because only visible rects are in the list)
            if (dicomrect.F() == frame and dicomrect.O() == overlay):
                self.redact_dicomrect(dicomrect)

    def undo_file_event(self, event):
        """ Remove all database entries for the current DICOM file.
        Triggers prev_frame_event so that the current frame can be refreshed onscreen.
        """
        filename = self.dcm.get_filename()
        logging.info('Remove all DB entries for %s' % filename)
        db = DicomRectDB()
        db.remove_file(filename)
        self.prev_frame_event(None)

    def info_file_event(self, event=None):
        """ Display a dialog showing the content of some DICOM tags.
        """
        man = str(self.dcm.get_tag('Manufacturer'))
        mod = str(self.dcm.get_tag('ManufacturerModelName'))
        swv = str(self.dcm.get_tag('SoftwareVersions'))
        bia = str(self.dcm.get_tag('BurnedInAnnotation'))
        imgtype = str(self.dcm.get_tag('ImageType'))
        moda = str(self.dcm.get_tag('Modality'))
        fn = self.dcm.get_filename()
        self.dcm.debug_tags()
        GridEntryDialog(self.tk_app, [
            ("Filename:", fn),
            ("Modality:", moda),
            ("Image type:", imgtype),
            ("Manufacturer:", man),
            ("Model:", mod),
            ("Software:", swv),
            ("Burned In Annotation:", bia)
            ])

    def display_without_rects(self, event=None):
        """ Update the display without the redaction rectangles
        """
        self.update_image()

    def display_with_rects(self, event=None):
        """ Update the display with the redaction rectangles
        """
        self.update_image(dicomrectlist = self.redacted_rects, dicomtransrectlist = self.possible_rects)


    def help_button_pressed(self, event=None):
        """ Display a dialog with some help text.
        """
        message=("Keyboard actions:\n\n"
            "i = display information about this file\n"
            "+ = display image with rectangles redacted\n"
            "- = display image without rectangles redacted\n"
            "\n"
            "n = display the next frame of this image\n"
            "p = display the previous frame of this image\n"
            "f = fast-forward to the last frame of this image\n"
            "\n"
            "Esc = move to the next file (does not mark this file as 'done')\n"
            "N = move to the next file (marks this file as 'done' so you won't see it again)\n"
            "P = back to the previous file (which has not been marked as 'done')\n"
            "\n"
            "r = redact the part of the frame which the draggable rectangle is over\n"
            "A = apply (redact) all of the suggested rectangles to be redacted\n"
            "right-click = apply (redact) the suggested rectangle under the mouse\n"
            "Z = undo, remove all redaction rectables from this file\n"
            "o = OCR, find redaction rectangles by finding text in the frame\n"
            "\n"
            "t = tag this image for further investigation (see the * in the window title bar)\n"
            "c = write a comment about this file\n")
        #tkinter.messagebox.showinfo(title="Help", message=message) # ugly
        t=tkinter.Toplevel()
        t.geometry(f'+{self.tk_app.winfo_x()+20}+{self.tk_app.winfo_y()+20}')
        t.title("Help")
        tx = tkinter.Text(t)
        tx.insert(tkinter.END, message)
        tx.pack()
        tkinter.Button(t, text='OK', command=t.destroy).pack()
        return

    def press_event(self, event):
        """ Internal: mouse pressed to start a drag
        """
        self.drag_start(event.x, event.y)
        return

    def motion_event(self, event):
        """ Internal: mouse moved whilst button pressed
        """
        self.drag_continue(event.x, event.y)
        return

    def idle_motion_event(self, event):
        what = self.classify_coord_as_drag(event.x, event.y)
        if self.if_busy:
            cursor = "watch"
        else:
            cursor = self.cursor_map.get(what, "")
        self.app_image.configure(cursor=cursor)
        return

    def quit_event(self, event):
        self.quit()

    def release_event(self, event):
        self.drag_end(event.x, event.y)
        return

    def enter_event(self, event):
        self.show_handles = True
        self.render()
        return

    def leave_event(self, event):
        self.show_handles = False
        self.render()
        return

    def done_file_event(self, event):
        self.done()
        return

    def prev_file_event(self, event):
        self.prev()
        return

    def escape_file_event(self, event):
        self.next_file()

    # Functionality

    def next_file(self):
        """ Called when user wants to move to next image
        without marking the current one as done.
        """
        self.wait_flag.set(App.RC_NEXTIMAGE)

    def quit(self):
        """ Called when user actually wants to quit.
        """
        self.wait_flag.set(App.RC_QUIT)

    def cancel(self):
        """ Called when user presses Escape,
        or Previous Frame or Next Frame - simply indicates
        to the gui loop that it should exit with NEXTFRAME.
        """
        self.wait_flag.set(App.RC_NEXTFRAME)

    def done(self):
        """ Called when user asks for Next File
        i.e. mark this one as done and view next file.
        """
        self.wait_flag.set(App.RC_DONEIMAGE)

    def prev(self):
        """ Called when user asks for Prev File
        i.e. don't mark this one as done, just view prev file.
        """
        self.wait_flag.set(App.RC_PREVIMAGE)

    # Internal functionality

    @staticmethod
    def construct_FileList(file_list):
        """ Given a list() of filenames construct a FileList object.
        The special feature of this function is that it checks for a
        database and pulls out the filenames from it. """
        dicomfilelist = FileList(file_list)
        # If you select a database then all files with rects or tags are added to the list
        for fn in file_list:
            if DicomRectDB.db_filename in fn:
                tmpdb = DicomRectDB(filename = fn)
                # Go via a set() to remove duplicates
                db_file_list = list(set(tmpdb.query_rect_filenames() + tmpdb.query_tag_filenames()))
                dicomfilelist = FileList(db_file_list)
        return dicomfilelist

    def fix_rect_bounds(self, a, b, lim):
        """
        a, b: interval to fix
        lim: upper bound
        """
        a, b = sorted((int(a), int(b)))
        return a, b

    def set_rect(self, top, left, right, bottom):
        self.rect_t, self.rect_b = self.fix_rect_bounds(top, bottom, self.image_height)
        self.rect_l, self.rect_r = self.fix_rect_bounds(left, right, self.image_width)
        self.render()

    def drag_start(self, x, y):
        self.drag_x0 = x
        self.drag_y0 = y
        self.drag_t0 = self.rect_t
        self.drag_l0 = self.rect_l
        self.drag_r0 = self.rect_r
        self.drag_b0 = self.rect_b
        self.state = self.classify_coord_as_drag(x, y)

    def drag_continue(self, x, y):
        dx = (x - self.drag_x0) * int(self.image_scale)
        dy = (y - self.drag_y0) * int(self.image_scale)
        new_top, new_left, new_right, new_bottom = self.get_drag_rect()
        if self.state == App.DRAG_C:
            # A center drag bumps into the edges
            if dx > 0:
                dx = min(dx, self.image_width - self.drag_r0)
            else:
                dx = max(dx, -self.drag_l0)
            if dy > 0:
                dy = min(dy, self.image_height - self.drag_b0)
            else:
                dy = max(dy, -self.drag_t0)
        if self.state in (App.DRAG_TL, App.DRAG_T, App.DRAG_TR, App.DRAG_C):
            new_top = self.drag_t0 + dy
        if self.state in (App.DRAG_TL, App.DRAG_L, App.DRAG_BL, App.DRAG_C):
            new_left = self.drag_l0 + dx
        if self.state in (App.DRAG_TR, App.DRAG_R, App.DRAG_BR, App.DRAG_C):
            new_right = self.drag_r0 + dx
        if self.state in (App.DRAG_BL, App.DRAG_B, App.DRAG_BR, App.DRAG_C):
            new_bottom = self.drag_b0 + dy
        # Keep every type of drag within the image bounds
        if new_top < 0:
            new_top = 0
        if new_left < 0:
            new_left = 0
        if new_right >= self.image_width:
            new_right = self.image_width-1
        if new_bottom >= self.image_height:
            new_bottom = self.image_height-1
        # A drag never moves left past right and so on
        if self.state != App.DRAG_C:
            new_top = min(self.rect_b-1, new_top)
            new_left = min(self.rect_r-1, new_left)
            new_right = max(self.rect_l+1, new_right)
            new_bottom = max(self.rect_t+1, new_bottom)

        self.set_rect(new_top, new_left, new_right, new_bottom)

    def drag_end(self, x, y):
        self.set_rect(self.rect_t, self.rect_l, self.rect_r, self.rect_b)
        self.state = App.DRAG_NONE


    def get_drag_rect(self):
        """ Return t,l,r,b of the drag rectangle
        """
        #return self.rect_top, self.rect_left, self.rect_right, self.rect_bottom
        return self.rect_t, self.rect_l, self.rect_r, self.rect_b

    def get_scaled_drag_rect(self):
        """ Return t,l,r,b of the drag rectangle scaled to screen coords
        """
        t, l, r, b = self.get_drag_rect()
        return(int(t/int(self.image_scale)), int(l/int(self.image_scale)),
               int(r/int(self.image_scale)), int(b/int(self.image_scale)))

    def classify_coord_as_drag(self, x, y):
        """ Return a DRAG_ code if the x,y is inside a drag rectangle region.
        Returns DRAG_NONE if the x,y is outside the rectangle.
        """
        t, l, r, b = self.get_scaled_drag_rect()
        dx = (r - l) / 4
        dy = (b - t) / 4

        if x < l: return App.DRAG_NONE
        if x > r: return App.DRAG_NONE
        if y < t: return App.DRAG_NONE
        if y > b: return App.DRAG_NONE

        if x < l+dx:
            if y < t+dy: return App.DRAG_TL
            if y < b-dy: return App.DRAG_L
            return App.DRAG_BL
        if x < r-dx:
            if y < t+dy: return App.DRAG_T
            if y < b-dy: return App.DRAG_C
            return App.DRAG_B
        else:
            if y < t+dy: return App.DRAG_TR
            if y < b-dy: return App.DRAG_R
            return App.DRAG_BR

    def wait_for_flag(self):
        self.tk_app.wait_variable(self.wait_flag)
        value = self.wait_flag.get()
        return value

    def set_busy(self, new_busy = True):
        self.if_busy = new_busy
        if new_busy:
            self.app_image.configure(cursor="watch")
            self.tk_app.configure(cursor="watch")
        else:
            self.app_image.configure(cursor="")
            self.tk_app.configure(cursor="")
        self.tk_app.update_idletasks()

    def render(self):
        """ Call this method when you want to update the display.
        It sets a flag to do the rendering when next idle.
        Will call do_render
        """
        if not self.render_flag:
            self.render_flag = True
            self.tk_app.after_idle(self.do_render)

    def do_render(self):
        """ Called internally when the GUI is idle to update the display.
        Uses render_drag_rect() to overlay the drag show_handles.
        """
        if not self.render_flag:
            return
        self.render_flag = False
        if self.image is None:
            if hasattr(self, 'dummy_tkimage'):
                self.app_image.configure(image=self.dummy_tkimage)
            self.info_label.configure(text="\n\n")
            return

        #tt, ll, rr, bb = self.get_drag_rect()
        #ratio = self.describe_ratio()
        #self.inf.configure(text=
        #    "Left:  %4d  Top:    %4d    Right: %4d  Bottom: %4d\n"
        #    "Width: %4d  Height: %4d    Ratio: %8s\n"
        #        % (ll, tt, rr, bb, rr-ll, bb-tt, ratio),
        #    font="fixed", justify="l", anchor="w")
        self.tkimage.paste(self.rendered_with_drag_rect())

    def rendered_with_drag_rect(self):
        """ Applies the drag rectangles onto the image and returns a new image.
        """
        # XXX could also use the list of redaction rectangles to redact the image.
        t, l, r, b = self.get_scaled_drag_rect()
        #logging.debug('Rendering rect at %d,%d,%d,%d' % (l,r,t,b))
        if self.show_handles:
            dx = (r - l) / 4
            dy = (b - t) / 4

            mask = Image.new('1', self.image.size, 1)
            draw = ImageDraw.Draw(mask)

            draw.line([l, t, r, t], fill=0)
            draw.line([l, b, r, b], fill=0)
            draw.line([l, t, l, b], fill=0)
            draw.line([r, t, r, b], fill=0)

            draw.line([l+dx, t, l+dx, t+dy, l, t+dy], fill=0)
            draw.line([r-dx, t, r-dx, t+dy, r, t+dy], fill=0)
            draw.line([l+dx, b, l+dx, b-dy, l, b-dy], fill=0)
            draw.line([r-dx, b, r-dx, b-dy, r, b-dy], fill=0)

            image = Image.composite(self.image, self.image_xor, mask)
        else:
            image = self.image
        return image

    def update_info_label(self):
        """ Update the description of the image in the text bar
        at the top of the window.
        """
        filename = self.dcm.get_filename()
        frame, overlay = self.dcm.get_current_frame_overlay()
        num_overlays = self.dcm.get_num_overlays()
        db = DicomRectDB()
        marked, commented = db.query_tags(filename)
        # Update the info label
        short_filename = filename.replace('/home/arb/','')
        short_filename = filename.replace('/beegfs-hdruk/extract/v12/PACS/','')
        marked_string = "[*]  " if marked else ""
        commented_string = " - " + commented if commented else ""
        dicom_text = self.dcm.get_tag_overview()
        fileidx, numfiles = self.filelist.get_current_index()
        if overlay > -1:
            self.info_label.configure(text = "%sFile: %d/%d %s\nTags: %s\n%dx%d Overlay: %d / %d Frame: %d / %d %s" %
                (marked_string, fileidx+1, numfiles, short_filename,
                dicom_text,
                self.image_width, self.image_height,
                overlay+1, num_overlays,
                frame+1, self.dcm.get_num_frames_in_overlays(overlay),
                commented_string))
        else:
            if num_overlays > 0:
                overlays_str = "(+" + str(num_overlays) + " overlays)"
            else:
                overlays_str = ''
            self.info_label.configure(text = "%sFile: %d/%d %s\nTags: %s\n%dx%d Frame: %d / %d %s %s" %
                (marked_string, fileidx+1, numfiles, short_filename, dicom_text,
                self.image_width, self.image_height,
                frame+1, self.dcm.get_num_frames(), overlays_str, commented_string))

    def update_image(self, dicomrectlist = [], dicomtransrectlist = []):
        """ Uses the current self.image to update the display
        by scaling it if necessary, calculating an xor mask,
        redacting rectangles from dicomrectlist
        (must be applicable to this frame, not checked here)
        drawing suggested rectangles from dicomtransrectlist,
        and calling render() to plot the image with the drag handles on top.
        """
        # Already a contrast-stretched 8-bit image, do we need to convert to 'L'?
        self.image = (self.raw_image.convert('L')) # .convert('RGB')
        # Update the rect back to default
        # XXX should we default to the previous rect? Or set of rectangles?
        #self.t, self.b = self.fix(0, self.h, self.h, self.round_y, self.rotation in (3, 8))
        #self.l, self.r = self.fix(0, self.w, self.w, self.round_x, self.rotation in (3, 6))
        self.rect_t = self.rect_l = 0
        self.rect_b = self.rect_r = 256

        # Prepare the image
        self.image_width, self.image_height = self.image.size
        self.image_scale = max(1, (self.image_width-1)//self.screen_width_max+1)
        self.image_scale = max(self.image_scale, (self.image_height-1)//self.screen_height_max+1)

        # Redact known regions
        draw = ImageDraw.Draw(self.image)
        for dicomrect in dicomrectlist:
            #logging.debug('PLOT redacting %s %s %s %s' % (dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()))
            draw.rectangle((dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()), fill=App.redact_colour)

        # Define a simple function to draw an outline rectangle
        def plot_highlight_rect(dicomrect, colour):
            draw.rectangle((dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()), outline=colour)
            draw.line([dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()], fill=colour)
            draw.line([dicomrect.R(), dicomrect.T(), dicomrect.L(), dicomrect.B()], fill=colour)

        # Highlight redacted rectangles
        if self.highlight_rects.get():
            for dicomrect in dicomrectlist:
                logging.debug('PLOT highlighting %s %s %s %s' % (dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()))
                plot_highlight_rect(dicomrect, 0*App.outline_colour)

        # Highlight suggested rectangles
        if self.highlight_suggested_rects.get():
            for dicomrect in dicomtransrectlist:
                #logging.debug('PLOT highlighting %s %s %s %s' % (dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()))
                plot_highlight_rect(dicomrect, App.outline_colour)

        # Highlight rectangles from the deid rules, but these will already
        # have been added to the redacted list in dicomrectlist so this is
        # not necessary but it can help you to see which rects are from deid.
        # XXX using a class member not a function parameter.
        if self.highlight_deid_rects.get():
            for dicomrect in self.deid_rects:
                #logging.debug('PLOT deid_rects %s %s %s %s' % (dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()))
                plot_highlight_rect(dicomrect, App.deid_rect_colour)

        # Highlight rectangles from the ultrasound regions, but these will
        # have been added to the redacted list in dicomrectlist so this is
        # not necessary but it can help you to see which rects are from ultrasound.
        # XXX using a class member not a function parameter.
        if self.highlight_ultrasound_rects.get():
            for dicomrect in self.us_rects:            
                #logging.debug('PLOT us_rects %s %s %s %s' % (dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()))
                plot_highlight_rect(dicomrect, App.us_rect_colour)

        # Create a scaled (smaller) image to fit on screen
        resized_image = self.image.copy()
        resized_image.thumbnail((self.image_width//self.image_scale, self.image_height//self.image_scale))
        self.image = resized_image
        # Mask
        mult = len(self.image.mode) # replicate filter for L, RGB, RGBA
        self.image_xor = resized_image.copy().point([x ^ 128 for x in range(256)] * mult)
        # Store the image in the Tk widget
        self.tkimage = ImageTk.PhotoImage(resized_image)
        self.app_image.configure(image=self.tkimage)
        logging.debug('Loaded image size %d x %d scaled by %f' % (self.image_width, self.image_height, self.image_scale))
        self.render()

    # Application functionality methods

    def set_image_list(self, filelist):
        """ Given a FileList object
        """
        self.filelist = filelist

    def gui_loop(self):
        """ Returns -1 (close = quit) or 0 (cancel = next image) or 1 (done)
        """
        self.set_busy(0)
        v = self.wait_for_flag()
        self.set_busy()
        logging.debug('XXX GUI loop finished with v=%d (-1=quit,0=next/prev frame,1=next image)' % v)
        return v

    def load_next_file(self):
        """ Load the next file from the list and loop through all frames/overlays.
        Returns False if the user wants to quit or when all files viewed.
        Returns True when the user has finished with this file.
        """
        # Loop over files already processed until we get a new file
        db = DicomRectDB()
        while True:
            filename = self.filelist.next()
            if not filename:
                return False
            if self.skip_marked_files.get() and db.file_marked_done(filename):
                logging.info('Ignore file already done: %s' % filename)
                continue
            if self.skip_untagged_files.get() and not db.file_tagged(filename):
                logging.info('Ignore file not tagged: %s' % filename)
                continue
            break

        try:
            filename_to_load = filename
            if s3url_is(filename):
                filename = s3url_sanitise(filename)
            self.dcm = DicomImage(filename_to_load)
        except Exception as e:
            logging.warning('Cannot load DICOM from file "%s"' % filename)
            logging.error(traceback.format_exc())
            tkinter.messagebox.showerror(title="Help",
                message='Cannot load DICOM from file "%s"' % filename)
            return True

        # Loop through each frame/overlay in this file
        while True:
            try:
                self.raw_image = self.dcm.next_image()
            except:
                logging.warning('Cannot load DICOM image/overlay frame from file "%s"' % filename)
                rc = tkinter.messagebox.showerror(title="Help",
                    message='Cannot load DICOM image/overlay from file "%s"' % filename,
                    type=tkinter.messagebox.OKCANCEL)
                # Cancel means abort all frames in this file, move to next file
                if rc == 'cancel':
                    return True
                # ok means try next frame
                continue
            if not self.raw_image:
                #logging.error('ERROR: no image extracted from file')
                return True
            logging.debug('Loaded file %s having %d frames %d overlays %d frames in overlays' %
                (filename, self.dcm.get_num_frames(),
                self.dcm.get_num_overlays(),
                self.dcm.get_num_frames_in_overlays()))

            # Find out whether it's been redacted already by querying database
            frame, overlay = self.dcm.get_current_frame_overlay()
            self.redacted_rects = db.query_rects(filename, frame=frame, overlay=overlay,
                ignore_allowlisted = True, ignore_summaries = True)
            #logging.debug('RECTS database: %s' % self.redacted_rects)

            # Look for similar files in the database and get their rectangles
            # Keep a copy of them so user can Apply them later
            self.possible_rects = db.query_similar_rects(filename, self.dcm.get_selected_metadata(), frame=frame, overlay=overlay)
            #logging.debug('RECTS similar file: %s' % self.possible_rects)

            # Get a list of suggested rectangles which may apply to this file from the deid recipes
            # XXX only do this if self.highlight_suggested_rects.get() ?
            # that would be faster but if options menu turned on then list would be empty
            self.deid_rects = deidrules.detect(self.dcm.get_dataset())
            #logging.debug('RECTS deid rules: %s' % self.deid_rects)

            # Get a list of rectangles from the ultrasound region tags
            self.us_rects = ultrasound.read_DicomRectText_list_from_region_tags(ds = self.dcm.get_dataset())
            #logging.debug('RECTS ultrasound: %s' % self.us_rects)
            logging.debug('RECTS %d from database, %d from similar files, %d from deid rules, (%d from ultrasound not used)' %
                (len(self.redacted_rects), len(self.possible_rects), len(self.deid_rects), len(self.us_rects)))
            if self.redact_us_rects.get():
                self.redacted_rects.extend(self.us_rects)

            # Add deid rects to the list to be redacted.
            # XXX should add to suggested rectangles list instead?
            if self.redact_deid_rects.get():
                self.redacted_rects.extend(self.deid_rects)

            # Resize to fit screen and apply rectangles, trigger window refresh
            self.update_image(dicomrectlist = self.redacted_rects, dicomtransrectlist = self.possible_rects)
            # Update the info label
            self.update_info_label()

            # Enter the GUI loop
            rc = self.gui_loop()
            if rc == App.RC_QUIT:
                # Quit
                return False
            elif rc == App.RC_NEXTFRAME:
                # Next (or prev) Frame
                pass
            elif rc == App.RC_NEXTIMAGE:
                # Next image
                return True
            elif rc == App.RC_PREVIMAGE:
                # Previous image need to step back two ready for next
                self.filelist.prev()
                self.filelist.prev()
                return True
            elif rc == App.RC_DONEIMAGE:
                # Next image (mark current image as done)
                db.mark_inspected(filename,
                    metadata_dict = self.dcm.get_selected_metadata())
                return True
        return True

    def run(self):
        while True:
            if self.filelist.is_exhausted():
                rc = self.gui_loop() # wait for Open menu
                if rc == App.RC_QUIT:
                    break
            ok = self.load_next_file()
            if not ok:
                break
            logging.debug('finished with this file')
        logging.debug('finished all files, exit')
        return




# =====================================================================

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='DICOM Audit')
    parser.add_argument('-d', '--debug', action="store_true", help='debug')
    parser.add_argument('-q', '--quiet', action="store_true", help='quiet')
    parser.add_argument('--dump-database', action="store_true", help='show database content')
    parser.add_argument('--db', action="store", help='database directory')
    parser.add_argument('--review', action="store_true", help='review files already marked as done')
    parser.add_argument('--tagged', action="store_true", help='only view files with a tag')
    parser.add_argument('-i', dest='infiles', nargs='*', help='list of DICOM files, or a filename.csv (for DicomFilePath)', default=[]) # can use: -i *.txt
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level = logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level = logging.WARNING)
    else:
        logging.basicConfig(level = logging.INFO)

    if args.db:
        database_path = args.db
    else:
        if not os.getenv('SMI_ROOT'):
            logging.error('$SMI_ROOT must be set, so we can write into data/dicompixelanon directory')
            exit(1)
        database_path = os.path.join(os.getenv('SMI_ROOT'), "data", "dicompixelanon/") # needs trailing slash
    DicomRectDB.set_db_path(database_path)

    if args.dump_database:
        db = DicomRectDB()
        db.query_all()
        exit(0)

    app = App()
    app.set_image_list(app.construct_FileList(args.infiles))
    if args.review:
        app.set_skip_marked_files(False)
    if args.tagged:
        app.set_skip_untagged_files(True)
    app.run()
