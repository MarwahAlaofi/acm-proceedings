# Affiliation Mapping Rules for SIGIR Proceedings

The goal of `affiliations_mapping.json` is to clean, standardize, and resolve
noisy affiliation data provided by authors and reviewers into exact matches
for conference proceedings.

The file has shape:

```json
{
  "affiliations": {
    "<lowercase-from>": "<presentation-ready-to>",
    ...
  }
}
```

It is loaded by `scan_referees.py` only when `--mappings PATH` is passed.
Without that flag, only general whitespace cleanup and name capitalization
run — affiliations pass through unchanged.

---

## Rule 1 — Top-Level Entity

Affiliations must be mapped strictly to the **University** or
**Company / Institute** level.

- **Remove departments.** Strip `Department of Computer Science`,
  `Faculty of Engineering`, `School of Information`, etc.
- **Remove countries / cities.** Strip geographic locations unless they are
  an official part of the institution's name.
  - Example: `"Tongji University, Shanghai, China"` → `"Tongji University"`.
- **Preserve corporate suffixes.** Keep legal entity suffixes like
  `Inc.`, `Ltd.`, `LLC`, `Corp.`, `Co., Ltd.`, `LP`, `SE`, or `Group`
  exactly as the author submitted them — they are part of the institution's
  preferred presentation name.

---

## Rule 2 — Autonomous Research Entity

If a subdivision or lab is a **distinct, heavily branded, autonomous
research entity**, preserve its specific name. Do not over-simplify it
to the parent corporation.

- `Microsoft Research` and `Microsoft Research Asia` stay distinct from
  `Microsoft`.
- `Google DeepMind` stays distinct from `Google`.
- `Huawei Ireland Research Center` stays distinct from `Huawei`.
- `Facebook` and `Meta` remain distinct if submitted as such.

### Exception — ICT-CAS preservation

`Institute of Computing Technology (ICT), Chinese Academy of Sciences`
and its variants **must always be preserved in their detailed form**.
Do not flatten ICT entries into the generic `Chinese Academy of Sciences`
parent.

### Exception — generic subdivisions are still flattened

Generic subdivisions of a parent corporation are stripped to the parent
level.

- Example: `"Walmart Global Tech"` → `"Walmart"`.

---

## Rule 3 — Compound Affiliation

When an author lists **two or more distinct top-level entities** (e.g., a
university and a company, or a university and an independent research
institute), preserve all of them by combining them with ` & ` (a single
space-padded ampersand).

- `"university of stavanger and google deepmind"` → `"University of Stavanger & Google DeepMind"`.
- `"inesc tec and faculty of engineering, university of porto"` → `"INESC TEC & Universidade do Porto"`.

The same applies to three-way compounds:
`"University of Kassel & hessian.AI & ScaDS.AI"`.

---

## Rule 4 — French UMR (Joint Labs)

For French **Joint Research Units (UMRs)** like IRIT or LIG, which are
co-owned by a university network and a national research center (CNRS),
map to the **combined parent institutions** so that neither entity loses
credit.

- Example: `"institut de recherche en informatique de toulouse"` → `"Université de Toulouse & CNRS"`.

---

## Rule 5 — Formatting & Key-Value Standardization

- **Keys are strictly lowercase.** All dictionary keys must be entirely
  lowercase to allow case-insensitive matching by the parsing script.
- **Values are presentation-ready.** Values must be perfectly capitalized
  and formatted exactly as they should appear in the SIGIR proceedings.
- **Native naming consistency.** Use consistent, often native-language
  formatting for specific major international universities.
  - `"University de Montreal"` / `"University of Montreal"` → `"Université de Montréal"`.
  - `"Technische Universität Wien"` → `"TU Wien"`.

---

## Rule 6 — Legacy Names and Typos

- **Resolve variations.** Map legacy or alternative names to the current
  official standard.
  - `"Université Pierre et Marie Curie"` → `"Sorbonne Université"`.
  - `"Beijing University of Aeronautics and Astronautics"` → `"Beihang University"`.
- **Catch typos.** Intentionally include misspellings in the lowercase
  keys if they appear in the raw data, so the script catches and corrects
  them.
  - Example: `"institute of computing technolgy, chinese academy of sciences"`
    is a real key whose value uses the corrected spelling.

---

## Quick checklist for adding a new entry

1. Is the key entirely lowercase?
2. Is the value the exact form you want printed in the proceedings?
3. Have you stripped department / city / country from the value (but
   kept any corporate suffix as submitted)?
4. Have you preserved any autonomous research entity (Rule 2) — including
   ICT-CAS — that the raw string referred to?
5. If the raw string lists multiple entities, are they joined by ` & `?
6. Does an existing key already cover this case (case-insensitively)?
   If yes, prefer adding another key pointing to the same value rather
   than changing the canonical value.
