# OCR class
#   Can be initialised with 'tesseract' or 'easyocr'
#   Looks in $SMI_ROOT/data/tessdata and $SMI_ROOT/data/easyocr
#   for the language models, otherwise /usr/share and ~/.EasyOCR.
#   Will run OCR on a numpy array (or, if you know what you are
#   doing you could run on an image file).
#   Can return just the text, or an array of text string dicts
#   (which uses our Rect class to represent the bounding box).
#   Tesseract requires the 'tesseract' program be in $PATH
#     export PATH=/opt/tesseract/bin:$PATH


import logging
import numpy
import os
import shutil
try:
    import easyocr
except:
    logging.warning('OCR: easyocr module not available')
try:
    import pytesseract
except:
    logging.warning('OCR: tesseract module not available')
from rect import Rect
import cv2


class OCR:
    # Configuration
    easy_language = 'en'
    easy_cfg_dir = os.path.join(os.environ.get('SMI_ROOT', ''), 'data', 'easyocr')
    easy_gpu = True
    tess_path = '/opt/tesseract/bin'
    tess_language = 'eng'
    tess_dir = os.path.join(os.environ.get('SMI_ROOT', ''), 'data', 'tessdata')
    tess_cfg = "--psm 11"  # default is 3 but 11 tries harder to get text fragments
    confidence_threshold = 0.4
    min_string_length = 2

    # Static constants
    TesseractEngine = 1
    EasyOCREngine = 2
    Keras = 3

    def __init__(self, engine):
        """ engine can be one of the enums, or one of the names
        'tesseract' or 'easyocr'
        """
        if engine == OCR.TesseractEngine or engine == 'tesseract':
            self.engine = OCR.TesseractEngine
            # Tesseract initialisation
            self.tess_language = OCR.tess_language
            self.tess_dir = OCR.tess_dir
            self.tess_cfg = OCR.tess_cfg
            if not os.path.isdir(self.tess_dir):
                self.tess_dir = '/usr/share/tesseract-ocr/4.00/tessdata/'
            if not shutil.which('tesseract'):
                os.environ['PATH'] = OCR.tess_path + ':' + os.environ['PATH']
                if not shutil.which('tesseract'):
                    logging.warning('OCR: tesseract program not found')
            logging.debug('OCR: Using Tesseract(%s,%s,%s)' % (shutil.which('tesseract'), self.tess_language, self.tess_dir))
        elif engine == OCR.EasyOCREngine or engine == 'easyocr':
            self.engine = OCR.EasyOCREngine
            # EasyOCR initialisation
            self.easy_language = OCR.easy_language
            self.easy_gpu = OCR.easy_gpu
            self.easy_cfg_dir = OCR.easy_cfg_dir
            if not os.path.isdir(self.easy_cfg_dir):
                self.easy_cfg_dir = os.path.join(os.environ.get('HOME'), '.EasyOCR', 'model')
            logging.debug('OCR: Using EasyOCR(%s,%s,%s' % (self.easy_language, self.easy_gpu, self.easy_cfg_dir))
            self.easyreader = easyocr.Reader([self.easy_language], gpu=self.easy_gpu, model_storage_directory=self.easy_cfg_dir)
        else:
            raise RuntimeError('unsupported OCR engine')
        self.ocr_data = []
        self.ocr_text = ''

    def __repr__(self):
        return '<OCR engine=%s %s>' % (self.engine, self.ocr_text)

    def engine_name(self):
        if self.engine == OCR.TesseractEngine:
            return "tesseract"
        elif self.engine == OCR.EasyOCREngine:
            return "easyocr"
        else:
            raise RuntimeError('unsupported OCR engine')

    def image_to_data(self, img):
        """ Run OCR on an image, which must be a numpy array.
        Return an array of items found by OCR, each item being a dict
        { "text", "conf" (percent confidence), "rect" (a Rect object)}
        """
        results = []
        if self.engine == OCR.TesseractEngine:
            # default config is --psm 3 --oem 3
            # Help if noisy but not for our DICOMS: c1 = cv2.GaussianBlur(img, (3,3), 0)
            # Use 35 for surrounding regions but larger fails?
            # Use THRESH_BINARY or THRESH_BINARY_INV depending on which makes background white
            # cv2 cannot handle 4-byte grayscale so reduce to uint8
            if img.itemsize > 1:
                max = img.max()
                img = numpy.divide(img, (max+256)/256).astype(numpy.uint8)
            # AdaptiveThreshold only works with grayscale
            if len(img.shape) != 2:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            # Two options for adaptive threshold: cv2.THRESH_BINARY or cv2.THRESH_BINARY_INV
            #img_thresh = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 45, 2)
            # Histogram equalisation
            #img_thresh = cv2.equalizeHist(img)
            # Adaptive histogram equalisation
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            img_thresh = clahe.apply(img)
            # Invert to get black on white?
            #img_thresh = cv2.bitwise_not(img_thresh)
            # Save image for debugging
            #cv2.imwrite('thresh.png', img_thresh)
            res = pytesseract.image_to_data(img_thresh,
                lang=self.tess_language,
                output_type=pytesseract.Output.DICT,
                config='--tessdata-dir "%s" %s' % (self.tess_dir, self.tess_cfg))
            # tess returns a dict of arrays(!)
            for rec in range(len(res['text'])):
                if len(res['text'][rec]) < OCR.min_string_length:
                    continue
                results.append( {
                    'text': res['text'][rec],
                    'conf': float(res['conf'][rec]) / 100.0,
                    'rect': Rect(left = res['left'][rec],
                        right = res['left'][rec] + res['width'][rec],
                        top = res['top'][rec],
                        bottom = res['top'][rec] + res['height'][rec])
                })
        elif self.engine == OCR.EasyOCREngine:
            # cv2 cannot handle 4-byte grayscale so reduce to uint8
            if img.itemsize > 1:
                max = img.max()
                img = numpy.divide(img, (max+256)/256).astype(numpy.uint8)
            res = self.easyreader.readtext(img, paragraph=True)
            str = ''
            # bbox is returned as [ [left,top], [a,b], [right,bottom], [c,d] ]
            # XXX with paragraph=False the tuple includes conf
            # so we will assume it's done its own threshold and conf=1
            for (bbox, txt) in res:
                if len(txt) < OCR.min_string_length:
                    continue
                results.append( {
                    'text': txt,
                    'conf': 1.0, # XXX
                    'rect': Rect(left = bbox[0][0],
                        right = bbox[2][0],
                        top = bbox[0][1],
                        bottom = bbox[2][1])
                })
        else:
            raise RuntimeError('unsupported OCR engine')
        self.ocr_data = results
        return results

    def image_to_text(self, img):
        dat = self.image_to_data(img)
        str = ''
        for item in dat:
            if item['conf'] > OCR.confidence_threshold:
                str += item['text'] + ' '
        logging.debug('OCR: found "%s"' % str)
        self.ocr_text = str
        return str
