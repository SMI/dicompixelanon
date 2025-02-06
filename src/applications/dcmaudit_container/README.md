# dcmaudit container

## Build

```
docker built -t dcmaudit .
```

## Push to registry

```
export CR_PAT=ghp_XXX
echo $CR_PAT | docker login ghcr.io -u USERNAME --password-stdin
docker tag dcmaudit ghcr.io/howff/dcmaudit:latest
docker push ghcr.io/howff/dcmaudit:latest
```

# Run

```
./dcmaudit_container.sh
```

The S3 credentials will be stored in the s3 directory.

Any DICOM files in the current directory will be visible inside /dicom when using dcmaudit.


# VersityGW

If you need to run a test S3 server, try:
```
docker run --rm -p 7070:7070 -v /:/x versity/versitygw:v1.0.10 --access a --secret s posix --nometa /x &
```
