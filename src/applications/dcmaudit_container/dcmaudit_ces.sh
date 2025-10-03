#!/bin/bash

# If ces-tools has been checked out
export PATH=$HOME/src/ces-tools/ces-podman-cli:$HOME/src/ces-tools/ces-cli:$PATH

# If you need an interactive container
#interactive="-it --entrypoint /bin/bash"

# If you need debugging info
#debug="-v"

# If you don't have a safe_data directory
#mkdir -p ~/safe_data

# Somewhere to store downloaded CSV files
mkdir -p ~/s3

# If you haven't yet got a config file directory
mkdir -p ~/.dcmaudit

ces-pm-run $debug --opt-file <(echo -v $HOME/.dcmaudit:/root/.dcmaudit -v $HOME/s3:/root/s3 --http-proxy=false $interactive) ghcr.io/howff/dcmaudit:cpu
