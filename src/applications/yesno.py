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
#  allow Prev button or Undo button
#  allow reading DICOM files
#  scale image to fit screen
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

def change_image(delta):
    global current_image, image_list
    if not (0 <= current_image + delta < len(image_list)):
        messagebox.showinfo('End', 'No more image.')
        return
    current_image += delta
    print('%d/%d   \r' % (current_image,len(image_list)), file=sys.stderr)
    image = Image.open(image_list[current_image])
    photo = ImageTk.PhotoImage(image)
    label['image'] = photo
    label.photo = photo

def answer(classification : int):
    print('%d,"%s"' % (classification, image_list[current_image]))

def yes(event_data):
    answer(1)
    change_image(+1)

def no(event_data):
    answer(0)
    change_image(+1)

# Construct the GUI
#  root window accepts keyboard shortcuts
root = tkinter.Tk()
root.bind("<n>", no)
root.bind("<y>", yes)
#  image is displayed in a 'label' widget
label = tkinter.Label(root, compound=tkinter.TOP)
label.pack()
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
