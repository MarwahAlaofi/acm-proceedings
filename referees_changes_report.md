# Referee data normalization — change report

Applied automatically by `scan_referees.py` after loading every `.xlsx`
in the input directory and before any cross-file consistency check or
merge into `referees.xlsx`.

The general rules below (whitespace cleanup, capitalization, row/file
filtering) **always run**. The affiliation substitutions are loaded from
an external JSON file (`affiliations_mapping.json`) and **only applied
when `--mappings PATH` is passed on the command line**. Without that
flag, only the general rules run and affiliation strings pass through
unchanged.

All substitution lookups are case-insensitive on the trimmed full
string; non-matching values pass through unchanged.

## CLI

```bash
# General cleanup only (no substitutions)
python scan_referees.py

# General cleanup + affiliation substitutions from the JSON map
python scan_referees.py --mappings affiliations_mapping.json
```

The JSON file has shape `{"affiliations": {"<lowercase from>": "<to>", ...}}`.
Edit it directly to add, remove, or change replacements — no code change
needed.

## General rules (non-substitution, always applied)

| Scope | Rule |
|---|---|
| Excel artifacts | Files starting with `~$` (lock files for open workbooks) are skipped. |
| Empty rows | Rows with no first name, last name, email, or profile are dropped. |
| Profile column | If `profile` looks like an email and `email` is empty, `email` is filled from `profile`. |
| Whitespace | Every cell collapses internal whitespace runs (line breaks, tabs, multi-space) into a single space and is `strip()`-ed; pandas `NaN`/`None` becomes `""`. Substitution lookups always see normalized strings, so the keys below never need newline variants. |
| Name capitalization | First / middle / last name title-cased only when the cell is *entirely* lowercase or *entirely* uppercase. Mixed-case strings (`de Vries`, `McDonald`) are preserved. |
| Track chairs | Records whose `role` is exactly `track chair` (case-insensitive) are kept for consistency checks but excluded from the merged `referees.xlsx`. |
| Merged output | Per-sheet rows in `referees.xlsx` are sorted alphabetically by first name, then last name (case-insensitive). |

## Affiliation substitutions

Sourced from `affiliations_mapping.json`. Applied only when
`--mappings affiliations_mapping.json` is passed.

| From | To |
|---|---|
| `royal melbourne institute of technology` | `RMIT University` |
| `adobe systems` | `Adobe` |
| `vody` | `Vody, Inc.` |
| `nask - national research institute` | `NASK National Research Institute` |
| `copenhagen university` | `University of Copenhagen` |
| `shanghai jiaotong university` | `Shanghai Jiao Tong University` |
| `aampe` | `Aampe` |
| `technion` | `Technion - Israel Institute of Technology` |
| `technion, israel institute of technology` | `Technion - Israel Institute of Technology` |
| `department of mechanical and industrial engineering, university of toronto` | `University of Toronto` |
| `gesis-leibniz institute for the social sciences` | `GESIS – Leibniz Institute for the Social Sciences` |
| `national institute of informatics` | `National Institute of Informatics (NII)` |
| `nii` | `National Institute of Informatics (NII)` |
| `universidade federal de minas gerais, universidade federal de minas gerais` | `Universidade Federal de Minas Gerais` |
| `friedrich-schiller universität jena` | `Friedrich-Schiller-Universität Jena` |
| `mst` | `Missouri University of Science and Technology` |
| `service australia` | `Services Australia` |
| `university of stavanger and google deepmind` | `University of Stavanger & Google DeepMind` |
| `saarland university of applied sciences` | `Saarland University of Applied Sciences (htw saar)` |
| `uned` | `Universidad Nacional de Educación a Distancia` |
| `university de montreal` | `University of Montreal` |
| `city st george's, university of london uk` | `City St George's, University of London` |
| `university of passau` | `Universität Passau` |
| `institut de recherche en informatique de toulouse` | `Institut de Recherche en Informatique de Toulouse (IRIT)` |
| `irit` | `Institut de Recherche en Informatique de Toulouse (IRIT)` |
| `university of tübingen` | `Eberhard-Karls-Universität Tübingen` |
| `university of massachusetts at amherst` | `University of Massachusetts Amherst` |
| `university of milano-bicocca` | `University of Milano - Bicocca` |
| `university of milano bicocca` | `University of Milano - Bicocca` |
| `university of milan - bicocca` | `University of Milano - Bicocca` |
| `university of rome` | `Sapienza University of Rome` |
| `laboratoire informatique d'avignon- université d'avignon` | `Avignon Université` |
| `university of california santa cruz` | `University of California, Santa Cruz` |
| `universidad de la coruña` | `Universidade da Coruña` |
| `universidad da coruña` | `Universidade da Coruña` |
| `it polytechnic university of bari` | `Polytechnic University of Bari` |
| `polytechnic institute of bari` | `Polytechnic University of Bari` |
| `th mittelhessen - university of applied sciences & herder institute for historical research on east central europe` | `TH Mittelhessen & Herder Institute for Historical Research on East Central Europe` |
| `cmu, carnegie mellon university` | `Carnegie Mellon University` |
| `department of informatics, national and kapodistrian university of athens` | `National and Kapodistrian University of Athens` |
| `dept. of informatics and telecommunications, national and kapodistrian university of athens` | `National and Kapodistrian University of Athens` |
| `technische universität wien` | `TU Wien` |
| `university of innsbruck` | `Universität Innsbruck` |
| `indian institute of science education and research, kolkata` | `IISER Kolkata` |
| `indian institute of science education and research (iiser) kolkata, india` | `Indian Institute of Science Education and Research (IISER) Kolkata` |
| `university of padua` | `Università degli Studi di Padova` |
| `universita' degli studi di padova` | `Università degli Studi di Padova` |
| `university grenoble alpes` | `Université Grenoble Alpes` |
| `radboud university and spinque` | `Radboud University & Spinque` |
| `inesc tec and faculty of engineering, university of porto` | `Universidade do Porto` |
| `tongji university, shanghai, china` | `Tongji University` |
| `computer science and systems laboratory, aix-marseille university` | `Aix-Marseille University` |
| `department of information and electronic engineering, international hellenic university` | `International Hellenic University` |
| `mixedbread and national institute of informtics (nii)` | `Mixedbread and National Institute of Informatics (NII)` |
| `university of illinois at urbana-champaign` | `University of Illinois Urbana-Champaign` |
| `universita della svizzera italiana` | `Università della Svizzera Italiana (USI)` |
| `università della svizzera italiana` | `Università della Svizzera Italiana (USI)` |
| `università della svizzera italiana, usi` | `Università della Svizzera Italiana (USI)` |
