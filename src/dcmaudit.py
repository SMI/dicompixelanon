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
import logging
import numpy as np
import os
import sys
from threading import Thread
import tkinter
import tkinter.filedialog
import tkinter.messagebox
import tkinter.simpledialog
from tkinter.ttk import Progressbar
import pytesseract
from filelist import FileList
from dicomrectdb import DicomRectDB
from rect import Rect, DicomRect, add_Rect_to_list
from ocrengine import OCR
from dicomimage import DicomImage


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


    def __init__(self):
        # Settings
        self.skip_marked_files = True
        # GUI
        self.tk_app = tkinter.Tk()
        self.tk_app.wm_title(("dcmaudit"))
        self.tk_app.wm_iconname(("dcmaudit"))
        self.tk_app.wm_protocol('WM_DELETE_WINDOW', self.quit)


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
        #self.tk_app.bind("<Return>", self.done_file_event)
        self.tk_app.bind("<Escape>", self.escape_file_event)
        self.tk_app.bind("<Shift-Escape>", self.prev_file_event)
        self.tk_app.bind("<t>", self.tag_file_event)
        self.tk_app.bind("<n>", self.next_frame_event)
        self.tk_app.bind("<N>", self.done_file_event)
        self.tk_app.bind("<p>", self.prev_frame_event)
        self.tk_app.bind("<P>", self.prev_file_event)
        self.tk_app.bind("<f>", self.ffwd_frame_event)
        self.tk_app.bind("<i>", self.info_file_event)
        self.tk_app.bind("<o>", self.ocr_frame_event)
        self.tk_app.bind("<r>", self.redact_event)
        self.tk_app.bind("<A>", self.apply_all_possible_rects_event)
        self.tk_app.bind("<q>", self.quit_event)
        self.tk_app.bind("<Z>", self.undo_file_event)
        self.render_flag = False # indicate that window should be rendered at next idle time
        self.wait_flag = tkinter.IntVar(self.tk_app) # effectively the return code -1=exit 0=cancel 1=done image

        self.app_button = tkinter.Button(self.tk_app, text="Help")
        self.app_button.pack(side="left")
        self.app_button.configure(command = self.help_button_pressed)

        # Add buttons (can have multiple, exactly like this)
        self.menu_button = tkinter.Menubutton(self.tk_app, text="Menu")
        self.menu_button.pack(side="left")
        self.menu = tkinter.Menu(self.menu_button)
        self.menu_button.config(menu=self.menu)
        self.menu.add_command(label='Redact [r]', command=lambda: self.redact_event(None))
        self.menu.add_command(label='Info [i]', command=lambda: self.info_file_event(None))
        self.menu.add_command(label='OCR frame [o]', command=lambda: self.ocr_frame_event(None))
        self.menu.add_command(label='Apply all suggested rects [A]', command=lambda: self.apply_all_possible_rects_event(None))
        self.menu.add_command(label='Next frame [n]', command=lambda: self.next_frame_event(None))
        self.menu.add_command(label='Fast forward frames [f]', command=lambda: self.ffwd_frame_event(None))
        self.menu.add_command(label='Previous frame [p]', command=lambda: self.prev_frame_event(None))
        self.menu.add_command(label='Mark done; Next file [N]', command=lambda: self.done_file_event(None))
        self.menu.add_command(label='Next file [Esc]', command=lambda: self.escape_file_event(None))
        self.menu.add_command(label='Prev file [P]', command=lambda: self.prev_file_event(None))
        self.menu.add_command(label='Tag file [t]', command=lambda: self.tag_file_event(None))
        self.menu.add_command(label='Undo file [Z]', command=lambda: self.undo_file_event(None))
        self.menu.add_command(label='Quit [q]', command=lambda: self.quit_event(None))

        self.info_label = tkinter.Label(self.tk_app)
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
        self.skip_marked_files = newval

    # User interface events

    def tag_file_event(self, event):
        logging.debug('Tag file')
        # Add to database
        filename = self.dcm.get_filename()
        db = DicomRectDB()
        db.toggle_tag(filename)
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
            add_Rect_to_list(self.possible_rects, dicomrect)
        self.update_image(dicomrectlist = self.redacted_rects, dicomtransrectlist = self.possible_rects)
        return

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

    def info_file_event(self, event):
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

    def help_button_pressed(self):
        """ Display a dialog with some help text.
        """
        tkinter.messagebox.showinfo(title="Help",
            message="Keyboard actions:\n"
                "r = redact the rectangle\n"
                "i = info for this file\n"
                "o = OCR this frame\n"
                "A = apply all suggested rectangles\n"
                "right-click = apply suggested rect\n"
                "n = next frame\n"
                "p = previous frame\n"
                "f = fast forward\n"
                "N = mark done; next file\n"
                "Esc = next file\n"
                "P = prev file\n"
                "t = tag this image for further investigation\n"
                "Z = reset file\n"
                "q = quit\n")
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
            self.app_button.configure(state="disabled")
        else:
            self.app_image.configure(cursor="")
            self.tk_app.configure(cursor="")
            self.app_button.configure(state="normal")
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
                (marked_string, fileidx+1, numfiles, short_filename, dicom_text,
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
        and calling render() to plot the image with the drag handles on top.
        """
        # Already a contrast-stretched 8-bit image, do we need to convert to 'L'?
        self.image = (self.raw_image.convert('L'))
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
            logging.debug('redacting %s %s %s %s' % (dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()))
            draw.rectangle((dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()), fill=App.redact_colour)
        # Highlight suggested rectangles
        for dicomrect in dicomtransrectlist:
            logging.debug('highlighting %s %s %s %s' % (dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()))
            draw.rectangle((dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()), outline=App.outline_colour)
            draw.line([dicomrect.L(), dicomrect.T(), dicomrect.R(), dicomrect.B()], fill=App.outline_colour)
            draw.line([dicomrect.R(), dicomrect.T(), dicomrect.L(), dicomrect.B()], fill=App.outline_colour)
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

    def open_file_dialog(self):
        """ Gets a list of DICOM filenames,
        calls set_image_list(),
        calls load_next_file().
        """
        filenames = tkinter.filedialog.askopenfilenames(master=app,
            defaultextension=".dcm", multiple=1, parent=app,
            filetypes=(
                    (_("All files"), "*"),
                ),
                title=_("Select DICOM files"))
        self.set_image_list(FileList(filenames))
        self.load_next_file()

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
        Returns False if the user wants to quit.
        Returns True when the user has finished with this file.
        """
        # Loop over files already processed until we get a new file
        db = DicomRectDB()
        while True:
            filename = self.filelist.next()
            if not filename:
                return False
            if not self.skip_marked_files:
                break
            if not db.file_marked_done(filename):
                break
            logging.info('Ignore file already done: %s' % filename)

        try:
            self.dcm = DicomImage(filename)
        except:
            logging.warning('Cannot load DICOM from file "%s"' % filename)
            tkinter.messagebox.showerror(title="Help",
                message='Cannot load DICOM from file "%s"' % filename)
            return True

        # Loop through each frame/overlay in this file
        while True:
            self.raw_image = self.dcm.next_image()
            if not self.raw_image:
                #logging.error('ERROR: no image extracted from file')
                return True
            logging.debug('Loaded file %s having %d frames %d overlays %d frames in overlays' %
                (filename, self.dcm.get_num_frames(),
                self.dcm.get_num_overlays(),
                self.dcm.get_num_frames_in_overlays()))
            # Find out whether it's been redacted
            frame, overlay = self.dcm.get_current_frame_overlay()
            self.redacted_rects = db.query_rects(filename, frame=frame, overlay=overlay)
            # Look for similar files in the database
            # Keep a copy of them so user can Apply them later
            self.possible_rects = db.query_similar_rects(filename, self.dcm.get_selected_metadata(), frame=frame, overlay=overlay)
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
            ok = self.load_next_file()
            if not ok:
                break
            logging.debug('XXX done with file')
        logging.debug('XXX done all files, exit')
        return




# =====================================================================

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='DICOM Audit')
    parser.add_argument('-d', '--debug', action="store_true", help='debug')
    parser.add_argument('-q', '--quiet', action="store_true", help='quiet')
    parser.add_argument('--dump-database', action="store_true", help='show database content')
    parser.add_argument('--db', action="store", help='database directory')
    parser.add_argument('--review', action="store_true", help='review files already marked as done')
    parser.add_argument('-i', dest='infiles', nargs='*', default=[]) # can use: -i *.txt
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level = logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level = logging.WARNING)
    else:
        logging.basicConfig(level = logging.INFO)

    if not os.getenv('SMI_ROOT'):
        logging.error('$SMI_ROOT must be set, so we can write into data/dicompixelanon directory')
        exit(1)

    if args.db:
        database_path = args.db
    else:
        database_path = os.path.join(os.getenv('SMI_ROOT'), "data", "dicompixelanon/") # needs trailing slash
    DicomRectDB.set_db_path(database_path)

    if args.dump_database:
        db = DicomRectDB()
        db.query_all()
        exit(0)

    app = App()
    app.set_image_list(FileList(args.infiles))
    if args.review:
        app.set_skip_marked_files(False)
    app.run()
