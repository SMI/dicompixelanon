""" A tk dialog for downloading a single file from a S3 server.
"""

import logging
import os
import tkinter
import tkinter.messagebox
from tktooltip import ToolTip
import boto3
from dcmaudit_s3credstore import S3CredentialStore


# Configuration:
MAX_S3_LIST = 200      # max files to list in download window
TTD=0.4                # delay in seconds before ToolTip is shown



class S3DownloadDialog:
    """ Pop up a window giving the ability to download a file from S3
    by selecting credentials, populating a listbox with the files in
    the bucket, and downloading the selected file to a given directory.
    """
    # Class variable
    # Default to ~/s3 if it exists as a directory, else ~
    default_output_dir = '~'
    if os.path.isdir(os.path.join(os.environ['HOME'], 's3')):
        default_output_dir = '~/s3'


    def __init__(self, parent):
        self.bucket = None
        self.access = self.secret = None
        self.endpoint = None
        self.output_dir = None

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
        top.geometry(f'+{max(0,parent.winfo_rootx()-30)}+{parent.winfo_rooty()}')
        tkinter.Label(top, text='Saved credentials:').grid(row=0, column=0)
        self.bucket_dropdown = tkinter.StringVar()
        def pick(_):
            self.bucket = self.bucket_dropdown.get()
            (self.access, self.secret, self.endpoint) = cred_store.read_cred(self.bucket)
        self.bucketMenu = tkinter.OptionMenu(top, self.bucket_dropdown, '', *cred_names, command = pick)
        ToolTip(self.bucketMenu, msg="Select the name of the bucket where the files are stored", delay=TTD)
        self.bucketMenu.grid(row=0, column=1)

        # List of files with scrollbar
        self.filelist = []
        self.filelistvar = tkinter.StringVar(value=self.filelist)
        self.myFileList = tkinter.Listbox(top, listvariable=self.filelistvar, height=10)
        ToolTip(self.myFileList, msg="Pick a file to download")
        self.myFileList.grid(row=1, column=0, sticky=(tkinter.N,tkinter.W,tkinter.E,tkinter.S))
        scroller = tkinter.Scrollbar(top, orient=tkinter.VERTICAL, command=self.myFileList.yview)
        self.myFileList.configure(yscrollcommand=scroller.set)
        scroller.grid(row=1, column=1, sticky=(tkinter.N,tkinter.S))

        # Output directory
        tkinter.Label(top, text='Output directory (use ~ for your home directory):').grid(row=2, column=0)
        self.outputEntry = tkinter.Entry(top)
        self.outputEntry.insert(tkinter.END, S3DownloadDialog.default_output_dir)
        ToolTip(self.outputEntry, msg="Enter an output directory, use ~ for your home directory", delay=TTD)
        self.outputEntry.grid(row=2, column=1)

        # List and Download buttons
        self.myListButton = tkinter.Button(top, text='List', command=self.list)
        self.myListButton.grid(row=3, column=0)
        ToolTip(self.myListButton, msg="List the files in the chosen bucket.", delay=TTD)
        self.myDownloadButton = tkinter.Button(top, text='Download', command=self.download)
        self.myDownloadButton.grid(row=3, column=1)
        ToolTip(self.myDownloadButton, msg="Download the selected file into the Output directory.", delay=TTD)
        top.grid_columnconfigure(0, weight=1)
        top.grid_rowconfigure(0, weight=1)


    def list(self):
        """ Called when List button pressed.
        Populate the dialog box with a list of files in the bucket.
        """
        # Check that credentials have been chosen
        if not self.access or not self.secret:
            tkinter.messagebox.showerror(title="Error", message='Please select some credentials')
            return

        # Connect to S3 service
        logging.debug('Logging into S3 at %s with %s:%s' % (self.endpoint, self.access, self.secret))
        try:
            s3 = boto3.resource('s3',
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access, aws_secret_access_key=self.secret)
        except:
            tkinter.messagebox.showerror(title="Error", message="Cannot connect to the S3 server, check the endpoint URL and the credentials in the credential manager")
            return

        # Select the bucket given by the credential name and make a list of files
        s3bucket = s3.Bucket(name=self.bucket)
        self.filelist = []
        try:
            for obj in s3bucket.objects.filter(Prefix = ''):
                self.filelist.append(obj.key)
                if len(self.filelist) > MAX_S3_LIST:
                    tkinter.messagebox.showerror(title="Error", message="Limited to %d files" % MAX_S3_LIST)
                    break
        except:
            tkinter.messagebox.showerror(title="Error", message="Cannot connect to the S3 server, check the endpoint URL and the credentials in the credential manager")
            return

        # Sort the list of files and store in the listbox widget
        self.filelist = sorted(self.filelist)
        self.filelistvar.set(self.filelist)
        return


    def download(self):
        """ Called when Download button pressed.
        Download the single file selected in the listbox.
        """
        # Check that credentials have been chosen (list() must have been called previously)
        if not self.access or not self.secret:
            tkinter.messagebox.showerror(title="Error", message='Please select some credentials')
            return
        self.output_dir = self.outputEntry.get()
        if not self.output_dir:
            tkinter.messagebox.showerror(title="Error", message='Please enter an output directory, for example use ~ for your home directory, or ~/s3 for the s3 directory inside your home directory.')
            return

        # Keep output dir for next time
        S3DownloadDialog.default_output_dir = self.output_dir
        # Expand ~ and $var in output directory
        self.output_dir = os.path.expanduser(os.path.expandvars(self.output_dir))
        # Get the selected filename from the listbox widget
        selected_indices = self.myFileList.curselection()
        if selected_indices:
            selected_index = selected_indices[0]
            selected_item = self.myFileList.get(selected_index)
        else:
            tkinter.messagebox.showerror(title="Error", message='Please select a filename.')
            return

        # Connect to S3 service
        logging.debug('Logging into S3 at %s with %s:%s' % (self.endpoint, self.access, self.secret))
        try:
            s3 = boto3.resource('s3',
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access, aws_secret_access_key=self.secret)
        except:
            tkinter.messagebox.showerror(title="Error", message="Cannot connect to the S3 server, check the endpoint URL and the credentials in the credential manager")
            return

        # Select the bucket given by the credential name and download the file
        s3bucket = s3.Bucket(name=self.bucket)
        try:
            for obj in s3bucket.objects.filter(Prefix = selected_item):
                os.makedirs(self.output_dir, exist_ok=True)
                s3bucket.download_file(obj.key, os.path.join(self.output_dir, os.path.basename(obj.key)))
                tkinter.messagebox.showinfo(title="Error", message="Downloaded "+os.path.basename(obj.key))
        except Exception as e:
            tkinter.messagebox.showerror(title="Error", message="Cannot download %s from S3 server, check the endpoint URL and the credentials in the credential manager, and check the output directory is writeable.")
            return

        # Cannot raise window to front using attributes('-topmost',1)
        # or lift() or focus_force(), so just close it:
        self.top.destroy()
        return
