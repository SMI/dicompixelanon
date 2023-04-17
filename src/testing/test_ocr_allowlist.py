import re
import argparse
from os import mkdir
from tqdm import tqdm

def is_in_allowlist(s, rules, verbose=False):
    """Checks if string matches any of the allowlist rules.

    Args:
        s (str): string to check
        rules (list): list of regex rules
        verbose (bool, optional): if true, print matches (defaults to False)

    Returns:
        boolean: True if s matches one of the allowlist rules, False o/w
    """
    for r in rules:
        try:
            if re.fullmatch(r, s) is not None:  # found match, s is allowlisted
                if verbose:
                    print(f"Full text match:\n{s}\n{r}\n\n")
                return True
        except re.error:
            print(re.error)
            print(f"problematic rule: {r}")
            exit()
    return False

def read_list_from_file(path):
    with open(path, "r") as f:
        l = f.read().split("\n")
    return l

def write_list_to_file(path, l):
    if len(l) > 0:
        with open(path, "w") as f:
            l.sort()  # sort alphabetically, makes analysis easier
            for s in l[:-1]:
                f.write(f"{s}\n")
            f.write(f"{l[-1]}")

def main(verbose, reduced):
    allowlist = read_list_from_file("../../data/ocr_allowlist_regex.txt")
    print(f"Loaded {len(allowlist)} rules.")
    pos = read_list_from_file("test_files_ocr_allowlisting/should_match.txt")
    neg = read_list_from_file("test_files_ocr_allowlisting/should_not_match.txt")
    if reduced:
        red = read_list_from_file("test_files_ocr_allowlisting/should_not_match_reduced.txt")
        neg += red
    false_pos = []
    false_neg = []
    for s in tqdm(pos):
        if not (reduced and s in red):
            if not is_in_allowlist(s, allowlist):
                false_neg.append(s)
    for s in tqdm(neg):
        if is_in_allowlist(s, allowlist, verbose):
            false_pos.append(s)
    # write results
    try:
        mkdir("test_files_ocr_allowlisting/test_results")
    except FileExistsError:
        pass
    write_list_to_file("test_files_ocr_allowlisting/test_results/false_positives.txt", false_pos)
    write_list_to_file("test_files_ocr_allowlisting/test_results/false_negatives.txt", false_neg)
    print(f"False positives: {len(false_pos)}\nFalse negatives: {len(false_neg)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='test_ocr_allowlist',
        description='Load samples, run against allowlist.'
    )
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="Print full text matches.")
    parser.add_argument("--reduced", action="store_true", default=False,
                        help="Indicates that the reduced set of allowlisting rules is used.")
    args = parser.parse_args()
    main(args.verbose, args.reduced)
    
