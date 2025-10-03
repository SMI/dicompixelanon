#!/bin/bash
# Run the dcmaudit container via ces-run.
# This is needed because we need to map some directories and turn off the proxy.
# Edit this script to change interactive, debug, and maybe /safe_data
# although you shouldn't need /safe_data for dcmaudit.

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

# Make sure all bucket names (i.e. upto first comma) are lowercase
if [ -f ~/.dcmaudit/s3creds.csv ]; then
    sed -i 's/[^,]*,/\L&/' ~/.dcmaudit/s3creds.csv
fi

ces-pm-run $debug --opt-file <(echo -v $HOME/.dcmaudit:/root/.dcmaudit -v $HOME/s3:/root/s3 --http-proxy=false $interactive) ghcr.io/howff/dcmaudit:cpu
