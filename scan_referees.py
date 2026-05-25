"""Read-only scanner for the referees/ directory.

Loads every .xlsx file (every non-empty sheet), normalizes columns,
prints reviewer counts per role per file, and reports cross-file
inconsistencies (EasyChair ID, email, or name collisions with diverging
affiliation, country, or partial name matches). Each file is assumed to
be already deduplicated, so all checks fire only when a match spans 2+
files.

The EasyChair-style files carry a "#" column with the reviewer's
EasyChair user id — a strong identity signal. The fp_/sp_ files come
from OpenReview and have no such column; for those we fall back to
email/name matching.

Output is colorized for human review: each finding shows the exact
file/sheet/row coordinates so an editor can jump straight to the cell
that needs fixing. Conflicting fields are highlighted in red, missing
fields in yellow. Disable colors with NO_COLOR=1 or by piping output.

No file is modified.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

DEFAULT_INPUT_DIR = "referees"
DEFAULT_OUTPUT_FILE = "referees.xlsx"

COLUMN_ALIASES = {
    "first name": "first_name",
    "first": "first_name",
    "middle name": "middle_name",
    "middle": "middle_name",
    "last name": "last_name",
    "last": "last_name",
    "email": "email",
    "e-mail": "email",
    "country": "country",
    "affiliation": "affiliation",
    "institution": "affiliation",
    "role": "role",
    "profile": "profile",
    "#": "easychair_id",
}

# Files where the column implying role is missing — derive role from file name.
FILE_IMPLIED_ROLE = {
    "fp_area-chairs.xlsx": "Area Chair (Full Papers)",
    "fp_program-committee-members.xlsx": "PC Member (Full Papers)",
    "fp_senior-program-committee-members.xlsx": "Senior PC (Full Papers)",
    "sp_program-committee-members.xlsx": "PC Member (Short Papers)",
    "sp_senior-program-committee-members.xlsx": "Senior PC (Short Papers)",
}

# Per-source-file track label, plus optional role override applied when the
# whole file represents one role (used for the merged output).
FILE_TRACK_INFO: dict[str, tuple[str, str | None]] = {
    "Reproducibility PC proceedings.xlsx": ("Reproducibility", None),
    "SIGIR 2026 Demo Track Reviewer Info.xlsx": ("Demos", None),
    "SIGIR 2026 Resource Track PC.xlsx": ("Resource", None),
    "SIGIR2026-DC-Reviewers.xlsx": ("Doctoral Consortium", None),
    "SIGIR26_Industry_Track_Reviewers.xlsx": ("Industry", None),
    "SIGIR26_PC_LRE.xlsx": ("LRE", None),
    "SIGIR 2026 workshop reviewers.xlsx": ("Workshop", "PC"),
    "Tutorials-PCs.xlsx": ("Tutorials", None),
    "fp_area-chairs.xlsx": ("Full Papers", "AC"),
    "fp_program-committee-members.xlsx": ("Full Papers", "PC"),
    "fp_senior-program-committee-members.xlsx": ("Full Papers", "SPC"),
    "perspectivesPCaffiliationscheck.xlsx": ("Perspectives", None),
    "sp_program-committee-members.xlsx": ("Short Papers", "PC"),
    "sp_senior-program-committee-members.xlsx": ("Short Papers", "SPC"),
}

# Free-text role string → short canonical code for sheet naming.
ROLE_CODE = {
    "pc member": "PC",
    "senior pc member": "SPC",
    "track chair": "Chair",
}

# Output worksheet ordering: tracks in this list come first (in this order),
# anything else is appended after, sorted alphabetically. Within each track
# roles follow ROLE_ORDER (AC → SPC → PC), then alphabetical.
TRACK_ORDER = [
    "Full Papers",
    "Perspectives",
    "Reproducibility",
    "Short Papers",
    "Resource",
    "Industry",
    "Demos",
    "Tutorials",
    "LRE",
    "Doctoral Consortium",
    "Workshop",
]
ROLE_ORDER = ["AC", "SPC", "PC"]


def _sheet_sort_key(item: tuple[str, str]) -> tuple:
    track, role = item
    track_idx = TRACK_ORDER.index(track) if track in TRACK_ORDER else len(TRACK_ORDER)
    role_idx = ROLE_ORDER.index(role) if role in ROLE_ORDER else len(ROLE_ORDER)
    return (track_idx, role_idx, track, role)


# Fields displayed for each reviewer record, in canonical order.
DISPLAY_FIELDS = (
    "first_name",
    "middle_name",
    "last_name",
    "email",
    "affiliation",
    "country",
    "role",
)
FIELD_LABELS = {
    "first_name": "first",
    "middle_name": "middle",
    "last_name": "last",
    "email": "email",
    "affiliation": "aff",
    "country": "country",
    "role": "role",
    "easychair_id": "ec_id",
}


# ---------------------------------------------------------------------------
# Color helpers (auto-disabled if stdout is not a TTY or NO_COLOR is set)
# ---------------------------------------------------------------------------


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


_COLOR = _color_enabled()


class C:
    # Bright palette tuned for dark terminals: hi-intensity foregrounds (90–97)
    # for the eye-catching bits, plain grey (90) for muted labels.
    RESET = "\033[0m" if _COLOR else ""
    BOLD = "\033[1m" if _COLOR else ""
    DIM = "\033[38;5;250m" if _COLOR else ""  # light grey — readable on dark bg
    RED = "\033[91m" if _COLOR else ""  # bright red
    GREEN = "\033[92m" if _COLOR else ""  # bright green
    YEL = "\033[93m" if _COLOR else ""  # bright yellow
    BLUE = "\033[94m" if _COLOR else ""  # bright blue
    MAG = "\033[95m" if _COLOR else ""  # bright magenta
    CYAN = "\033[96m" if _COLOR else ""  # bright cyan
    GREY = "\033[38;5;253m" if _COLOR else ""  # near-white grey for file/sheet
    WHITE = "\033[97m" if _COLOR else ""  # bright white for row numbers


# ---------------------------------------------------------------------------
# Reviewer record
# ---------------------------------------------------------------------------


@dataclass
class Reviewer:
    source_file: str
    sheet: str
    row_number: int  # 1-based Excel row including the header (row 1 = header)
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    email: str = ""
    country: str = ""
    affiliation: str = ""
    role: str = ""
    profile: str = ""
    easychair_id: str = ""

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p).strip()

    @property
    def name_key(self) -> tuple[str, str]:
        return (self.first_name.lower().strip(), self.last_name.lower().strip())

    @property
    def email_key(self) -> str:
        return self.email.lower().strip()

    @property
    def easychair_id_key(self) -> str:
        return self.easychair_id.strip()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    # pandas reads integer cells as floats when the column has any NaN — strip
    # the trailing ".0" so EasyChair ids stay as plain integer strings.
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    # Collapse all whitespace runs (line breaks, tabs, multi-space) into a
    # single space so downstream lookups don't need to know about variants.
    return " ".join(str(value).split())


# Affiliation / country canonicalizations (exact, case-insensitive whole-string).
AFFILIATION_REPLACEMENTS = {
    "royal melbourne institute of technology": "RMIT University",
    "adobe systems": "Adobe",
    "vody": "Vody, Inc.",
    "nask - national research institute": "NASK National Research Institute",
    "copenhagen university": "University of Copenhagen",
    "shanghai jiaotong university": "Shanghai Jiao Tong University",
    "aampe": "Aampe",
    "technion": "Technion - Israel Institute of Technology",
    "department of mechanical and industrial engineering, university of toronto": "University of Toronto",
    "gesis-leibniz institute for the social sciences": "GESIS – Leibniz Institute for the Social Sciences",
    "national institute of informatics": "National Institute of Informatics (NII)",
    "nii": "National Institute of Informatics (NII)",
    "universidade federal de minas gerais, universidade federal de minas gerais": "Universidade Federal de Minas Gerais",
    "friedrich-schiller universität jena": "Friedrich-Schiller-Universität Jena",
    "mst": "Missouri University of Science and Technology",
    "service australia": "Services Australia",
    "university of stavanger and google deepmind": "University of Stavanger & Google DeepMind",
    "saarland university of applied sciences": "Saarland University of Applied Sciences (htw saar)",
    "uned": "Universidad Nacional de Educación a Distancia",
    "university de montreal": "University of Montreal",
    "city st george's, university of london uk": "City St George's, University of London",
    "university of passau": "Universität Passau",
    "technion, israel institute of technology": "Technion - Israel Institute of Technology",
    "institut de recherche en informatique de toulouse": "Institut de Recherche en Informatique de Toulouse (IRIT)",
    "irit": "Institut de Recherche en Informatique de Toulouse (IRIT)",
    "university of tübingen": "Eberhard-Karls-Universität Tübingen",
    "university of massachusetts at amherst": "University of Massachusetts Amherst",
    "university of milano-bicocca": "University of Milano - Bicocca",
    "university of rome": "Sapienza University of Rome",
    "laboratoire informatique d'avignon- université d'avignon": "Avignon Université",
    "university of california santa cruz": "University of California, Santa Cruz",
    "universidad de la coruña": "Universidade da Coruña",
    "universidad da coruña": "Universidade da Coruña",
    "it polytechnic university of bari": "Polytechnic University of Bari",
    "polytechnic institute of bari": "Polytechnic University of Bari",
    "th mittelhessen - university of applied sciences & herder institute for historical research on east central europe": "TH Mittelhessen & Herder Institute for Historical Research on East Central Europe",
    "cmu, carnegie mellon university": "Carnegie Mellon University",
    "department of informatics, national and kapodistrian university of athens": "National and Kapodistrian University of Athens",
    "dept. of informatics and telecommunications, national and kapodistrian university of athens": "National and Kapodistrian University of Athens",
    "technische universität wien": "TU Wien",
    "university of innsbruck": "Universität Innsbruck",
    "indian institute of science education and research, kolkata": "IISER Kolkata",
    "indian institute of science education and research (iiser) kolkata, india": "IISER Kolkata",
    "university of milano bicocca": "University of Milano - Bicocca",
    "university of milan - bicocca": "University of Milano - Bicocca",
    "university of padua": "Università degli Studi di Padova",
    "universita' degli studi di padova": "Università degli Studi di Padova",
    "university grenoble alpes": "Université Grenoble Alpes",
    "radboud university and spinque": "Radboud University & Spinque",
    "inesc tec and faculty of engineering, university of porto": "Universidade do Porto",
    "tongji university, shanghai, china": "Tongji University",
    "computer science and systems laboratory, aix-marseille university": "Aix-Marseille University",
    "department of information and electronic engineering, international hellenic university": "International Hellenic University",
    "mixedbread and national institute of informtics (nii)": "Mixedbread and National Institute of Informatics (NII)",
    "university of illinois at urbana-champaign": "University of Illinois Urbana-Champaign",
    "universita della svizzera italiana": "Università della Svizzera Italiana (USI)",
    "università della svizzera italiana": "Università della Svizzera Italiana (USI)",
    "università della svizzera italiana, usi": "Università della Svizzera Italiana (USI)",
}
COUNTRY_REPLACEMENTS = {
    "netherlands": "The Netherlands",
}


def _fix_capitalization(name: str) -> str:
    """Title-case a name only if it is entirely lower-case or upper-case.
    Mixed-case strings (e.g., 'de Vries', 'McDonald') are left untouched.
    """
    if not name:
        return name
    if name.islower() or name.isupper():
        # capwords-style: title-case each whitespace-separated token
        return " ".join(p[:1].upper() + p[1:].lower() for p in name.split())
    return name


def normalize(reviewers: list[Reviewer]) -> None:
    """Apply known fixups in place: capitalization, affiliation/country substitutions."""
    for r in reviewers:
        r.first_name = _fix_capitalization(r.first_name)
        r.middle_name = _fix_capitalization(r.middle_name)
        r.last_name = _fix_capitalization(r.last_name)

        aff_repl = AFFILIATION_REPLACEMENTS.get(r.affiliation.strip().lower())
        if aff_repl:
            r.affiliation = aff_repl

        country_repl = COUNTRY_REPLACEMENTS.get(r.country.strip().lower())
        if country_repl:
            r.country = country_repl


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    new_cols = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in COLUMN_ALIASES:
            new_cols[col] = COLUMN_ALIASES[key]
    return df.rename(columns=new_cols)


def _df_to_reviewers(df: pd.DataFrame, source_file: str, sheet: str) -> list[Reviewer]:
    reviewers: list[Reviewer] = []
    # df.index from read_excel is 0-based; Excel row = index + 2 (header is row 1).
    for idx, row in df.iterrows():
        excel_row = int(idx) + 2
        rec = {
            f: ""
            for f in (
                "first_name",
                "middle_name",
                "last_name",
                "email",
                "country",
                "affiliation",
                "role",
                "profile",
                "easychair_id",
            )
        }
        for col in df.columns:
            if col in rec:
                rec[col] = _clean(row[col])
        # Skip rows that are entirely empty for identity fields.
        if not any([rec["first_name"], rec["last_name"], rec["email"], rec["profile"]]):
            continue
        # If profile field looks like an email, populate email from it.
        if not rec["email"] and rec["profile"] and "@" in rec["profile"]:
            rec["email"] = rec["profile"]
        reviewers.append(
            Reviewer(
                source_file=source_file,
                sheet=sheet,
                row_number=excel_row,
                **rec,
            )
        )
    return reviewers


def load_all(directory: str) -> list[Reviewer]:
    all_reviewers: list[Reviewer] = []
    for fname in sorted(os.listdir(directory)):
        if not fname.lower().endswith(".xlsx"):
            continue
        if fname.startswith("~$"):  # Excel lock files for open workbooks
            continue
        path = os.path.join(directory, fname)

        try:
            xl = pd.ExcelFile(path)
        except Exception as exc:
            print(f"[WARN] Cannot open {fname}: {exc}", file=sys.stderr)
            continue

        for sheet in xl.sheet_names:
            try:
                df = pd.read_excel(path, sheet_name=sheet)
            except Exception as exc:
                print(f"[WARN] Cannot read {fname}::{sheet}: {exc}", file=sys.stderr)
                continue
            if df.empty:
                continue

            # Special-case: Resource Track PC has unnamed first column = first_name
            if (
                fname == "SIGIR 2026 Resource Track PC.xlsx"
                and "Unnamed: 0" in df.columns
            ):
                df = df.rename(columns={"Unnamed: 0": "First name"})

            df = _normalize_columns(df)
            recs = _df_to_reviewers(df, fname, sheet)
            implied = FILE_IMPLIED_ROLE.get(fname, "")
            for r in recs:
                if not r.role and implied:
                    r.role = implied
            all_reviewers.extend(recs)
    return all_reviewers


# ---------------------------------------------------------------------------
# Per-file role counts
# ---------------------------------------------------------------------------


def report_per_file_role_counts(reviewers: list[Reviewer]) -> None:
    by_file: dict[str, list[Reviewer]] = defaultdict(list)
    for r in reviewers:
        by_file[r.source_file].append(r)

    _banner("REVIEWERS PER ROLE PER FILE", C.CYAN)
    for fname in sorted(by_file):
        recs = by_file[fname]
        print(f"\n  {C.BOLD}{fname}{C.RESET}  {C.DIM}(rows: {len(recs)}){C.RESET}")
        per_role: dict[str, int] = defaultdict(int)
        for r in recs:
            role = r.role or "(unspecified)"
            per_role[role] += 1
        for role in sorted(per_role):
            print(f"    {role:40s} {C.GREEN}{per_role[role]:>5d}{C.RESET}")
        print(f"    {C.DIM}{'-- TOTAL --':40s} {len(recs):>5d}{C.RESET}")

    chairs = sum(1 for r in reviewers if _is_track_chair(r))
    non_chairs = len(reviewers) - chairs
    print(f"\n  {C.BOLD}OVERALL{C.RESET}")
    print(f"    {'reviewers (non-chairs)':40s} {C.GREEN}{non_chairs:>5d}{C.RESET}")
    print(f"    {'track chairs':40s} {C.GREEN}{chairs:>5d}{C.RESET}")
    print(f"    {C.DIM}{'-- TOTAL ROWS --':40s} {len(reviewers):>5d}{C.RESET}")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _diff_field(values: Iterable[str]) -> list[str]:
    seen = []
    for v in values:
        v = (v or "").strip()
        if v and v not in seen:
            seen.append(v)
    return seen


def _spans_multiple_files(group: Iterable[Reviewer]) -> bool:
    return len({r.source_file for r in group}) > 1


def _has_distinct_easychair_ids(group: Iterable[Reviewer]) -> bool:
    """True if the group contains 2+ distinct non-empty EasyChair ids.

    A name match between records with different EC ids is a coincidence
    (homonyms), not the same person — name-based reports skip these so
    they don't drown out real inconsistencies.
    """
    ids = {r.easychair_id_key for r in group if r.easychair_id_key}
    return len(ids) >= 2


def _levenshtein(a: str, b: str) -> int:
    """Standard iterative Levenshtein edit distance."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(
                curr[j - 1] + 1,  # insertion
                prev[j] + 1,  # deletion
                prev[j - 1] + cost,  # substitution
            )
        prev = curr
    return prev[-1]


def _first_names_similar(a: str, b: str) -> bool:
    """True if strings differ only in capitalization, or case-insensitive
    Levenshtein distance < 3."""
    al, bl = a.lower(), b.lower()
    if al == bl:
        return True
    return _levenshtein(al, bl) < 3


def _banner(text: str, color: str = C.MAG) -> None:
    bar = "═" * 78
    print(f"\n{color}{bar}{C.RESET}")
    print(f"{color}{C.BOLD} {text}{C.RESET}")
    print(f"{color}{bar}{C.RESET}")


def _section(text: str) -> None:
    print(f"\n{C.BOLD}{C.BLUE}── {text}{C.RESET}")


def _issue_header(
    label: str, key: str, note: str = "", diff_fields: Iterable[str] = ()
) -> None:
    extra = f"  {C.DIM}({note}){C.RESET}" if note else ""
    print(f"\n  {C.BOLD}{C.YEL}● {label}:{C.RESET} {C.BOLD}{key}{C.RESET}{extra}")
    diffs = list(diff_fields)
    if diffs:
        labels = ", ".join(FIELD_LABELS.get(f, f) for f in diffs)
        print(f"    {C.DIM}disagrees on:{C.RESET} {C.RED}{labels}{C.RESET}")


def _location(r: Reviewer) -> str:
    return (
        f"{C.BOLD}{C.GREY}{r.source_file}{C.RESET} "
        f"{C.DIM}▸{C.RESET} {C.GREY}{r.sheet}{C.RESET} "
        f"{C.DIM}▸ row{C.RESET} {C.BOLD}{C.WHITE}{r.row_number}{C.RESET}"
    )


def _format_value(field_name: str, value: str, is_diff: bool) -> str:
    label = FIELD_LABELS[field_name]
    if not value:
        return f"{C.DIM}{label}={C.YEL}(missing){C.RESET}"
    if is_diff:
        return f"{C.DIM}{label}={C.RESET}{C.RED}{C.BOLD}{value!r}{C.RESET}"
    return f"{C.DIM}{label}={C.RESET}{value!r}"


def _print_records(
    group: list[Reviewer], diff_fields: set[str], fields: tuple[str, ...]
) -> None:
    """Print each record on two lines: location, then field values.

    Fields named in `diff_fields` are highlighted; fields listed in `fields`
    are the ones shown for this issue type.
    """
    for r in group:
        print(f"      {_location(r)}")
        parts = [_format_value(f, getattr(r, f), f in diff_fields) for f in fields]
        print(f"        {'  '.join(parts)}")


def _diff_fields_in(group: list[Reviewer], fields: Iterable[str]) -> set[str]:
    """Return the set of fields where non-empty values disagree across the group."""
    diffs: set[str] = set()
    for f in fields:
        vals = _diff_field((getattr(r, f) for r in group))
        if len(vals) > 1:
            diffs.add(f)
    return diffs


def _diff_or_missing_fields_in(
    group: list[Reviewer], fields: Iterable[str]
) -> set[str]:
    """Like _diff_fields_in, but also flags fields where some records have a
    value and others don't. Use only when group identity is established
    (e.g., shared email) so 'missing' is a real gap, not legitimate variation.
    """
    diffs: set[str] = set()
    for f in fields:
        raw = [getattr(r, f).strip() for r in group]
        non_empty = {v for v in raw if v}
        if len(non_empty) > 1:
            diffs.add(f)
        elif non_empty and any(not v for v in raw):
            diffs.add(f)
    return diffs


# ---------------------------------------------------------------------------
# Within-file duplicate check
# ---------------------------------------------------------------------------


def report_within_file_duplicates(reviewers: list[Reviewer]) -> int:
    """Flag potential duplicates inside a single file.

    Two tiers, in this order per file:
      1. Full match — same first+last name and every displayed field agrees
         (no missing values either).
      2. Name match — same first+last name but other fields differ or are
         partially filled.
    """
    by_file: dict[str, list[Reviewer]] = defaultdict(list)
    for r in reviewers:
        by_file[r.source_file].append(r)

    _banner("WITHIN-FILE DUPLICATES — same reviewer repeated in one file", C.MAG)
    fields = (
        "first_name",
        "middle_name",
        "last_name",
        "email",
        "affiliation",
        "country",
        "role",
    )
    issues = 0

    for fname in sorted(by_file):
        recs = by_file[fname]
        by_name: dict[tuple[str, str], list[Reviewer]] = defaultdict(list)
        for r in recs:
            if r.first_name or r.last_name:
                by_name[r.name_key].append(r)

        full_matches: list[tuple[tuple[str, str], list[Reviewer]]] = []
        name_matches: list[tuple[tuple[str, str], list[Reviewer]]] = []
        for key, group in by_name.items():
            if len(group) < 2:
                continue
            diffs = _diff_or_missing_fields_in(group, fields)
            if not diffs:
                full_matches.append((key, group))
            else:
                name_matches.append((key, group))

        if not full_matches and not name_matches:
            continue

        print(f"\n  {C.BOLD}{fname}{C.RESET}")

        for key, group in sorted(full_matches):
            issues += 1
            _issue_header("full duplicate", f"{key[0]} {key[1]}".strip())
            _print_records(group, set(), fields)

        for key, group in sorted(name_matches):
            issues += 1
            diffs = _diff_or_missing_fields_in(group, fields)
            _issue_header(
                "name duplicate",
                f"{key[0]} {key[1]}".strip(),
                diff_fields=sorted(diffs, key=fields.index),
            )
            _print_records(group, diffs, fields)

    if issues == 0:
        print(f"  {C.GREEN}✓ no duplicates{C.RESET}")
    else:
        print(f"\n  {C.DIM}{issues} duplicate group(s) found{C.RESET}")
    return issues


# ---------------------------------------------------------------------------
# Cross-file checks
# ---------------------------------------------------------------------------


def report_easychair_id_collisions(reviewers: list[Reviewer]) -> int:
    """Same EasyChair user id across files = same person → flag any drift.

    Only the EasyChair-source files carry a "#" column; sp_/fp_ files come
    from OpenReview and have no id, so they're naturally excluded.
    """
    by_id: dict[str, list[Reviewer]] = defaultdict(list)
    for r in reviewers:
        if r.easychair_id_key:
            by_id[r.easychair_id_key].append(r)

    _banner(
        "EASYCHAIR ID COLLISIONS — same '#', diverging name / email / affiliation / country",
        C.MAG,
    )
    issues = 0
    fields = (
        "first_name",
        "middle_name",
        "last_name",
        "email",
        "affiliation",
        "country",
    )
    for ec_id, group in sorted(by_id.items()):
        if not _spans_multiple_files(group):
            continue
        diffs = _diff_or_missing_fields_in(group, fields)
        if not diffs:
            continue
        issues += 1
        _issue_header("ec_id", ec_id, diff_fields=sorted(diffs, key=fields.index))
        _print_records(group, diffs, fields)
    if issues == 0:
        print(f"  {C.GREEN}✓ no inconsistencies{C.RESET}")
    else:
        print(f"\n  {C.DIM}{issues} EasyChair id(s) with diverging fields{C.RESET}")
    return issues


def report_email_collisions(reviewers: list[Reviewer]) -> int:
    by_email: dict[str, list[Reviewer]] = defaultdict(list)
    for r in reviewers:
        if r.email_key:
            by_email[r.email_key].append(r)

    _banner(
        "EMAIL COLLISIONS — same email, diverging name / affiliation / country", C.MAG
    )
    issues = 0
    # Same email = same person → flag missing fields and any name drift.
    # Role is omitted: legitimate per-track variation, not an inconsistency.
    fields = ("first_name", "middle_name", "last_name", "affiliation", "country")
    for email, group in sorted(by_email.items()):
        if not _spans_multiple_files(group):
            continue
        diffs = _diff_or_missing_fields_in(group, fields)
        if not diffs:
            continue
        issues += 1
        _issue_header("email", email, diff_fields=sorted(diffs, key=fields.index))
        _print_records(group, diffs, fields)
    if issues == 0:
        print(f"  {C.GREEN}✓ no inconsistencies{C.RESET}")
    else:
        print(f"\n  {C.DIM}{issues} email(s) with diverging fields{C.RESET}")
    return issues


def report_same_name_diff_email(by_name: dict[tuple[str, str], list[Reviewer]]) -> int:
    _section("Same full name, different non-empty email")
    issues = 0
    fields = ("email", "affiliation", "country")
    for key, group in sorted(by_name.items()):
        if not _spans_multiple_files(group):
            continue
        if _has_distinct_easychair_ids(group):
            continue
        emails = _diff_field((r.email for r in group))
        if len(emails) <= 1:
            continue
        # Filter to records that have an email (only those tell the story)
        shown = [r for r in group if r.email]
        diffs = _diff_fields_in(shown, fields)
        # Name-only match with ≥2 other fields disagreeing → almost certainly
        # different people who share a common name.
        if len(diffs) >= 2:
            continue
        issues += 1
        _issue_header(
            "name",
            f"{key[0]} {key[1]}".strip(),
            diff_fields=sorted(diffs, key=fields.index),
        )
        _print_records(shown, diffs, fields)
    if issues == 0:
        print(f"  {C.GREEN}✓ no inconsistencies{C.RESET}")
    return issues


def report_same_name_diff_aff(by_name: dict[tuple[str, str], list[Reviewer]]) -> int:
    _section("Same full name, different non-empty affiliation or country")
    issues = 0
    fields = ("email", "affiliation", "country")
    for key, group in sorted(by_name.items()):
        if not _spans_multiple_files(group):
            continue
        if _has_distinct_easychair_ids(group):
            continue
        affs = _diff_field((r.affiliation for r in group))
        countries = _diff_field((r.country for r in group))
        if len(affs) <= 1 and len(countries) <= 1:
            continue
        diffs = _diff_fields_in(group, fields)
        # Name-only match with ≥2 other fields disagreeing → likely namesakes,
        # not the same person.
        if len(diffs) >= 2:
            continue
        issues += 1
        _issue_header(
            "name",
            f"{key[0]} {key[1]}".strip(),
            diff_fields=sorted(diffs, key=fields.index),
        )
        _print_records(group, diffs, fields)
    if issues == 0:
        print(f"  {C.GREEN}✓ no inconsistencies{C.RESET}")
    return issues


def report_same_last_initial_diff_first(reviewers: list[Reviewer]) -> int:
    _section(
        "Same last name + first initial, different first name "
        "(matching affiliation or email domain)"
    )
    by_last_initial: dict[tuple[str, str], list[Reviewer]] = defaultdict(list)
    for r in reviewers:
        first, last = r.name_key
        if first and last:
            by_last_initial[(first[0], last)].append(r)

    issues = 0
    fields = ("first_name", "middle_name", "last_name", "email", "affiliation")
    for key, group in sorted(by_last_initial.items()):
        firsts = {r.first_name.lower() for r in group if r.first_name}
        if len(firsts) < 2:
            continue
        buckets: dict[str, list[Reviewer]] = defaultdict(list)
        for r in group:
            buckets[r.first_name.lower()].append(r)
        names = sorted(buckets)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if not _first_names_similar(names[i], names[j]):
                    continue
                a_recs = buckets[names[i]]
                b_recs = buckets[names[j]]
                combined = a_recs + b_recs
                if not _spans_multiple_files(combined):
                    continue
                if _has_distinct_easychair_ids(combined):
                    continue
                a_affs = {r.affiliation.lower() for r in a_recs if r.affiliation}
                b_affs = {r.affiliation.lower() for r in b_recs if r.affiliation}
                a_dom = {
                    r.email.split("@")[-1].lower() for r in a_recs if "@" in r.email
                }
                b_dom = {
                    r.email.split("@")[-1].lower() for r in b_recs if "@" in r.email
                }
                shared_aff = a_affs & b_affs
                shared_dom = a_dom & b_dom
                if not (shared_aff or shared_dom):
                    continue
                issues += 1
                hint = []
                if shared_aff:
                    hint.append(f"shared affiliation: {sorted(shared_aff)[0]}")
                if shared_dom:
                    hint.append(f"shared domain: {sorted(shared_dom)[0]}")
                # Highlight first_name as diff (always differs by definition)
                # plus any other field that disagrees.
                diffs = _diff_fields_in(combined, fields) | {"first_name"}
                _issue_header(
                    "last name",
                    key[1],
                    note=f"first initial '{key[0]}' — " + "; ".join(hint),
                    diff_fields=sorted(diffs, key=fields.index),
                )
                _print_records(combined, diffs, fields)
    if issues == 0:
        print(f"  {C.GREEN}✓ no inconsistencies{C.RESET}")
    return issues


def report_first_or_last_only(reviewers: list[Reviewer]) -> int:
    _banner(
        "FIRST-OR-LAST-NAME ONLY MATCHES — same email, partial name agreement",
        C.MAG,
    )
    by_email: dict[str, list[Reviewer]] = defaultdict(list)
    for r in reviewers:
        if r.email_key:
            by_email[r.email_key].append(r)

    issues = 0
    fields = ("first_name", "middle_name", "last_name", "affiliation", "country")
    for email, group in sorted(by_email.items()):
        if not _spans_multiple_files(group):
            continue
        firsts = {r.first_name.lower() for r in group if r.first_name}
        lasts = {r.last_name.lower() for r in group if r.last_name}
        only_first_agrees = len(firsts) == 1 and len(lasts) > 1
        only_last_agrees = len(lasts) == 1 and len(firsts) > 1
        if not (only_first_agrees or only_last_agrees):
            continue
        which = (
            "first matches, last differs"
            if only_first_agrees
            else "last matches, first differs"
        )
        issues += 1
        diffs = _diff_or_missing_fields_in(group, fields)
        _issue_header(
            "email", email, note=which, diff_fields=sorted(diffs, key=fields.index)
        )
        _print_records(group, diffs, fields)
    if issues == 0:
        print(f"  {C.GREEN}✓ no inconsistencies{C.RESET}")
    return issues


# ---------------------------------------------------------------------------
# Unique reviewer estimate
# ---------------------------------------------------------------------------


def estimate_unique_reviewers(reviewers: list[Reviewer]) -> int:
    """Cluster rows that *could* refer to the same person and count clusters.

    Two rows are unioned when they agree on a strong identity signal:
      • same non-empty EasyChair id, or
      • same non-empty email (case-insensitive), or
      • same non-empty full name and same non-empty affiliation
        (case-insensitive).

    Missing fields don't contradict; non-empty differing fields are simply
    never unioned, so two rows with the same name but different emails stay
    in separate clusters. Track chairs are excluded.
    """
    pool = [r for r in reviewers if not _is_track_chair(r)]
    n = len(pool)

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    by_ec: dict[str, list[int]] = defaultdict(list)
    by_email: dict[str, list[int]] = defaultdict(list)
    by_name_aff: dict[tuple[str, str], list[int]] = defaultdict(list)

    for i, r in enumerate(pool):
        if r.easychair_id_key:
            by_ec[r.easychair_id_key].append(i)
        if r.email_key:
            by_email[r.email_key].append(i)
        name = r.full_name.lower().strip()
        aff = r.affiliation.lower().strip()
        if name and aff:
            by_name_aff[(name, aff)].append(i)

    for buckets in (by_ec.values(), by_email.values(), by_name_aff.values()):
        for idxs in buckets:
            first = idxs[0]
            for j in idxs[1:]:
                union(first, j)

    roots = {find(i) for i in range(n)}
    unique = len(roots)

    _banner(f"ESTIMATED UNIQUE REVIEWERS — {unique} (from {n} non-chair rows)", C.CYAN)
    print(
        f"  {C.DIM}clustered by EasyChair id, email, or "
        f"(full name + affiliation){C.RESET}"
    )
    print(f"  {C.DIM}rows merged: {n - unique}{C.RESET}")
    return unique


# ---------------------------------------------------------------------------
# Merge to single workbook
# ---------------------------------------------------------------------------

# Worksheet names must be ≤ 31 chars and exclude : \ / ? * [ ]
_FORBIDDEN = set(":\\/?*[]")


def _safe_sheet_name(stem: str, used: set[str]) -> str:
    cleaned = "".join(c for c in stem if c not in _FORBIDDEN).strip()
    cleaned = cleaned[:31] or "Sheet"
    name = cleaned
    n = 2
    while name in used:
        suffix = f" ({n})"
        name = (cleaned[: 31 - len(suffix)]) + suffix
        n += 1
    used.add(name)
    return name


def _is_track_chair(r: Reviewer) -> bool:
    return r.role.strip().lower() == "track chair"


def _track_and_role(r: Reviewer) -> tuple[str, str]:
    """Return (track label, short role code) for grouping in the merged output."""
    info = FILE_TRACK_INFO.get(r.source_file)
    track = info[0] if info else os.path.splitext(r.source_file)[0]
    if info and info[1]:
        return track, info[1]
    role_lower = r.role.lower().strip()
    role_code = ROLE_CODE.get(role_lower, r.role or "PC")
    return track, role_code


def write_merged_workbook(reviewers: list[Reviewer], output_path: str) -> None:
    """Write reviewer rows into one xlsx with one sheet per (track, role).

    Track chairs are dropped — their entries exist in the source files only
    to support cross-file consistency checks. Output keeps only first name,
    middle name, last name, and affiliation; sheet names are like
    "Full Papers - PC", "Resource - PC", "Tutorials - PC".
    """
    kept = [r for r in reviewers if not _is_track_chair(r)]
    dropped = len(reviewers) - len(kept)

    grouped: dict[tuple[str, str], list[Reviewer]] = defaultdict(list)
    for r in kept:
        grouped[_track_and_role(r)].append(r)

    columns = ["first name", "middle name", "last name", "affiliation"]
    used_names: set[str] = set()
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for track, role_code in sorted(grouped, key=_sheet_sort_key):
            sheet_label = f"{track} - {role_code}"
            sheet_name = _safe_sheet_name(sheet_label, used_names)
            sorted_recs = sorted(
                grouped[(track, role_code)],
                key=lambda r: (r.first_name.lower(), r.last_name.lower()),
            )
            rows = [
                {
                    "first name": r.first_name,
                    "middle name": r.middle_name,
                    "last name": r.last_name,
                    "affiliation": r.affiliation,
                }
                for r in sorted_recs
            ]
            pd.DataFrame(rows, columns=columns).to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )
    print(
        f"\n{C.GREEN}✓ wrote {len(kept)} rows to {output_path}"
        f" across {len(grouped)} sheets"
        f" ({dropped} track chair row(s) dropped){C.RESET}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Scan referees/ for cross-file inconsistencies and merge into one workbook.",
    )
    p.add_argument(
        "--input",
        "-i",
        default=DEFAULT_INPUT_DIR,
        help=f"Input directory containing per-track xlsx files (default: {DEFAULT_INPUT_DIR})",
    )
    p.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output xlsx file with one sheet per source file (default: {DEFAULT_OUTPUT_FILE})",
    )
    p.add_argument(
        "--no-merge",
        action="store_true",
        help="Skip writing the merged xlsx; only print the inconsistency report.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not os.path.isdir(args.input):
        print(f"Directory not found: {args.input}", file=sys.stderr)
        return 2

    reviewers = load_all(args.input)
    normalize(reviewers)
    print(f"{C.BOLD}Loaded {len(reviewers)} reviewer rows from {args.input}/{C.RESET}")

    report_per_file_role_counts(reviewers)

    total = 0
    total += report_within_file_duplicates(reviewers)
    total += report_easychair_id_collisions(reviewers)
    total += report_email_collisions(reviewers)

    by_name: dict[tuple[str, str], list[Reviewer]] = defaultdict(list)
    for r in reviewers:
        if r.first_name or r.last_name:
            by_name[r.name_key].append(r)

    _banner("SUSPICIOUS NAME MATCHES ACROSS FILES", C.MAG)
    total += report_same_name_diff_email(by_name)
    total += report_same_name_diff_aff(by_name)
    total += report_same_last_initial_diff_first(reviewers)

    total += report_first_or_last_only(reviewers)

    _banner(
        f"SUMMARY — {total} potential inconsistency group(s) found",
        C.GREEN if total == 0 else C.YEL,
    )

    if not args.no_merge:
        write_merged_workbook(reviewers, args.output)

    estimate_unique_reviewers(reviewers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
