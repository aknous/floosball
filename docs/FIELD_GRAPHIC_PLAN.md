# The Field Graphic — showing the game instead of summarising it

> Owner direction, 2026-08-26: *"there are many aspects about players that are just
> values to be read, but you cant actually see how fast a player is, how accurate a QB
> is, how agile they are. you cant see the defender intercept the ball."*

**The thesis.** The sim already choreographs every play — who covered whom, which gap the
back chose, how much separation the receiver had, which level he was stopped at, who made
the tackle. The field graphic then flattens all of it into a single line along the
midfield axis. The work is not to invent an animation; it is to **stop discarding the one
that already happened**.

## Status at a glance

| | state |
|---|---|
| Per-play semantics in the engine | **BUILT** — and mostly unemitted, see the table below |
| `play_choreography.py` — the script writer | **NOT BUILT** — the whole first phase |
| Formation + pre-snap phase (incl. the disguise reveal) | **NOT BUILT** — offence is READ from the call (23 packages), defence derived |
| `cast` + `script` on the payload | **NOT BUILT** |
| Physical attributes on the payload | **NOT BUILT** — required; see "How fast is he" |
| Delivery: `broadcast_to_watchers` on the existing `/ws/season` | **NOT BUILT** — the watch map already exists |
| Renderer (dumb: plays a script, applies a camera) | **NOT BUILT** |

## Settled (owner, 2026-08-26)

1. **Every motion is DERIVED.** Nothing moves unless a real value drives it. Where the
   data is silent the figure holds; it does not improvise. ⚠️ This is the decision the
   whole plan hangs on — see "The sticker risk".
2. **All ten figures, both sides.** A snap is effectively 5-on-5 (six roster slots, and
   the kicker only kicks), so the full cast is drawable — unlike real football's 22.
3. **Physical attributes ride the payload**, so pace and cuts are the player's real
   numbers rather than a property of the play's outcome.

⚠️ **Decisions 1 and 2 look contradictory and are not.** Derived-only says nothing moves
without a value; all-ten means six figures are usually not named by the play. The
resolution is that **every player has an ASSIGNMENT even when the play never reaches
him**, and an assignment is data:

- `coverageAssignments` maps every offensive slot to the defender covering it — computed
  on every snap for all five defenders.
- `passBlockers` names who stayed in rather than releasing.
- `insights.pass.targets` carries `route`, `openness`, `routeQuality` and `coveredBy` for
  **every** receiver in the pattern, not only the one thrown to. Measured over 1,871
  production plays: 855 pass plays list 1–3 targets, and **1,599 of 1,601 name a coverer
  (100%)**.

So a figure moves according to what it was ASKED to do (real), and reacts according to
what HAPPENED to it (real). Neither is invented.

## What the engine already computes and throws away

Measured by grep against `floosball_game.py`:

| value | what it gives the picture | emitted today |
|---|---|---|
| `coverageAssignments` | every defender's man, all five | **no** |
| `passBlockers` | who blocked instead of releasing | **no** |
| `_gateOutcome` | `{level, breaks, lineWins, moves, firstContactYards}` — the run's three contests, where contact happened, which moves were used | **no** |
| `passRusher` / `_captureBlitzer` | who rushed, who blitzed | **no** |
| `_levelDefender` | the named defender at each level of a run | **no** |
| `targetSideline` | which boundary the throw worked | partial |
| `tackledBy`, `forcedFumbleBy`, `runnerMove` | who finished the play, and how | partial |

`insights.pass` and `insights.run` are already rich — air yards, YAC, gap qualities for
every gap, `designedGap` vs `selectedGap` (the back *chose* a hole), the three gate odds.

## The data contract — the backend hands over a SCRIPT

> Owner, 2026-08-26: *"each play should hand the frontend the script for the play and the
> front end just renders it."*

⚠️ **THE PRECEDENT IS ALREADY IN THE CODEBASE: the backend writes the play-by-play TEXT.**
`formatPlayText` turns a resolved play into prose because the sim is what knows what
happened. A script is the same artifact in a different medium, so it belongs in the same
place — and the two can then be checked against each other, which is the only way the
animation and the text can be guaranteed never to disagree.

Three things follow, and they are why this beats emitting raw assignments and letting the
client work it out:

- **The derived-only rule becomes ENFORCEABLE rather than aspirational.** A client handed
  a script has nothing to invent from. A client handed `openness: 66` has to decide what
  that looks like, and that decision is sim knowledge living in TypeScript.
- **One implementation.** Where the A-gap is, how much separation an openness of 66 means,
  how long a drop takes — all of it stays in Python, next to the code that produced the
  numbers, instead of being re-derived client-side and drifting from it.
- **It is TESTABLE.** A script is data, so it can be asserted on in the Python regressions
  this project already leans on heavily. A React animation cannot be.

### Shape

⚠️ **KEYFRAMES, NOT FRAMES.** The backend states where each actor is at each moment and
what happens there; the client eases between. Measured against real payloads (mean 3,163
bytes a play):

| shape | per play | per game |
|---|---|---|
| today | 3,163 B | 361 KB |
| every-frame script (40 beats) | 4,622 B (**+46%**) | 528 KB |
| **keyframes (16 beats)** | 3,813 B (**+21%**) | 436 KB |
| cast repeated per play, on top of either | +1,736 B | — |

⚠️ This rides the WebSocket to every client on every play across sixteen concurrent games,
so the shape is a real decision and not a formatting preference.

**1. `cast` — once per game.** Names, positions and physical attributes do not change
during a game, so repeating them per play is pure waste (measured at +1,736 bytes a snap).
Keyed by slot, referenced from every beat:

```
cast: {
  off: { qb|rb|wr1|wr2|te: {name, position, speed, agility, acceleration} },
  def: { s|lb|cb1|cb2|de:  {name, position, speed, agility} }
}
```

The defensive five are the offensive roster's mirror (`DEFENSIVE_POSITION_MAP`: QB→S,
RB→LB, WR→CB, TE→DE), so both sides come from data that exists today.

**2. `script` — per play.**

```
script: {
  dur, los, dir,                       # length in seconds, anchor, attacking direction
  beats: [
    {t, a: <slot>, p: [downfield, lateral], k?: <event>, b?: {to, arc, dur}}
  ]
}
```

`t` is seconds from the snap. `p` is **field space** — yards downfield and yards lateral
from the anchor, never screen pixels (see "The camera"). `k` is an event that happens AT
that keyframe (`snap`, `drop`, `throw`, `catch`, `drop-ball`, `tackled`, `sack`,
`intercept`, `break`, `stiffarm`, `cut`, `oob`), and `b` describes the ball when it
leaves someone's hands.

### Where it is built

A choreographer module — `play_choreography.py` — that takes a resolved `Play` plus game
state and returns the script, reading the same insights the engine already produces. It is
the only place that knows what an openness of 66 looks like in yards, and it is unit-
testable without a browser.

⚠️ **This means the BACKEND now owns a presentation convention**, which is a real change in
where responsibility sits. It is the right place for it — the alternative is the same
convention living in the client, where it cannot be tested against the play it describes,
and where a second client (board card, phone) would need its own copy.

## Delivery — only to the people looking at it

> Owner, 2026-08-26: *"feels like we may need to spin up a new websocket for this that
> only connects when a user browses to the game page. I dont think we should have all this
> data coming over for every game all the time."*

⚠️ **THE INSTINCT IS RIGHT AND A NEW SOCKET IS NOT NEEDED — the targeting already exists
and is already maintained.** `/ws/season` handles `{type:'watch', gameId}` /
`{type:'unwatch'}` per connection and keeps `ws_manager.connection_watching`, a map from
socket to the game that client has open. The game modal already sends it. It is used today
only for viewer counts.

Everything a fourth channel would have to re-solve is therefore already solved:

- **The modal already announces itself** on open and on close.
- **A dropped socket clears the entry** (`websocket_manager.py:86`), and
  `test_viewer_count.py` asserts it.
- **A reconnect re-announces the open game** — there is an explicit effect for it in
  `SeasonWebSocketContext`, with a note that without it "this viewer silently stops being
  counted for the rest of the session". ⚠️ That bug class is exactly what a new socket
  would reintroduce, and it has already been paid for once.

So the addition is **one method**, not a channel: `broadcast_to_watchers(gameId, message)`,
alongside the existing per-channel and per-user paths.

### What it saves

The script rides only to sockets watching that game. Over a full 16-game slate:

| | reaching one client | server egress at 100 viewers |
|---|---|---|
| broadcast to everyone | 1.2 MB | 121.7 MB |
| **watch-targeted** | **0.1 MB** (6%) | **7.6 MB** |

⚠️ The multiplier is the point: a client that has one game open was going to receive
fifteen games' worth of choreography it will never draw.

### The late joiner

⚠️ **A client that opens the page mid-drive has missed the `cast`, and must not be sent it
over the socket.** It comes from `GET /api/games/{id}` — the fetch the modal already
makes on open — so the cast is a property of the REST payload and the socket only ever
carries scripts. No replay buffer, no catch-up message, and a reconnect re-fetches it for
free.

⚠️ **A script is for the play it describes and is worthless afterwards**, so a viewer who
joins mid-play simply starts at the next snap. Nothing needs to be queued or replayed —
which is what keeps this from growing a delivery-guarantee problem it does not have.

## Formation, and the pre-snap

> Owner, 2026-08-26: *"the graphic also needs to know offensive and defensive formations
> at the start, as well as any per play changes, like when a QB calls an audible."*

⚠️ **THE OFFENSIVE FORMATION IS EXPLICIT PER PLAY, AND AN EARLIER DRAFT OF THIS PLAN SAID
OTHERWISE.** It claimed the sim "has no formations and does not need them" — that reading
came from the playbook entries being called `Play1`..`Play24` rather than being named
formations, and it was wrong. Counted directly: **23 distinct receiver packages across the
24 pass plays**, each one a specific combination of who releases, at what depth, and who
stays in to protect:

```
wr1:deep, wr2:short, te:short     blocks: rb            three out, back protects
wr1:long,  wr2:long               blocks: te, rb        two out, max protect
wr1:hailMary, wr2:hailMary        blocks: te, rb        everything deep
te:short                          blocks: wr1, wr2, rb  one out, everyone in
wr2:medium                        blocks: wr1, te, rb   single release
```

...crossed with **four dropback depths** (short / medium / long / extraLong). So the
formation is READ, not derived — the play call already states it, and it is known before
the snap, which is exactly when the graphic needs it.

⚠️ **Half of it is already on the wire and half is not.** `insights.pass.targets` lists
the releasing receivers with their route depth, so the blockers are its complement — that
much a client could work out today. **`dropback` is NOT emitted**, and it is the part that
decides where the quarterback sets up. The package identity should ride along too, so the
graphic can show the same shape the same way every time rather than reconstructing it from
the target list.

⚠️ **This is a better position than the earlier draft assumed, and it changes what the
graphic can teach.** A viewer who watches enough snaps starts to recognise max protect
from an empty set — the packages are distinct enough to be learnable, and that only works
if the same package always draws the same way.

The DEFENSIVE side is the part that genuinely has no named formation, and there the
alignment does have to be derived:

| the engine decides | the alignment that falls out |
|---|---|
| `runStopFocus` | how stacked the box is |
| `coverageType` (man / zone / match) | pressed on receivers vs spaced off them |
| `blitzPackage`, `passRusher` | who is walked up |
| `coverageAssignments` | who is aligned over whom |

And on run plays the offence is derived too — `runConcept` (sweep / counter / draw /
sneak) says where the back sets and which way he opens, and `passConcept` (screen) says
whether he leaks out.

Either way the derived-only rule holds through the pre-snap: the offence is read from the
call, the defence from the decisions the coordinator already made.

### The script starts before the snap

The shape gains a phase. Beats carry **negative `t`** up to the snap at `t = 0`:

```
script: {
  dur, los, dir,
  snap: 0.0,                 # everything before this is the pre-snap
  beats: [
    {t: -2.4, a: 'cb1', p: [...], k: 'align'},     # the SHOWN look
    {t: -1.1, a: 'qb',  k: 'audible'},             # only when one was called
    {t: -0.6, a: 'lb',  p: [...], k: 'shift'},     # a tipped disguise, before the snap
    {t:  0.0, a: 'qb',  k: 'snap'},
    ...
  ]
}
```

⚠️ **This is what makes the audible visible at all.** `insights.audible` is present on
**45% of plays** and carries `{checked, sawStacked, readRight}` — whether the quarterback
changed the call, what he thought he saw, and whether he was right. Today that resolves
entirely between the whistle and the snap and the feed reports only what happened after
it. A graphic that starts at the snap throws away the most interesting half of the
decision.

### The disguise, and why this is the medium for it

⚠️ **THE DEFENCE HAS TWO ALIGNMENTS AND THE SCRIPT MUST CARRY BOTH.**
`insights.disguise` is `{shown, actual, tipped}` — present on **19% of plays**. The
defence lines up in one look and plays another, `tipped` says whether it failed to hold
the lie, and `preSnapRead` (**76% of plays**) says what it actually committed to.

CLAUDE.md already states the rule this was designed around:

> the pre-snap line reports what the QB SEES *including when it is a lie*, and the play
> text reveals the truth — the reader is fooled alongside the quarterback and learns with
> him

⚠️ **That was specced as PROSE and never built**, with the accompanying note that without
it "the whole system is invisible work". A field graphic is a far better medium for a lie
than a sentence: the viewer sees the stacked box, watches the quarterback check into a
pass against it, and then watches the box empty out at the snap. Nothing has to be
narrated, and the reveal lands as a thing seen rather than a thing read.

So the pre-snap beats draw `shown`, the snap swaps to `actual`, and `tipped` decides
whether the swap leaks early enough for a sharp quarterback to have caught it. All three
are fields that exist today.

⚠️ **Do NOT reveal the disguise before the snap when it was held.** The whole value is
that the viewer is fooled with the quarterback. A graphic that draws `actual` throughout
destroys the one system this feature was best placed to make visible.

## How fast is he

⚠️ **The payload carries situational ratings, not physical attributes.** `rbVision`,
`routeQuality`, `qbVision`, `openness` and `reach` are all present; `speed`, `agility`
and `acceleration` are not. Without them, pace could only be inferred from the outcome —
which makes speed a property of the PLAY rather than the PLAYER, so the same fast back
looks slow on a stuffed run. That is precisely the thing this feature exists to fix, so
the attributes go on the `cast` block.

The split that keeps it honest:

- **Attributes decide HOW a figure moves** — stride, top speed, how sharply it can change
  direction.
- **Play values decide WHERE it goes and what happens** — the lane, the separation, the
  contact point, the result.

So a fast back on a stuffed run is *quick to the hole and met at it*, which is both
truthful and legible.

## What is NOT derivable

⚠️ **There are no coordinates anywhere in the sim, and there never will be.** Lateral
placement — how far from the hash a receiver lines up, the exact curve of a route — is a
**convention**. The script model does not remove that; it decides WHO OWNS IT. The
choreographer invents the positions, and it does so in one testable place against the play
it is describing, rather than in a client that cannot check itself.

The convention is acceptable *provided it is consistent and never contradicts a value*: a
receiver with `openness: 89` must end up visibly more separated than one at `41`, and that
relationship is exactly the sort of thing a Python regression can assert.

⚠️ **There is also no clock within a play.** The engine knows the play consumed 4–7 seconds
of game clock, not when each thing happened inside it. SEQUENCE is known (drop → throw →
catch → YAC → contact → tackle; or gate 1 → 2 → 3), and durations are derived from the
attributes and distances — so `dur` and every `t` are the choreographer's construction
from real inputs, not a timeline the sim hands over.

State plainly in the UI what is measured and what is staged, or this becomes the next
thing a reader mistrusts.

## The camera — broadcast angle, not top-down

> Owner, 2026-08-26: *"it would be interesting to try to make the view an oblique angle
> like an actual broadcast instead of top down."*

⚠️ **THIS COSTS THE BACKEND NOTHING, AND IT IS WHY THE SCRIPT IS IN FIELD SPACE.** The
angle is a PROJECTION of positions the script already carries, so the division is clean:
**the backend owns WHAT HAPPENED AND WHERE (yards); the frontend owns HOW IT IS SEEN
(pixels).** A camera change never touches the sim, and a choreography change never touches
the camera. It only stays that clean if the renderer projects at the very end:

```
field space            projection            screen
(yards downfield,  ->  identity      ->  top-down
 yards lateral,        oblique 3x3   ->  broadcast
 height)               ...
```

Build it that way and the camera is a swappable function — the two views can be A/B'd,
and a phone can fall back to top-down without a second renderer. Build it screen-first and
switching the angle means redoing every position, which is the expensive version of this
conversation happening later.

What the oblique view then needs, none of it new data:

- **Depth sort.** Figures nearer the camera draw over those further away — a z-order on
  the lateral axis, which the projection already knows.
- **Scale with depth.** Distant figures smaller. This is most of what sells the angle.
- **A converging field.** Yard lines, hashes and numbers skew toward the vanishing point.
- **Vertical room.** The current graphic is a 600×220 viewBox with everything on one axis;
  depth needs real height in the box.

⚠️ **IT ALSO RAISES THE STAKES ON THE CONVENTION.** In a top-down schematic, a receiver's
lateral position reads as diagrammatic and nobody takes it literally. In a broadcast
angle it reads as WHERE HE ACTUALLY WAS. The lateral placement is the one thing the sim
cannot tell us (see "What is NOT derivable"), so the more convincing the camera, the more
carefully that convention has to be chosen — and the more it matters that separation is
driven by `openness` rather than by eye.

⚠️ **The trade is legibility for immersion, and the graphic still has a day job.** Its
current purpose is showing FIELD POSITION, and an oblique view compresses distance and
makes "whose 34?" harder to read at a glance. Whether top-down survives as an option — for
the board cards, for phones, or as a user preference — is an owner call, but the
projection architecture above is what keeps that option open for free.

## The sticker risk

⚠️ This is the single easiest place in the project to ship something that looks like a
system and is decoration. The precedents are on the record: contested scoring read as
*"flavor on top of the score instead of another gate"*, and the weather plan names itself
as the same hazard. An animation that contradicts the play text is worse than the line we
have now, because it is more convincing.

⚠️ **The script model is what turns this from a promise into a property.** A client that
receives a script cannot embellish, because it has nothing to embellish from — so the rule
is enforced by the shape of the interface rather than by everyone remembering it.

Two rules follow, and both are assertable in Python:

1. **A figure with no value backing its motion holds position.** A sparse play looking
   sparse is correct.
2. **The script and the play text describe the SAME play.** Both are generated from one
   resolved `Play`, so a regression can take the text and the script and check they agree
   — that an interception in the prose is an `intercept` beat, that the yardage in the
   text is where the last beat lands. ⚠️ That check is the whole defence against this
   shipping as decoration, and it is only possible because both are built server-side.

## Build order

1. **`play_choreography.py`, with no rendering at all.** Take a resolved `Play`, return a
   script. Prove it over real production plays: every one of the ten figures resolves to a
   beat on every snap, every script's final position matches the play's yardage, and every
   outcome in the prose has a matching event. ⚠️ The feature's whole foundation is
   provable here, before a pixel moves.
2. **`cast` + `script` on the wire.** The cast on `GET /api/games/{id}`; the script
   through a new `broadcast_to_watchers` so it reaches only the sockets with that game
   open. Confirm the measured payload cost and that nothing else on the broadcast
   regressed. ⚠️ Assert the negative too — a client watching game A must receive NO
   script for game B — since the whole saving is in that being true.
3. **A dumb renderer, static.** Play the first beat only — ten figures at their spots. This
   alone already shows coverage and blocking, which the current graphic cannot.
4. **Playback.** Tween the keyframes. Top-down projection first, because it is the identity
   transform and isolates any motion bug from any camera bug.
5. **The camera.** Swap in the oblique projection; keep top-down selectable.
6. **The moments.** Interception, sack, forced fumble, broken tackle — each one an event
   the script already carries, none of them bespoke animation.
7. **The pre-snap.** Formation, the audible, and the disguise reveal. Deliberately LAST
   even though it happens first: it is the part with no precedent on screen, and it wants
   a renderer already trusted to draw the snap correctly. ⚠️ It is also the phase that
   pays off a system built in 2026-08 and never surfaced.

⚠️ **Play-by-play is deliberately not persisted** (the feed is far larger than the box
score, and that trade is settled). So this is a LIVE and in-memory-replay feature; a game
that has aged out has no plays to animate. Scripts should NOT be persisted either — they
are derivable from a play, and storing them would be storing the same thing twice.

⚠️ **`GameModalNew.tsx` is 3,698 lines** and the field graphic is already a large inline
block inside it. The renderer lands as its own module or it will not be reviewable.

## Open questions

- **Where does it play?** The modal's field only, or the game board's cards too?
- **Live pacing.** In a scheduled game plays arrive seconds apart; does the animation run
  in real time, or is it a replayable beat the user scrubs?
- **The 5-on-5 tell.** Drawing the real cast makes it visible that a club fields five, not
  eleven. That is true of the sim today and nobody has had to look at it — worth an owner
  call before it is on screen.
