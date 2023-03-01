#!/bin/bash
for csv in \
extract_BIA_from_OTHER.csv \
extract_BIA_from_NM.csv \
extract_BIA_from_PR.csv \
extract_BIA_from_MG.csv \
extract_BIA_from_DX.csv \
extract_BIA_from_RF.csv \
extract_BIA_from_XA.csv \
extract_BIA_from_OT.csv \
extract_BIA_from_CR.csv \
extract_BIA_from_PT.csv \
extract_BIA_from_SR.csv \
extract_BIA_from_US.csv \
extract_BIA_from_MR.csv \
extract_BIA_from_CT.csv \
; do
  ./random_combinations.py $csv
  if [ $? -ne 0 ]; then echo "ERROR in $csv"; exit 1; fi
done
