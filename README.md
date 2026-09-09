# Spinnaker Adventure Language (SAL)

This was a system used for some text adventure games made by Trillium/Telarium
in the mid 80s.

AFAIK, no one has reverse engineered the virtual machine it used nor are there
any surviving examples of the source for a game using it.  While many other
systems have been decoded, notably those used by Infocom and Sierra in the same
era, this system remains unknown.

I've focused on the game *Nine Princes in Amber*, as it was the only one I had
as a child, and haven't looked into the similarities and differences between it
an the other SAL games.

## The Virtual Machine

Common for the era, whatever language the games was written in was "compiled"
into a program that ran on a virtual CPU, or sequencer.  It's not really much
like a real CPU, there are no loops, and more like I would call a sequencer.  It
runs a series of mid to high level instructions with branches and jumps.

I have reverse engineered a great deal of how it works, see [Detailed
information about SAL sequencer](./docs/sequencer.md)

The "scenes" of the game can be decoded with the `decode.py` program.  It will
print out a disassembly of the code.  It's annotate with source location of
jumps, words assigned to token ID when making comparisons, automatically follows
goto chains, etc.

## Images

The program `img-convert.py` will convert the CGA format images into modern
image files (e.g., PNGs).  I've only bothered to decode this image format, other
systems (C64, etc.) used different formats.

## Games

### *Nine Princes in Amber*

Information about how this games works, e.g. specific variables used for game
state and the details of the fencing game.

[Amber information](./docs/amber.md)
