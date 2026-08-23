#!/usr/bin/env python3
# Decoder for SAL scenes
# Copyright © 2026 Trent Piepho <tpiepho@gmail.com>

import amb
from pathlib import Path
import argparse

if __name__ == "__main__":

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Decode SAL scene file")
    parser.add_argument("input", help="Input File", type=Path)
    parser.add_argument("-v", "--vocab", help="Vocabulary File", type=Path, default="AMB.V")
    parser.add_argument("-t", "--token", help="Token File", type=Path, default="AMB.TOK")
    parser.add_argument("-d", "--dib", help="Scene file list", type=Path, default="AMB.DIB")
    parser.add_argument("-l", "--location", help="Address of scene in memory", type=lambda x: int(x,0), default=None)
    args = parser.parse_args()

    tokens = amb.tokens(args.token)
    vocab = amb.vocab(args.vocab)
    scenes = amb.scenes(args.dib)

    strings, sal, offset = amb.scene(args.input, tokens)
    if args.location is None:
        args.location = offset

    amb.decode2(strings, sal, args.location, voc=vocab, scenes=scenes)
