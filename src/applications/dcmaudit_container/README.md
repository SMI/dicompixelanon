# dcmaudit container

## Build

```
docker build --progress=plain --build-arg CACHEDATE=$(date +%N) -t dcmaudit .
```

(CACHEDATE must change each time to prevent docker cache keeping an old copy of a repo from git pull)

To build for use on a GPU change Dockerfile:
use `--extra-index-url https://download.pytorch.org/whl/cu118` (instead of `cpu`).

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

If using the container execution service then you should use the following to ensure
that the S3 preferences file is saved in your home directory:
```
ces-pull podman USER TOKEN ghcr.io/howff/dcmaudit:cpu
ces-pm-run --opt-file <(echo -v $HOME/.dcmaudit:/root/.dcmaudit) ghcr.io/howff/dcmaudit:cpu
```

# VersityGW

If you need to run a test S3 server, try:
```
docker run --rm -p 7070:7070 -v /:/x versity/versitygw:v1.0.10 --access a --secret s posix --nometa /x &
```
Bucket name will be a directory name in `/`, access key and secret key are `a` and `s` respectively.
