""" The s3url module provides helper functions for the specific URL format
which we use, i.e. instead of s3://bucket/path/to/key
we use s3://accesskey:secretkey@endpoint/bucket/path/to/key
where endpoint is host:port, so the http is implied (no https).
"""

import boto3
import io
import json
import logging
import pydicom
import re
import numpy as np
from PIL import Image


def s3url_is(url):
    """ Return True if it's an S3 URL """
    return 's3://' in url


def s3url_sanitise(url):
    """ Remove the access and secret for safety.
    """
    m=re.match('s3://([^:]*):([^@]*)@([^/]*)/([^/]*)/(.*)', url)
    if not m:
        return None
    return s3url_create(None, None, m.group(3), m.group(4), m.group(5))


def s3url_compare(url1, url2):
    """ Compare two URLs but ignore the access:secret part
    """
    return s3url_sanitise(url1) == s3url_sanitise(url2)


def s3url_parse(url):
    """ Parse our format of S3 URL:
    s3://access:secret@endpoint/bucketname/path/key
    NOTE this is different from normal s3 URLs because
    the endpoint comes before the bucket name.
    The endpoint can't have http:// prefix (or / suffix)
    so http is assumed (not https).
    Returns (access, secret, endpoint, bucket, key) or None
    """
    m=re.match('s3://([^:]*):([^@]*)@([^/]*)/([^/]*)/(.*)', url)
    if not m:
        return None
    return (m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))


def s3url_create(access, secret, endpoint, bucket, key):
    """ Create our format of S3URL.
    Can handle endpoint URLs which include http: by removing that prefix
    because we don't store the http:// in our URL format.
    """
    endpoint = endpoint.replace('https://','').replace('http://','').replace('/','')
    assert(':' not in access)
    assert('@' not in secret)
    assert('/' not in endpoint)
    assert('/' not in bucket)
    if not access or not secret:
        return f's3://{access}:{secret}@{endpoint}/{bucket}/{key}'
    return f's3://{access}:{secret}@{endpoint}/{bucket}/{key}'
