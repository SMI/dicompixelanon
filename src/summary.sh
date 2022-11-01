#!/bin/bash

modalities="OTHER NM PR MG DX RF XA OT CR PT SR US MR CT"

for modality in $modalities; do
  ./summary.py extract_BIA_from_${modality}.csv > extract_BIA_from_${modality}.csv.summary
  echo $(date) done $modality 
done

