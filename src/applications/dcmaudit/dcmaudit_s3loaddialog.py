""" A tk dialog for collecting a list of Study/Series/Image
from a S3 bucket, and either saving the files to disk or
preserving the list in the self.path_list variable.
"""

import logging
import random
import os
import tkinter
import tkinter.filedialog
import tkinter.messagebox
from tktooltip import ToolTip
import boto3
from DicomPixelAnon.s3url import s3url_create
from dcmaudit_s3credstore import S3CredentialStore
from seekablecsv import SeekableCsv
import container_utils


# =====================================================================
# Configuration:
NUM_RANDOM_S3_IMAGES = 50
MAX_S3_LOAD = 10000    # max to load from S3 if not limited by study/series
TTD=0.4                # delay in seconds before ToolTip is shown


# =====================================================================
class S3LoadDialog:
    """ Display a window giving options to download or view a set
    of images held in a S3 bucket.
    """
    # Class variables
    default_csv_file_dir = '.'
    default_output_dir = ''

    def __init__(self, parent, s3loadprefs = None):
        # Initialise instance variables
        self.bucket = None
        self.access = self.secret = None
        self.endpoint = None
        self.onePerSeries = False
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
            self.csv_file_dir = S3LoadDialog.default_csv_file_dir
            self.output_dir = S3LoadDialog.default_output_dir

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
        top.transient(parent) # appear above parent
        top.grab_set() # modal
        top.focus_set() # grab focus
        top.lift() # on top
        top.geometry(f'+{max(0,parent.winfo_rootx()-20)}+{parent.winfo_rooty()}')
        tkinter.Label(top, text='Saved credentials:').grid(row=0, column=0)
        self.bucket_dropdown = tkinter.StringVar()
        def pick(_):
            self.bucket = self.bucket_dropdown.get()
            (self.access, self.secret, self.endpoint) = cred_store.read_cred(self.bucket)
        self.bucketMenu = tkinter.OptionMenu(top, self.bucket_dropdown, '', *cred_names, command = pick)
        ToolTip(self.bucketMenu, msg="Select the name of the bucket where the files are stored", delay=TTD)
        self.bucketMenu.grid(row=0, column=1)

        # Random sample
        tkinter.Label(top, text='Random sample:').grid(row=1, column=0)
        self.randomVar = tkinter.IntVar()
        self.randomCheck = tkinter.Checkbutton(top, text='Random',variable=self.randomVar, onvalue=1, offvalue=0) # command=<func>
        ToolTip(self.randomCheck, msg=f"If selected then {NUM_RANDOM_S3_IMAGES} will be selected randomly from the CSV file", delay=TTD)
        self.randomCheck.grid(row=1, column=1)

        # First of each Series
        tkinter.Label(top, text='One image per series:').grid(row=2, column=0)
        self.singlePerSeriesVar = tkinter.IntVar()
        self.singlePerSeriesCheck = tkinter.Checkbutton(top, text='Overview',variable=self.singlePerSeriesVar, onvalue=1, offvalue=0)
        ToolTip(self.singlePerSeriesCheck, msg="If selected then only one image is selected per-Series", delay=TTD)
        self.singlePerSeriesCheck.grid(row=2, column=1)

        # CSV file
        #tkinter.Label(top, text='CSV file (optional):').grid(row=3, column=0)
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
        tkinter.Button(top, text='CSV file (optional)', command=showFileChooser).grid(row=3, column=0)
        self.csvEntry = tkinter.Entry(top)
        ToolTip(self.csvEntry, msg="A CSV file can be used to lookup Study numbers given Series numbers, or for random sampling", delay=TTD)
        self.csvEntry.grid(row=3, column=1)

        # Study Ids
        tkinter.Label(top, text='Study Ids:').grid(row=4, column=0)
        self.studyEntry = tkinter.Entry(top)
        ToolTip(self.studyEntry, msg="Enter one (or more, comma separated) Study numbers, or leave blank if random sampling", delay=TTD)
        self.studyEntry.grid(row=4, column=1)

        # Series Ids
        tkinter.Label(top, text='Series Ids:').grid(row=5, column=0)
        self.seriesEntry = tkinter.Entry(top)
        ToolTip(self.seriesEntry, msg="Enter one (or more, comma separated) Series numbers, or leave blank for all Series in a Study", delay=TTD)
        self.seriesEntry.grid(row=5, column=1)

        # Output directory
        def showDirChooser():
            startingdir = self.output_dir
            if not startingdir:
                startingdir = self.outputEntry.get()
            if not startingdir:
                startingdir = os.path.join(os.environ['HOME'], 's3')
            directory = tkinter.filedialog.askdirectory(initialdir = startingdir)
            self.outputEntry.delete(0, tkinter.END)
            self.outputEntry.insert(0, directory)
            self.output_dir = directory
        #Instead of Label use Button tkinter.Label(top, text='Output directory:').grid(row=6, column=0)
        self.myDirButton = tkinter.Button(top, text='Output directory (blank to view images):', command=showDirChooser)
        self.myDirButton.grid(row=6, column=0)
        self.outputEntry = tkinter.Entry(top)
        self.outputEntry.insert(tkinter.END, self.output_dir)
        ToolTip(self.outputEntry, msg="Leave blank to load the images straight into the viewer without saving as a file, or enter an output directory. You can add {study} and {series} to directory names. Directories will be created as necessary.", delay=TTD)
        self.outputEntry.grid(row=6, column=1)

        # Load button
        self.mySubmitButton = tkinter.Button(top, text='Load', command=self.load)
        self.mySubmitButton.grid(row=7, column=1)
        ToolTip(self.mySubmitButton, msg="Download the images (and save as files, if output directory specified) and load into the viewer", delay=TTD)

    def load(self):
        """ Called when Load button is pressed.
        """
        # Save preferences for next time XXX needs s3loadprefs passed
        #if s3loadprefs:
        #    s3loadprefs.output_dir = self.output_dir
        #    s3loadprefs.csv_file_dir = self.csv_file_dir
        if not self.access or not self.secret:
            tkinter.messagebox.showerror(title="Error", message='Please select some credentials')
            return
        self.random = True if self.randomVar.get() else False
        self.onePerSeries = True if self.singlePerSeriesVar.get() else False
        self.study_list = self.studyEntry.get().split(',') if self.studyEntry.get() else []
        self.series_list = self.seriesEntry.get().split(',') if self.seriesEntry.get() else []
        self.output_dir = self.outputEntry.get()
        self.csv_file = self.csvEntry.get()

        if self.output_dir and container_utils.running_in_container() and not container_utils.directory_is_mounted(self.output_dir):
            tkinter.messagebox.showwarning(title="Warning", message="Files will be downloaded to an output directory which is not accessible outside this container")

        # Save for next time
        S3LoadDialog.default_output_dir = self.output_dir
        S3LoadDialog.default_csv_file_dir = os.path.dirname(self.csv_file)

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
        if len(self.study_list)>0 and (len(self.study_list) == len(self.series_list)):
            s3prefix_list.update([ f'{stu}/{ser}' for (stu,ser) in zip(self.study_list, self.series_list)])

        # Open CSV file
        csvr = None
        if self.csv_file:
            csvr = SeekableCsv(self.csv_file)
            if 'StudyInstanceUID' not in csvr.fieldnames or 'SeriesInstanceUID' not in csvr.fieldnames:
                tkinter.messagebox.showerror(title="Error", message="The CSV file does not have columns called StudyInstanceUID and SeriesInstanceUID")
                return
            #if 'SOPInstanceUID' in csvr.fieldnames:
            #    tkinter.messagebox.showerror(title="Error", message="The CSV file has a column called SOPInstanceUID which means multiple instances of Study+Series so queries may not work well; please try a CSV file reduced to only Study and Series")

        # Random: read CSV and select random rows
        if self.random:
            csv_filesize = os.path.getsize(self.csv_file)
            for _ in range(NUM_RANDOM_S3_IMAGES):
                csv_offset = random.randint(0, max(0,csv_filesize-10))
                csvr.seekafter(csv_offset)
                csv_data = next(csvr)
                if csv_data:
                    s3prefix_list.add('%s/%s/' % (csv_data['StudyInstanceUID'], csv_data['SeriesInstanceUID']))

        # If we don't have Study or Series then read all from CSV
        if not self.study_list and not self.series_list and not self.random:
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

        #for pfx in s3prefix_list:
        #    print('S3 prefix: %s' % pfx)

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
            # replace ~ and ~user and $var and ${var}
            self.output_dir = os.path.expanduser(os.path.expandvars(self.output_dir))
            # if relative then prefix with home
            if not os.path.isabs(self.output_dir):
                self.output_dir = os.path.expanduser(os.path.join('~', self.output_dir))
            # if no template given then use standard directory hierarchy
            if '{' not in self.output_dir:
                self.output_dir += '/{study}/{series}/{file}'
            logging.debug('Files will be saved in\n%s' % self.output_dir)

        # List bucket and download files, creating directories as necessary
        self.path_list = []
        def get_obj(key):
            # given a study/series/sop string in key, append S3 URL to
            # self.path_list, and download to self.output_dir if set.
            (stu,ser,sop) = key.split('/')
            path = self.output_dir.format(study=stu, series=ser, file=sop)
            logging.debug("%s\t->\t%s" % (key,path))
            if self.output_dir:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                s3bucket.download_file(key, path)
                self.path_list.append(path)
            else:
                self.path_list.append(s3url_create(self.access, self.secret, self.endpoint, self.bucket, key))

        # Build a list of objects to retrieve by doing an 'ls' in the series directories
        s3objdict = {}
        for s3prefix in s3prefix_list:
            try:
                for obj in s3bucket.objects.filter(Prefix = s3prefix):
                    # Expecting Study/Series/SOP but if we only get Study/Series
                    # then need to do an additional 'ls' inside the Series
                    # (typically if Series is a symlink):
                    key_parts = obj.key.split('/')
                    if len(key_parts) < 2:
                        # ignore files in root directory (also symlinks to directory)
                        continue
                    studyseries = key_parts[0] + '/' + key_parts[1]
                    if len(key_parts)==2:
                        # iterate through Series
                        for obj2 in s3bucket.objects.filter(Prefix = '%s/' % obj.key):
                            s3objdict.setdefault(studyseries, []).append(obj2.key.split('/')[2])
                    else:
                        s3objdict.setdefault(studyseries, []).append(key_parts[2])
            except:
                tkinter.messagebox.showerror(title="Error", message="Cannot retrieve object from the S3 server (%s)" % s3prefix)
                return

        # Filter list if only one per series is required
        if self.onePerSeries:
            for studyseries in s3objdict:
                s3objdict[studyseries] = [ random.choice(s3objdict[studyseries]) ]

        # Get all objects
        for studyseries in s3objdict:
            for sop in s3objdict[studyseries]:
                try:
                    get_obj('%s/%s' % (studyseries, sop))
                except:
                    tkinter.messagebox.showerror(title="Error", message="Cannot retrieve object from the S3 server (%s/%s)" % (studyseries, sop))
                    break

        self.top.destroy()

# =====================================================================
