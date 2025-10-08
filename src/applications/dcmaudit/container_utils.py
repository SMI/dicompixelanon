#!/usr/bin/env python3
# Utilities to help when running code inside a container.
# Including:
#  how to check whether a particular directory is internal to the container
#  or mounted from outside meaning that if we write to it the files will be
#  available afterwards.

import os
import subprocess

def running_in_container():
    """ Return True if the process is running inside a container.
    NOTE this is only True if run in the container execution service
    which sets the 'container' environment variable to the runtime,
    e.g. "podman"
    """
    if os.environ.get('container', None):
        return True
    return False


def mounted_directories_list():
    """ Return a list of directories mounted into the container
    (also works outside containers too) ignoring the system directories
    like /dev etc.
    """
    dirs = []
    rc = subprocess.check_output(['mount'])
    for line in rc.decode().splitlines():
        mountpoint = line.split()[2]
        rootdir = mountpoint.split('/')[1]
        if not rootdir:
            continue
        if rootdir in ['boot', 'run', 'snap', 'proc', 'var', 'sys', 'dev']:
            continue
        dirs.append(mountpoint)
    return dirs


def directory_is_mounted(directory):
    """ Returns True if the given directory is mounted into the container
    or is a subdirectory of a mounted directory.
    """
    # This is not necessarily correct because of complications due to
    # the way things get mounted, hard links, symbolic links, etc.
    for path in mounted_directories_list():
        if directory.startswith(path):
            return True
    return False


def main():
    print('Mounted directories: %s' % mounted_directories_list())
    print('Home directory is mounted: %s' % directory_is_mounted(os.environ['HOME']))


if __name__ == '__main__':
    main()
