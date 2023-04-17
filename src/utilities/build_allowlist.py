import requests
import string
import json
import itertools
import argparse
from bs4 import BeautifulSoup
from bs4 import element

def parse_tag(tag):
    """Parse HTML tag holding abbreviation and its meaning into a dictionary entry.

    Args:
        tag (bs4.element.Tag): HTML tag to be parsed

    Returns:
        dict<str, list<str>>: dictionary with single entry mapping found abbreviation to list of its meanings
    """
    # go down to only navigable strings
    stringified = list(tag.stripped_strings)
    # split first element if necessary
    if ":" in stringified[0]:
        split = stringified[0].split(":")
        new_head = []
        for s in split:
            new_head.append(s.strip(" "))
        stringified = new_head + stringified[1:]
    parsed = []
    for s in stringified:
        # remove clutter
        s = s.replace(u"\xa0", " ")
        s = s.replace(u"\u200b", "")
        s = s.replace("\n", " ")
        # test for empty and meaningless strings
        s = s.strip("(")
        s = s.strip(" ")
        if s not in ["", ":", ",", "(", ")"]:
            parsed.append(s)
    if len(parsed) > 1:  # cannot hold mean
        return {parsed[0]: parsed[1:]}
    else:
        return {}

def parse_glossary_html(html_str):
    """Given HTML response string, parse abbreviations from it into a dictionary holding the abbreviation and its meaning if it is unambiguous.

    Args:
        html_str (str): HTML response

    Returns:
        dict: dictionary of extracted abbreviations as keys mapping to meaning (str -> str)
    """
    abb_dict = {}
    soup = BeautifulSoup(html_str, "html.parser")
    lists = soup.find_all("ul")
    list_of_abbrevs = lists[3]
    for child in list_of_abbrevs.children:
        if type(child) == element.Tag:  # o/w it's a NavigableString with content "\n"
            abb_dict |= parse_tag(child)
    return abb_dict

def get_raw_glossary_from_radiopaedia(write_to_file=True):
    """Send HTML request querying for the medical abbreviations on radiopaedia.org once for each letter, yielding HTML response.
    As this is technically scraping a website, this function should run only once to write the response to files.
    Subsequent work with the HTML response should be done using the get_raw_glossary_from_file function instead.
    
    Args:
        write_to_file (bool, optional): Whether to write the HTML response into a file in the data/radiology_glossary directory (highly recommended). Defaults to True.

    Yields:
        str: HTML response text
    """
    for letter in string.ascii_letters[:26]:
        r = requests.get(f"https://radiopaedia.org/articles/medical-abbreviations-and-acronyms-{letter}?lang=gb")
        if write_to_file:
            with open(f"../../data/radiology_glossary/raw/glossary_{letter}.html", "w") as f:
                f.write(r.text)
        yield r.text

def get_raw_glossary_from_file():
    """Read HTML response from files and yield content.
    """
    for letter in string.ascii_letters[:26]:
        with open(f"../../data/radiology_glossary/raw/abbreviations_{letter}.html", "r") as f:
            yield(f.read())

def store_glossary(abb_dict):
    """Store dictionary for later use.

    Args:
        abb_dict (dict): dictionary of abbreviations
    """
    with open("../../data/radiology_glossary/glossary.json", "w") as f:
        json.dump(abb_dict, f, indent=4)

def get_abbreviations_from_json(path):
    """Load abbreviations only (not their meanings) from JSON file holding a dictionary as produced by store_abbreviations_dict().

    Args:
        path (str): Path to JSON file

    Returns:
        list<str>: List of abbreviations
    """
    with open(path, "r") as f:
        d = json.load(f)
    return list(d.keys())

def numerical_regex():
    """Build hand-crafted list of regex rules for allowlisting commonly found strings containing digits.

    Returns:
        list: regex rules
    """
    # whenever we might expect 0, allow O or o as well
    dap_rule = r"[dD][aA][pP]( |:|: |=|\.|\.:)?( - )?(([Oo0-9]{1,2}\.[Oo0-9]{2})|[Oo0-9]{2}) e\([Oo0-9]\)( mGycm2)?"
    kv_rule = r"[kK][vV][pP]?( |:|: |=|\.|\.:)?[Oo0-9]{2,3} mAs( |:|: |=|\.|\.:)?[Oo0-9]{1,2}(\.[0-9]{2})?"
    rex_rule = r"[rR][eE][xX]( |:|: |=|\.|\.:)?([Oo0-9]{1,3}|([Oo0-9]{1,3})?( |\.)[Oo0-9]{2}\.[Oo0-9]{2}\.[Oo0-9]{2})"
    regex_numerical_rules = [dap_rule, kv_rule, rex_rule]
    combos = list(itertools.permutations(regex_numerical_rules))  # combinations of the three
    combo_separator = r"(:|\.| |: )?"
    for combo in combos:
        regex_numerical_rules.append(rf"({combo[0]}{combo_separator})?({combo[1]}{combo_separator})?{combo[2]}")
    return regex_numerical_rules

def build_regex(abbreviations, annotations, reduce=False):
    """Build case-insensitive regex rules for strings commonly found.
    Writes rules into file data/ocr_allowlist_regex.txt, separated by newlines.

    Args:
        abbreviations (list<str>): abbreviations
        annotations (list<str>): medical annotations
        reduce (bool, optional): whether to reduce the number of regex rules refering to the views and orientations. Defaults to False.
    """
    regex_rules = []
    regex_rules += numerical_regex()
    regex_rules.append(r"(?i)[123](of| of |of | of|/)[123]")  # image no.
    # view rules
    views = [r"(semi |semi-)?(erect|supine)", r"(weight |wt |weight-|weight)bearing", r"(hb|horizontal beam)( l| lateral|l)?", r"(sitting|standing)"]
    one_of_views_rule = r"(" + r"|".join(views) + r")"
    modes = [r"([lr]t?|(left|right))", r"(pa|ap)", r"(mobile|portable|port)", r"under trolley", r"(in )?resus"]
    if reduce:  # fewer permutations, resulting in the view always being the last element. Leads to some things not being allowlisted that could be.
        combos = itertools.permutations(modes)
        for combo in combos:
            rule = r"(?i)"
            for el in combo:
                rule += rf"({el} )?"
            rule += rf"{one_of_views_rule}"
            regex_rules.append(rule)
    else:
        combos = itertools.permutations(modes + [one_of_views_rule])
        for combo in combos:
            rule = r"(?i)"
            for el in combo[:-1]:
                rule += rf"({el} )?"
            rule += rf"{combo[-1]}"
            regex_rules.append(rule)
    rotations_rule = r"(?i)(r |l )?(ext|int)(ernal)?(( |-)rot(ation)?)?( r| l)?"
    regex_rules.append(rotations_rule)
    for an in annotations:
        regex_rules.append(rf"(?i){an}")
    for ab in abbreviations:
        regex_rules.append(rf"(?i){ab}")
    with open("../../data/ocr_allowlist_regex.txt", "w") as f:
        for r in regex_rules[:-1]:
            f.write(f"{r}\n")
        f.write(f"{regex_rules[-1]}")

def main(fetchbuild, build, reduce):
    if fetchbuild or build:  # rebuild glossary dictionary
        glossary_dict = {}
        if fetchbuild:
            for html_response in get_raw_glossary_from_radiopaedia(write_to_file=True):
                glossary_dict |= parse_glossary_html(html_response)
        elif build:
            for html_response in get_raw_glossary_from_file():
                glossary_dict |= parse_glossary_html(html_response)
        store_glossary(glossary_dict)  # for later use
    allowlist_annotations = ["red dot", "diabetes", "ankle", "elbow", "expiration", "knee", "little finger", "middle finger", "skull", "ring finger"]
    abbreviations_list = get_abbreviations_from_json("../../data/radiology_glossary/glossary.json")
    build_regex(abbreviations_list, allowlist_annotations, reduce) 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='build_allowlist',
        description='Build list of regular expressions allowlisting OCR output and write to file.'
    )
    parser.add_argument("--fetchbuild", action='store_true', default=False,
                        help="Fetch glossary from radiopeadia.org to build local glossary.  Only do this if it is absolutely necessary, it usually won't be.")
    parser.add_argument("--build", action="store_true", default=False,
                        help="Build local glossary from HTML files in data/radiology_glossary/raw.")
    parser.add_argument("--reduce", action="store_true", default=False,
                        help="Produces reduced number of regex rules refering to view and orientation from 3692 to 3092.")
    args = parser.parse_args()
    main(args.fetchbuild, args.build, args.reduce)
