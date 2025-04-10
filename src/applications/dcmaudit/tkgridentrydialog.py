""" A tk dialog to display a set of items in a grid as rows of
 label:text
where text is editable, not so the user can edit the text, but
so that they can scroll inside and copy/paste out.
"""

import tkinter
import tkinter.simpledialog


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
