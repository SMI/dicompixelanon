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
import os
import sys
from DicomPixelAnon.torchdicom import ScannedFormDetector

# Command line parameters
parser = argparse.ArgumentParser(description='Detect scanned forms vs clinical images')
parser.add_argument('-d', '--debug', action="store_true", help='debug')
parser.add_argument('-e', '--epochs', dest='epochs', action="store", default='20', help='number of epoch runs during training, or 0 to run only testing inference')
parser.add_argument('-m', '--model', dest='modelfile', action="store", default='learn_forms_model.pytorch.pth', help='filename to load/save trained model')
parser.add_argument('-r', '--rootdir', dest='rootdir', action="store", help='directory prefix for images')
parser.add_argument('-t', '--traincsv', dest='traincsv', action='store', default=None, help='CSV of training images')
parser.add_argument('-v', '--valcsv', dest='valcsv', action="store", default=None, help='CSV of validation images (can be same as traincsv for auto 80/20 split)')
args = parser.parse_args()

n_epochs = int(args.epochs)
model_file = args.modelfile

det = ScannedFormDetector(save_model_path = model_file)
rc = det.train_csv_file(train_csv_file = args.traincsv, test_csv_file = args.valcsv, n_epochs = n_epochs)
print('Training finished with accuracy %s %% on test images (%s/%s)' % (rc, det.infer_num_correct, det.infer_num_total))
