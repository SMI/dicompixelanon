#!/bin/bash
# Install dcmaudit into the user's home directory:
# 1. Download the dcmaudit:cpu container image.
# 2. Create ~/s3 which gets mapped into the container.
# 3. Create a dcmaudit.desktop file in ~/Desktop for running it.
# 4. Create ~/s3/dcmaudit.sh script which calls ces-run with suitable arguments.
# 5. If ces-pm-run is too old then use a temporary version.

s3dir=${HOME}/s3
runscript=${s3dir}/dcmaudit.sh
credsdir=${HOME}/.dcmaudit
credsfile=${credsdir}/s3creds.csv
GHCR="01mKxgty0Bnribv9rcLhCCqdG4hYhq16fTgH"

set -e

# Create the .desktop file
echo "Creating a desktop launcher"
cat <<_EOF > "${HOME}/Desktop/dcmaudit.desktop"
[Desktop Entry]
Name=dcmaudit
Comment=dcmaudit - view DICOM images
Exec=$runscript
Terminal=false
Type=Application
_EOF
chmod +x "${HOME}/Desktop/dcmaudit.desktop"

# Ensure we have a 's3' directory in our home directory
echo "Creating an s3 directory"
mkdir -p "${s3dir}"

# Ensure we have the credentials file directory ~/.dcmaudit
echo "Creating a directory to store credentials"
mkdir -p "${credsdir}"

# Ensure all credentials are lower-case in ~/.dcmaudit/s3creds.csv
echo "Updating credentials to lower-case"
if [ -f "${credsfile}" ]; then
    sed -i 's/[^,]*,/\L&/' "${credsfile}"
fi

# Check that CES tools are installed
echo "Checking for the Container Execution Service"
if [ ! -f "/usr/local/bin/ces-pull" ]; then
	echo "The CES tools have not been installed in /usr/local/bin; please raise a helpdesk ticket" >&2
	exit 1
fi

# Pull the container
echo "Downloading the container"
ces-pull podman howff 'ghp'_"$GHCR" ghcr.io/howff/dcmaudit:cpu

# Install a newer version of ces-pm-run to get X11 support
if grep -q 'VERSION="2.5.0"' /usr/local/bin/ces-pm-run; then
	# need a newer version than 2.5.0
	if [ ! -f /safe_data/tmp/dcmaudit/ces-pm-run ]; then
		echo "Error: we need a new version of ces-pm-run but it's not installed; please raise a helpdesk ticket" >&2
		exit 2
	fi
else
	if [ -f /safe_data/tmp/dcmaudit/ces-pm-run ]; then
		echo "Error: we have an old version of ces-pm-run in /safe_data/tmp; please raise a helpdesk ticket" >&2
		exit 3
	fi
fi

# Create the script to run dcmaudit from a container
echo "Creating a start-up script ($runscript)"
echo '#!/bin/bash' > "${runscript}"
echo "# Created $(date) by $0" >> "${runscript}"
echo 'export PATH=/safe_data/tmp/dcmaudit:${PATH}' >> "${runscript}"
echo 'ces-pm-run --opt-file <(echo -v $HOME/.dcmaudit:/root/.dcmaudit -v $HOME/s3:/root/s3 --http-proxy=false) ghcr.io/howff/dcmaudit:cpu' >> "${runscript}"
chmod +x "${runscript}"

# Finished
echo "OK - double-click on the dcmaudit icon on your desktop"
