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

## Next

1. **Owner labels round 2.** On the same page, collection `labels_v2`,
   shown in a fixed shuffled order.
2. **Calibrate from the labels**, for example a minimum height in ATRs or a
   minimum life.
3. **Implement as a `RangeEngine` mode with TDD.** It keeps the
   `RANGE_*` event vocabulary, so manipulation, HTF and entries are
   unchanged. Then rerun the 30-pair sweep.
