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

# Run with ces-run

You need the latest version of the ces-tools (specifically ces-pm-run having support for X11 applications).

Download the container:
```
ces-pull podman howff KEY ghcr.io/howff/dcmaudit:cpu
```

Mounts:
* The container needs to be able to read/write your `.dcmaudit/s3creds.csv` file so bind mount that directory.
* The container needs to be able to write to your home directory so you can save files (e.g. reports, CSV files)
but you can't mount your whole home directory as that would hide the container's downloaded models
so bind mount a `~/s3` directory.

If you don't have a safe_data directory because you are not in a research project then `mkdir -p ~/safe_data`.

The proxy environment variables are passed into the container by default so disable this with `--http-proxy=false`.

```
mkdir -p ~/s3
ces-pm-run --opt-file <(echo -v $HOME/.dcmaudit:/root/.dcmaudit -v $HOME/s3:/root/s3 --http-proxy=false) ghcr.io/howff/dcmaudit:cpu
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
