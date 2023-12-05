#!/usr/bin/env python3

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
parser.add_argument('-j', '--json', action="store", default=None, help='output JSON file')
parser.add_argument('-m', '--model', dest='modelfile', action="store", default='learn_forms_model.pytorch.pth', help='filename to load/save trained model')
parser.add_argument('-r', '--rootdir', dest='rootdir', action="store", default=None, help='directory prefix for images')
parser.add_argument('-v', '--valcsv', dest='valcsv', action="store", help='CSV of validation images')
parser.add_argument('-i', '--image', dest='image', action="store", nargs='*', help='image to test (an image file or a DICOM file)')
args = parser.parse_args()
model_file = args.modelfile

rc = []
det = ScannedFormDetector(load_model_path = model_file)

if args.valcsv:
    rc = det.test_csv_file(args.valcsv, root_dir = args.rootdir)
if args.image:
    rc += det.test_image_list(args.image, root_dir = args.rootdir)

if args.json:
    with open(args.json, 'w') as fd:
        print(json.dumps(rc), file=fd)
print('Accuracy %s (%s / %s)' % (det.infer_accuracy, det.infer_num_correct, det.infer_num_total))
