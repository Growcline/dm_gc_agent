#!/usr/bin/env python3
"""Verify every image in an images/ folder carries the client's footer bar.

Usage: python3 check_footer.py IMAGES_DIR [IMAGES_DIR...]
       (checks against the Growcline kit in ../brand/brand.json)

Each PNG must have its html/<name>.html source (written by render.py), and that
source must contain the kit's footer bar colour and every footer item text.
Exits non-zero and lists the offending files if anything is missing.
"""
import glob
import json
import os
import sys


def main():
    args = [a for a in sys.argv[1:] if a != "growcline"]  # "growcline" accepted for the old CLIENT argument
    if not args:
        sys.exit("usage: check_footer.py IMAGES_DIR [IMAGES_DIR...]")
    kit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "brand", "brand.json")
    bar = json.load(open(kit_path, encoding="utf-8"))["footer_bar"]
    needles = [bar["color"]] + [item["text"] for item in bar["items"]]
    bad, total = [], 0
    for d in args:
        for png in sorted(glob.glob(os.path.join(d, "*.png"))):
            total += 1
            src = os.path.join(d, "html", os.path.basename(png)[:-4] + ".html")
            if not os.path.exists(src):
                bad.append(f"{png}: no html source (not rendered by render.py?)")
                continue
            doc = open(src, encoding="utf-8").read()
            missing = [n for n in needles if n not in doc]
            if missing:
                bad.append(f"{png}: missing {', '.join(missing)}")
    if bad:
        print("FOOTER CHECK FAILED\n" + "\n".join(bad))
        sys.exit(1)
    print(f"growcline footer OK on {total} image(s)")


if __name__ == "__main__":
    main()
