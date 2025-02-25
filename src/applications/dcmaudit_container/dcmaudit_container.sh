#!/bin/bash

# Make sure docker doesn't create these as root
mkdir -p s3
touch s3/s3creds.csv

XSOCK=/tmp/.X11-unix
if expr match "$DISPLAY" "^:" > /dev/null; then
    # Unix domain sockets need a new Xauthority
    XAUTH=/tmp/.docker.xauth.$(id -u)
    xauth nlist "$DISPLAY" | sed -e 's/^..../ffff/' | xauth -f "$XAUTH" nmerge -
else
    # Network sockets and tunnels need real Xauthority, xhost, docker network
    XAUTH="$XAUTHORITY"
    xhost +local:docker
    export DISPLAY=$(echo $DISPLAY | sed 's/localhost/host.docker.internal/')
fi
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
