

class OCREnum:
    """ A class which holds the mappings between OCR Engine names and enums.
    """
    TesseractEngine = 1
    EasyOCREngine = 2
    Keras = 3
    UltrasoundRegions = 4
    ScannedForm = 5

    def __init__(self):
        self._mapping = {}
        self._mapping[OCREnum.TesseractEngine] = 'tesseract'
        self._mapping[OCREnum.EasyOCREngine] = 'easyocr'
        self._mapping[OCREnum.Keras] = 'keras'
        self._mapping[OCREnum.UltrasoundRegions] = 'ultrasoundregions'

    def name(self, ocrenum):
        """ Return the name (string) given an enum (integer).
        """
        return self._mapping.get(ocrenum, None)

    def enum(self, name):
        """
        Return the enum (integer) given a name (string).
        """
        ocrenum = -1
        for key in self._mapping:
            if self._mapping[key] == name:
                ocrenum = key
        return ocrenum

def test_OCREnum():
    assert(OCREnum().name(OCREnum.EasyOCREngine) == 'easyocr')
    assert(OCREnum().enum('easyocr') == OCREnum.EasyOCREngine)