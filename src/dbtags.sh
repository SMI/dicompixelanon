#!/bin/bash
sqlite3 -separator , -cmd 'select * from DicomTags' dcmaudit.sqlite.db < /dev/null
