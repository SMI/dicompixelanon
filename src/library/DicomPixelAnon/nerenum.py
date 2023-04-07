

class NEREnum:
    """ A class which holds the mappings between NER Engine names and enums.
    """
    spacy_en_core_web_trf = 10
    spacy_en_core_web_lg = 11
    spacy_en_core_web_md = 12
    spacy_en_core_web_sm = 13
    flair = 20
    stanford = 30
    stanza = 40
    whitelist = 50

    def __init__(self):
        """
        Note that some NER engines give the same name to multiple
        language models.
        """
        self._mapping = {}
        self._mapping[NEREnum.spacy_en_core_web_trf] = 'spacy'
        self._mapping[NEREnum.spacy_en_core_web_lg] = 'spacy'
        self._mapping[NEREnum.spacy_en_core_web_md] = 'spacy'
        self._mapping[NEREnum.spacy_en_core_web_sm] = 'spacy'
        self._mapping[NEREnum.flair] = 'flair'
        self._mapping[NEREnum.stanford] = 'stanford'
        self._mapping[NEREnum.stanza] = 'stanza'
        self._mapping[NEREnum.whitelist] = 'whitelist'

    def name(self, nerenum):
        """ Return the name (string) given an enum (integer).
        """
        return self._mapping.get(nerenum, None)

    def enum(self, name):
        """
        Return the enum (integer) given a name (string).
        Cannot distinguish between the different language models
        so just returns the first which matches (the default).
        """
        nerenum = -1
        for key in self._mapping:
            if self._mapping[key] == name:
                nerenum = key
        return nerenum

def test_NEREnum():
    assert(NEREnum().name(NEREnum.flair) == 'flair')
    assert(NEREnum().enum('flair') == NEREnum.flair)