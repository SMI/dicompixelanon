# dcmaudit container

## Build

```
docker build --progress=plain --build-arg CACHEDATE=$(date +%N) -t dcmaudit:cpu -f Dockerfile .
docker build --progress=plain --build-arg CACHEDATE=$(date +%N) -t dcmaudit:gpu -f Dockerfile_gpu .
```

(CACHEDATE must change each time to prevent docker cache keeping an old copy of a repo from git pull)

The difference between building for CPU and for GPU is the pytorch repo `cpu` or `cu118`:
```
--extra-index-url https://download.pytorch.org/whl/cpu
--extra-index-url https://download.pytorch.org/whl/cu118
```

## Push to registry

```
export CR_PAT=ghp_XXX
echo $CR_PAT | docker login ghcr.io -u USERNAME --password-stdin
docker tag dcmaudit:cpu ghcr.io/howff/dcmaudit:cpu
docker tag dcmaudit:gpu ghcr.io/howff/dcmaudit:gpu
docker push ghcr.io/howff/dcmaudit:cpu
docker push ghcr.io/howff/dcmaudit:gpu
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
Bucket name will be a directory name in `/`, access key and secret key are `a` and `s` respectively.
