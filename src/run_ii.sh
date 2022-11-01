#!/bin/bash
# Run IsIdentifiable against the given DICOM file (only)
# More than one filename can be given but it will run IsIdentifiable once
# for each file.
# make symbolic links in a temp dir to the list of files so that
# IsIdentifiable only needs to be started once on that temp dir.
# XXX problem is that the CSV report will have the wrong path names.

yaml=$SMI_ROOT/configs/smi_dataExtract.yaml

# Find the ii program in the $PATH, or in $SMI_ROOT, or in source tree
if [ "$(which ii)" != "" ]; then
    ii=$(which ii)
elif [ -f $SMI_ROOT/SmiServices/smi ]; then
    ii="$SMI_ROOT/SmiServices/smi is-identifiable -y $yaml"
else
    ii=../../IsIdentifiable/ii/bin/Debug/net6.0/ii
fi

# tessdir should be the parent of the tessdata directory
# use $TESSDATA_PREFIX, or $SMI_ROOT, or from the deb package.
if [ "$TESSDATA_PREFIX" != "" ]; then
    tessdir=$TESSDATA_PREFIX
    if [ -f $tessdir/eng.traineddata ]; then
        tessdir=$(dirname $tessdir)
    fi
elif [ -d $SMI_ROOT/data/tessdata ]; then
    tessdir=$SMI_ROOT/data
else
    tessdir=/usr/share/tesseract-ocr/4.00
fi

tmpdir=$(mktemp -d)
for file do
  filedir=$(dirname $file)
  filename=$(basename $file)
  if [ ! -d $filedir ]; then
    filedir=$PACS_ROOT/$filedir
  fi
  ln -s ${filedir}/${filename} ${tmpdir}/${filename}
done

# Run IsIdentifable on the temporary directory
${ii}  dir \
  -d ${tmpdir} \
  --pattern '*' \
  --tessdirectory $tessdir \
  --storereport

# Tidy up
rm -fr "${tmpdir}"

# eg. smi is-identifiable dir -d /beegfs-hdruk/extract/v12/PACS/2016/10/17/G516H31952747 --pattern 'CR.1.2.392.200036.9125.9.0.386861736.573905152.1050243015' --tessdirectory $SMI_ROOT/data/tessdata --storereport -y $SMI_ROOT/configs/smi_dataExtract.yaml
