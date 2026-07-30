#!/bin/bash
# Try to solve the problems of dcmaudit cannot start due to:
#   container already in use
#   container cannot be unmounted

# Try to remove the container
echo "* Trying to remove the container"
podman rm -f dcmaudit

if [ $? -ne 0 ]; then
    # Find out which path is preventing removal
    path=$(podman rm -f dcmaudit 2>&1 | grep -oE '/mnt[^ ]+merged' | head -n 1)
    # Try to unmount it (see podman issues 19913)
    echo "* Trying to unmount the container"
    podman unshare mount -t tmpfs none "${path}"
    # Try to remove container again
    echo "* Trying to remove the container"
    podman rm -f dcmaudit
    if [ $? -ne 0 ]; then 
        # Remove the offending directory
        echo "* Trying to remove the directory"
        rm -fr "${path}_backup"
        mv "${path}" "${path}_backup"
        # Try to remove container again
        echo "* Trying to remove the container"
        podman rm -f dcmaudit
    fi
fi
