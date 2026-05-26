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
- **Remove countries / cities** that are *not* part of the institution's name.
  - Example: `"Tongji University, Shanghai, China"` → `"Tongji University"`.
  - Example: `"Donghua University, Shanghai"` → `"Donghua University"`.
  - Example: `"Hansung University Seoul"` → `"Hansung University"`.
- **Preserve campus qualifiers** that distinguish one campus of a
  multi-campus institution. The qualifier is part of the official name and
  must stay. When authors submit a bare flagship name, normalize it to the
  qualified flagship campus.
  - `University of Maryland` / `…, College Park` → `University of Maryland, College Park`.
  - `University of Michigan` / `…, Ann Arbor` / `… - Ann Arbor` →
    `University of Michigan - Ann Arbor`.
  - `University of Minnesota` / `…, Twin Cities` / `… - Twin Cities` →
    `University of Minnesota - Twin Cities`.
  - `University of Virginia` / `…, Charlottesville` →
    `University of Virginia, Charlottesville`.
  - `New York University, Abu Dhabi` → `New York University Abu Dhabi`
    (its own degree-granting campus, distinct from NYU New York).
  - `The University of Nottingham Ningbo China` — already preserved as a
    distinct branch campus.
- **Corporate suffixes — case-by-case, prefer the data-majority form.**
  Legal entity suffixes like `Inc.`, `Ltd.`, `LLC`, `Corp.`, `Co., Ltd.`,
  `LP`, `SE`, `Group` are *sometimes* dropped and sometimes kept. The
  rule is: pick the form most common in the raw submissions, falling
  back to the company's own self-presentation when raw counts are tied
  or absent. Marwah's hand-edited preference breaks remaining ties.
  - **Bare brand wins** (data-majority used the unsuffixed form):
    - `Adobe`, `Adobe Inc.`, `Adobe Systems` → `Adobe`
    - `Apple Inc`, `Apple Inc.` → `Apple`
    - `Baidu Inc.` → `Baidu`
    - `Google LLC` → `Google`
    - `Kuaishou Tech`, `Kuaishou Technology` → `Kuaishou`
  - **Suffix kept** (data-majority used the suffixed form, or the
    suffix is the official self-presentation):
    - `Alibaba` → `Alibaba Group`
    - `Bloomberg` → `Bloomberg LP`
    - `Booking` → `Booking.com`
    - `eBay Inc` → `eBay Inc.`
    - `Huawei Technologies Co Ltd` → `Huawei Technologies Ltd.`
- **Drop `(ACRONYM)` parenthetical suffixes** when no raw record
  actually uses the parenthesized form. The acronym is implicit in
  context and not part of the institution's day-to-day branding.
  Decision basis: **data-majority** (no raw record carries the
  acronym), **official branding** (institutions don't include their
  own acronym in their published name on their website), and Marwah's
  edits consistently strip the suffix.
  - `Agency for Science, Technology and Research (A*STAR)` →
    `Agency for Science, Technology and Research`
  - `Institut National de la Recherche Scientifique (INRS)` →
    `Institut National de la Recherche Scientifique`
  - `Massachusetts Institute of Technology (MIT)` →
    `Massachusetts Institute of Technology`
  - `Mohamed bin Zayed University of Artificial Intelligence (MBZUAI)` →
    `Mohamed bin Zayed University of Artificial Intelligence`
  - `National Institute of Advanced Industrial Science and Technology (AIST)` →
    `National Institute of Advanced Industrial Science and Technology`
  - `Norwegian University of Science and Technology (NTNU)` →
    `Norwegian University of Science and Technology`
  - `Pohang University of Science and Technology (POSTECH)` →
    `Pohang University of Science and Technology`
  - `Tomorrow Advancing Life (TAL)` → `Tomorrow Advancing Life`
  - `Ulsan National Institute of Science and Technology (UNIST)` →
    `Ulsan National Institute of Science and Technology`
  - `Universidade Estadual de Campinas (UNICAMP)` →
    `Universidade Estadual de Campinas`
  
  Exception — keep `(qualifier)` when the parenthetical is a *campus
  or location qualifier* (Rule 1) rather than an acronym, e.g.
  `Harbin Institute of Technology (Shenzhen)`,
  `Hong Kong University of Science and Technology (Guangzhou)`,
  `Qilu University of Technology (Shandong Academy of Sciences)`
  (the parenthetical here is part of the legal merged name, not an
  acronym).

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

### Exception — CAS sub-institute preservation

Named institutes of the Chinese Academy of Sciences (ICT, IIE, IA, CNIC,
etc.) are distinct, heavily branded research entities and **must always
be preserved in their detailed form**. Do not flatten them into the
generic `Chinese Academy of Sciences` parent.

- `Institute of Computing Technology, Chinese Academy of Sciences`
  (ICT-CAS) — also catches the typo variants
  `Institute of Computing Technolgy, ...` and
  `Intitute of Computing Technology, ...`.
- `Institute of Information Engineering, Chinese Academy of Sciences`
  (IIE-CAS).
- `Institute of Automation, Chinese Academy of Sciences` (IA-CAS).
- `Computer Network Information Center, Chinese Academy of Sciences`
  (CNIC-CAS).

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
