# English weapon catalog

The full English catalog is built from Companion rules data and its `en-EN`
localization. One English card JSON is written per weapon to
`data/weapons/cards/en/`. The committed combined A4 PDF is
`docs/render/samples/book-weapon-catalog-en.pdf`; regenerate it with the command
below, then copy the result from `docs/render/out/` to the samples path to update
the published artifact.

```bash
python3 -m pip install -r tools/requirements-pdf.txt
python3 tools/weapons2cards_en.py --pdf docs/render/out/weapon-catalog-en.pdf
cp docs/render/out/weapon-catalog-en.pdf docs/render/samples/book-weapon-catalog-en.pdf
```

The PDF contains all 146 weapon records, grouped and alphabetized by the
Companion `weaponType`. Its outline has category bookmarks and per-weapon
entries. The Institute Laser is in **Energy Weapons** because Companion marks
its `weaponType` as `Energy`; it is not inferred from its name.

## Data and known source gaps

- Numeric stats and weapon-to-mod slot relationships come from
  `data/companion/equipment/`.
- Names, descriptions, mod and ammunition names, range names, qualities,
  effects, damage-type labels, and slot labels come from the checked-in
  `data/companion/i18n/en-EN/` snapshot of Fallout-2d20-companion commit
  `2e66c7dc7c07d1fe1e62b1585e8764f453417193`.
- Two Companion records retain a Russian `rangeName` in the English bundle.
  Their labels are resolved from matching RU/EN Companion weapon records with
  the same localized range label; the generated pages therefore remain English.
- Five Companion records have no English `flavour` description; those cards
  intentionally leave the description blank rather than inventing text.
Translations are required for all named stats. Generation stops on an
unresolved ammo, damage type, quality, effect, or mod translation so the build
cannot silently omit a Companion field. Re-run the command above after the
English Companion snapshot or numeric equipment data changes. Reference-source
cross-check notes are in [`weapon-reference-check.md`](weapon-reference-check.md).
