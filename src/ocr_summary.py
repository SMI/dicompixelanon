#!/usr/bin/env python3
# Reads ocr_random_combinations_files.sh_DX.csv.no_ovl.csv
# Finds the Manufacturers where all their images contained no text.

import csv
import pandas as pd

modality='CR'

# Read OCR results for non-overlay image frames (summaries not rects)
# NOTE must use na_filter=False to prevent empty string becoming NaN
# filename,frame,overlay,imagetype,manufacturer,burnedinannotation,ocr_engine,left,top,right,bottom,ocr_text,ner_engine,is_sensitive
df = pd.read_csv(f'ocr_random_combinations_files.sh_{modality}.csv.no_ovl.csv', na_filter=False)
print('Count of rows is:')
print(df.count()) # oops, count per column!
print('Just the ocr_text column:')
print(df.ocr_text[0:20])

# Calculated column containing length of the OCR text
df['ocr_len'] = df['ocr_text'].apply(len)
print('ocr_len col:')
print(df.ocr_len[0:20])

# Special case for empty strings where len(NA) should be 0 but was not!
# Find rows where ocr_text is NA and set ocr_len column to zero.
df.loc[ (pd.isnull(df.ocr_text)), 'ocr_len' ] = 0

df_text = df.ocr_text
print('Just the ocr_text column as a new df:')
print(df_text)

# Group by Manufacturer, then find those whose max(ocr_len)==0
df2 = df.groupby('manufacturer')['ocr_len'].max() == 0
print('df2 is grouped by Manuf where max(ocr_len)==0:')
print(df2)
print('Count is:')
print(df2.count())
print('All-empty Manufacturers:')
for f in df2[df2 == True].keys():
    print(f)

print('Short <10 strings:')
df3 = df.loc[df.ocr_len < 10]['ocr_text']
print(df3)

print('Long >10 strings:')
df3 = df.loc[df.ocr_len > 10]['ocr_text']
print(df3)

print('PII strings')
df4 = df.loc[df.is_sensitive == 1]
print(df4.ocr_text)
