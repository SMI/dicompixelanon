#!/bin/bash
# find the full path of a DICOM given its filename
dcm="$1"
dcm=$(echo $dcm | sed 's,\./,,') # strip off leading ./
for modality in DX CR; do
    path=$(grep "$dcm" $SMI_ROOT/MongoDbQueries/BurnedInAnnotations/extract_BIA_from_${modality}.csv | awk -F, '{print$2}')
    if [ "$path" != "" ]; then
        echo "$path"
        exit 0
    fi
done
exit 1
