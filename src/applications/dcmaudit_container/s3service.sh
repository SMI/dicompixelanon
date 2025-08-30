#!/bin/bash
# Create a fake bucket and run a S3 server
mkdir -p s3/bucket1/study1/series1
echo "Hello World" > s3/bucket1/testfile.txt
rsync -a ../../../data/sample_dicom/*.dcm  s3/bucket1/study1/series1
docker run --rm -p 7070:7070 -v $(pwd)/s3:/s3 versity/versitygw:latest --access a --secret s posix --nometa /s3 &
