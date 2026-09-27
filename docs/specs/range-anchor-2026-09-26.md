# Guide-anchored range detection - design draft, 2026-09-26 [U-RANGE-ANCHOR-001]

Status: prototype under owner review. The engine is unchanged.
Prototype: `docs/research/range-anchor-prototype/` (`run.py` writes
`runs/range-anchor-prototype.json`).

## Why

- **Round 1 labels.** The owner labelled 50 ranges from the funnel audit's
  review page ([Range Kontrolü](https://claude.ai/artifact/PUkS2Mwvv2qLuBsc2oJvce), collection `labels`): 3 real, 1 unsure,
  46 not.
- **Their notes.** The same points recur:
  - "RH yanlış";
  - "RL ihlal ediliyor";
  - "böyle range olmaz";
  - and once: "burdan range çıkar, engine hatalı".
- **The cause is how the levels are chosen, not the touch tolerance.**
  `RangeEngine` [U-RANGE-GUIDE-001] pairs the first Valid Low after a reseek
  with the first Valid High after it. Four consequences:
  - **Wrong swing.** RH is often a lower, secondary peak, not the top of the
    move. RL is often a higher low inside the impulse, or a single spike.
  - **No impulse.** The guide's impulse precondition (3.1) is not
    implemented, so any pullback in a trend becomes a candidate.
  - **No sideways check.** During formation a close beyond a level is
    tolerated up to 25% of the height, so drifting prices keep a candidate
    alive.
  - **Born below the floor.** 411 of 1,615 candidates start with price
    already below RL (PROJECT_STATE, 2026-09-26).

## Model (prototype)

Per 1H stream, causal: a swing is used from its confirmation on.

1. **Impulse.** A confirmed swing extreme starts a candidate when it is the
   extreme of the previous 48 bars and the move into it is at least 6 ATR
   (guide 3.1).
2. **Reference boundary.** That extreme is the reference: RH after a rise,
   RL after a fall (guide 3.2, "Referans Tavan"). The first confirmed opposite
   swing is the reaction boundary.
3. **Formation.** The owner's "violation" notes apply here.
   - A close beyond the reference by more than 10% of the height ends the
     candidate: the impulse resumed.
   - A close beyond the reaction level moves that level, since the reaction
     is going on.
   - A reaction past the impulse origin is a reversal, and ends the
     candidate.
   - An unconfirmed candidate is dropped after 240 bars.
4. **Touches.** Guide 3.2 asks for two per side.
   - A confirmed swing within 15% of the height from a boundary counts, and
     so does a wick past it.
   - Each touch counts only after price next reaches EQ.
   - One EQ visit validates at most one touch per side.
   - The reference and reaction swings are each side's first touch.
   - The candidate is confirmed at 2 + 2 touches, and at least 24 bars after
     the reference.
5. **Retire.** A confirmed range retires on a close beyond the guide 4.1
   deviation limit, half of (RH - EQ).

## Prototype result

- **Volume.** 527 ranges on the 30 pairs. Median life 70 hours, time to
  confirm 40 hours, height 5%.
- **The three owner-approved ranges are found, at the owner's levels:**
  - ADA 2026-06-24, RL 0.1396 and RH 0.1508;
  - LTC 2026-05-18;
  - AVAX 2025-08-14, where RH is the true top (26.0).
- **Claude's spot check of 12 random ranges.** 8 are clear ranges and 4 are
  borderline boxes lasting a day or two, like flags.
  - Each range records its height in ATRs at the reference (`hAtr`,
    quartiles 2.8 / 3.6 / 5.0), for a possible filter.

## Round 2 and the owner's touch rules (2026-09-27)

- **Round 2 labels.** 13 labels (`labels_v2`): 2 real, 1 unsure, 10 not.
  - The notes name the touches: "rh temas hatalı", "temas invalid",
    "2. yeşil temas invalid".
  - The boxes were in the right places, but touches were counted wrongly.
- **The prototype's touch errors.** Three kinds:
  - A swing that stopped short of the level counted (BNB 2025-08-14: 825
    against RL 820.3, 9.6% of the height).
  - Wicks past a level during formation counted (21-28% of the height).
  - Levels sat on spike tips.
- **The owner's answers.** Asked directly on 2026-09-27:
  1. A touch needs the wick to reach the level.
  2. A wick past a level before confirmation breaks the range.
  3. A level sits at the wick tip, even a long spike.
  4. A wick reaching EQ is enough for the EQ return.
- **Prototype v3** (`detector3.py`, `run3.py`) applies these rules.
  - Touches are read from candle wicks, not swings.
  - A wick stopping more than `under` of the height short is no touch.
  - Before confirmation, a wick more than `over` past either level ends the
    candidate.
  - Touches of one side with no EQ visit between them are one touch.
- **Settings against the labels.** Five approved ranges (rounds 1 and 2) and
  the ten round-2 rejections:

  | under / over | Ranges | Approved found | Rejected still found |
  |---|---|---|---|
  | v2 (15% band, wick past counts) | 527 | 5 / 5 | 10 / 10 |
  | 3% / 10% | 74 | 0 / 5 | 0 / 10 |
  | 5% / 10% | 105 | 0 / 5 | 0 / 10 |
  | 5% / 15% | 160 | 0 / 5 | 0 / 10 |
  | 5% / 20% | 240 | 0 / 5 | 1 / 10 |
  | 7% / 20% | 281 | 0 / 5 | 1 / 10 |

- **The conflict.** The answers and the round-1 approvals cannot both hold:
  - On LTC 2026-05-18 RH is touched four times, but RL (53.18) never again:
    the lows turn at 53.42-53.50.
  - On ADA 2026-06-24 the second RH touch comes only with the breakout.
  - Round 1 judged whole boxes; the answers are about touches. The strict
    rules were kept, and round 3 lets the owner judge their result.
- **Round 3.** 5% / 10% gives 105 ranges on 29 pairs, on the same page
  ([Range Kontrolü](https://claude.ai/artifact/PUkS2Mwvv2qLuBsc2oJvce), collection `labels_v3`).
  - Claude's check of 8 random ones: the touches reach the lines. Some
    boxes last only a day or two.

## Next

1. **Owner labels round 3** (`labels_v3`) and settles the conflict above.
2. **Calibrate from the labels**, for example the tolerances, a minimum height
   in ATRs or a minimum life.
3. **Implement as a `RangeEngine` mode with TDD.** It keeps the
   `RANGE_*` event vocabulary, so manipulation, HTF and entries are
   unchanged. Then rerun the 30-pair sweep.

## Round 3 (2026-09-27)

- **Labels** (`labels_v3`, 30): 18 real, 3 unsure, 9 not, against 3 of 50 in
  round 1.
- **The separator is a close outside the levels during formation.** All 18
  real ranges have none; the four rejected with "RL ihlali" / "RL altı
  kapanış" have at least one, and so does the unsure FIL.
  - Wicks past a level up to 10% of the height were accepted.
- **Prototype v4** (`detector4.py`, `run4.py`) adds that rule: 91 ranges. It
  keeps all 18 real ones and drops those four and FIL (72% real among the
  labelled ranges it keeps).
- **The remaining rejections are shape judgements.** For example, on ADA
  2025-11-21 the levels sit on liquidation spikes while the bodies stay in
  the upper half. The owner suggested an AI check for this.
- **Manipulation depth.** XLM 2026-01-08: pokes 0.1-14% of the height below
  RL after confirmation are not manipulations for the owner. ENA 2026-04-29:
  a 19% sweep that closed inside is one. The engine counts any tick past the
  level as a sweep; a minimum depth near 15% fits both.
