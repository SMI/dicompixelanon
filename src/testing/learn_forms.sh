#!/bin/bash
# Given a list of DICOM filenames
#  determine whether it is a clinical image or a form, based on the tags,
#  and extract a JPEG into an appropriate directory
# Splits the files into training (first 80%) and validation directories.

datadir="/nfs/smi/home/smi/MongoDbQueries/Scanned_Forms"

cd $datadir

# Create JPEGs and save in either clinical or form directory
# depending on whether the Manufacturer is one which produces forms.

mkdir -p img/training/clinical
mkdir -p img/training/form
mkdir -p img/validation/clinical
mkdir -p img/validation/form

total=$(wc -l < random_per_manufacturer2.txt)
numtrain=$(expr $total '*' 8 / 10)
destdir="training"
count=0
cat random_per_manufacturer2.txt | while read dcm; do
    let count++
    if [ $count -gt $numtrain ]; then
        destdir="validation"
    fi
    if dcm2json $PACS_ROOT/$dcm | dicom_tag_string_replace.py | jq '.Manufacturer.Value[0], .ManufacturerModelName.Value[0]' | egrep -qi 'MASTERPAGE|BV Family|KEN MANTHEY|PACS Support PAH|Fluorospot Compact FD|null'; then
        dcm2jpg $PACS_ROOT/$dcm img/$destdir/form
    else
        dcm2jpg $PACS_ROOT/$dcm img/$destdir/clinical
    fi
done


wget -O "/home/abrooks/.cache/torch/hub/checkpoints/resnet18-f37072fd.pth" "https://download.pytorch.org/models/resnet18-f37072fd.pth" 

