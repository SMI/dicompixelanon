#!/usr/bin/env python3

# Requirements:
#  tqdm, torch, torchvision [matplotlib]
# You will need "https://download.pytorch.org/models/resnet18-f37072fd.pth"
# in "/home/arb/.cache/torch/hub/checkpoints/resnet18-f37072fd.pth"
# (it will be downloaded automatically if not already present).

# Usage:
#  create a CSV file containing two columns, class (integer) and filename
#  The filenames can be relative as a root_dir may be specified.
#  There should only be two classes 0 and 1 (but you can use more?)
#  All files should be DICOM, only first frame is used, it is converted
#  to greyscale when loaded (although training is done using a model
#  trained on RGB so greyscale is converted to RGB internally).

# References:
# Binary image classification:
#  https://towardsdatascience.com/binary-image-classification-in-pytorch-5adf64f8c781
# Uses dataset https://www.kaggle.com/datasets/biaiscience/dogs-vs-cats

# Alternatively, training for 10 classes with RGB images from CIFAR
#  https://pytorch.org/tutorials/beginner/blitz/cifar10_tutorial.html
# which references this (1-channel mono images):
#  https://pytorch.org/tutorials/recipes/recipes/defining_a_neural_network.html

import argparse
import csv
import json
import logging
import os
import sys
from DicomPixelAnon.torchdicom import ScannedFormDetector

logger = logging.getLogger(__name__)

# Command line parameters
parser = argparse.ArgumentParser(description='Detect scanned forms vs clinical images')
parser.add_argument('-d', '--debug', action="store_true", default=False, help='debug')
parser.add_argument('-m', '--model', dest='modelfile', action="store", default='learn_forms_model.pytorch.pth', help='filename to load/save trained model')
parser.add_argument('-r', '--rootdir', dest='rootdir', action="store", default=None, help='directory prefix for images')
parser.add_argument('-v', '--valcsv', dest='valcsv', action="store", help='CSV of validation images')
parser.add_argument('-i', '--image', dest='image', action="store", nargs='*', help='image to test (an image file or a DICOM file)')
args = parser.parse_args()
model_file = args.modelfile

rc = []
det = ScannedFormDetector(model_file)
if args.valcsv:
    rc = det.test_csv_file(args.valcsv, root_dir = args.rootdir)
if args.image:
    rc = det.test_image_list(args.image, root_dir = args.rootdir)
print(json.dumps(rc))
