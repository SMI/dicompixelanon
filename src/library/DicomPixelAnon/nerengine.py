#!/usr/bin/env python3
""" The NER class encapsulates a variety of different NLP engines
allowing NER to be run on text to find possible PII.
"""
# NB export HF_HUB_OFFLINE=1  if using flair inside safe haven.
# SpaCy models can be installed from pip or as wheels.
# Flair models have to be downloaded and cached manually,
#  it will look in $FLAIR_CACHE_ROOT/.flair, $SMI_ROOT/data/flair,
#  and $HOME/.flair, for a file like ner-english/pytorch_model.bin, named
#  eg. 4f4cdab26f24cb98b732b389e6cebc646c36f54cfd6e0b7d3b90b25656e4262f
# Main program:
#  no arguments, runs through a set of test strings
#  argument: tests each NER with the given string

import logging
import os
import re
import sys
from pathlib import Path
from importlib.util import find_spec
from DicomPixelAnon.nerenum import NEREnum

# Try to import spacy
try:
    import spacy
except:
    pass

# Try to import flair
try:
    import flair
    from flair.data import Sentence
    from flair.models import SequenceTagger
except:
    pass

# Try to import stanford
try:
    import stanford_ner
except:
    pass

# Try to import the new Stanford
try:
    import stanza
except:
    pass


class NER():
    """ The NER class wraps several NLP engines for NER.
    It identifies named entities in text and assigns one of four
    classes: PER, LOC, ORG, MISC (but not all NER engines return
    all of those classes). It can be instantiated with one of the
    following engine names: spacy, flair, stanford, stanza, and
    ocr_allowlist. The latter is a set of regex rules trained on
    the OCR output from a set of CR and DX images which identify
    safe text, not PII text. The others are language models
    (which typically require some textual context to determine PII).
    """

    @staticmethod
    def spacy_entity_map(entity : str):
        """ Return a common entity type if likely to be PII, or None.
        Common types are PER (Person) LOC (Location) ORG (Organisation).
        """
        map = {'PERSON': 'PER',
            'PER': 'PER', # when trained on Wikipedia it returne PER
            'GPE': 'LOC',
            'LOC': 'LOC', # when trained on Wikipedia it returns LOC
            'DATE': 'MISC',
            'ORG': 'ORG'}
        return map.get(entity, None)

    @staticmethod
    def flair_entity_map(entity : str):
        """ Return a common entity type if likely to be PII, or None
        Common types are PER (Person) LOC (Location) ORG (Organisation).
        """
        map = {'PER': 'PER',
            'LOC': 'LOC',
            'MISC': 'MISC',
            'ORG': 'ORG'}
        return map.get(entity, None)

    @staticmethod
    def stanford_entity_map(entity : str):
        """ Return a common entity type if likely to be PII, or None
        Common types are PERSON, ORGANIZATION, DATE.
        """
        map = {'PERSON': 'PER',
            'DATE': 'MISC',
            'ORGANIZATION': 'ORG'}
        return map.get(entity, None)

    @staticmethod
    def stanza_entity_map(entity : str):
        """ Return a common entity type if likely to be PII, or None
        Common types are PERSON, ORGANIZATION, DATE.
        See https://stanfordnlp.github.io/stanza/ner_models.html
        """
        map = {
            'PER': 'PER',
            'PERSON': 'PER',
            'LOC': 'LOC',
            'LOCATION': 'LOC',
            'FAC': 'ORG',
            'ORG': 'ORG',
            'ORGANIZATION': 'ORG',
            'DATE': 'MISC'}
        return map.get(entity, None)


    def __init__(self, engine, model = None):
        self._engine_name = 'Undefined'
        self._engine_enum = 0
        self.engine_model = 'undefined'
        self.engine_version = '0.0'

        if engine == 'spacy':
            if 'spacy' not in sys.modules:
                logging.error('spacy requested but not available')
                return
            self._engine_enum = 10
            # Default model is trf for spacy v3, or lg for spacy v2
            if not model:
                for ii, trymodel in enumerate(['en_core_web_trf',
                    'en_core_web_lg',
                    'en_core_web_md',
                    'en_core_web_sm']):
                    if find_spec(trymodel):
                        model = trymodel
                        self._engine_enum = NEREnum.spacy_en_core_web_trf + ii
                        break
            self._engine_name = engine
            self.engine_version = spacy.__version__
            #self.engine_data_dir = os.path.join(os.environ.get('SMI_ROOT'), 'data', 'spacy_'+self.engine_version) # not needed yet
            logging.debug('Loading %s version %s with %s' % (self._engine_name, self.engine_version, model))
            self.nlp = spacy.load(model)
            # Mark this object as valid by updating value of model
            self.engine_model = model

        elif engine == 'flair':
            if 'flair' not in sys.modules:
                logging.error('flair requested but not available')
                return
            self._engine_enum = NEREnum.flair
            # default model is 'ner' but can use 'ner', 'ner-fast', 'ner-large', 'ner-ontonotes', etc.
            if not model:
                model = 'ner'
            self._engine_name = engine
            self.engine_version = flair.__version__
            self.engine_data_dir = None
            flair_path_list = [ os.getenv('FLAIR_CACHE_ROOT', '.flair'),
                os.path.join(os.environ.get('SMI_ROOT','.'), 'data', 'flair'),
                os.path.join(os.environ.get('HOME'), '.flair')]
            for flair_path in flair_path_list:
                if os.path.isdir(flair_path):
                    self.engine_data_dir = flair_path
                    break
            if not self.engine_data_dir:
                logging.error('flair requested but no data directory found')
                return
            flair.cache_root = Path(self.engine_data_dir)
            logging.debug('Loading %s version %s with %s from %s' % (self._engine_name, self.engine_version, model, self.engine_data_dir))
            self.tagger = SequenceTagger.load(model)
            # Mark this object as valid by updating value of model
            self.engine_model = model

        elif engine == 'stanford':
            if 'stanford_ner' not in sys.modules:
                logging.error('stanford_ner requested but not available')
                return
            self._engine_name = engine
            self._engine_enum = NEREnum.stanford
            self.engine_version = stanford_ner.__version__
            self.engine_data_dir = None
            # '../../Stanford-NER-Python/stanford-ner/'
            stanford_path_list = [ os.getenv('CORENLP_DATA_ROOT', '.stanford_ner'),
                os.path.join(os.environ.get('SMI_ROOT','.'), 'data', 'stanford_ner'),
                '../../Stanford-NER-Python/stanford-ner/',    # checked-out source tree
                '../../../Stanford-NER-Python/stanford-ner/', # checked-out source tree
                os.path.join(os.environ.get('HOME'), '.stanford_ner')]
            for stanford_path in stanford_path_list:
                if os.path.isdir(stanford_path):
                    self.engine_data_dir = stanford_path
                    break
            if not self.engine_data_dir:
                logging.error('stanford_ner requested but no data directory found')
                return
            # Mark this object as valid by updating value of model
            self.engine_model = model
            logging.debug('Loading %s version %s with %s from %s' % (self._engine_name, self.engine_version, self.engine_model, self.engine_data_dir))

        elif engine == 'stanza':
            if 'stanza' not in sys.modules:
                logging.error('stanza requested but not available')
                return
            self._engine_name = engine
            self._engine_enum = NEREnum.stanza
            self.engine_version = stanza.__version__
            self.engine_data_dir = None
            stanza_path_list = [ os.getenv('STANZA_DATA_ROOT', '.stanford_ner'),
                os.path.join(os.environ.get('SMI_ROOT','.'), 'data', 'stanza'),
                os.path.join(os.environ.get('HOME'), 'stanza_resources')]
            for stanza_path in stanza_path_list:
                if os.path.isdir(stanza_path):
                    self.engine_data_dir = stanza_path
                    break
            if not self.engine_data_dir:
                logging.error('stanza requested but no data directory found')
                return
            self.stanza_nlp = stanza.Pipeline('en',
                processors='tokenize,ner',
                download_method=None,
                dir=self.engine_data_dir)
            # Mark this object as valid by updating value of model
            self.engine_model = model

        elif engine == 'ocr_allowlist':
            # Default is $SMI_ROOT/data/dicompixelanon/ocr_allowlist_regex.txt
            self._engine_name = engine
            self._engine_enum = NEREnum.allowlist
            self.engine_model = model
            self.engine_version = '1.0.0' # XXX maybe timestamp of file?
            self.engine_data_dir = None
            ocr_allowlist_path_list = [ os.path.join(os.environ.get('SMI_ROOT','.'), 'data', 'dicompixelanon'),
                '../../data',
                '../../../data']
            for allowlist_path in ocr_allowlist_path_list:
                if os.path.isdir(allowlist_path):
                    self.engine_data_dir = allowlist_path
                    break
            if not self.engine_data_dir:
                logging.error('ocr_allowlist requested but no data directory found')
                return
            if not model:
                model = 'ocr_allowlist_regex.txt'
            ocr_allowlist_file = os.path.join(self.engine_data_dir, model)
            if not os.path.isfile(ocr_allowlist_file):
                logging.error('ocr_allowlist requested but no data file found (%s)' % ocr_allowlist_file)
                return
            self.ocr_allowlist_regex_list = []
            with open(ocr_allowlist_file) as fd:
                self.ocr_allowlist_regex_list = [re.compile(line.strip()) for line in fd.readlines()]
            # Mark this object as valid by updating value of model
            self.engine_model = model

        else:
            logging.error('unknown NER engine %s (expected spacy/flair/stanford/stanza/ocr_allowlist)' % engine)
            return

    def __repr__(self):
        return '<NER %s %s %s>' % (self._engine_name, self.engine_version, self.engine_model)

    def isValid(self):
        """ Returns True if the initialisation was successful for the given engine.
        """
        return self.engine_model != 'undefined'

    def engine_name(self):
        """ Returns the name (only) of the engine used to perform NER, e.g. "flair"
        """
        return self._engine_name

    def engine_enum(self):
        """ Returns an integer representing the NER engine, and possibly the
        language model used by that engine, e.g. 10 = SpaCy with TRF, 11 = SpaCy with LG.
        """
        return self._engine_enum

    def detect(self, text):
        """ Detect PII in the text and return a list of entites,
        where each entity is a dict {'text': the text, 'label': entity type}
        where the types are 'PER', 'LOC', 'ORG', 'MISC' only.
        Returns empty list if nothing detected.
        """
        if self._engine_name == 'spacy':
            entities = self.nlp(text).ents
            # en_core_web_sm/md/lg/trf has DATE,GPE,ORG,PERSON, etc
            # scispacy has others.
            entities_list = [ {'text':e.text, 'label':NER.spacy_entity_map(e.label_)}
                for e in entities if NER.spacy_entity_map(e.label_) ]
            return entities_list
        elif self._engine_name == 'flair':
            sentence = Sentence(text)
            self.tagger.predict(sentence)
            entities = sentence.get_spans('ner')
            # ner-english has 4 classes: PER,LOC,ORG,MISC
            entities_list = [ {'text':e.text, 'label':NER.flair_entity_map(e.get_label('ner').value)}
                for e in entities if NER.flair_entity_map(e.get_label('ner').value) ]
            return entities_list
        elif self._engine_name == 'stanford':
            # Returns [ ['str','CLASS'], ... ]
            entities = stanford_ner.stanford_ner(text, verbose=False, stanford_dir=os.path.abspath(self.engine_data_dir))
            entities_list = [ {'text':e[0], 'label':NER.stanford_entity_map(e[1])}
                for e in entities if NER.stanford_entity_map(e[1]) ]
            return entities_list
        elif self._engine_name == 'stanza':
            entities = self.stanza_nlp(text).entities
            entities_list = [ {'text':e.text, 'label':NER.stanford_entity_map(e.type)}
                for e in entities if NER.stanza_entity_map(e.type) ]
            return entities_list
        elif self._engine_name == 'ocr_allowlist':
            # Return the whole string as a MISC entity if it's not in the allowlist
            entities_list = [ {'text': text, 'label': 'MISC'} ]
            for pattern in self.ocr_allowlist_regex_list:
                # Use fullmatch to ensure whole string matches pattern
                if pattern.fullmatch(text):
                    entities_list = []
                    break
            return entities_list
        return []


def test_spacy():
    ner = NER('spacy')
    assert ner.isValid()
    assert ner.detect('Queen Elizabeth Hospital') == [{'label': 'PER', 'text': 'Queen Elizabeth Hospital'}]

def test_flair():
    ner = NER('flair')
    assert ner.isValid()
    assert ner.detect('Queen Elizabeth Hospital') == [{'label': 'LOC', 'text': 'Queen Elizabeth Hospital'}]

def test_stanford():
    ner = NER('stanford')
    assert ner.isValid()
    assert ner.detect('Queen Elizabeth Hospital') == [{'label': 'LOC', 'text': 'Queen Elizabeth Hospital'}]

def test_ocr_allowlist():
    ner = NER('ocr_allowlist')
    assert ner.isValid()
    assert ner.detect('PA ERECT') == []
    assert ner.detect('AP ERECT') == []
    assert ner.detect('NOT ERECT') == [{'label': 'MISC', 'text': 'NOT ERECT'}]


if __name__ == '__main__':
    persons = [
        "John", "James", "Smith", "John Smith", "Mr. Smith", "Dr. James"
    ]
    hospitals = [
        "hospital" ,
        "Ninewells Hospital" ,
        "Biggar Hospital" ,
        "Ndadmte Hospital" ,
        "Slow Hospital" ,
        "James Hospital" ,
        "King James Hospital" ,
        "Elizabeth Hospital" ,
        "Queen Elizabeth Hospital" ,
        "Queen Hospital" ,
        "King Hospital"
    ]

    def run(input):
        entities = ner_engine.detect(input)
        result = '[%d] %s' % (len(entities),
            '/ '.join([e['text'] for e in entities]))
        print('%s /FROM "%s"' % (result, input))

    for engine in ['spacy', 'flair', 'stanford', 'stanza']:
        ner_engine = NER(engine)
        if not ner_engine.isValid():
            continue
        print('============================= %s' % ner_engine)
        if len(sys.argv) > 1:
            run(sys.argv[1])
        else:
            run("McDonald,Ernest J 1308656131 TIS_ TIB: 1.8 SE Golden Jubilee National Hospital 15.05.50 22/06/2016 SIEMENS VFX9-4 / PV-Ven 2D THI / 3.08 MHz 10 dB / DR 55 SC 2 Map ETRS 3 VEL / 4.0 MHz 0 dB / Flow Gen PRF 867 /F 2 cmi LEFT SEV 7fps 6cm Fr84")
            run("WOOD GENERAL HOSPITAL MISS BETH LESLEY MCDONALD WEIGHT BEARING OFD 14 CM OFD 17.5 18 8 2  2 OFD 16")
            for person in persons:
                for hospital in hospitals:
                    input = 'We are taking %s to %s today.' % (person, hospital)
                    run(input)
