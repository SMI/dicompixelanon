""" S3CredentialsDialog is a tk dialog for managing S3 credentials.
It uses the S3CredentialStore class to actually store the credentials.
The default S3 endpoint URL is defined in this module.
"""

import logging
import tkinter
import tkinter.messagebox
from tktooltip import ToolTip
import boto3
from dcmaudit_s3credstore import S3CredentialStore

# =====================================================================

# Configuration:
DEFAULT_S3_ENDPOINT = 'http://nsh-fs02:7070/' # 127.0.0.1 OR nsh-fs02
TTD=0.4                # delay in seconds before ToolTip is shown

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
        self.bucketname = None
        # Read the stored credentials
        # Add an empty one so there's at least one item
        cred_store = S3CredentialStore()
        cred_list = cred_store.read_creds()
        cred_names = list(cred_list.keys())
        options = cred_names if len(cred_names)>0 else ['---']
        # Construct GUI
        top = self.top = tkinter.Toplevel(parent)
        top.geometry(f'+{max(0,parent.winfo_rootx()-20)}+{parent.winfo_rooty()}')
        tkinter.Label(top, text='Saved credentials:').grid(row=0, column=0)
        #self.myLabel.pack() instead of pack()ing every widget we use grid(row,column)
        self.bucket_dropdown = tkinter.StringVar()
        def pick(_):
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
        self.bucketMenu = tkinter.OptionMenu(top, self.bucket_dropdown, '', *options, command = pick)
        ToolTip(self.bucketMenu, msg="Select from a set of saved credentials", delay=TTD)
        self.bucketMenu.grid(row=0, column=1)

        # Endpoint URL
        tkinter.Label(top, text='Server:').grid(row=1, column=0)
        self.serverEntry = tkinter.Entry(top)
        self.serverEntry.insert(0, DEFAULT_S3_ENDPOINT)
        ToolTip(self.serverEntry, msg="Enter the web address of the bucket server", delay=TTD)
        self.serverEntry.grid(row=1, column=1)

        # Access key
        tkinter.Label(top, text='Access key:').grid(row=2, column=0)
        self.accessEntry = tkinter.Entry(top)
        ToolTip(self.accessEntry, msg="Enter the access key you were given for the bucket. An empty key will remove the named bucket from the list.", delay=TTD)
        self.accessEntry.grid(row=2, column=1)

        # Secret key
        tkinter.Label(top, text='Secret key:').grid(row=3, column=0)
        self.secretEntry = tkinter.Entry(top)
        ToolTip(self.secretEntry, msg="Enter the secret key you were given for the bucket", delay=TTD)
        self.secretEntry.grid(row=3, column=1)

        # Bucket name
        tkinter.Label(top, text='Bucket name:').grid(row=4, column=0)
        self.bucketEntry = tkinter.Entry(top)
        ToolTip(self.bucketEntry, msg="Enter the name of the bucket exactly as given when you were provided access", delay=TTD)
        self.bucketEntry.grid(row=4, column=1)

        # Save button
        self.myDeleteButton = tkinter.Button(top, text='Delete', command=self.delete)
        self.mySubmitButton = tkinter.Button(top, text='Save', command=self.save)
        ToolTip(self.myDeleteButton, msg="The bucket credentials will be removed from the list (the bucket itself is not deleted)", delay=TTD)
        ToolTip(self.mySubmitButton, msg="The credentials will be saved under the name you have selected for the bucket", delay=TTD)
        self.myDeleteButton.grid(row=5, column=0)
        self.mySubmitButton.grid(row=5, column=1)


    def delete(self):
        """ Called when the delete button os pressed.
        Remove the bucket from the credential store
        """
        bucketname = self.bucketEntry.get()
        if bucketname:
            cred_store = S3CredentialStore()
            cred_store.add_cred(bucketname, None, None, None)
        self.top.destroy()


    def save(self):
        """ Called when Save button pressed.
        Saves the entries in the credential store.
        """
        self.access = self.accessEntry.get()
        self.secret = self.secretEntry.get()
        self.bucketname = self.bucketEntry.get()
        self.endpoint = self.serverEntry.get()
        if self.bucketname:
            cred_store = S3CredentialStore()
            cred_store.add_cred(self.bucketname, self.access, self.secret, self.endpoint)
            if self.access and self.secret and self.bucketname:
                try:
                    logging.debug(f'Logging into S3 at {self.endpoint} with {self.access}:{self.secret}')
                    s3 = boto3.resource('s3',
                        endpoint_url=self.endpoint,
                        aws_access_key_id=self.access, aws_secret_access_key=self.secret)
                    s3.meta.client.head_bucket(Bucket = self.bucketname)
                except:
                    tkinter.messagebox.showerror(title="Error", message="Cannot connect to the S3 server, check the bucket name, endpoint URL and the credentials")
                    return
        self.top.destroy()
