# SAL Sequencer

The SAL code is executed on a simple virtual CPU.  It's very similar to the system used for the
early Sierra games, [AGI](https://www.agidev.com/intro/).  The instructions are similar to what
a real CPU would have, but also somewhat different.

Opcodes are one byte.  Instructions are variable sized:  ranging from just one byte to many
bytes.  Most instructions have a fixed set of arguments, but for a few the arguments list is
variable length too.

A very strange thing about the virtual CPU is it appears to have two modes:  predicate mode and
action mode.

The mode determines how it interprets the opcode.  E.g., opcode 0x06 in action mode is `create`
and in predicate mode it is `inteq`.

Opcode 0x01 (in both modes) is `toggle`, a single byte instruction that switches between modes.

There are 68 action opcodes, which means the opcode fits into a single byte.  In fact, it fits
into 7 bits.  There are 91 unique opcodes total, which also fits into 7 bits.  So I can't see
any reason for the CPU to have two modes so that opcodes can be reused.  It takes 7 bits either way.

To disassemble the instructions correctly, we need to know both the start byte of the
instruction and the mode the CPU is in when it gets there.  Thankfully, branch instructions
appear to always switch to predicate mode following the jump, so a sequence of instructions will
always start in predicate mode.

#### Returns
The opcode 0 (`NULL`) appears to be a return opcode, which returns from the last `CALL` or
`INVOKE`.  Maybe it jumps to the start of the current file if the call stack is empty? 
Returning from an INVOKE will go to the start of the invoking (or main?) file, rather than to
the instruction after the invoke.  I.e., the invoke call stack doesn't store the origin address. 
It's not clear if multiple invokes can be stacked.

#### Invokes and Calls
The processor has a call stack.  A return from a `call` will return to the instruction after the
call.  The call instruction uses an absolute address from the start of the current file, rather
than a forward offset value as in a `goto` or conditional branch instruction.  Thus the `call`
instruction appears to be the only way to jump backward.

`invoke` is used to jump to another scene file.  It takes the ID of the scene file as its
argument and jumps to the first instuction in that file.  A return will go back to the calling
file.

## Arguments
There are few common types of arguments for instructions.  Some arguments can be one or two
bytes, e.g. short offsets vs long offsets.

#### String ID
Use to refer to strings in the scene file's string table, which starts at 0 and goes up.  The ID
can be one or two bytes.

Only the low 6 bits are used as the ID.  If the high bit is set, it means to use the string
table from the top level scene, i.e. `AMB`, and not the current string.  Common responses like,
"Dropped." or "Taken." do this.

If the 0x40 bit is set in the ID, then the next byte should be used to get the string ID.  E.g.,
`14 40 4c` encods print string `4c`.  This allows IDs larger than 6-bits to be encoded using two
bytes.

My guess is that the low six bits of the 1st byte are used too, to allow encoding values that
are more than 8-bits, but none of the scenes have enough strings to need that.  E.g., `4a bc`
would encode ID `abc`.  This is similar to how more than 8-bit offsets are encoded.

#### Offsets
Some instructions have jump offsets which appear to be one or two bytes long.  I'm not sure if
all offsets use this format, or if some instructions don't.  But it seems that at least most of
them do use this format.

If the high bit of the first offset byte is not set, then it's a one byte offset.  If the high
bit is set, then that byte and the next form the offset (big endian), with the high bit masked
off.  E.g.:  

`02 06 14`
: Goto with one byte offset, value is 0x06.  The 14 is not part of the instruction.  
`02 82 14`
: Goto with two byte offset, value is 0x0214.  The 14 is part of the instruction.  

The offset size does not affect the amount the PC is incremented by.  E.g., a goto will advance
to PC+offset+1 in both one-byte and two-byte forms.  Another way to describe this is that the
offset is relative to the 1st byte of the offset and not to the last byte.

I'm not sure if just the high bit is masked off, or the entire high nybble.  Haven't found a
goto with a jump greater than `0fff` to see what it does.

Sometimes there are small offsets that still use the two byte form, e.g. `80 34`, which would
seem to be the same as the one byte offset `34`.  I suspect this is a forward reference in the
source file and the assembler is a simple single-pass design.  There's a "goto label" statement
and the assembler doesn't know the address of "label" until it assembles all the code up to it,
so it doesn't know if it needs one or two bytes for the offset.  But it needs to assemble the
goto now so it can keep going.  The easy way is to just reserve the larger size for the offset,
even it ultimately it would have fit in a smaller offset.

## Variables
There appear to be four different types of variables used: `int`, `usr`, `obj`, and `str`.  
Opcodes that use variables have the type of the variable in their name, e.g. `intset`, `usrset`,
and `objset`.

Variables appear to be global, rather than local to a scene file.  But sometimes the same ID
will get re-used in a different scene for another purpose.  There's a "first run" flag variable
that gets used by the scene's program to initialize variables used by that scene the first time
it gets invoked.

#### Objects
Objects, which seems to be things you can have in your inventory, appear to share the same ID as
the corresponding nouns.  E.g., the noun with id 0x08 is "money", which is also the ID used to
put the money carried by the orderly into your inventory.

My guess is objects have flags to indicate if you have them in your inventory and also if their
appear when you use the `inv` command.

There are opcodes `objget` and `objdrop` which take only an object ID argument and appear to do
as the names implies.  But sometimes `objset` is used, which takes both an object ID and a value
to set it to.  Setting it to zero seems to be the same as dropping the object and 0x40 as
getting the object.

#### Integer and "usr"

Both `int` and `usr` variables are set to and tested against integer values.  It's not clear if
the same ID used with int vs usr instructions refers to the same variable or different
variables.  I think they are different.

While both types store integer values, only the int variables have less than, greater than, etc. 
comparison opcodes.  `usr` can only be tested for equality.  And only `int` has an add
instruction.  But `usr` has a "between" comparsion that tests if the value is between two
values, `int` doesn't have this comparision.  Also the random number instruction stores the
value into a `usr` variable not an `int`.

There is only an test for equal, not unequal.  This is efficient for minimizing the number of
opcodes, as both aren't needed.  Jumping over a goto on equal does the same thing as jumping
where the goto went on unequal.  But it's not efficient for the size of the compiled code, as
unequal effectively needs two instructions vs one.  In the same way, the full set of >, <, ≥,
and ≤ aren't needed.  Yet for these, there are all opcodes for all four, rather than the minimum
number.

#### String
I'm not sure what `str` variables do.  They don't seem to be used much.

It appears they can be used to hold the exact words entered in a command and repeat them back. 
While `usr` variables are used to hold the token ID of parsed words, a `str` variable holds the
entire string.  The game lexicon usually only stores the first four letters.  So the `str`
variable is used to repeat back a word you typed while the `usr` variable is used to check what
word it was by its ID.

#### Variables with Words
Some of the usr variables (perhaps the first 16?) are used in predicates to test for parsed
words.  It's not clear how the token IDs of words from the last parse end up in variables, and
if they are aways in the same variables.  It does seem to be consistent.  I suspect the many
arguments to the `parse` command control what variables the parsed sentence is placed into.

Identified variables and what kind of word they have:

|ID     | Type | Part of Sentence |
|-------|------|------------------|
|usr 00 | ??
|usr 01 | noun | Subject
|usr 02 | verb | Predicate
|usr 03 | adverb | Adverb.  E.g., "cut *high*", "thrust *low*"
|usr 06 | noun | Not sure about this one
|usr 07 | noun | Direct Object
|usr 0b | noun | Indirect Object
|usr 0c | ??
|usr 0d | ??
|usr 0e | ??
|usr 0f | ??
|usr 10 | loneword |
|str 02 | ??
|str 0b | ??
|str 0d | ??
|int 01 | ??

#### Word Token ID Order
The token IDs' of the words are not random.  The verbs appear to be in an order, with "action"
verbs in sequence and "conversation" verbs in another.  The friendly, hostile, and neutral
conversion verbs are also in sequence.  The game logic uses this, e.g. it might check for any
friendly conversion verb to trigger a path.

Word sequences that appear in tests in the code and their apparent meaning:

| Type |Range  | Contents |
|------|------:|:----------|
| Verb | 2b–5e | All communication verbs |
| Verb | 2b–35 | Hostile: kill, attack, challenge, accuse, betray, demand, ignore, insult, refuse, threaten |
| Verb | 36–3e | Friendly: flatter, calm, greet, hug, aid, enlist, join, offer, support |
| Verb | 3f–53 | Neutral: consult, say, discus, ask, why, bluff, admit, speak, tell, bribe, beg, agree, disagree, hello, maybe, answer, argue, persist, explain, flirt, thank |
| Verb | 55–57 | Hostile actions: sneer, snarl, spit, shout, yell, swear
| Verb | 58–59 | ally, bargain, negotiate |
| Verb | 91–95 | Fencing: parry, thrust, cut, feint, dodge
| Lone | 00–09 | Movement: north, south, east, west, up, down, back, away, around
| Lone | 11-23 | Game commands: save, restore, restart, etc.
| Noun | c2–ce | Names of siblings
| Noun | 00-0e | Objects that can be in inventory

#### Other Variables
Some variables seem to have been assigned a common use.  This is probably different for each game.  The ones
from *Amber* that I've identified:

|Variable|Use|
|-------:|:--|
|usr 33|Scene re-init on restore?
|usr 34|The scene to jump to.  The top level code will use this.  E.g. 0 will cause it to invoke "a:hospital"
|usr 3a|Scene init.  First run of scene is 1, scene then sets it to zero after initializing.
|usr 37|You died if set to 0.
|usr 38|Set to 1 to restart game.
|usr 3b|Set to 1 when returning from an invoke to indicate a scene has not used the command and a default response should be generated.
|usr 2d|Location inside scene.
|usr 2f|Difficulty Mode: Expert, Novice, and Moron.  Expert gives you fewer chances to do the wrong thing, Moron avoids some things, like fights.
|usr 3c|Won't let you save if this is nonzero.  Restarting executes 'chucktable' if this is 1.
|usr 3d|Won't let you save if this is nonzero.

## Predicates (conditional branches)
If a predicate is true, it will go to the next instruction.  If it's false, then the offset
argument is used as an offset to jump.  This is backward from how the conditional jumps in most
real CPUs are named (taking the jump when the condition is met).

The exact address jumped to (i.e., the base address the offset is from) appears to be based on
offset 0 corresponding to the first byte with the offset in it, and not the start of the
instruction nor the byte following the instruction, which would be more efficient.  E.g., in a
four byte `ifeq`, the offset byte is at PC+3, so on a false branch the PC will advance to
PC+3+offset.

An offset of 0 would jump into the current instruction and so is never used.  This is somewhat
helpful in determing if a disassembly is invalid.

Offsets appear to always be positive.  So there is no way to code a loop.  Even goto uses a
positive offset.

## Action Opcodes
|Opcode| Name           | Size | Arguments | Description|
|:-----|:---------------|:-----|:----------|:-----------|
|00 | NULL              | 1 | - | Returns from a call or invoke.  There's a stack.  Goes to the TOP of the current file when the stack is empty.
|01 | a_toggle          | 1 | - | Switch to predicate mode
|02 | a_goto            | 2-3 | [Offset] | Unconditional jump by Offset+1.  Seems to implicitly switch to predicate mode?
|03 | a_invoke          | 2 | [File ID] | Jump to 1st byte of the scene file with File ID (ID matches the .DIB list).
|04 | a_call            | 2 | [Offset] | Jump to Offset from start of file.  A return goes to the next instruction.  And apparently restores the mode too?
|05 | cast              | 5 | ?? | Something to do with changing how a word was parsed.
|06 | create            | 1 | - |
|07 | intadd            | 3 | [ID] [Value] | Add Value to int variable with ID
|08 | intdec            |
|09 | intinc            | 2 | [ID] | Add 1 to integer variable with ID
|0a | intset            |
|0b | more              | 1 | - | Often comes in a pair with `nomore`
|0c | newdata           | 1 | - | Display `NEWDATA` text file.  Appears to be hardcoded to the specific file name.
|0d | nomore            | 1 | - | Often comes in a pair with `more`
|0e | pause             |
|0f | kpause            | 2 | ?? | Seems to delay and wait for a key.  E.g., after knocking at Flora's door.
|10 | quit              | 1 | - | Leave game.  Doesn't return.
|11 | restore           | 1 | - | Restore a saved game.  Doesn't return.
|12 | save              | 1 | - | Save the game.  This does return.
|13 | strmove           | 3-4 | [ID] [String ID] | Move string with String ID into variable str ID.
|14 | strprt            | 2-3 | [String ID] | Print string from scene string table with preceeding newline.
|15 | strprtn           | 2-3 | [String ID] | Print string, without preceeding newline.
|16 | strset            |
|17 | usrrnd            | 4 | [ID] [Min] [Max] | Store a random value betwene Min and Max, inclusive, into usr var ID
|18 | usrset            | 3 | [ID] [Value] | Set variable with ID to Value
|19 | vintadd           | 3 | [ID L] [ID R] | Add the value of int variable R to the int variable L, i.e. L += R
|1a | vintset           | 3 |
|1b | vstrprt           | 2 | [ID] | Print word with in variable str ID, with newline
|1c | vstrprtn          | 2 | [ID] | Print word with in variable str ID, no newline
|1d | vstrset           | 3 |
|1e | vusrset           | 3 | [ID]? [Value]? | Set something.  First byte appears to be the id.  Maybe Value is the ID of the source variable?
|1f | getchar_nowait    |
|20 | setup             | 1 | - | Configure game for one or two floppy drives.
|21 | strget            |
|22 | strprts           |
|23 | vstrmove          | 3 | [ID Dest] [ID Src] | Copy string from str ID Src into str ID dst.
|24 | color             |
|25 | remblank          |
|26 | upcase            | 2 | [??] | Maybe alters the word from token ID argument?
|27 | flookup           | 2 | [Value] | Lookup and execute code from the `loadtable` table.  The Value relates to what is looked up.
|28 | chucktable        | 1 | - | Probably drops the table loaded by `loadtable`.
|29 | pattern           |
|2a | patt_end          |
|2b | patt_draw         |
|2c | prepare_to_invoke | 2 | [Value] | Maybe checks which floppy is inserted?  Seems like it sets usr 34 (hardcoded variable?) to Value.  That's used in the main code to select which scene to invoke.  Note that the value in usr 34 is not the same as the value suppled to `invoke` to run the scene.
|2d | objset            | 3 |
|2e | objget            |
|2f | vobjget           | 2 | [ID] | Get object in variable ID
|30 | objdrop           |
|31 | vobjdrop          | 2 | [ID] | Drop object in variable ID
|32 | inventory         | 1 | - | Print inventory.
|33 | yes_no            | 3 | [String ID] [USR ID] | Print string ID and give the 'Y', 'N', or 'R' prompt.  Store result into register with ID.
|34 | spareact          |
|35 | musicoff          |
|36 | musicon           |
|37 | picoff            | 1 | - | Disable images.  Clears the screen too.
|38 | picon             | 1 | - | Enable pictures
|39 | traceoff          | 1 | - | Dsiable sequencer debug trace.
|3a | traceon           | 1 | - | Enable sequencer debug trace.
|3b | w_open            | 2 | ?? | Something to do with the picture/text window?
|3c | show              | 4–5 | [X?] [Y] [String ID] | Draw a picture, given the String ID of the image file name.  X, Y might be where to draw it?
|3d | clearpic          | 2 | ?? | Clear image, e.g. when you die.  Argument seems to be related to the value used with ifwind.
|3e | clearscreen       |
|3f | play              | 2–3 | [String ID] | Play sound in file given by String ID
|40 | niplay            |
|41 | kill_music        |
|42 | end_game          |
|43 | parse             | 40? | ?? | Get input from user

## Predicate Opcodes
|Opcode| Name          | Size | Arguments | Description|
|:-----|:--------------|:-----|:----------|:-----------|
|00 | NULL              | 1 |- | Appears to be a "return" call
|01 | p_toggle          | 1 |- | Toggle to action mode
|02 | p_goto            | 2-3 | [Offset] | Jump Offset+1 bytes
|03 | p_dense           | 3+ | [ID] [Count] (Count*[Offset]) [Default] | A lookup table.  If the variable is 0, jumps to the first offset, 1 the next, and so on.  If the value greater than the last address, it uses the final default offset.  The offset is from the location of the offset (first byte for two byte offsets).
|04 | p_sparse          | 3+ | [ID] [Count] Count*([Value] [Offset]) [Default] | A lookup table, somewhat like dense.  Each of the Count entries is a value and offset to jump if the variable has that value.  The Default offset is taken if none matched.
|05 | TRUE              | 2-3 | [Offset] | Always true predicate, i.e. do nothing.  I suspect this is a commented out "goto" in the code.
|06 | inteq             | 4 | [ID [Value] [Offset] | Compare int ID to Value, jump by Offset+3 if false.
|07 | intge             |
|08 | intgt             |
|09 | intle             |
|0a | intlt             | 4 | [ID] [Value] [Offset] | Compare int to value
|0b | refresh           |
|0c | streq             | 4-6 | [ID] [String Id] [Offset] | Compare variable str ID to the string in the string table with String ID.  Jump to Offset if false.
|0d | usreq             | 4 | [ID] [Value] [Offset] | Test variable == Value, next instruction if true, jump Offset+3 bytes if false
|0e | usrmem            | 5 | [ID] [Min] [Max] [Offset] | Appears to test if variable is between Min and Max inclusive, jump to Offset+4 if false
|0f | vusreq            |
|10 | noun_is           | 3 | [Token ID] [Offset] | Compare last parsed noun's token ID to Token ID.  Jump Offset+2 if false.  Appears to check both direct and indirect object.
|11 | objroom           | 3 | ?? |
|12 | vobjroom          |
|13 | objhave           |
|14 | vobjhave          | 3 | [ID] [Offset] | Jump Offset+2 if you don't have the object with the ID in usr variable ID
|15 | strclose          | 4-6 | [ID] [String ID] [Offset] | Compare in some way the string in variable ID to string ID, if not "close" jump to offset + 3
|16 | loadtable         | 3 | [ID] [Offset] | Load table for fencing game with name from string ID.  Jump to Offset if loading fails.
|17 | patt_init         |
|18 | ifwind            | 3 | [??] [Offset] | Appears to test the graphics/text window in some way.  First argument might be window type?  0 = top, 1 = left?
|19 | picsoff           |
