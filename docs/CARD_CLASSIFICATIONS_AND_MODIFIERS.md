# Card Classifications & Weekly Modifiers — Design Doc

## Overview

Two new systems layered on top of the existing card effect/edition system:

1. **Classifications** — rare utility perks tied to player achievements, changing game mechanics (not scoring)
2. **Weekly Modifiers** — a rotating global effect each week that shifts optimal card strategy

---

## Part 1: Card Classifications

### Philosophy

Classifications are about *who the player is*, not what the card effect does. They grant **utility perks** that change game mechanics — extra card slots, roster flexibility, etc. They do NOT add +FP, +FPx, or xFPx.

Classifications are **rare**. Only ~10 players per season have one, making these cards highly sought after.

### Classifications

| Classification | Who Gets It | Count | Perk |
|---|---|---|---|
| **Rookie** | First-season players (season 2+) | ~5/season | Card sells for 2x Floobits value |
| **MVP** | Previous season's MVP | 1/season | +1 card equip slot |
| **Champion** | All 6 players on previous Floosbowl-winning team | 6/season | +1 FLEX roster spot |

### Details

**Rookie**
- Only applies starting season 2+ (season 1 has no rookies since everyone is new)
- ~5 new rookies enter per season (as veterans retire)
- Perk: Card sells for 2x Floobits — helps users accumulate currency in early seasons
- Least powerful perk since rookies are the most common classification
- Classification applies only in the player's first season — not permanent
- Cannot stack with other classifications (rookies didn't play the previous season)

**MVP**
- Awarded to one player per season (previous season's MVP)
- Perk: +1 card equip slot (normally 3 slots → 4 with MVP card equipped)
- Most powerful perk on the rarest classification
- Creates compound value — the extra slot holds another scoring card
- Only one MVP card can be equipped at a time (no stacking to 5+ slots)
- Classification expires after one season (must be the *reigning* MVP)
- Can stack with Champion if the MVP was also on the Floosbowl-winning team

**Champion**
- Awarded to all 6 players on the Floosbowl-winning team
- Perk: +1 FLEX roster spot (can roster an extra player of any position)
- Strong perk — more roster players = more base FP generation
- Only one Champion card can apply the FLEX bonus at a time
- Classification expires after one season (must be the *reigning* champion)
- Can stack with MVP — a card with both grants +1 slot AND +1 FLEX, and shows both badges

### Stacking Rules

- **MVP + Champion can stack** — if the MVP was on the Floosbowl-winning team, their card has both classifications and grants both perks. This is extremely rare and powerful.
- **Rookie cannot stack** — rookies didn't play the previous season, so they can't be MVP or Champion.
- **Only one MVP perk and one Champion perk can be active** — equipping two Champion cards doesn't give +2 FLEX spots. But one MVP card + one Champion card grants both perks.

### Data Model

```python
# On CardTemplate
classification = Column(String, nullable=True)  # "rookie", "mvp", "champion", or None

# Classification assigned during template generation:
# - cardManager.generateRookieTemplates() → classification="rookie"
# - cardManager.generateSeasonTemplates() → check MVP/Champion from previous season
```

### How Perks Apply

Classification perks are checked when computing the user's fantasy state:
- **Rookie (2x sell value)**: Applied in the card sell/disenchant flow
- **MVP (+1 card slot)**: Checked when loading equipped cards — if any equipped card has classification="mvp", max slots = 4
- **Champion (+1 FLEX)**: Checked when validating roster composition — if any equipped card has classification="champion", allow one extra player

Perks only apply while the card is **equipped**, not just owned. This creates a strategic tradeoff — the MVP card might have a weak scoring effect but its slot perk is invaluable.

---

## Part 2: Weekly Modifiers

### Philosophy

A single global modifier rotates each week (every 7 games), announced **before games start** so users can plan their card loadouts. Creates strategic variety — no single card build dominates every week.

### Modifier Pool

| Modifier | Display Name | Effect | Strategy Shift |
|---|---|---|---|
| `amplify` | **Amplify** | +FPx values are doubled | Load up additive mult cards |
| `cascade` | **Cascade** | xFPx bonus portions are doubled (×1.3 → ×1.6) | Even one xFPx becomes huge |
| `ironclad` | **Ironclad** | K-slot cards that grow over time won't reset this week | Safe to ride risky K-slot cards |
| `overdrive` | **Overdrive** | Match bonus is 2.5x instead of 1.5x | Prioritize matched cards |
| `payday` | **Payday** | Floobits earned are tripled | Equip RB floobits cards |
| `grounded` | **Grounded** | All mult effects disabled (+FPx and xFPx) | Pure flat FP + floobits day |
| `wildcard` | **Wildcard** | All cards treated as matched | Equip best effects regardless of roster |
| `spotlight` | **Spotlight** | Card-player-specific effects get +50% FP | Favor main_character, hype_man, etc. |
| `longshot` | **Longshot** | Conditional thresholds halved | Conditionals trigger much easier |
| `frenzy` | **Frenzy** | +FP values are doubled | Stack flat FP cards |
| `steady` | **Steady** | No special effect — all normal rules apply | Standard week, no adaptation needed |

### Selection Rules

- One modifier active per week, randomly selected at week start
- No repeat within 3 weeks (recent history tracked)
- Some modifiers are weighted lower (Grounded is disruptive, appears less often)
- `steady` (no effect) is weighted normally — provides breathing room between strategic shifts
- Modifier is broadcast via WebSocket `week_start` event and shown on the fantasy dashboard
- Playoffs: all fantasy aspects disabled (no FP, no card effects, no Floobits, no modifiers). Users manage rosters between rounds as teams get eliminated.

### Suggested Weights

```python
MODIFIER_WEIGHTS = {
    "amplify":   10,
    "cascade":   8,
    "ironclad":  10,
    "overdrive": 10,
    "payday":    10,
    "grounded":  5,   # Disruptive — less frequent
    "wildcard":  8,
    "spotlight": 8,
    "longshot":  10,
    "frenzy":    10,
    "steady":    10,  # No effect — normal week
}
```

### Data Model

```python
# On Season or as a separate table
weekly_modifier = Column(String, nullable=True)  # Current week's active modifier
modifier_history = Column(JSON, default=list)     # Recent modifiers to prevent repeats

# Or stored per-week:
class WeeklyModifier(Base):
    season = Column(Integer)
    week = Column(Integer)
    modifier = Column(String)  # e.g. "amplify"
```

### Calculator Integration

The active modifier is passed into `CardCalcContext` as a new field:

```python
# In CardCalcContext
activeModifier: str = ""  # e.g. "amplify", "grounded", ""

# In calculateWeekCardBonuses(), after computing base values:
if ctx.activeModifier == "amplify":
    matchedMult *= 2
elif ctx.activeModifier == "frenzy":
    matchedFP *= 2
elif ctx.activeModifier == "grounded":
    matchedMult = 0
    matchedXMult = 0
elif ctx.activeModifier == "overdrive":
    # Match multiplier is 2.5x instead of 1.5x
    # (applied earlier in match bonus section)
elif ctx.activeModifier == "wildcard":
    isMatch = True  # Force match for all cards
# etc.
```

### Frontend Display

- Fantasy dashboard shows the active modifier prominently (icon + name + short description)
- Shown in the card equip screen so users can plan
- Breakdown could show "Amplify: +FPx doubled" as a note
- Color-coded: green for beneficial, yellow for neutral, red for restrictive (Grounded)

---

## Part 3: Season Transition & Roster Management

### End of Regular Season

When the final regular season week completes (before playoffs begin):

1. **Fantasy standings lock** — final season FP totals are frozen, winner determined
2. **Unequip all cards** — clear all equipped card slots for all users, reset all streak counts to 0
3. **Cards stay in collection** — users keep all their cards, just unequipped
4. **Rosters persist** — rostered players carry over into next season (casual-friendly)
5. **Playoffs begin** — all fantasy aspects disabled (no FP, no card effects, no Floobits, no modifiers)

### Player Retirement Handling

When a player retires (during offseason or mid-season):

1. **Remove from all rosters** — player is dropped, slot left empty
2. **Auto-fill check** — if user has auto-fill enabled, empty slot is filled from best available free agents (by player rating, matching position slot)
3. **Notification** — user is notified that their player retired and was dropped (and auto-replaced if applicable)
4. **Cards unaffected** — cards for retired players stay in collection (they just won't generate match bonuses since the player isn't active)

### Player Becomes Free Agent

- Player stays on roster — free agents can still sign with a new team
- No action needed unless the player is dropped entirely from the league (not currently a mechanic)

### Auto-Fill Setting

User preference (stored on User model):

```python
# On User
auto_fill_roster = Column(Boolean, default=True)
```

- **Enabled (default)**: When a roster slot is emptied (retirement, etc.), automatically fill with the best available player for that position
- **Disabled**: Slot left empty, user notified to fill manually
- Auto-fill picks the highest-rated available player at the matching position who isn't already on another user's roster
- Auto-fill also applies at season start if a user's roster has empty slots from offseason changes

### New Season Start

When a new season begins:

1. **Expire classifications** — remove MVP/Champion classifications from previous season's cards. Assign new ones based on last season's results.
2. **Generate new card templates** — including Rookie cards for new players (season 2+)
3. **Rosters carry over** — existing roster players remain, users can swap as desired
4. **Auto-fill empty slots** — for users with auto-fill enabled who have gaps from retirements
5. **Cards can be equipped again** — users choose which cards to equip for the new season
6. **New users get a free starter pack** — first-time users receive a free card pack when they join (any season). Returning users buy packs with Floobits — that's the point of the economy.
7. **Starter pack available in shop** — same contents as the free new-user pack, purchasable with Floobits for users who want to rebuild their collection

### Data Model Additions

```python
# On User
auto_fill_roster = Column(Boolean, default=True)

# Notification system (future)
# Could use a simple notifications table or in-app alerts
class UserNotification(Base):
    user_id = Column(Integer, ForeignKey('users.id'))
    type = Column(String)        # "player_retired", "auto_fill", "season_end", etc.
    message = Column(String)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime)
```

---

## Implementation Order

1. **Classifications** — simpler, mostly data model + template generation changes
   - Add `classification` column to CardTemplate
   - Update template generation to assign classifications
   - Update card slot/roster checks to respect MVP/Champion perks
   - Update sell flow for Rookie 2x value
   - Frontend: show classification badge on card

2. **Weekly Modifiers** — touches the calculator and season flow
   - Add modifier selection at week start
   - Pass modifier into CardCalcContext
   - Apply modifier effects in calculator
   - Broadcast via WebSocket
   - Frontend: show active modifier on dashboard

3. **Season Transition** — end-of-season cleanup and new season setup
   - Unequip all cards and reset streaks at regular season end
   - Lock fantasy standings
   - Handle player retirements (remove from rosters, auto-fill if enabled)
   - Add `auto_fill_roster` user setting + auto-fill logic
   - Expire old classifications, assign new ones
   - Generate new card templates (including Rookies)
   - Free card pack at season start

---

## Resolved Decisions

- **Classifications can stack**: MVP + Champion is possible if the MVP was on the winning team. Rookie cannot stack (didn't play previous season).
- **MVP/Champion expire after one season**: Only the *reigning* MVP/Champion players have the classification. Old cards lose it.
- **"No modifier" week exists**: Called "Steady" — normal rules apply, weighted same as other modifiers.
- **Modifiers are universal**: No spending Floobits to reroll for everyone.
- **Modifier nullification**: Shop item (expensive) that cancels the current week's modifier for that user only. Single-use, applies to the active modifier only.

---

## Part 4: Weekly Modifier UI

### Current State

- Backend: modifier selection, history tracking, and calculator integration are all implemented
- Frontend: no dedicated UI — modifier is not displayed anywhere to the user

### Required UI Elements

**Fantasy Dashboard — Active Modifier Banner**
- Prominent banner at top of fantasy page showing this week's active modifier
- Shows: modifier icon/emoji, display name, one-line effect description
- Color-coded: green (beneficial like Amplify, Frenzy), yellow (neutral like Steady), red (restrictive like Grounded)
- If `steady` (no effect), show a subtle "Normal Week" indicator

**Card Equip Screen**
- Show the active modifier as a small badge/chip so users can plan card loadout accordingly
- Tooltip on hover explains the modifier's impact on card types

**Points Breakdown**
- If a modifier affected the score, show it as a line item in the breakdown (e.g., "Amplify: +FPx doubled")

### Modifier Display Data

The modifier name and metadata should come from the backend via the fantasy snapshot or a dedicated endpoint. Each modifier needs:
- `name`: internal key (e.g., "amplify")
- `displayName`: user-facing name (e.g., "Amplify")
- `description`: short effect description (e.g., "+FPx values are doubled")
- `color`: category color (green/yellow/red)

---

## Part 5: Roster Swaps UI

### Current State

- Backend: fully implemented — swap grants (1 per 7 weeks), swap execution (costs 1 Floobit), swap history tracking, banked FP calculation
- Frontend: no swap UI — users cannot currently perform swaps from the app

### How Swaps Work (Backend)

1. **Earning swaps**: Users receive 1 roster swap every 7 weeks (regular season only), capped per grant cycle
2. **Cost**: Each swap costs 1 Floobit (deducted on execution)
3. **Timing**: Swaps can only be made between games (not during active games)
4. **FP banking**: When a player is swapped out, their earned FP since roster lock is "banked" (preserved in season total). The new player starts fresh from their current season FP.
5. **Swap limit**: Users can only use swaps they've accumulated — `swaps_available` on the roster tracks this

### Required UI Elements

**Roster View — Swap Available Indicator**
- Show number of available swaps (e.g., "2 swaps available") near the roster
- Disabled/hidden when games are active

**Swap Flow**
- User clicks a roster slot → opens a player picker for that position
- Player picker shows available players (same position, not already rostered by this user)
- Players sorted by rating/performance, showing key stats
- Confirmation dialog: "Swap [Old Player] for [New Player]? Costs 1 Floobit. [Old Player]'s FP will be banked."
- After swap: roster updates, swap count decrements, swap appears in history

**Swap History**
- Collapsible section showing past swaps: week, slot, old → new player, banked FP
- Already returned by the roster API (`swapHistory` array)

**Swap Availability**
- When `swaps_available == 0`: show "No swaps available" with info on when the next one is earned (every 7 weeks)
- When games are active: show "Swaps locked during games" or disable the swap buttons

### API Endpoints

- `GET /api/fantasy/roster` — returns roster with `swapsAvailable` count and `swapHistory`
- `POST /api/fantasy/roster/swap` — body: `{ slot: "qb1", newPlayerId: 123 }` — executes the swap

---

## Open Questions

- Modifier nullification shop item cost (TBD — depends on economy design, should be expensive to prevent stockpiling)
- Swap UI: should we show a "next swap in X weeks" countdown, or just the current count?
