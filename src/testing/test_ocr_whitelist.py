import re
import argparse
from tqdm import tqdm

verbose = True

def is_in_whitelist(s, rules):
    """Checks if string matches any of the whitelist rules.

    Args:
        s (str): string to check
        rules (list): list of regex rules

    Returns:
        boolean: True if s matches one of the whitelist rules, False o/w
    """
    for r in rules:
        try:
            if re.fullmatch(r, s) is not None:  # found match, s is whitelisted
                return True
        except re.error:
            print(re.error)
            print(f"problematic rule: {r}")
            exit()
    return False

def main(path, verbose):
    with open(path, "r") as f:
        ocr_text = f.read().split("\n")
        print(f"Loaded {len(ocr_text)} samples.")
    with open("../../data/ocr_whitelist_regex.txt", "r") as f:
        whitelist = f.read().split("\n")
        print(f"Loaded {len(whitelist)} rules.")
    redact = []
    for s in tqdm(ocr_text):
        if not is_in_whitelist(s, whitelist):
            redact.append(s)
        else:
            if verbose:  # NOTE: debugging purposes
                print(f"  {s} found in whitelist")
    print(f"Need to redact {len(redact)} out of {len(ocr_text)} samples.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='test_ocr_whitelist',
        description='Load samples from file, run against whitelist.'
    )
    parser.add_argument("path", help="file containing samples separated by newlines")
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="Output full text matches.")
    args = parser.parse_args()
    main(args.path, args.verbose)
    