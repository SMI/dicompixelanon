# A Tk window which contains a table listing all the tags in a DICOM file.
# NB. display of tag values is limited to 120 characters wide, after that
# they are truncated silently.

import tkinter
from DicomPixelAnon.dicomimage import DicomImage
from tkintertable import TableCanvas, TableModel

# =====================================================================

class TagInfoWindow:

    MAX_TAG_VALUE_LEN = 120 # max length of tag value string in info window

    def __init__(self, tk_app):
        self.taginfo_window = tkinter.Toplevel(tk_app)
        self.taginfo_window.geometry('640x480')
        self.taginfo_window.title('DICOM file tag values')
        self.frame = tkinter.Frame(self.taginfo_window)
        self.frame.pack(fill=tkinter.BOTH, expand=1)
        self.table = None

    def window(self):
        return self.taginfo_window

    def taginfo_window_populate(self, dcm):
        if self.table:
            del self.table
        self.table = TableCanvas(self.frame)
        man = str(dcm.get_tag('Manufacturer'))
        mod = str(dcm.get_tag('ManufacturerModelName'))
        swv = str(dcm.get_tag('SoftwareVersions'))
        bia = str(dcm.get_tag('BurnedInAnnotation'))
        imgtype = str(dcm.get_tag('ImageType'))
        moda = str(dcm.get_tag('Modality'))
        fn = dcm.get_filename()
        self.taginfo_window.title('DICOM file tag values for %s' % fn)
        tagdict1 = {
            '0': {'Tag':'Filename', 'Value':fn},
            '1': {'Tag':'Modality', 'Value':moda},
            '2': {'Tag':'Image type', 'Value':imgtype},
            '3': {'Tag':'Manufacturer', 'Value':man},
            '4': {'Tag':'Model', 'Value':mod},
            '5': {'Tag':'Software', 'Value':swv},
            '6': {'Tag':'Burned In Annotation', 'Value':bia},
            }
        # Build a dict like {'rowname': {'Tag': 'the name of the tag', 'Value': 'the tag value'}}
        # from all the tags in the DICOM dataset (XXX uses the private ds element from self.dcm)
        tagdict2 = {t.name : {'Tag':t.name, 'Value':str(t.value)[:TagInfoWindow.MAX_TAG_VALUE_LEN]} for t in dcm.ds}
        self.table = TableCanvas(self.frame, data={**tagdict1, **tagdict2})
        self.table.show()
