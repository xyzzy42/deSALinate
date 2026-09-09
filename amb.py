# SAL decoding tools
#
# Copyright (C) 2026 Trent Piepho <tpiepho@gmail.com>
#
from pathlib import Path
import struct
import itertools
from enum import Enum
from typing import Literal, Optional, Callable, Sequence

def tokens(tokenfile:Path) -> Sequence[str]:
    """ Decode .TOK file, return list of tokens. """
    data = tokenfile.read_bytes()
    size, *offsets = struct.unpack_from("<h128h", data)
    start = struct.calcsize("<128h") + 2
    return [data[s+start:e+start-1].decode() for s, e in zip(offsets, offsets[1:] + [size-start])]

def detok(input:bytes, toks:Sequence[str]) -> str:
    """
    Detokenize a string.
    Stops at terminating NUL byte, which means it decodes the first string in
    `input` and stops.  There can be more data after the first string.
    Needs token list, from tokens(). """
    out = ""
    for b in input:
        if b == 0:
            return out
        if b & 0x80:
            out += f" {toks[b & 0x7f]}"
        else:
            out += chr(b)
    # No terminating NUL byte?!
    return out

def scene(file:Path, tokens:Sequence[str]) -> tuple[Sequence[str], bytes, int]:
    """
    Decode scene file.
    Needs token tabel for decompressing strings, as returned by `tokens()`.
    Returns detokenized list of strings, scene logic data, and offset of scene instructions in file.
    """

    data = file.read_bytes()
    # Four byte magic, then "01 09 00", then file size and string table size
    header = "<4x3xHH"
    headersize = struct.calcsize(header)
    fsize, ssize = struct.unpack_from(header, data)
    if len(data) != fsize:
        raise RuntimeError(f"File size {len(data)} doesn't match header size {fsize}")
    sdata = data[headersize:headersize+ssize]
    tablestart = headersize + ssize

    #offset = 0
    #strings:list[str] = []
    #offs:list[int] = []
    #while offset < size:
    #    string, length = detok(sdata[offset:], tokens)
    #    strings.append(string)
    #    offs.append(offset)
    #    offset += length + 1

    # Number of strings in table, followed by pointers to each string's start
    count, = struct.unpack_from("<H", data, offset=tablestart)
    table = struct.unpack_from(f"<{count}H", data, offset=tablestart+2)
    strings = [detok(sdata[o:], tokens) for o in table]

    if sdata.count(b'\0')-1 != count and sdata.count(b'\0') != count:
        # One NUL per string plus a double NUL to end table
        raise RuntimeError(f"String data has {sdata.count(b'\0')-1} strings but the table has {count}?")

    # Data that follows the string table.  Appears to mostly/entirely be the
    # sequencer program for the game logic in the scene.
    pstart = tablestart+2+count*2
    extra = data[pstart:]

    return strings, extra, pstart

type PartOfSpeech = Literal["noun", "pronoun", "conj", "dansep", "ppronoun",
    "listsep", "delim", "loneword", "verb", "adjective", "prep", "adverb", "article"]
PoSs:list[PartOfSpeech] = ["noun", "pronoun", "conj", "dansep", "ppronoun",
    "listsep", "delim", "loneword", "verb", "adjective", "prep", "adverb", "article"]

# Token ID to list of words with that ID
type TokenList = dict[int, list[str]]

# TokenLists for each part of speech
type Vocab = dict[PartOfSpeech, TokenList]

def vocab(file:Path, verbose=False) -> Vocab:
    """
    Decode the .V vocabulary file.
    Print out list if verbose is set.
    Returns Vocab data.  Each part of speech has a word list.  The word list is indexed by the
    token ID of the word for a given token ID is a list of words that have that ID (i.e., they
    are synonyms).
    """
    data = file.read_bytes()
    # First four bytes look like some kind of magic value.
    # Then index of start of each letters' words (26), plus punctuation (1), and then the total size (1)
    header = "<4x28H"
    index = struct.unpack_from(header, data)
    end = index[-1]
    if len(data) != end:
        raise RuntimeError(f"End of vocab at {end} in header but file is {len(data)} bytes")
    if index[0] != struct.calcsize(header):
        raise RuntimeError(f"Word list (start @ {index[0]:04x}) not after index (end @ {struct.calcsize(header):04x})")
    
    ids:Vocab = {p: {} for p in PoSs}
    def addword(word:str, tid:int, pos:int) -> None:
        pids = ids[PoSs[pos]]
        if tid in pids:
            pids[tid].append(word)
        else:
            pids[tid] = [word]

    i = index[0] # Start of "A" words, index[1] is start of 'B' words, etc.
    while i < end:
        slen = data[i]
        i += 1
        word, = struct.unpack_from(f"{slen}s", data, offset=i)
        i += slen
        word = word.decode("ASCII")
        last = False
        while not last:
            id, pos = struct.unpack_from("BB", data, offset=i)
            i += 2
            last = pos >> 4 == 8
            pos &= 0x7f
            addword(word, id, pos)
            if verbose:
                print(f"{word:11s} {':' if last else '.'} {id:02x} {PoSs[pos]}")
    # Add the ID used to indicate an unknown word
    for pos in ids.values():
        pos[max(pos.keys())+1] = ["*UNK*"]
    return ids

def trace(file:Path) -> Sequence[str]:
    """
    Decode the trace debug word list.
    This is used by the game's trace feature to display the sequencer program
    Returns list of opcode nodes.
    """
    data = file.read_bytes()

    # 4 byte magic value.  Then length of string data.
    size, = struct.unpack_from("<4xH", data)
    start = 6
    end = size+start

    # Number of strings in string data, then offsets of each string's start
    count, = struct.unpack_from("<H", data, offset=end)
    index = struct.unpack_from(f"<{count}H", data, offset=end+2)

    if end + 2 + count*2 != len(data):
        raise RuntimeError(f"File size {len(data)} doesn't match string data {end} plus index {count*2 + 2}")

    return [data[i+start:data.index(b'\0', i+start, end)].decode("ASCII") for i in index]

def scenes(file:Path) -> Sequence[str]:
    """
    Read list of scene files from the .DIB file.
    """
    with open(file, "r") as f: return [n.rstrip() for n in f.readlines() if n != '\x1a']


# Extracted from AMB.T via trace(), above
OpP = Enum('OpP', [
    'NULL', 'p_toggle', 'p_goto', 'p_dense', 'p_sparse', 'TRUE', 'inteq', 'intge', 'intgt', 'intle',
    'intlt', 'refresh', 'streq', 'usreq', 'usrmem', 'vusreq', 'noun_is', 'objroom', 'vobjroom', 'objhave',
    'vobjhave', 'strclose', 'loadtable', 'patt_init', 'ifwind', 'picsoff' ])
OpA = Enum('OpA', [
    'NULL', 'a_toggle', 'a_goto', 'a_invoke', 'a_call', 'cast', 'create', 'intadd', 'intdec', 'intinc',             # 0
    'intset', 'more', 'newdata', 'nomore', 'pause', 'kpause', 'quit', 'restore', 'save', 'strmove',                 # 10
    'strprt', 'strprtn', 'strset', 'usrrnd', 'usrset', 'vintadd', 'vintset', 'vstrprt', 'vstrprtn', 'vstrset',      # 20
    'vusrset', 'getchar_nowait', 'setup', 'strget', 'strprts', 'vstrmove', 'color', 'remblank', 'upcase', 'flookup',# 30
    'chucktable', 'pattern', 'patt_end', 'patt_draw', 'prepare_to_invoke', 'objset', 'objget', 'vobjget', 'objdrop', 'vobjdrop', # 40
    'inventory', 'yes_no', 'spareact', 'musicoff', 'musicon', 'picoff', 'picon', 'traceoff', 'traceon', 'w_open',   # 50
    'show', 'clearpic', 'clearscreen', 'play', 'niplay', 'kill_music', 'end_game', 'parse' ])                       # 60
    
# Strings from "AMB" file.  Referenced from other scenes by setting high bit of string ID.
GLOBAL_STR = [ 'Try rephrasing this.', 'You cannot go that way.',
    'You do not have the ', 'You already have the ', 'You do not see that.', 'Dropped.', 'Taken.',
    "That doesn't help.", 'Your attempt fails.' ]

type BranchType = Literal["C", "G", "B"] | tuple[Literal["S"], int, int]
# Dict key is branch target address, value is dict with branch origin address and the branch type
type ComeFrom = dict[int, dict[int, BranchType]]

def decode(strings:list[str], data:bytes, loc=0x0, 
           quiet=False, comefrom:ComeFrom = {},
           t=trace(Path("AMB.T")), voc=vocab(Path("AMB.V")), scenes=scenes(Path("AMB.DIB"))) -> ComeFrom:
    """ 
    Attempt to decode the sequencer opcodes.
    Pass in the string list and the program data from scene()'s return value.
    The start location offset can be provided so that the instruction addresses match the
    location in the file or the location in memory when the scene is being run.

    Also uses the trace term list, vocabulary and scene list.  These will be read from files if
    not provided.

    Setting quiet will not print anything, but still return the comefrom data.  This allows
    a two pass mode to get backward jump addresses.
    """

    # Seems like there are two lists of opcodes, each begins with NULL
    aops = t[t.index('NULL', 1):]
    pops = t[:t.index('NULL', 1)]

    # Seems like variable 2 has the verb and 6 the noun, from the last parse.  Not sure if
    # there's sequencer code to put them there, and it might not always do the same thing, or if
    # that's just where the parser puts them all the time.
    VPoS = { 1: voc['noun'], 2: voc['verb'], 3: voc['adverb'], 6: voc['noun'], 7: voc['noun'], 11: voc['noun'], 16: voc['loneword'] }

    found = set()       # Keep track of strings we find used somewhere

    i = 0 # Current position in data
    offset = 0 # Start of current instruction
    mode = 'P'
    start = True # Start of new sequence
    end = False # End of the sequence

    def prfrom(whence:int, how:BranchType) -> str:
        nonlocal loc
        if how == "G":
            return f"{whence+loc:04x}"
        elif how == "C":
            return f"↻{whence+loc:04x}"
        elif how == "B":
            return f"⌥{whence+loc:04x}"
        elif isinstance(how, tuple):
            if how[0] == 'S':
                if how[2] == -1:
                    return f"{whence+loc:04x}←??"
                words = VPoS.get(how[1])
                if words:
                    return f"{whence+loc:04x}←'{words[how[2]][0]}'"
                else:
                    return f"{whence+loc:04x}←{how[2]:02x}"
        return f"{whence+loc:04x}?"

    # Convert string ID to string
    def sidstr(sid:int, ex:str="") -> str:
        if ex.startswith('!'):
            if sid < len(GLOBAL_STR):
                return f"<{ex}{sid:02x}>{GLOBAL_STR[sid]}"
        return f"<{ex}{sid:02x}>{strings[sid]}"

    # Print an instruction.
    def pr(text:str="") -> None:
        nonlocal data
        nonlocal i
        nonlocal offset
        nonlocal start
        nonlocal end
        next = [f"{d:02x}" for d in data[i:i+2]]
        ops = [f"{d:02x}" for d in data[offset:i]]

        if start: ch = ' '
        else: ch = '|'
        if offset in comefrom:
            print(f"{ch}     ↙ {" ".join(prfrom(o, b) for o, b in comefrom[offset].items())}")

        if start: ch = '⮦'
        elif end: ch = '⮡'
        else: ch = '⍿'
        print(f"{ch} {offset+loc:04x} | {data[offset-1]:02x} ← ", end='')
        for j, block in enumerate(itertools.batched(ops, 8)):
            print(f"{"\n              " if j else ""}{" ".join(block):23s}", end='')
        print(f" → {" ".join(next):5s} {mode}: {text}")

    # Print extra instruction text
    def prtext(text:str) -> None:
        print(f"| {text}")

    # Quiet mode, just parse instructions
    if quiet:
        pr = lambda text="": None
        prtext = lambda text: None

    # Consume a 1 or 2 byte offset
    def getoffset() -> int:
        nonlocal data
        nonlocal i
        o = data[i]
        i += 1
        if o & 0x80:
            o = (o & 0x7f) << 8 | data[i]
            i += 1
        return o

    # Consume a 1 or 2 byte string ID
    def getstr() -> tuple[int, str]:
        nonlocal data
        nonlocal i
        ex = ""
        sid = data[i] & 0x7f
        if data[i] & 0x80: ex += "!"
        i += 1
        if sid & 0x40:
            ex += "+"
            sid = (sid & 0x3f) << 8 | data[i]
            if sid < 0x40:
                raise RuntimeError(f"Unexpected String ID {data[i-1]:02x} {data[i]:02x}")
            i += 1
        return sid, ex

    # Turn offset into string.  Follows the offset if it goes to a goto instruction.
    def offstr(o:int, base:Optional[int]=None, delta=True) -> str:
        if base is None: base = offset
        if base+o > len(data): note = " SEGFAULT"
        elif data[base+o] == 0: note = " RET"
        # Maybe we can always assume mode P after a jump?
        elif data[base+o] not in OpA and data[base+o] not in OpP: note = " ILL"
        elif data[base+o] == 0x02:
            # it's a goto
            next = data[base+o+1]
            if next & 0x80:
                next = (next & 0x7f) << 8 | data[base+o+2]
            note = f" ⇒ {offstr(next+1, base+o, False)}"
        else: note = ""
        prefix = f"+{o} " if delta else ""
        return f"{prefix}@{base+o+loc:04x}{note}"
        #return f"{prefix}{base+o:04x} (@{base+o+loc:04x}){note}"

    # Mark an address as the target of a jump instruction
    def jmptarget(where:int, what:BranchType, base:Optional[int]=None) -> None:
        nonlocal comefrom
        nonlocal offset
        if base is None: base = offset
        where += base
        if where not in comefrom: comefrom[where] = dict()
        comefrom[where][offset] = what

    while i < len(data):
        b = data[i]
        offset = i
        i += 1

        if end:
            start = True
            end = False

        try:
            op = OpA(b+1) if mode == 'A' else OpP(b+1)
        except ValueError:
            pr("Error")
            continue

        if op == OpA.strprt or op == OpA.strprtn:
            ss:list[str] = []
            i -= 1
            # Join print op sequences together
            while b == 0x14 or b == 0x15:
                i += 1
                sid, ex = getstr()
                found.add(sid)
                nl = "\n" if len(ss) > 0 and b == 0x14 else ""
                ss.append(f"{nl}{sidstr(sid, ex)}")
                b = data[i]
            pr(f"Print (length {len(ss)})")
            prtext("".join(ss))

        elif op in [OpA.vstrprt, OpA.vstrprtn]:
            f = data[i]
            i += 1
            pr(f"Print str {f:02x}")

        elif op == OpA.yes_no:
            sid, ex = getstr()
            f = data[i]
            found.add(sid)
            i += 1
            pr(f"Yes/No usr {f:02x} {sidstr(sid, ex)}")

        elif op in [OpA.vusrset, OpA.vintset, OpA.vstrset, OpA.usrset, OpA.objset, OpA.intset]:
            f = data[i]
            v = data[i+1]
            i += 2
            # Get usr, int, str type
            vartype = op.name[1:4] if op.name[0] == 'v' else op.name[0:3]
            pr(f"Set {vartype} {f:02x} = {vartype+' ' if op.name[0] == 'v' else ''}{v:02x}")

        elif op == OpA.strmove:
            f = data[i]
            i += 1
            sid, ex = getstr()
            found.add(sid)
            pr(f"Set str {f:02x} = {sidstr(sid, ex)}")
        elif op == OpA.vstrmove:
            f = data[i]
            v = data[i+1]
            i += 2
            pr(f"Set str {f:02x} = str {v:02x}")

        elif op in [OpA.intinc, OpA.intdec]:
            f = data[i]
            i += 1
            pr(f"{op.name[3:]} int {f:02x}")

        elif op in [OpA.vintadd, OpA.intadd]:
            f = data[i]
            v = data[i+1]
            i += 2
            pr(f"Add int {f:02x} += {"int " if op == OpA.vintadd else ""}{v:02x}")

        elif op == OpA.usrrnd:
            f = data[i]
            v = data[i+1]
            v2 = data[i+2]
            i += 3
            pr(f"Random usr {f:02x} = {v}-{v2}")

        elif op in [OpP.usreq]:
            f = data[i]
            v = data[i+1]
            i += 2
            o = getoffset() + 3
            jmptarget(o, 'B')
            word = VPoS[f][v] if f in VPoS else ""
            pr(f"Test {op.name[:3]} {f:02x} == {v:02x}, else {offstr(o)} {word}")

        elif op in [OpP.inteq, OpP.intgt, OpP.intge, OpP.intlt, OpP.intle]:
            f = data[i]
            v = data[i+1]
            i += 2
            o = getoffset() + 3
            jmptarget(o, 'B')
            pr(f"Compare int {f:02x} {op.name[3:]} {v}, else {offstr(o)}")

        elif op in [OpP.strclose, OpP.streq]:
            f = data[i]
            i += 1
            sid, ex = getstr()
            o = i - offset # Location based on start of offset byte
            o += getoffset()
            jmptarget(o, 'B')
            pr(f"{"Equal" if op == OpP.streq else "Close"} str {f:02x} to {sidstr(sid, ex)}, else goto {offstr(o)}")
            found.add(sid)

        elif op in [OpP.objroom, OpP.objhave]:
            f = data[i]
            i += 1
            o = getoffset() + 2
            jmptarget(o, 'B')
            word = voc['noun'][f]
            pr(f"{op.name[3:]}? obj {f:02x} else {offstr(o)} {word}")
        elif op in [OpP.vobjhave, OpP.vobjroom]:
            f = data[i]
            i += 1
            o = getoffset() + 2
            jmptarget(o, 'B')
            pr(f"{op.name[4:]}? obj usr {f:02x}, else {offstr(o)}")

        elif op in [OpA.vobjdrop, OpA.vobjget]:
            f = data[i]
            i += 1
            pr(f"{op.name[4:].capitalize()} obj usr {f:02x}")
        elif op in [OpA.objdrop, OpA.objget]:
            f = data[i]
            i += 1
            word = voc['noun'][f]
            pr(f"{op.name[3:]} obj {f:02x} {word}")

        elif op == OpP.p_dense:
            f = data[i]
            n = data[i+1]
            i += 2
            end = True
            dtable:list[int] = []
            for j in range(n+1):
                o = data[i] << 8 | data[i+1]   # big endian
                o += i - offset
                i += 2
                dtable.append(o)
                jmptarget(o, ('S', f, j if j != n else -1))
            pr(f"Dense usr {f:02x} ({len(dtable)-1} entries)")
            for j, o in enumerate(dtable):
                prtext(f"{'-' if j == len(dtable)-1 else j} ⇒ {offstr(o)}")
            del dtable

        elif op == OpP.p_sparse:
            f = data[i]
            n = data[i+1]
            i += 2
            end = True
            stable:list[tuple[int,int]] = []
            for _ in range(n):
                v = data[i]
                i += 1
                b = i - offset # Base for offset, from start of instruction
                o = getoffset() + b
                jmptarget(o, ('S', f, v))
                stable.append((v, o))
            b = i - offset
            default = getoffset() + b
            jmptarget(default, ('S', f, -1))
            pr(f"Sparse usr {f:02x} ({n} entries)")

            words = VPoS.get(f)
            for v, o in stable:
                word = words[v] if words else ""
                prtext(f"{v:02x} ⇒ {offstr(o)} {word}")
            prtext(f"-- ⇒ {offstr(default)}")
            del stable

        elif op == OpP.TRUE:
            o = getoffset()  # unused, but we need to decode the length
            pr(f"NOP")

        elif op == OpP.refresh:
            o = getoffset() + 1
            jmptarget(o, 'C')
            pr(f"Refresh? {offstr(o)}")

        elif op == OpP.usrmem:
            f = data[i]
            v = data[i+1]
            v2 = data[i+2]
            i += 3
            o = getoffset() + 4
            jmptarget(o, 'B')
            pr(f"Between usr {f:02x} {v:02x}–{v2:02x}, else {offstr(o)}")

        elif op == OpA.a_call:
            o = getoffset()
            jmptarget(o, 'C', 0)
            pr(f"Call {offstr(o, 0)}")
            # Not end, it can return to here
            # mode = 'P'
        elif op == OpA.prepare_to_invoke:
            f = data[i]
            i += 1
            # Not sure if this uses the scene list or not.
            pr(f"Prepare to Invoke {f:02x} '{scenes[f]}'")

        elif op == OpA.a_invoke:
            f = data[i]
            i += 1
            if f & 0x80:
                pr(f"Invoke {f:02x}")
            else:
                pr(f"Invoke {f:02x} '{scenes[f]}'")
            # I think a return goes back to the next instruction

        elif op == OpA.show:
            v = data[i]
            i += 1
            if v & 0x80:
                # theory is high bit indicates two byte value
                v = (v & 0x7f) << 8 | data[i]
                i += 1
            # high bit here too?
            f = data[i]
            i += 1
            p, ex = getstr()
            pr(f"Show {v},{f} {sidstr(p, ex)}")
            found.add(p)

        elif op == OpA.w_open:
            f = data[i]
            i += 1
            pr(f"Window Open {f:02x}")

        # Misc one byte argument actions
        elif op in [OpA.kpause, OpA.upcase, OpA.clearpic]:
            f = data[i]
            i += 1
            pr(f"{op.name} {f:02x}")

        # Misc no argument actions
        elif op in [OpA.newdata, OpA.inventory, OpA.setup, OpA.create, OpA.more, OpA.nomore, OpA.picon, OpA.picoff, OpA.quit, OpA.musicon, OpA.musicoff, OpA.traceon, OpA.traceoff, OpA.restore, OpA.save, OpA.chucktable]:
            pr(op.name)
            
        elif op == OpA.play:
            f, ex = getstr()
            found.add(f)
            pr(f"Play sound {sidstr(f, ex)}")

        elif op == OpP.ifwind:
            v = data[i]
            i += 1
            o = getoffset() + 2
            jmptarget(o, 'B')
            # Don't know the meaning of the value
            pr(f"If window {v}, else goto {offstr(o)}")

        elif op == OpP.noun_is:
            v = data[i]
            i += 1
            o = getoffset() + 2
            jmptarget(o, 'B')
            pr(f"Noun is {v:02x} '{voc['noun'][v]}', else goto {offstr(o)}")

        elif op == OpP.picsoff:
            o = getoffset() + 1
            jmptarget(o, 'B')
            pr(f"{op.name}, else goto {offstr(o)}")

        elif op == OpA.cast:
            p1 = data[i]
            v = data[i+1]
            p2 = data[i+2]
            v2 = data[i+3]
            i += 4
            pr(f"Cast usr {v:02x} from {PoSs[p1]} to {PoSs[p2] if p2 < len(PoSs) else "??"}")

        elif op == OpP.loadtable:
            sid, ex = getstr()
            o = getoffset() + 2
            jmptarget(o, 'B')
            pr(f"Loadtable {sidstr(sid, ex)}, else {offstr(o)}")
            found.add(sid)

        elif op == OpA.flookup:
            f = data[i]
            i += 1
            pr(f"Flookup {f:02x}")

        elif op == OpA.parse:
            i += 39 # Seems like it's this big?
            pr(f"Parse")

        elif b == 0x00:
            end = True
            pr("Return")
            mode = 'P'
        elif b == 0x01:
            pr("Toggle")
            mode = 'A' if mode == 'P' else 'P'
        elif b == 0x02:
            o = getoffset() + 1
            jmptarget(o, 'G')
            end = True
            pr(f"Goto {offstr(o)}")
            mode = 'P'
        else:
            # Undecoded instructions
            acode = "" if b >= len(aops) else aops[b]
            pcode = "" if b >= len(pops) else pops[b]
            if acode != "" or pcode != "":
                pr(f"Opcode {acode} {pcode}")

        start = False

    # Print strings that never got used
    if not quiet:
        unused = set(range(len(strings))) - found
        if unused:
            print("Unused strings:")
            for i in unused: print(f"<{i:02x}>{strings[i]}")

    return comefrom

def decode2(strings:list[str], data:bytes, loc=0x0, 
            t=trace(Path("AMB.T")), voc=vocab(Path("AMB.V")), scenes=scenes(Path("AMB.DIB"))) -> None:
    """ Two pass decode.
    First pass finds all the branch targets, second pass prints the program and annotates
    branch targets with data from the first pass.
    """

    comefrom = decode(strings, data, loc, quiet=True, t=t, voc=voc, scenes=scenes)
    decode(strings, data, loc, quiet=False, comefrom=comefrom, t=t, voc=voc, scenes=scenes)

from PIL import Image

def image(file:Path) -> Image.Image:
    """
    Decode an image file into a PIL image
    """
    data = file.read_bytes()

    pal, bg, count, height, width = struct.unpack_from("<BBhBB", data)

    if bg != 0:
        raise RuntimeError(f"Background/intensity value {bg} not supported")

    i = Image.new(mode="P", size=(width*2, height), color=0)
    # Low intensity CGA palettes 0 and 1
    cga = [[0,0,0, 0,0xaa,0, 0xaa,0,0, 0xaa,0x55,0],
           [0,0,0, 0,0xaa,0xaa, 0xaa,00,0xaa, 0xaa,0xaa,0xaa] ]
    i.putpalette(cga[pal])

    # Byte with four packed doublepixels into to 8x1 pixel image
    def toimage(p:int) -> Image.Image:
        block = bytearray(8)
        for n in range(4):
            color = p & 3
            block[7-2*n] = color
            block[6-2*n] = color
            p >>= 2
        return Image.frombytes(mode="P", size=(8,1), data=block)

    x = 0
    y = 0
    total = 0
    for t in itertools.batched(data[6:], 3):
        if x >= width*2:
            raise RuntimeError(f"Image finished but there's still data left")
        if len(t) == 2:
            total += 1
            t = (t[0], t[1], 0)
        else:
            total += 2
        c1, l, c2 = t
        l2 = l & 0x0f
        l1 = l >> 4
        for l, c in ((l1, c1), (l2, c2)):
            block = toimage(c)
            for n in range(l):
                i.paste(block, (x, y))
                y += 1
                if y == height:
                    y = 0
                    x += 8
    if count != total:
        raise RuntimeError(f"Expected {count} pixels but image finished with only {total}")

    return i

def image_save(img:Image.Image, filename:str, scale=3, keepaspect=True) -> None:
    # Scale up, but correct for CGA aspect ratio of 5:6
    if keepaspect:
        width = img.size[0] * scale
    else:
        width = img.size[0] * scale * 5 // 6
    img.resize((width, img.size[1] * scale), Image.Resampling.LANCZOS).save(filename)
