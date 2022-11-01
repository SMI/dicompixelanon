#!/bin/bash
# Extract a single column, eg. ManufacturerModelName
#  get a list of the unique values
#  and store in a file with the column name as a suffix.

modalities="OTHER NM PR MG DX RF XA OT CR PT SR US MR CT"

column="ManufacturerModelName"

#for f in extract_BIA_from_OTHER.csv extract_BIA_from_NM.csv extract_BIA_from_PR.csv extract_BIA_from_MG.csv extract_BIA_from_DX.csv extract_BIA_from_RF.csv extract_BIA_from_XA.csv extract_BIA_from_OT.csv extract_BIA_from_CR.csv extract_BIA_from_PT.csv extract_BIA_from_SR.csv extract_BIA_from_US.csv ; do csvx.py ManufacturerModelName $f | uniq | sort -u > $f.Model; echo done $f; done

for modality in $modalities; do
  f="extract_BIA_from_${modality}.csv"
  csvx.py $column $f | uniq | sort -u > ${f}.$column
  echo "Extracted 
done
