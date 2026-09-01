# Nine Princes in Amber
This is the one SAL game I had as a kid and the only one I've tried to decode so
far.  I was only about seven and never got past the fight with Julian.

This documents what I've learned from reverse engineering the game data.

## Amber Variables
These seem to be global variables that are used across scenes to track game
choices.  I haven't determined what exactly they do, and they might well
never get used again, but I haven't found a place where they are re-used
for a different part of the game logic.

|Variable|Description|
|--------|:----------|
|usr 2f|Mode: Expert, Novice, and Moron.  Expert gives you fewer chances to do the wrong thing, Moron avoids some things, like fights.
|usr 43|Kill the orderly in the hospital: 0 = unconscious, 1 = dead
|usr 21|Gerard's opinion of you at end of ship scene: 3 = hostile, 1 = neutral, 2 = friendly
|usr 26|Caught stealing Flora's Trumps: 0a = caught, 0b = not caught
|usr 42|Meet Random with Flora?: 1 = yes

## Fencing Game
My nemesis!  Got mad at the randomness as a kid and stopped playing the game.  As far as I can
tell now, it is in fact mostly random.  But there are better and worse things to do.

The game appears to mostly be implemented as a sequencer program.  The commands are parsed with
the same code as in other scenes.  The fencing scene's program looks are the parsed words and
decides what to do.  Thus the different fencing scenes could be almost totally different rules. 
However, I've decoded both the Julian and Eric fights, and they appear to be exactly the same
rules and logic.

But there is something different vs the other, less random, game scenes.  The initialization of
the scene uses the `loadtable` instruction to load the `.FEN` file and the scene program uses
the `flookup` instruction to determine and print out the results of a move.

### Scoring
This ends up being very simple.  Each round someone can get hit.  Get hit four times and you
lose, hit them four times you win.  You, Julian, and Eric all take four hits.

Hits can be to the head, side, or leg.  But it makes no difference other than what text is
printed.  They all count equally and don't appear to affect anything else.

At the end of each round, there's a 20% chance of a "bleeding" message being printed if someone
has been hit at least once.  It doesn't mean anything and doesn't indicate someone is getting
more hurt or is closer to losing. 

It will always reference the first place they are hit in the order:  head, side, leg.  The
chance is 20% no matter how many times hit or where the hits were.  The code is a bit
convoluted, and ultimately a lot of it is pointless, and don't think it's working as intended. 
Probably they intended it to randomly pick one of the places a combatant was hit and print a
message.

### The FEN File
This appears to be some sort of lookup table.  There are clearly sequencer opcodes in it.  When
`flookup` is run, it prints out the result of a move and the FEN file is full of 0x14 `strprt`
instructions combined with the string IDs of the move result strings ("Julian refuses to give
ground" and "as he lunges toward your head.")

But these instructions aren't inside subroutines with return statements or gotos at the end. 
There seems to mostly be one byte between each print and that byte makes no sense when
interpreted as an opcode.  I think the table might somehow encode the probabilities of the
possible outcomes for each action and `flookup` will randomly pick one of thos possibilities and
run its code.  Or perhaps it randomly picks a move for your opponent and then a matrix of your
move vs their move provides a table of results.

### Moves
It seems the fencing action you write is ultimately parsed into one of sixteen different
moves.  This move ID is the parameter to the `flookup` call.

|ID|Move|Note
|-:|:---|---|
|01| cut high
|02| cut low
|03| feint high
|04| feint low
|05| feint cut high
|06| feint cut low
|07| fient thrust high 
|08| fient thrust low 
|09| thrust high
|0a| thrust low
|0b| parry | Prints the same message as `parry parry`, but is a different move ID.
|0c| parry cut high
|0d| parry cut low
|0e| parry thrust high
|0f| parry thrust low
|10| parry parry | This has a 50% chance of you immediately dying or executing `flookup 10`. `parry` alone doesn't have this chance and is a different move ID too.

Omitting the `high` or `low` has the effect of randomly picking one of the two with equal
probability.  It's not a different move, such as some sort of middle attack.  Except for
`thrust` alone!  With that move, ommitting the adverb results in the move not parsing.  I think
it's a mistake in the code.  `parry thrust` and `feint thrust` are parsed correctly and randomly
pick high/low.

### Unparsed Moves
If you fail to use a verb from the allowed set, you die.  If you use a verb from the allowed
set, but otherwise produce an unparsed move (such as `cut forward`) then it's effectively a
pass.  You'll get, "You search for an opening," and it goes the next round without doing
anything.  There's no `flookup` call, no one can get a hit, etc.

### Special Moves
**Hadoken!**

Just kidding, you can't do that.  But there is a secret move to win the game in the fight with
Eric: a pun to summon a powerful advocate from an earlier game.

There are some other commands that are allowed, but don't use the moves from the table above and
thus don't use the `.FEN` file via `flookup`.

| Verb | Action |
|:-----|:-------|
| jump | Has a 40% chance of avoiding an attack and a 60% chance of dying.  You lose the advantage flag if you don't die.
| duck, dodge | Has a 40% chance of avoiding an attack and a 60% chance of dying.  This doesn't lose the advantage.
| attack, punch, hit | Prints a message and you lose the advantage flag.
| kill | Kamikaze attack; 20% chance of winning outright and 80% chance of dying.

Note that the actions that avoid an attack, `jump` and `duck`, don't benefit you at all.  If you
don't die, it's the same as going to the next round without doing anything, i.e. like an
unparsed command would do.  Maybe it allows you to "use up" a bad random number without getting
hit?  But not specifying "low" or "high" also uses up a random number, so there seems to be no
reason to ever use them.

### Having the Advantage

Variable usr 51 appears to have a flag that indicates you are "on the defensive" (0) vs
"pressing your advantage" (1).  It's better for it to be 1, which is where it starts.

You lose the advantage in a few ways:

* Using the "jump" move and not outright dying.
* Using the "attack" move.
* Using "parry" or "parry parry", i.e. parry *without* an attack.

Once you are on the defensive you must parry every round, or you die.  You can combine the parry
with an attack, i.e. moves 0b–10 are allowed.  There's code to set the advantage flag back to 1
if you don't use parry, but if you don't parry you die before getting there, so that branch is
unreachable and seems to be a bug in the game code.

### Variables
The following variables are used in the fencing game:

|Variable|Initial Value| Description|
|-------:|:-----------:|:-----------|
| usr 3a | 00 | "Need init".  If 1, does init code and sets to 0.  Can't find what would set it to 1.
| usr 51 | 01 | "Advantage Flag", relating to using `parry`.  1 is good, 0 means you are "defensive."
| int 0c | 00 | Initialized to zero, but never seems to be used.
| int 0e | 00 | Self hit: 0 none, 1 head, 2 rib, 3 leg
| int 0f | 00 | Julian/Eric hit: as above
| int 10 | 00 | Total self head hits
| int 11 | 00 | Total self rib hits
| int 12 | 00 | Total self leg hits
| int 13 | 00 | Total Julian head hits
| int 14 | 00 | Total Julian rib hits
| int 15 | 00 | Total Julian leg hits
| int 17 | - | Totals up hits when checking for winner, i.e. (10+11+12) or (13+14+15)
