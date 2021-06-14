#! /usr/bin/python3
#
# Suck in a YAML file and spit it back out
#
# June-2021, Pat Welch, pat@mousebrains.com

import argparse
import yaml

parser = argparse.ArgumentParser()
parser.add_argument("fn", nargs="+", help="Input yaml files")
args = parser.parse_args()

for fn in args.fn:
    with open(fn, "r") as fp:
        print(fn)
        data = yaml.safe_load(fp)
        print(data)
