# Overview

This project hosts scripts for preparing ACM proceedings from conference management systems.

**Supported sources:**
1. **OpenReview** - Export accepted papers from OpenReview venues
2. **EasyChair** - Export accepted papers from EasyChair exports (Excel format)

**Output formats:**
- ACM/Sheridan XML format (following: https://cms.acm.org/paperLoad/paperLoadSAMPLE.xml)
- Plain text (TXT) - Human-readable listing of papers and authors
- Markdown (MD) - Formatted listing with headers
- MS Word document listing titles and authors

---

# Quick Reference

## Typical Workflow

1. **Export from conference system:**
   - **OpenReview:** `python openreview_to_acm_xml.py --venue_id "ICLR.cc/2024/Conference" --paper_type "Full Paper" --output output.xml`
   - **EasyChair:** `python easychair_to_acm_xml_v2.py --input export.xlsx --proceeding_id "2026-SIGIR" --output output.xml`

2. **Validate and analyze the XML (RECOMMENDED):**
   ```bash
   # Single file
   python validate_acm_xml.py output.xml
   
   # Multiple files (aggregates statistics)
   python validate_acm_xml.py full_papers.xml short_papers.xml demo_papers.xml
   ```
   This verifies data quality, checks contact authors, and generates comprehensive statistics.

3. **(Optional) Convert to Word document:**
   ```bash
   python acm_xml_to_ms_word.py --input_xml output.xml --output_docx papers.docx
   ```

---

# Repository Structure

```
.
├── readme.md                           # This file
├── requirements.txt                    # Python dependencies
│
├── openreview_to_acm_xml.py               # OpenReview export script
├── openreview_to_acm_xml.ipynb            # OpenReview export (Jupyter)
│
├── easychair_to_acm_xml.py            # EasyChair v1 (original)
├── easychair_to_acm_xml_v2.py         # EasyChair v2 (Pydantic)
├── acm_xml_to_ms_word.py              # XML to Word converter
├── validate_acm_xml.py                # XML validation & analysis
│
├── lib/                                # Core library modules (v2)
│   ├── README.md                      # Library documentation
│   ├── easychair_models.py            # Pydantic models
│   ├── easychair_loader.py            # Data loader
│   ├── easychair_exporters.py         # Export formatters
│   └── __init__.py                    # Package init
│
├── tests/                              # Test scripts
│   ├── README.md                      # Test documentation
│   ├── test_pydantic_validation.py    # Unit tests
│   └── test_author_order.py           # Integration tests
│
└── docs/                               # Documentation
    ├── README.md                      # Documentation index
    ├── VALIDATION_README.md           # Validation guide
    ├── MULTI_AFFILIATION_SUPPORT.md   # Multi-affiliation docs
    ├── VALIDATION_IMPROVEMENTS.md     # v1 vs v2 comparison
    ├── FINAL_SUMMARY.md               # Complete summary
    ├── IMPLEMENTATION_CHECKLIST.md    # Feature checklist
    └── EasyChair_MATCHING_EXPLANATION.md
```

# Files

## OpenReview Export

- `openreview_to_acm_xml.py`  
  Exports submissions from OpenReview into ACM-compatible XML  

- `openreview_to_acm_xml.ipynb`  
  Jupyter notebook version of the script above, provided for easier setup

## EasyChair Export

- `easychair_to_acm_xml.py` **(v1 - Original)**  
  Exports accepted papers from EasyChair Excel export into ACM-compatible XML/TXT/MD  
  Includes data quality checks, duplicate consolidation, and typo detection

- `easychair_to_acm_xml_v2.py` **(v2 - Enhanced with Pydantic Validation)**  
  Same functionality as v1 with enhanced runtime validation using Pydantic models  
  Provides structured error/warning/info reporting and better data quality checks  
  **Recommended for new work**

- `lib/` - Supporting modules for v2
  - See [`lib/README.md`](lib/README.md) for details

## Utilities

- `validate_acm_xml.py` **(Comprehensive XML Validation)**  
  Validates and analyzes ACM XML files with detailed statistics  
  - Verifies contact author constraints (exactly one per paper)
  - Checks data quality (missing emails, affiliations, names)
  - Generates statistics (papers per track, authors, affiliations)
  - Shows most prolific authors, affiliations, and countries
  - Works with XML from any source (OpenReview or EasyChair)

- `acm_xml_to_ms_word.py`  
  Reads the generated XML file(s) and generates a formatted `.docx` file of titles and authors (for website use). 

## Documentation

- `docs/` - Detailed documentation
  - See [`docs/README.md`](docs/README.md) for complete documentation index

## Tests

- `tests/` - Unit and integration tests
  - See [`tests/README.md`](tests/README.md) for running tests  

---

# Requirements

## For OpenReview Export

Install dependencies:

```bash
pip install openreview-py python-docx python-dotenv
```

Create a `.env` file with your OpenReview credentials:

```
OPENREVIEW_USERNAME=your_email
OPENREVIEW_PASSWORD=your_password
```

## For EasyChair Export

**v1 (Original Script):**

```bash
pip install pandas openpyxl
```

**v2 (Enhanced with Pydantic):**

```bash
pip install -r requirements.txt
# Or manually:
pip install pandas openpyxl pydantic email-validator
```

No credentials needed - works with Excel export files.

**Which version to use?**
- **v1**: Simple, no extra dependencies, production-ready
- **v2**: Enhanced validation, better error messages, recommended for new work

---

# Export Accepted Papers from OpenReview

Run the script with command-line arguments. Example to export ICLR'24 accepted papers:

```bash
python openreview_to_acm_xml.py \
  --venue_id "ICLR.cc/2024/Conference" \
  --paper_type "Full Paper" \
  --output_file "ICLR_acm_comp_output.xml"
```

Parameters:

- `--venue_id` (required): OpenReview venue ID  
- `--paper_type` (optional): "Full Paper" or "Short Paper" (default: N/A)  
- `--output_file` (optional): Output XML file (default: acm_output.xml)  

---

# Notes and Assumptions

- **Author name parsing**
  - Author names are provided by OpenReview as a single string.
  - Names are split on white space:
    - First token → first name  
    - Last token → last name  
    - Middle tokens → middle name(s)  
  - This may not always be accurate for all naming conventions.

- **Contact Author (OpenReview-specific)**
  - **OpenReview exports always use first author as contact author**
  - OpenReview API does not provide a "corresponding author" field
  - Unlike EasyChair exports (which use 3-tier priority with email validation), OpenReview simply designates the first author
  - Author order is preserved as provided by OpenReview
  - **Automatic validation** runs at end of export to verify exactly one contact author per paper

- **Affiliations**
  - Affiliations are extracted from OpenReview profiles (`profile.content["history"]`). 
  - Current affiliations are entries without an endDate (may not be accurate if not current but not filled by users) 
  - If no current affiliation is found, the most recent entry is used as a fallback.

- **Paper Submission and Decision Dates**
  - The **submission date** is taken from `tcdate` (true creation date), which reflects the original submission date.
  - The **approval date** is set to the last modification date (tmdate) as a proxy for the approval date. There might be a better more accurate way for this if it is important.

---

# Export Accepted Papers from EasyChair

## Quick Reference

**Choose your version:**
- `easychair_to_acm_xml.py` (v1) - Simple, no extra dependencies ✓
- `easychair_to_acm_xml_v2.py` (v2) - Enhanced validation, recommended for new work ✓

**Choose your format:**
- `--format xml` - ACM/Sheridan XML for proceedings submission
- `--format txt` - Plain text listing (human-readable)
- `--format md` - Markdown listing (human-readable with headers)

**Detailed documentation:**
- `VALIDATION_README.md` - Complete validation system guide (v2)
- `MULTI_AFFILIATION_SUPPORT.md` - Multi-affiliation details
- `VALIDATION_IMPROVEMENTS.md` - v1 vs v2 comparison

## Step 1: Export Data from EasyChair

1. Log in to EasyChair as conference administrator
2. Go to your conference management page
3. Navigate to **Data** → **Export** → **Excel format**
4. Download the Excel file (contains Submissions, Authors, and Summary sheets)

## Step 2: Run the Conversion Script

**Basic usage (all tracks, auto-detect paper types):**

```bash
# XML format (both v1 and v2 work)
python easychair_to_acm_xml.py \
  --input "path/to/EasyChair_export.xlsx" \
  --proceeding_id "2026-SIGIR" \
  --output "sigir2026.xml"

# Plain text format (human-readable)
python easychair_to_acm_xml.py \
  --input "path/to/EasyChair_export.xlsx" \
  --format txt \
  --output "papers.txt"

# Markdown format
python easychair_to_acm_xml.py \
  --input "path/to/EasyChair_export.xlsx" \
  --format md \
  --output "papers.md"

# Using v2 with enhanced validation (same interface)
python easychair_to_acm_xml_v2.py \
  --input "path/to/EasyChair_export.xlsx" \
  --proceeding_id "2026-SIGIR" \
  --output "sigir2026.xml"
```

This automatically assigns appropriate paper types based on track names:
- Full Papers Track → "Full Research Paper"
- Short Papers Track → "Short Research Paper"
- Demo Papers Track → "Demo Short Paper"
- Resources Papers Track → "Resource Paper"
- Reproducibility Track → "Reproducibility Paper"
- Industry Papers Track → "Industry Paper"
- Perspectives Paper Track → "Perspective Paper"
- Workshop Proposals → "Workshop Summary"
- Tutorial Proposals → "Tutorial Paper"
- Doctoral Colloquium → "Doctoral Abstract"
- Low Resource Environments Track → "Low Resource Environment"

**Output Format Options:**

The script supports three output formats via the `--format` parameter:

1. **XML** (default) - ACM/Sheridan XML format for proceedings submission
2. **TXT** - Plain text listing (track name, paper title, authors with affiliations)
3. **MD** - Markdown format with headers (same structure as TXT, easier to read)

**Example TXT/MD output:**
```
Full Research Paper
First Paper Title
John Doe, MIT
Jane Smith, Stanford

Second Paper Title
Alice Brown, CMU
Bob Wilson, University of Washington
```

**Parameters:**

- `--input` (required): Path to EasyChair Excel export file
  - Must contain 'Submissions' and 'Authors' sheets

- `--format` (optional): Output format - `xml`, `txt`, or `md`
  - Default: `xml`
  - For TXT/MD formats, `--proceeding_id` is not required

- `--proceeding_id` (required for XML): ACM proceeding ID
  - Examples: `"2026-SIGIR"`, `"2018-1234.1234"`
  - Can use different IDs for different tracks if submitting separately

- `--output` (optional): Output XML file name
  - Default: `"acm_output.xml"`

- `--source` (optional): Source system name for XML metadata
  - Default: `"EasyChair"`

- `--paper_type` (optional): Override paper type for ALL papers
  - **Default behavior (recommended):** Auto-derives from track/section name:
    - "Full Papers Track" → "Full Research Paper"
    - "Short Papers Track" → "Short Research Paper"
    - "Demo Papers Track" → "Demo Short Paper"
    - "Workshop Proposals" → "Workshop Summary"
    - See full mapping list above
  - **Only use `--paper_type` when:**
    - Exporting a single track with `--track` and want to override the auto-detected type, OR
    - You need all papers to have the same type regardless of track (rare)

- `--track` (optional): **Export ONLY papers from this specific track**
  - Excludes all papers from other tracks
  - Track name must be **EXACT match** (case-sensitive) from EasyChair's "Track name" column
  - Examples:
    - `"SIGIR 2026 Demo Papers Track"`
    - `"SIGIR 2026 Full Papers Track"`
    - `"SIGIR 2026 Workshop Proposals"`
  - **Use cases:**
    - Generate separate XML files per track for separate ACM submissions
    - Test with a small track (e.g., 10 workshops) before exporting all 300+ papers
    - Use different proceeding IDs for different paper types
  - **To find available track names:** Open your Excel file and check the "Track name" column

**Example: Export specific track only**

When exporting a single track, paper type is auto-detected, but you can override if needed:

```bash
# Auto-detect paper type from track name (recommended)
python easychair_to_acm_xml.py \
  --input "SIGIR2026_export.xlsx" \
  --proceeding_id "2026-SIGIR-Demo" \
  --track "SIGIR 2026 Demo Papers Track" \
  --output "sigir2026_demos.xml"

# Or explicitly set paper type (optional)
python easychair_to_acm_xml.py \
  --input "SIGIR2026_export.xlsx" \
  --proceeding_id "2026-SIGIR-Demo" \
  --track "SIGIR 2026 Demo Papers Track" \
  --paper_type "Demo Short Paper" \
  --output "sigir2026_demos.xml"
```

**Example: Generate separate XML files for each track**

```bash
# Export each track separately with different proceeding IDs
python easychair_to_acm_xml.py \
  --input "SIGIR2026.xlsx" \
  --proceeding_id "2026-SIGIR-Demo" \
  --track "SIGIR 2026 Demo Papers Track" \
  --output "sigir2026_demos.xml"

python easychair_to_acm_xml.py \
  --input "SIGIR2026.xlsx" \
  --proceeding_id "2026-SIGIR-Full" \
  --track "SIGIR 2026 Full Papers Track" \
  --output "sigir2026_full.xml"

python easychair_to_acm_xml.py \
  --input "SIGIR2026.xlsx" \
  --proceeding_id "2026-SIGIR-Workshops" \
  --track "SIGIR 2026 Workshop Proposals" \
  --output "sigir2026_workshops.xml"
```

**How to find available track names:**

Method 1 - Open Excel and check "Track name" column in Submissions sheet

Method 2 - Use Python to list all tracks:
```python
import pandas as pd
df = pd.read_excel("your_export.xlsx", sheet_name="Submissions")
print("\nAvailable tracks:")
for track in sorted(df['Track name'].unique()):
    count = len(df[df['Track name'] == track])
    print(f"  - {track} ({count} submissions)")
```

Method 3 - Run the script without --track to see track mapping in the summary output

## Features

The script automatically:

✅ **Filters accepted papers only** (status: "Accept paper/proposal" or "tentatively accepted")  
✅ **Cleans text fields** - removes line feeds, tabs, extra whitespace from all fields  
✅ **Auto-detects conference name** - extracts from track names (e.g., "SIGIR 2026")  
✅ **Maps track names to ACM sections** - removes conference prefix, normalizes format  
✅ **Consolidates duplicate authors** - fills ONLY empty fields, never overwrites existing values  
✅ **Multi-affiliation support** - authors can have different affiliations/emails across papers  
✅ **Detects typos** - flags same email with different names (warning), same name with different emails (info)  
✅ **Sets single contact author per paper** - 3-tier priority: (1) first corresponding with valid email, (2) first author with valid email, (3) first author fallback  
✅ **Generates detailed statistics** - track mapping, author counts, quality warnings  
✅ **Shows top prolific authors** - displays top 5 authors with paper type breakdown, includes all ties  
✅ **Comprehensive logging** - saves detailed log file (`.xml.log`, `.txt.log`, `.md.log`) for debugging and audit  
✅ **Multiple output formats** - XML (ACM submission), TXT (human-readable), MD (markdown)  

### Multi-Affiliation Support

Authors can legitimately have different information across papers:
- ✅ Different affiliations (changed institutions)
- ✅ Different emails (multiple addresses, moved institutions)
- ✅ Different countries (relocated)

**How it works:**
- Empty fields are filled from other papers (same author)
- Existing values are NEVER overwritten
- Example: Paper 1: "John, MIT" | Paper 2: "John, Stanford" → Both preserved ✓

See `MULTI_AFFILIATION_SUPPORT.md` for details.  

## Logging and Output

The script provides comprehensive logging to both console and file:

**Console output (INFO level and above):**
- Summary statistics and progress
- Data quality warnings (summary counts only)
- Typo detection results (summary counts only)
- References to log file for complete details

**Log file (ALL levels including DEBUG):**
- Everything shown on console
- **Detailed field corrections** - Complete list of which fields were filled for which authors
- **Detailed typo listings** - Full list of all email/name mismatches with paper numbers
- Processing details for debugging
- Complete audit trail with timestamps

**Log file location:**
- Automatically created alongside the XML output
- Named: `<output_filename>.log`
- Example: If output is `sigir2026.xml`, log is `sigir2026.log`

**Log levels used:**
- `DEBUG` - Detailed field corrections, full typo listings, internal processing steps
- `INFO` - Progress updates, summary statistics, successful operations
- `WARNING` - Data quality issue summaries with log file references
- `ERROR` - Critical errors (e.g., papers with no authors)

## Output Summary

The script prints a detailed summary including:

```
================================================================================
EASYCHAIR TO ACM XML CONVERSION
================================================================================
Loading Excel file: SIGIR2026.xlsx
Loaded 304 submissions and 3958 author records
Found 304 accepted submissions
Detected conference: SIGIR 2026

Consolidating duplicate author entries...
✓ Made 15 field correction(s) across duplicate author entries
  → Check log file for detailed list of corrections

Checking for potential typos in author data...
⚠ Found 12 potential typo(s) or data inconsistencies:
  • Same email, different names: 3 email(s) affected
  • Same name, different emails: 5 name(s) affected
  → Check log file for complete details

Generating ACM XML...

================================================================================
EXPORT SUMMARY
================================================================================

✓ XML generated: sigir2026.xml
✓ Total papers exported: 304
✓ Total author entries: 1,234
✓ Unique authors: 987
✓ Average authors per paper: 4.1
✓ Average papers per author: 1.25

--------------------------------------------------------------------------------
TRACK NAME MAPPING
--------------------------------------------------------------------------------
  SIGIR 2026 Full Papers Track
    → Full Research Paper (131 papers)
  SIGIR 2026 Short Papers Track
    → Short Research Paper (58 papers)
  SIGIR 2026 Demo Papers Track
    → Demo Short Paper (24 papers)
  SIGIR 2026 Workshop Proposals
    → Workshop Summary (10 papers)
  ...

--------------------------------------------------------------------------------
TOP 5 MOST PROLIFIC AUTHORS
--------------------------------------------------------------------------------
  1. John Smith (john@mit.edu): 5 paper(s)
     Paper types: 3 Demo Short Paper, 2 Full Research Paper
     Papers: #78, #105, #110, #118, #128
  2. Jane Doe (jane@stanford.edu): 4 paper(s)
     Paper types: 2 Full Research Paper, 1 Workshop Summary, 1 Tutorial Paper
     Papers: #162, #165, #169, #172
  3. Bob Wang: 3 paper(s)
     Paper types: 2 Industry Paper, 1 Resource Paper
  4. Alice Chen: 3 paper(s)
     Paper types: 3 Full Research Paper
  5. Carol Lee: 3 paper(s)
     Paper types: 2 Demo Short Paper, 1 Full Research Paper

Note: If multiple authors are tied at the 5th position, all tied authors are included

Examples:
  • Normal case (no ties): Shows exactly 5 authors
    Title: "TOP 5 MOST PROLIFIC AUTHORS"
  
  • With ties at 5th place: Paper counts [10, 8, 7, 3, 3, 3, 2, 1...]
    Shows 6 authors (top 3 + three authors tied with 3 papers)
    Title: "TOP 6 MOST PROLIFIC AUTHORS (including ties)"
  
  • Fewer than 5 authors: Shows all authors (e.g., 3 total)
    Title: "TOP 3 MOST PROLIFIC AUTHORS"

--------------------------------------------------------------------------------
DATA QUALITY WARNINGS
--------------------------------------------------------------------------------
  ⚠ 15 paper(s) used fallback contact author selection
     → Priority 2 (first author with valid email) or Priority 3 (first author fallback)
  ⚠ 8 paper(s) have at least one author with missing affiliation
  ⚠ 3 author(s) have missing or invalid email addresses
================================================================================
Log file saved to: sigir2026.log
```

**Note:** All detailed corrections and typo listings are logged to the `.log` file but only summaries are shown on console to keep output concise.

**Example log file content (showing DEBUG details):**
```
2026-04-09 14:23:15 - INFO - ================================================================================
2026-04-09 14:23:15 - INFO - EASYCHAIR TO ACM XML CONVERSION
2026-04-09 14:23:15 - INFO - ================================================================================
2026-04-09 14:23:15 - INFO - Loading Excel file: SIGIR2026.xlsx
2026-04-09 14:23:15 - DEBUG - Proceeding ID: 2026-SIGIR
2026-04-09 14:23:15 - DEBUG - Output file: sigir2026.xml
2026-04-09 14:23:15 - DEBUG - Log file: sigir2026.log
2026-04-09 14:23:16 - INFO - Loaded 304 submissions and 3958 author records
2026-04-09 14:23:16 - INFO - Found 304 accepted submissions
2026-04-09 14:23:16 - INFO - Detected conference: SIGIR 2026

2026-04-09 14:23:17 - INFO - Consolidating duplicate author entries...
2026-04-09 14:23:17 - DEBUG -   → Filling Affiliation for John Smith (Paper #123): '' → 'MIT'
2026-04-09 14:23:17 - DEBUG -   → Filling Email for Jane Doe (Paper #456): 'nan' → 'jane@example.com'
2026-04-09 14:23:17 - WARNING - ✓ Made 15 field correction(s) across duplicate author entries
2026-04-09 14:23:17 - WARNING -   → Check log file for detailed list of corrections

2026-04-09 14:23:18 - INFO - Checking for potential typos in author data...
2026-04-09 14:23:18 - WARNING - ⚠ Found 12 potential typo(s) or data inconsistencies:
2026-04-09 14:23:18 - WARNING -   • Same email, different names: 3 email(s) affected
2026-04-09 14:23:18 - WARNING -   • Same name, different emails: 5 name(s) affected
2026-04-09 14:23:18 - WARNING -   → Check log file for complete details
2026-04-09 14:23:18 - DEBUG - 
2026-04-09 14:23:18 - DEBUG - ================================================================================
2026-04-09 14:23:18 - DEBUG - DETAILED TYPO/INCONSISTENCY REPORT
2026-04-09 14:23:18 - DEBUG - ================================================================================
2026-04-09 14:23:18 - DEBUG - 
2026-04-09 14:23:18 - DEBUG - Same email, different names (3 email(s) affected):
2026-04-09 14:23:18 - DEBUG - --------------------------------------------------------------------------------
2026-04-09 14:23:18 - DEBUG -   Email: john@example.com
2026-04-09 14:23:18 - DEBUG -     → First: 'John' | Last: 'Smith' (Papers: #100)
2026-04-09 14:23:18 - DEBUG -     → First: 'Jon' | Last: 'Smith' (Papers: #200)
...
```

## Notes and Assumptions (EasyChair)

- **Paper Type Assignment**
  - By default, paper type is **automatically derived** from the track/section name
  - This ensures correct paper types when exporting multiple tracks simultaneously
  - Examples:
    - "Full Papers Track" → paper_type: "Full Research Paper"
    - "Demo Papers Track" → paper_type: "Demo Short Paper"
    - "Workshop Proposals" → paper_type: "Workshop Summary"
    - See complete mapping list above
  - Use `--paper_type` override only when all papers should have the same type

- **Track Name Mapping**
  - EasyChair track names are automatically cleaned to match ACM section conventions
  - Conference prefix is auto-detected and removed (e.g., "SIGIR 2026 ")
  - " Track" suffix is removed
  - Track names are mapped to ACM paper types using a predefined dictionary:
    - Full Papers → Full Research Paper
    - Short Papers → Short Research Paper
    - Demo Papers → Demo Short Paper
    - Resources Papers → Resource Paper
    - Reproducibility → Reproducibility Paper
    - Industry Papers → Industry Paper
    - Perspectives Paper → Perspective Paper
    - Workshop Proposals → Workshop Summary
    - Tutorial Proposals → Tutorial Paper
    - Doctoral Colloquium → Doctoral Abstract
    - Low Resource Environments → Low Resource Environment
  - If a track is not in the mapping, the cleaned track name is used as-is

- **Event Tracking Numbers**
  - Each paper gets a unique event tracking number with a paper type prefix
  - Format: `{prefix}{submission_number}`
  - Example: Submission #78 as Full Research Paper → `fp78`
  - Prefix mapping:
    - Full Research Paper → `fp`
    - Short Research Paper → `sp`
    - Resource Paper → `rr`
    - Reproducibility Paper → `rp`
    - Demo Short Paper → `de`
    - Perspective Paper → `per`
    - Industry Paper → `ip`
    - Tutorial Paper → `tut`
    - Low Resource Environment → `lre`
    - Doctoral Abstract → `dc`
    - Workshop Summary → `wk`
  - This makes it easy to identify paper types at a glance in the XML file

- **Author Data Consolidation**
  - Authors with multiple papers may have missing information in some entries
  - The script fills ONLY empty fields using data from other papers by the same author
  - **Existing values are NEVER overwritten** - authors can have different affiliations per paper
  - Example: Paper 1: "John Doe, MIT" | Paper 2: "John Doe, Stanford" → Both kept unchanged
  - All corrections are logged for review (see `.log` file)

- **Affiliation Parsing**
  - EasyChair stores affiliations as a single string
  - The script attempts to split "Department, Institution" format
  - If no comma, entire string is treated as institution name

- **Contact Author Selection (EasyChair-specific)**
  - **Exactly one contact author per paper** using 3-tier priority system:
    1. **Priority 1:** First corresponding author (✔ in EasyChair) with valid email
    2. **Priority 2:** First author with valid email (logs WARNING with paper details)
    3. **Priority 3:** First author regardless of email validity (logs ERROR with paper details)
  - Priority 2 and 3 usage is logged with paper ID and title for data quality tracking
  - Summary shows count of papers using fallback priorities
  - **Note:** OpenReview exports use simpler logic (always first author) due to API limitations

- **Accepted Papers**
  - Only papers with decision "Accept paper/proposal" or "tentatively accepted" are included
  - All other submissions are filtered out

---

# Validate and Analyze ACM XML Files

After generating an ACM XML file, you can validate and analyze it with a comprehensive validation script:

```bash
# Validate single file
python validate_acm_xml.py <xml_file>

# Validate multiple files with aggregated statistics
python validate_acm_xml.py <xml_file1> <xml_file2> ...

# Examples
python validate_acm_xml.py sigir2026.xml
python validate_acm_xml.py full_papers.xml short_papers.xml demo_papers.xml
python validate_acm_xml.py sigir2026-*.xml
```

## What the Validation Script Does

The validation script performs comprehensive checks and analysis:

**Validation:**
- ✓ Verifies exactly one contact author per paper
- ✓ Checks for missing data (emails, affiliations, names)
- ✓ Validates XML structure

**Statistics (per file or aggregated):**
- Papers by track/section (with percentages)
- Papers by type
- Author statistics (total, unique, averages)
- Top 10 most prolific authors (with paper type breakdown)
- Top 20 most common affiliations
- Top 20 most common countries

**Multi-file Support:**
- Validate multiple XML files at once
- Each file is validated separately
- Statistics are aggregated across all files
- Useful when different tracks are exported to separate files

**Output:**
- Detailed issue reports (if any)
- Summary statistics
- Exit code 0 if valid, 1 if issues found

This script works with XML files generated from:
- OpenReview exports (`openreview_to_acm_xml.py`)
- EasyChair exports (`easychair_to_acm_xml.py`, `easychair_to_acm_xml_v2.py`)

---

# Convert the XML file(s) into .docx 

Run the script with command-line arguments. Example to convert SIGIR papers from XML files(s) into an MS Word doc:

```bash
    python acm_xml_to_ms_word.py \
    --input_xml sigir26-short.xml sigir26-full.xml SIGIR2026-others.xml \
    --output_docx accepted-papers.docx
```

Parameters:

- `--input_xml` (required): Path to input XML file(s)  
- `--output_docx` (optional): Output Word file (default: papers_list.docx)  

