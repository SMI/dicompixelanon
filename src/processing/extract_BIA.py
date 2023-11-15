#!/usr/bin/env python3

# This will extract all the fields which might be used
# to indicate whether an image has PII burned into the pixels.
# The fields chosen are those identified by CTP's DicomPixelAnonymiser.script
# The output is CSV of every DICOM in every modality.
# You'll need to parse it afterwards to check the actual images!
# v2 - added NumberOfFrames, RecognizableVisualFeatures, BitsStored, BitsAllocated
# Usage: [modality or comma-separated list of modalities], default is all

import csv, os, re, sys, socket
import bson.json_util
import pymongo

# List of modalities in the image_OTHER collection:
other_collection = [ "PX", "IO" ]

modalities = [
  "PX",
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


def get_or(doc, key, valIfNone):
  """ using doc.get(key, valIfNone) might return None if key exists with value None,
  so we want to catch this and return valIfNone.
  """
  rc = doc.get(key, valIfNone)
  return rc if rc else valIfNone


def is_SecondaryCapture(doc):
  """ Check if doc looks like it might be a SecondaryCapture image.
  """
  # XXX see also the implementation in dicomimage.py
  sopclass = get_or(doc, 'SOPClassUID', '')
  is_SC = (sopclass.startswith('1.2.840.10008.5.1.4.1.1.7') or
    get_or(doc, 'SecondaryCaptureDeviceManufacturer', '') or
    get_or(doc, 'SecondaryCaptureDeviceManufacturerModelName', '') or
    get_or(doc, 'DateOfSecondaryCapture', ''))
  return is_SC


def fix_imagetype(imagetype, doc):
  """ If imagetype is empty then, if doc is SecondaryCapture, assume DERIVED/SECONDARY.
  Works on a simple string, so use it on the output of imagetype_summary.
  """
  # XXX see also the implementation in dicomimage.py
  if not imagetype:
    if is_SecondaryCapture(doc):
      imagetype = 'DERIVED/SECONDARY'
  return imagetype

def test_fix_imagetype():
  sc_doc = {'SOPClassUID': '1.2.840.10008.5.1.4.1.1.7.1' }
  assert(fix_imagetype('ORIG/PRIM', {}) == 'ORIG/PRIM')
  assert(fix_imagetype('', {}) == '')
  assert(fix_imagetype('', sc_doc) == 'DERIVED/SECONDARY')


def imagetype_summary(imtype):
  """ Return a /-separated string of the first two elements
  of the ImageType tag, so just ORIGINAL/PRIMARY even if
  the input is ORIGINAL/PRIMARY///STUFF/NONSENSE
  Input can be a list ['ORIG','PRIM'] or a string
  separated by a single backslash or two backslashes.
  After using this the string might still be empty so
  use fix_imagetype to guess a value.
  """
  ret = ''
  if not isinstance(imtype, list):
    # split on \\ first
    if r'\\' in imtype and not re.search(r'[^\\]+\\[^\\]+', imtype):
      imtype = imtype.split(r'\\')
    else:
      imtype = imtype.split('\\')
  if len(imtype) > 0:
    ret = imtype[0]
  if len(imtype) > 1:
    ret += '/' + imtype[1]
  return ret

def test_imagetype_summary():
  assert(imagetype_summary(r'X') == 'X')
  assert(imagetype_summary(r'X\Y') == 'X/Y')
  assert(imagetype_summary(r'X\\Y') == 'X/Y')
  assert(imagetype_summary(r'X\Y\Z') == 'X/Y')
  assert(imagetype_summary(r'DERIVED\SECONDARY\POST_PROCESSED\RT\\\\150000') == 'DERIVED/SECONDARY')
  assert(imagetype_summary(r'DERIVED\\SECONDARY\\POST_PROCESSED\\RT\\\\150000') == 'DERIVED/SECONDARY')
  assert(imagetype_summary(['X']) == 'X')
  assert(imagetype_summary(['X','Y']) == 'X/Y')
  assert(imagetype_summary(['X','Y','Z']) == 'X/Y')


def derived_model_name(Manufacturer,
      ManufacturerModelName,
      SecondaryCaptureDeviceManufacturer,
      SecondaryCaptureDeviceManufacturerModelName,
      SoftwareVersions):
  # XXX see also the implementation in dicomimage.py
  if not Manufacturer:
    Manufacturer = SecondaryCaptureDeviceManufacturer
  if not ManufacturerModelName:
    ManufacturerModelName = SecondaryCaptureDeviceManufacturerModelName
  if not ManufacturerModelName:
    ManufacturerModelName = Manufacturer + ' ' + SoftwareVersions
  if (not ManufacturerModelName) or (ManufacturerModelName == ' '):
    ManufacturerModelName = 'NoModel'
  return ManufacturerModelName.lstrip().rstrip()

def test_derived_model_name():
  assert(derived_model_name('man','mod','','','1.2') == 'mod')
  assert(derived_model_name('man','',   '','','1.2') == 'man 1.2')
  assert(derived_model_name('man','mod','scman','scmod','1.2') == 'mod')
  assert(derived_model_name('man','',   'scman','scmod','1.2') == 'scmod')
  assert(derived_model_name('',   '',   'scman','scmod','1.2') == 'scmod')
  assert(derived_model_name('',   '',   'scman','',     '1.2') == 'scman 1.2')


# ---------------------------------------------------------------------
if __name__ == '__main__':

  if len(sys.argv)>1:
    modalities = sys.argv[1].split(',')

  for modality in modalities:
    csv_file = 'extract_BIA_from_%s.csv' % modality
    collection = 'image_'+modality
    if modality in other_collection:
      collection = 'image_OTHER'
    print('Extracting %s from %s to %s' % (modality, collection, csv_file))
    coll = db[collection]
    out_fd = open('extract_BIA_from_%s.csv' % modality, 'w', newline='')
    out_csv = csv.writer(out_fd, quoting = csv.QUOTE_MINIMAL, lineterminator='\n')
    out_csv.writerow(['Modality','DicomFilePath','BurnedInAnnotation','RecognizableVisualFeatures',
      'Manufacturer','ManufacturerModelName','SoftwareVersions',
      'SecondaryCaptureDeviceManufacturer','SecondaryCaptureDeviceManufacturerModelName', 'ModelName',
      'CodeMeaning','CommentsOnRadiationDose','ImageType2','ImageType',
      'ImplementationVersionName','SeriesDescription','WindowWidth',
      'Rows','Columns','BitsStored','BitsAllocated','NumberOfFrames',
      'OverlayRows','OverlayColumns','OverlayType','NumberOfFramesInOverlay',
      'OverlayDescription','OverlayBitsAllocated','OverlayBitPosition',
      'ZeihmCreator', 'ZeihmImageCaptureData'])
  
    if collection == 'image_OTHER':
      cursor = coll.find( { "Modality" : modality } )
    else:
      cursor = coll.find( { } )
    for doc in cursor:
      file = doc['header']['DicomFilePath']
      mod = get_or(doc, 'Modality', modality)
      bia = get_or(doc, 'BurnedInAnnotation', 'NOBIATAG')
      rvf = get_or(doc, 'RecognizableVisualFeatures', 'NORVFTAG')
      man = get_or(doc, 'Manufacturer', '')
      model = get_or(doc, 'ManufacturerModelName', '')
      scman = get_or(doc, 'SecondaryCaptureDeviceManufacturer', '')
      scmodel = get_or(doc, 'SecondaryCaptureDeviceManufacturerModelName', '')
      swv = get_or(doc, 'SoftwareVersions', '')
      modelname = derived_model_name(man, model, scman, scmodel, swv)
      cm = get_or(doc, 'CodeMeaning', '')
      cord = get_or(doc, 'CommentsOnRadiationDose', '')
      imtype = get_or(doc, 'ImageType', '')
      imtype2 = fix_imagetype(imagetype_summary(imtype), doc)
      ivn = get_or(doc, 'ImplementationVersionName', '')
      sd = get_or(doc, 'SeriesDescription', '')
      ww = get_or(doc, 'WindowWidth', '')
      rows = get_or(doc, 'Rows', '')
      columns = get_or(doc, 'Columns', '')
      bitsstored = get_or(doc, 'BitsStored', '')
      bitsalloc = get_or(doc, 'BitsAllocated', '')
      numframes = get_or(doc, 'NumberOfFrames',1)
      orows = get_or(doc, "(6000,0010)-OverlayRows", '')
      ocols = get_or(doc, "(6000,0011)-OverlayColumns", '')
      otype = get_or(doc, "(6000,0040)-OverlayType",'')
      oframes = get_or(doc, "(6000,0015)-NumberOfFramesInOverlay", '')
      odesc = get_or(doc, '(6000,0022)-OverlayDescription', '')
      obits = get_or(doc, "(6000,0100)-OverlayBitsAllocated", '')
      obitpos = get_or(doc, "(6000,0102)-OverlayBitPosition", '')
      zeihmcreator = get_or(doc, '(0019,0010)-PrivateCreator', '') # is "ZIEHM_1.0 DeviceConfigData" ?
      zeihmimagecapture = get_or(doc, '(0019,1201:ZIEHM_1_0 ImageCaptureData)-Unknown', '') # is "Fluoro" ?
  
      out_csv.writerow([mod,
        file, bia, rvf, man, model, swv, scman, scmodel, modelname,
        cm, cord, imtype2, imtype, ivn, sd, ww, rows, columns,
        bitsstored, bitsalloc, numframes,
        orows, ocols, otype, oframes, odesc, obits, obitpos,
        zeihmcreator, zeihmimagecapture])
  
    out_fd.close()
