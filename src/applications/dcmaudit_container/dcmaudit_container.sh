#!/bin/bash

# Make sure docker doesn't create these as root
mkdir -p s3
touch s3/s3creds.csv

# Two ways to get a container able to access a service on the host:
#	--net=host \
#	--add-host=host.docker.internal:host-gateway \

XSOCK=/tmp/.X11-unix
XAUTH=/tmp/.docker.xauth.$(id -u)
xauth nlist "$DISPLAY" | sed -e 's/^..../ffff/' | xauth -f "$XAUTH" nmerge -
docker run --rm -it \
 --add-host=host.docker.internal:host-gateway \
 -e USER="$USER" \
 -e DISPLAY="$DISPLAY" \
 -e XAUTHORITY="$XAUTH" \
 -v $XSOCK:$XSOCK \
 -v $XAUTH:$XAUTH \
 -v $(pwd):/dicom \
 -v $(pwd)/s3:/root/.dcmaudit \
 dcmaudit "$@"
