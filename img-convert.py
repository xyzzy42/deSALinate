#!/usr/bin/env python3

# Wrapper around SAL utilities to decode a CGA image
# Copyright (C) 2026 Trent Piepho <tpiepho@gmail.com>

import amb
from pathlib import Path
import argparse

if __name__ == "__main__":

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Convert SAL CFA image file to PNG (or other format)",
        epilog="""
The output filename extension is used to determine the image format of the output.  The formats
supported depends on PIL, but at least PNG should work.

CGA has an unusual for today pixel aspect ratio of 5:6.  This is compensated for so that the
output images don't look stretched on a modern screen.  This can be turned off by using the "-1"
option to have the output pixels match the input pixels exactly as in the image.

The image is also blown up, since the resolution is quite small by modern standards and this
helps the aspect ratio correction work.  A scale of 1 can be used to get the original size.
""")

    parser.add_argument("input", help="Input File", type=Path)
    parser.add_argument("output", help="Output File", type=Path)
    parser.add_argument("-s", "--scale", help="Scale up image", type=int, default=3)
    parser.add_argument("-1", "--onetoone", help="Keep 1:1 input to output aspect ratio", action='store_true')
    args = parser.parse_args()


    img = amb.image(args.input)
    amb.image_save(img, args.output, scale=args.scale, keepaspect=args.onetoone)
