#!/usr/bin/env python3
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
import sys
from pathlib import Path
from importlib.util import find_spec

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
    """ A class which wraps several NLP engines for NER
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
        self.engine_model = 'undefined'
        self.engine_version = '0.0'
        if engine == 'spacy':
            if 'spacy' not in sys.modules:
                logging.error('spacy requested but not available')
                return
            # Default model is trf for spacy v3, or lg for spacy v2
            if not model:
                for trymodel in ['en_core_web_trf',
                    'en_core_web_lg',
                    'en_core_web_md',
                    'en_core_web_sm']:
                    if find_spec(trymodel):
                        model = trymodel
                        break
            self._engine_name = engine
            self.engine_model = model
            self.engine_version = spacy.__version__
            #self.engine_data_dir = os.path.join(os.environ.get('SMI_ROOT'), 'data', 'spacy_'+self.engine_version) # not needed yet
            logging.debug('Loading %s version %s with %s' % (self._engine_name, self.engine_version, self.engine_model))
            self.nlp = spacy.load(model)
        elif engine == 'flair':
            if 'flair' not in sys.modules:
                logging.error('flair requested but not available')
                return
            # default model is 'ner' but can use 'ner', 'ner-fast', 'ner-large', 'ner-ontonotes', etc.
            if not model:
                model = 'ner'
            self._engine_name = engine
            self.engine_model = model
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
            logging.debug('Loading %s version %s with %s from %s' % (self._engine_name, self.engine_version, self.engine_model, self.engine_data_dir))
            self.tagger = SequenceTagger.load(model)
        elif engine == 'stanford':
            if 'stanford_ner' not in sys.modules:
                logging.error('stanford_ner requested but not available')
                return
            self._engine_name = engine
            self.engine_model = model
            self.engine_version = stanford_ner.__version__
            self.engine_data_dir = None
            # '../../Stanford-NER-Python/stanford-ner/'
            stanford_path_list = [ os.getenv('CORENLP_DATA_ROOT', '.stanford_ner'),
                os.path.join(os.environ.get('SMI_ROOT','.'), 'data', 'stanford_ner'),
                os.path.join(os.environ.get('HOME'), '.stanford_ner')]
            for stanford_path in stanford_path_list:
                if os.path.isdir(stanford_path):
                    self.engine_data_dir = stanford_path
                    break
            # XXX temporary hack
            self.engine_data_dir = '../../Stanford-NER-Python/stanford-ner/'
            if not self.engine_data_dir:
                logging.error('stanford_ner requested but no data directory found')
                return
            logging.debug('Loading %s version %s with %s from %s' % (self._engine_name, self.engine_version, self.engine_model, self.engine_data_dir))
        elif engine == 'stanza':
            if 'stanza' not in sys.modules:
                logging.error('stanza requested but not available')
                return
            self._engine_name = engine
            self.engine_model = model
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
        else:
            logging.error('unknown NER engine %s (expected spacy/flair/stanford/stanza)' % engine)
            return

    def __repr__(self):
        return '<NER %s %s %s>' % (self._engine_name, self.engine_version, self.engine_model)

    def isValid(self):
        """ Returns True if the initialisation was successful for the given engine.
        """
        return self.engine_model != 'undefined'

    def engine_name(self):
        return self._engine_name

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

    for engine in ['stanza', 'spacy', 'flair', 'stanford', 'stanza']:
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
