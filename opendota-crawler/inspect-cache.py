#!/usr/bin/env python

from __future__ import print_function
import argparse
import pickle
from pprint import pprint

def main():
    parser = argparse.ArgumentParser(description='Opendota match information')
    parser.add_argument('--file', type=str, required=True, help='Cache file path')
    args = parser.parse_args()

    file_path = args.file

    cache_file = open(file_path, 'rb')
    pprint(pickle.loads(cache_file.read()))

if __name__ == "__main__":
    main()
