#!/bin/bash
sqlite3 -separator , -cmd 'select * from DicomRects' dcmaudit.sqlite.db < /dev/null
