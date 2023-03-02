import re
import argparse
from os import mkdir
from tqdm import tqdm

verbose = True

def is_in_whitelist(s, rules, verbose=False):
    """Checks if string matches any of the whitelist rules.

    Args:
        s (str): string to check
        rules (list): list of regex rules
        verbose (bool, optional): if true, print matches (defaults to False)

    Returns:
        boolean: True if s matches one of the whitelist rules, False o/w
    """
    for r in rules:
        try:
            if re.fullmatch(r, s) is not None:  # found match, s is whitelisted
                if verbose:
                    print(f"Full text match:\n{s}\n{r}\n\n")
                return True
        except re.error:
            print(re.error)
            print(f"problematic rule: {r}")
            exit()
    return False

def main(verbose):
    with open("../../data/ocr_whitelist_regex.txt", "r") as f:
        whitelist = f.read().split("\n")
        print(f"Loaded {len(whitelist)} rules.")
    with open("test_files_ocr_whitelisting/should_match.txt", "r") as f:
        pos = f.read().split("\n")
    with open("test_files_ocr_whitelisting/should_not_match.txt", "r") as f:
        neg = f.read().split("\n")
    false_pos = []
    false_neg = []
    for s in tqdm(pos):
        if not is_in_whitelist(s, whitelist):
            false_neg.append(s)
    for s in tqdm(neg):
        if is_in_whitelist(s, whitelist, verbose):
            false_pos.append(s)
    # write results
    try:
        mkdir("test_files_ocr_whitelisting/test_results")
    except FileExistsError:
        pass
    with open("test_files_ocr_whitelisting/test_results/false_positives.txt", "w") as f:
        false_pos.sort()  # sort alphabetically, makes analysis easier
        for s in false_pos:
            f.write(f"{s}\n")
    with open("test_files_ocr_whitelisting/test_results/false_negatives.txt", "w") as f:
        false_neg.sort()  # sort alphabetically, makes analysis easier
        for s in false_neg:
            f.write(f"{s}\n")
    print(f"False positives: {len(false_pos)}\nFalse negatives: {len(false_neg)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='test_ocr_whitelist',
        description='Load samples, run against whitelist.'
    )
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="Print full text matches.")
    args = parser.parse_args()
    main(args.verbose)
    