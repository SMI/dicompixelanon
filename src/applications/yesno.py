#!/usr/bin/env python3
# Simply program to display a set of images and allow you to click
# Yes or No button (or keypress). The meaning is up to you!
# The output goes to stdout in a CSV format with two columns
# class 0=No, 1=Yes and filename.
# Usage: yesno.py filenames...
# if you only give one filename then it's treated as a text file
# containing a list of filenames, or a CSV file.
# To do:
#  proper command line arguments, esp. -i input -o output
#  allow Undo button
#  allow reading DICOM files
#  contrast adjustment
#  custom buttons
#  multi-frame images

import csv
import os
import sys
from PIL import Image
from PIL import ImageTk
import tkinter
from tkinter import messagebox

# Read list of images from command line
image_list = sys.argv[1:]
if len(image_list) < 2:
    filename = sys.argv[1]
    if '.csv' in filename or '.CSV' in filename:
        with open(filename) as fd:
            csvreader = csv.DictReader(fd)
            image_list = [row['filename'] for row in csvreader]
    else:
        with open(filename) as fd:
            image_list = fd.read().splitlines()

# Initialise list pointer
current_image = 0
image_data = None

def refresh_photo(photo):
    label['image'] = photo
    label.photo = photo

def change_image(delta):
    global current_image, image_list, image_data
    if not (0 <= current_image + delta < len(image_list)):
        messagebox.showinfo('End', 'No more images.')
        return
    current_image += delta
    print('%d/%d   \r' % (current_image,len(image_list)), file=sys.stderr)
    root.title(os.path.basename(image_list[current_image]))
    image_data = Image.open(image_list[current_image])
    max_width = root.winfo_screenwidth() - 150
    max_height = root.winfo_screenheight() - 150
    if image_data.width > max_width or image_data.height > max_height:
        image_data.thumbnail((max_width, max_height), Image.ANTIALIAS)
    photo = ImageTk.PhotoImage(image_data)
    refresh_photo(photo)

def resize_image(event_data):
    if not image_data:
        return
    photo = image_data.resize((event_data.width, event_data.height))
    refresh_photo(photo)

def answer(classification : int):
    print('%d,"%s"' % (classification, image_list[current_image]))

def yes(event_data):
    answer(1)
    change_image(+1)

def no(event_data):
    answer(0)
    change_image(+1)

def prev(event_data):
    change_image(-1)

# Construct the GUI
#  root window accepts keyboard shortcuts
root = tkinter.Tk()
root.title('yesno')
#root.geometry('400x400')
root.bind("<n>", no)
root.bind("<y>", yes)
root.bind("<p>", prev)
#  image is displayed in a 'label' widget
label = tkinter.Label(root, compound=tkinter.TOP)
label.pack()
#label.bind('<Configure>', resize_image)
frame = tkinter.Frame(root)
frame.pack()
#  buttons along the bottom
tkinter.Button(frame, text='Quit', command=root.quit).pack(side=tkinter.LEFT)
#tkinter.Button(frame, text='Previous picture', command=lambda: change_image(-1)).pack(side=tkinter.LEFT)
#tkinter.Button(frame, text='Next picture', command=lambda: change_image(+1)).pack(side=tkinter.LEFT)
tkinter.Button(frame, text='Yes', command=lambda: answer(1)).pack(side=tkinter.LEFT)
tkinter.Button(frame, text='No', command=lambda: answer(0)).pack(side=tkinter.LEFT)

# Start at first image
change_image(0)

# Run the GUI
root.mainloop()
