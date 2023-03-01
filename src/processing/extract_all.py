#!/usr/bin/env python3

# This will extract all the fields which might be used
# to indicate whether an image has PII burned into the pixels.
# The fields chosen are those identified by CTP's DicomPixelAnonymiser.script
# The output is CSV of every DICOM in every modality.
# You'll need to parse it afterwards to check the actual images!
# v2 - added NumberOfFrames, RecognizableVisualFeatures

import csv,json,os,sys,socket
import bson.json_util
import pymongo

modalities = [
  "OTHER",
  "NM",
  "PR",
  "MG",
  "DX",
  "RF",
  "XA",
  "OT",
  "CR",
  "PT",
  "SR",
  "US",
  "MR",
  "CT",
];

client = pymongo.MongoClient('nsh-smi02', username='reader', password='reader', authSource='admin')
db = client['dicom']


for modality in modalities:
  collection = 'image_'+modality
  coll = db[collection]
  cursor = coll.find( { } )
  for doc in cursor:
    del doc['_id']
    print(json.dumps(doc, indent=2))
