""" Classes and functions to implement S3 support in dcmaudit.
"""


import csv
import os


# =====================================================================

CREDS_FILENAME = '.dcmaudit_s3creds.csv'

class S3CredentialStore:
    """ Store S3 credentials in home directory
    """
    def __init__(self):
        self.cred_path = os.path.join(os.environ.get('HOME','.'), CREDS_FILENAME)
        self.creds = dict()
        self.read_creds()


    def read_creds(self):
        """ Returns a dict mapping nickname to a tuple (access,secret,endpoint)
        """
        self.creds = dict()
        if os.path.isfile(self.cred_path):
            with open(self.cred_path, newline='') as fd:
                csvr = csv.DictReader(fd)
                for row in csvr:
                    self.creds[row['name']] = (row['access'], row['secret'], row['endpoint'])
        return self.creds


    def read_cred(self, nickname):
        """ Returns tuple (access,secret) or None
        """
        self.read_creds()
        (acc,sec,srv) = self.creds.get(nickname, ('',''))
        return (acc,sec,srv)


    def add_cred(self, nickname, access, secret, endpoint):
        """ Appends to the CSV
        XXX possibly re-read the file in case someone else modified it,
        and merge with the values held in self.creds?
        """
        self.creds[nickname] = (access, secret, endpoint)
        if not access or not secret:
            del self.creds[nickname]
        with open(self.cred_path, 'w', newline='') as fd:
            csvw = csv.DictWriter(fd, fieldnames=['name','access','secret','endpoint'], lineterminator='\n')
            csvw.writeheader()
            for nickname in self.creds:
                (acc,sec,srv) = self.creds[nickname]
                csvw.writerow( { 'name': nickname, 'access': acc, 'secret': sec, 'endpoint': srv } )