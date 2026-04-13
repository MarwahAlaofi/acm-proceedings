# Validation Package

This package provides comprehensive validation and analysis tools for ACM XML files, including data quality checks, affiliation similarity detection, and statistical analysis.

## Key Assumptions (TL;DR)

**Affiliation Similarity Detection:**
- **Primary signal**: Institutional email domains (@university.edu)
- **Excluded**: Public email services (gmail.com, yahoo.com, hotmail.com, acm.org, etc.)
- **Normalization**: Student/staff subdomains treated as equivalent (student.X.edu → X.edu)
- **Three-tier matching**: Known aliases → Email domain → String similarity
- **False positive prevention**: Matching email domains must pass basic similarity check
- **See flowchart in [Algorithm Details](#algorithm-details) section below**

**Country Normalization:**
- Uses `pycountry` library for standardization
- Converts ISO codes to full names (US → United States, CN → China)
- Handles abbreviations (U.S., U.K., U.A.E.)

**Statistics:**
- Tracks both author counts AND unique paper counts per affiliation/country
- Multi-file aggregation: author counts sum, paper IDs deduplicate

## Table of Contents

- [Quick Start](#quick-start)
- [Module Overview](#module-overview)
- [Usage Examples](#usage-examples)
- [Assumptions and Design Decisions](#assumptions-and-design-decisions)
- [Algorithm Details](#algorithm-details)
- [Configuration](#configuration)

## Quick Start

**Command-line validation (most common usage):**

```bash
# Validate single XML file
python validate_acm_xml.py sigir2026.xml

# Generate formatted reports (creates 3 files: validation, statistics, similar affiliations)
python validate_acm_xml.py sigir2026.xml --output sigir2026_report

# Control top-k items in statistics (default: 20)
python validate_acm_xml.py sigir2026.xml --output report --top_k 10
python validate_acm_xml.py sigir2026.xml --output report --top_k full  # Show all items

# Validate multiple XML files with aggregated statistics
python validate_acm_xml.py full.xml short.xml demo.xml --output combined
```

**Output files** (when using `--output prefix`):
- `prefix_validation.txt` - Data quality issues and validation status
- `prefix_statistics.txt` - Comprehensive statistics with formatted tables
- `prefix_similar_affiliations.txt` - Detailed affiliation similarity groups

**Programmatic usage:**

```python
from validation import (
    check_name_capitalization,
    check_email_name_consistency,
    find_similar_affiliations,
    generate_statistics,
    print_statistics
)

# Load and parse XML
tree = ET.parse('proceedings.xml')
root = tree.getroot()

# Run validation checks
name_issues = check_name_capitalization(root)
email_issues = check_email_name_consistency(root)
similar_groups = find_similar_affiliations(root)

# Generate and print statistics
stats = generate_statistics(root)
print_statistics(stats, root=root, top_k=20)
```

## Module Overview

### Structure

```
validation/
├── __init__.py         # Package initialization and exports
├── checks.py           # Author name, email, and affiliation validation
├── aggregation.py      # Multi-file statistics merging
├── statistics.py       # Statistics generation and reporting
└── README.md          # This file
```

### checks.py

**Data quality validation functions:**

- `check_name_capitalization(root)` - Validates first/last names start with capitals
- `check_email_name_consistency(root)` - Detects same email with different names
- `find_similar_affiliations(root)` - Three-tier affiliation matching (aliases → email domain → string similarity)
- `merge_similar_affiliation_counts(stats, similar_groups)` - Merges counts for similar affiliations

**Output formatting functions:**

- `print_name_capitalization_issues(issues)` - Formats name capitalization problems
- `print_email_name_consistency_issues(issues)` - Formats email-name inconsistencies
- `print_similar_affiliations(similar_groups)` - Formats affiliation similarity groups

**Configuration:**

- `INSTITUTION_ALIASES` - Whitelist of known institution name variations
- `INSTITUTION_BLACKLIST` - Blacklist of institutions that should never merge
- `normalize_email_domain(domain)` - Treats institutional subdomains as equivalent

### aggregation.py

**Multi-file statistics merging:**

- `merge_statistics(stats_list)` - Merges statistics from multiple XML files
  - Author counts sum across files
  - Paper IDs deduplicate (same paper in multiple files counted once)
- `merge_quality_stats(quality_list)` - Merges data quality statistics from multiple files

### statistics.py

**Statistics generation and reporting:**

- `generate_statistics(root)` - Generates comprehensive statistics from single XML file
  - Papers per track/type with author counts
  - Author counts and unique paper counts per author
  - Affiliation and country distributions
  - Prolific authors (most papers)
  
- `print_statistics(stats, root=None, top_k=20)` - Prints formatted statistics
  - Optionally includes merged affiliation statistics when root provided
  - Controls number of items shown with top_k parameter

**Country normalization:**

- `normalize_country(country_str)` - Uses pycountry for standardization
- Converts ISO codes (US, USA, CHN) to full names
- Handles abbreviations with periods (U.S., U.K., U.A.E.)
- Maps official names to common names (Korea, Republic of → South Korea)

## Usage Examples

### Example 1: Basic Validation

```python
import xml.etree.ElementTree as ET
from validation import (
    check_name_capitalization,
    check_email_name_consistency,
    find_similar_affiliations
)

# Parse XML
tree = ET.parse('proceedings.xml')
root = tree.getroot()

# Check for name capitalization issues
name_issues = check_name_capitalization(root)
if name_issues:
    print(f"Found {len(name_issues)} papers with name capitalization issues")
    for paper_id, authors in name_issues.items():
        print(f"  Paper {paper_id}: {len(authors)} authors with issues")

# Check email-name consistency
email_issues = check_email_name_consistency(root)
if email_issues:
    print(f"Found {len(email_issues)} emails with inconsistent names")

# Find similar affiliations
similar_groups = find_similar_affiliations(root)
if similar_groups:
    print(f"Found {len(similar_groups)} groups of similar affiliations")
```

### Example 2: Statistics with Merged Affiliations

```python
import xml.etree.ElementTree as ET
from validation import generate_statistics, print_statistics

# Parse XML
tree = ET.parse('proceedings.xml')
root = tree.getroot()

# Generate statistics (includes merged affiliation analysis)
stats = generate_statistics(root)

# Print with merged affiliations, showing top 15 items
print_statistics(stats, root=root, top_k=15)

# Or show all items (sorted)
print_statistics(stats, root=root, top_k="full")
```

### Example 3: Multi-File Aggregation

```python
import xml.etree.ElementTree as ET
from validation import generate_statistics, merge_statistics

# Parse multiple files
files = ['full_papers.xml', 'short_papers.xml', 'demo_papers.xml']
stats_list = []

for filename in files:
    tree = ET.parse(filename)
    root = tree.getroot()
    stats = generate_statistics(root)
    stats_list.append(stats)

# Merge statistics across all files
combined = merge_statistics(stats_list)

# Access aggregated data
total_papers = sum(combined['papers_by_track'].values())
total_authors = sum(combined['authors'].values())
print(f"Total: {total_papers} papers, {total_authors} author entries")
```

### Example 4: Custom Affiliation Analysis

```python
import xml.etree.ElementTree as ET
from validation import find_similar_affiliations

# Parse XML
tree = ET.parse('proceedings.xml')
root = tree.getroot()

# Get similar affiliation groups with match type information
similar_groups = find_similar_affiliations(root)

# Analyze groups by match type
for group in similar_groups:
    affiliations = group['affiliations']
    match_type = group.get('match_type', 'string_similarity')
    
    print(f"\nMatch Type: {match_type}")
    print(f"Group Size: {len(affiliations)} variations")
    
    if match_type == 'known_alias':
        print("  → High confidence (whitelisted institution)")
    elif match_type == 'email_domain':
        email_domain = group.get('email_domain', 'N/A')
        print(f"  → Email domain: @{email_domain}")
    elif match_type == 'string_similarity':
        print("  → Based on string similarity and distinctive tokens")
    
    for aff in affiliations:
        print(f"  - {aff}")
```

## Assumptions and Design Decisions

### Name Validation

**Assumptions:**
- First names and last names should start with capital letters
- Middle names/initials may be optional or missing
- Non-Latin scripts are not validated (capitalization rules vary)

**Edge cases handled:**
- Names with hyphens, apostrophes, or spaces are allowed
- Single-letter names are allowed (e.g., middle initials)
- Empty names are flagged but not considered capitalization issues

### Email Validation

**Assumptions:**
- Same email address should always be associated with the same author name
- Email addresses are case-insensitive for comparison
- Empty emails are allowed (will be flagged in data quality report)

**Design decisions:**
- Only flags inconsistencies where the email is non-empty
- Compares full name strings (first + middle + last)
- Does not attempt to normalize name variations (e.g., "John Smith" vs "J. Smith")

### Affiliation Similarity Detection

**Core assumption:**
Academic institutions often appear with variations in proceedings data due to:
- Capitalization differences (RMIT vs Rmit vs rmit)
- Punctuation differences (JD.com vs JD.COM vs jd.com)
- Abbreviation vs full name (RMIT University vs Royal Melbourne Institute of Technology)
- Extra words (University of Melbourne vs The University of Melbourne)
- Language/translation variations (Tsinghua University vs 清华大学)

**Key Signal: Email Domains**

The algorithm uses **institutional email domains as the primary signal** for affiliation similarity:

- **Assumption**: Authors from the same institution typically share the same email domain
  - Example: @rmit.edu.au indicates RMIT University
  - Example: @tsinghua.edu.cn indicates Tsinghua University

- **Domain normalization**: Student/staff subdomains are treated as equivalent
  - student.rmit.edu.au → rmit.edu.au
  - mail.tsinghua.edu.cn → tsinghua.edu.cn
  
- **Exclusions**: Public and generic email services are ignored
  - gmail.com, yahoo.com, hotmail.com (consumer services)
  - acm.org (generic email service for ACM members, unrelated to affiliation)
  - See `PUBLIC_DOMAINS` set in checks.py for full list

- **False positive prevention**: Even with matching email domains, affiliations are only merged if they pass a basic similarity check (shared tokens OR string similarity >= 0.4)
  - Prevents merging when email domain is incorrectly entered in data

**Three-tier matching priority:**

1. **Known aliases (highest confidence)**
   - Use predefined whitelist of institution name variations
   - Example: "RMIT University" and "Royal Melbourne Institute of Technology" are known aliases
   - Canonical name selected as merge target

2. **Exact email domain match (high confidence)**
   - Primary signal for affiliation similarity
   - Email domains are normalized (student.rmit.edu.au → rmit.edu.au)
   - Requires basic similarity check to prevent false positives from data quality issues
   - Example: All authors with @rmit.edu.au are likely from RMIT University

3. **String similarity (medium confidence)**
   - Fallback for affiliations without email domain or not in whitelist
   - Uses distinctive token matching + Levenshtein similarity
   - Requires both token overlap AND high similarity score
   - Example: "Tsinghua Univ" and "Tsinghua University" are similar

**Why this design:**
- Prevents false positives (RMIT and University of Melbourne have different email domains)
- Handles data quality issues (author lists wrong email domain for affiliation)
- Balances precision and recall (known aliases have 100% confidence, string matching lower)
- Extensible (easy to add new aliases or blacklist entries)

### Country Normalization

**Assumptions:**
- Country names in XML may be:
  - Full names (United States, United Kingdom)
  - ISO 3166-1 alpha-2 codes (US, GB, CN)
  - ISO 3166-1 alpha-3 codes (USA, GBR, CHN)
  - Abbreviations with periods (U.S., U.K., U.A.E.)
  - Common variations (America, England, Mainland China)

**Design decisions:**
- Uses `pycountry` library as authoritative source
- Normalizes all variations to official ISO country names
- Maps official names to common names where appropriate (e.g., "Korea, Republic of" → "South Korea")
- Case-insensitive matching (US = us = Us)
- Special handling for territories (Taiwan, Hong Kong, Macao)

**Edge cases:**
- Unknown country names are preserved as-is (not normalized)
- Empty or None values are preserved
- Multiple matches prefer shortest official name

### Statistics Generation

**Author counts vs paper counts:**

**Design decision:** Track both metrics to reveal collaboration patterns

- **Author count**: Total number of author entries (can include duplicates across papers)
  - Example: Author appears on 3 papers → count = 3
  
- **Paper count**: Unique papers per affiliation/country using set deduplication
  - Example: 45 authors on 3 papers from same institution → 45 authors, 3 papers
  
**Why both metrics:**
- Author count reveals size of contributor base
- Paper count reveals publication volume
- Ratio reveals team sizes (high author/paper ratio = large collaborative teams)

**Multi-file aggregation:**
- Author counts sum across files (additive metric)
- Paper IDs deduplicate across files (same paper in multiple files counted once)
- Prevents double-counting when same paper appears in multiple exports

## Algorithm Details

### Affiliation Similarity Algorithm - Flowchart

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT: All unique affiliations from XML + author email domains │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│ STEP 0: Initialize                                                  │
│ • Extract email domains from author emails                         │
│ • Filter out public domains (gmail.com, yahoo.com, acm.org, etc.) │
│ • Normalize institutional domains (student.X → X, mail.X → X)     │
│ • Create affiliation → email_domain mapping                        │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│ STEP 1: Known Aliases (Highest Confidence)                         │
│ • Check against INSTITUTION_ALIASES whitelist                      │
│ • Example: "RMIT" + "Royal Melbourne Inst of Tech" → merge        │
│ • Check blacklist (never merge blacklisted pairs)                 │
│ • Mark as match_type='known_alias'                                 │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│ STEP 2: Email Domain Matching (High Confidence)                    │
│ For affiliations with same normalized institutional email domain:  │
│   1. Check if blacklisted → Skip if yes                           │
│   2. Run basic_similarity_check():                                 │
│      • Known aliases? → Merge                                      │
│      • Share distinctive tokens? → Merge                           │
│      • String similarity >= 0.4? → Merge                           │
│      • Otherwise → Don't merge (data quality issue)                │
│   3. Mark as match_type='email_domain'                             │
│                                                                     │
│ Example:                                                            │
│ • "Tsinghua University" @tsinghua.edu.cn                           │
│ • "Tsinghua Univ" @tsinghua.edu.cn                                 │
│ • Share token "tsinghua" → Merge ✓                                 │
│                                                                     │
│ Counter-example (prevents false positive):                         │
│ • "City Univ of Hong Kong" @ustc.edu.cn (typo in data)            │
│ • "USTC" @ustc.edu.cn                                              │
│ • No shared tokens, similarity < 0.4 → Don't merge ✗               │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│ STEP 3: String Similarity (Medium Confidence)                      │
│ For remaining affiliations not matched by email:                   │
│   1. Extract distinctive tokens (filter out generic words)         │
│      Generic: "university", "institute", "of", "the", etc.        │
│      Distinctive: geographic names, unique identifiers            │
│   2. Check if blacklisted → Skip if yes                           │
│   3. Require BOTH conditions:                                      │
│      • Share distinctive tokens                                    │
│      • String similarity >= 0.7 (strict threshold)                │
│   4. Mark as match_type='string_similarity'                        │
│                                                                     │
│ Example:                                                            │
│ • "Beijing Institute of Technology"                                │
│ • "Beijing Inst. of Tech."                                         │
│ • Share token "beijing", similarity 0.85 → Merge ✓                 │
│                                                                     │
│ Counter-example (prevents false positive):                         │
│ • "Dalian University of Technology"                                │
│ • "Delft University of Technology"                                 │
│ • Different distinctive tokens (dalian ≠ delft) → Don't merge ✗   │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│ OUTPUT: Similar affiliation groups                                  │
│ • Each group: list of affiliations + match_type + details         │
│ • Groups used for merged statistics                                │
│ • Representative affiliation chosen (shortest, no dept prefix)     │
└─────────────────────────────────────────────────────────────────────┘
```

### Affiliation Similarity Algorithm (checks.py)

The `find_similar_affiliations()` function uses a three-step priority system with union-find for grouping:

#### Step 0: Initialize Union-Find Structure

```
For each unique affiliation:
    parent[affiliation] = affiliation
    match_info[affiliation] = None
```

#### Step 1: Group Known Aliases (Highest Confidence)

```
For each canonical_name, aliases in INSTITUTION_ALIASES:
    affiliations_in_data = [a for a in all_affiliations if normalize(a) in aliases]
    
    If len(affiliations_in_data) >= 2:
        Pick first as root
        For each other affiliation:
            If not blacklisted(affiliation, root):
                union(affiliation, root)
                match_info[affiliation] = {
                    'type': 'known_alias',
                    'canonical': canonical_name
                }
```

**Example:**
- Data contains: "RMIT University", "Royal Melbourne Institute of Technology", "RMIT"
- Whitelist defines these as aliases
- All three merged with match_type='known_alias'

#### Step 2: Group by Exact Email Domain (High Confidence)

```
Build email_domain_map from XML:
    For each author with non-empty email:
        domain = normalize_email_domain(email.split('@')[1])
        If domain not in PUBLIC_DOMAINS:
            email_domain_map[affiliation] = domain

For each domain, affiliations_list in email_domain_map (grouped):
    If len(affiliations_list) >= 2:
        For each pair (aff1, aff2):
            If exact_domain_match(aff1, aff2) AND not already_in_same_group(aff1, aff2):
                If blacklisted(aff1, aff2):
                    Skip
                
                If basic_similarity_check(aff1, aff2):
                    union(aff1, aff2)
                    match_info[aff1] = {
                        'type': 'email_domain',
                        'domain': domain
                    }

basic_similarity_check(aff1, aff2):
    Return (
        are_known_aliases(aff1, aff2) OR
        share_distinctive_tokens(aff1, aff2) OR
        string_similarity(aff1, aff2) >= 0.4
    )
```

**Example:**
- Authors from "Tsinghua University" use @tsinghua.edu.cn
- Authors from "Tsinghua Univ" also use @tsinghua.edu.cn
- String similarity check passes (0.95 > 0.4)
- Both merged with match_type='email_domain'

**False positive prevention:**
- If author from "City Univ of Hong Kong" mistakenly uses @ustc.edu.cn (should be @cityu.edu.hk)
- "City Univ of Hong Kong" and "USTC" don't share distinctive tokens
- String similarity < 0.4
- basic_similarity_check() fails
- Affiliations NOT merged (prevents false positive from data quality issue)

#### Step 3: Group by String Similarity (Medium Confidence)

```
For each remaining affiliation not yet grouped by email:
    For each other remaining affiliation:
        If share_distinctive_tokens(aff1, aff2):
            similarity = string_similarity(aff1, aff2)
            
            If similarity >= 0.7:
                If not blacklisted(aff1, aff2):
                    union(aff1, aff2)
                    match_info[aff1] = {'type': 'string_similarity'}
```

**Example:**
- "Beijing Institute of Technology" vs "Beijing Inst. of Tech."
- Share distinctive tokens: {"beijing"}
- High string similarity (> 0.7)
- Merged with match_type='string_similarity'

**False negative prevention:**
- If affiliations share NO distinctive tokens (e.g., "University of Melbourne" vs "University of Michigan")
- String similarity alone not enough (even if > 0.7)
- Prevents merging unrelated institutions with similar generic structures

### Email Domain Normalization

The `normalize_email_domain()` function treats institutional subdomains as equivalent:

```python
SUBDOMAIN_PREFIXES = [
    'student.', 'mail.', 'connect.', 'alumni.', 'staff.',
    'students.', 'email.', 'webmail.', 'my.', 'campus.'
]

def normalize_email_domain(domain):
    if not domain:
        return domain
    
    for prefix in SUBDOMAIN_PREFIXES:
        if domain.startswith(prefix):
            return domain[len(prefix):]  # Strip prefix
    
    return domain
```

**Examples:**
- student.rmit.edu.au → rmit.edu.au
- campus.university.edu → university.edu
- alumni.stanford.edu → stanford.edu
- regular.domain.edu → regular.domain.edu (no change)

**Rationale:**
- Students, staff, and alumni are all from the same institution
- Different email systems (mail., webmail., my.) are same institution
- Prevents fragmenting affiliation counts by subdomain

### Distinctive Token Extraction

The algorithm identifies tokens that distinguish institutions:

```python
GENERIC_WORDS = {
    'university', 'college', 'institute', 'school', 'center',
    'department', 'of', 'the', 'and', 'for', 'technology',
    'science', 'research', 'academy', 'education'
}

def extract_distinctive_tokens(affiliation):
    # Normalize: lowercase, remove punctuation
    normalized = normalize_affiliation(affiliation)
    
    # Tokenize
    tokens = normalized.split()
    
    # Filter out generic words
    distinctive = {t for t in tokens if t not in GENERIC_WORDS and len(t) >= 3}
    
    return distinctive
```

**Examples:**
- "Tsinghua University" → {"tsinghua"}
- "MIT" → {"mit"}
- "Royal Melbourne Institute of Technology" → {"royal", "melbourne", "technology"} → {"royal", "melbourne"} (technology is generic)
- "University of Melbourne" → {"melbourne"}

**Why distinctive tokens:**
- Generic words like "university", "institute" appear in many institution names
- Distinctive tokens (geographic names, unique identifiers) are strong signals
- Prevents false positives (e.g., "University of Technology Sydney" vs "Dalian University of Technology" share "university" and "technology" but not distinctive tokens)

### String Similarity Metric

Uses Levenshtein distance normalized by length:

```python
def string_similarity(str1, str2):
    distance = levenshtein_distance(str1, str2)
    max_len = max(len(str1), len(str2))
    return 1 - (distance / max_len)
```

**Examples:**
- "RMIT" vs "rmit" → similarity = 0.75 (4 char changes / 4 chars)
- "Tsinghua University" vs "Tsinghua Univ" → similarity ≈ 0.95
- "RMIT University" vs "Royal Melbourne Institute of Technology" → similarity ≈ 0.18 (very different)

**Threshold:**
- Step 2 (email domain): 0.4 (lenient, because email domain is strong signal)
- Step 3 (string similarity): 0.7 (strict, because no other signals)

### Country Normalization Algorithm (statistics.py)

```python
def normalize_country(country_str):
    if not country_str:
        return country_str
    
    # Clean input
    country = country_str.strip()
    
    # Try exact lookup (case-insensitive)
    try:
        return pycountry.countries.lookup(country).name
    except LookupError:
        pass
    
    # Handle abbreviations with periods (U.S. → US)
    if '.' in country:
        clean = country.replace('.', '').upper()
        try:
            return pycountry.countries.lookup(clean).name
        except LookupError:
            pass
    
    # Handle special mappings
    SPECIAL_MAPS = {
        'korea, republic of': 'South Korea',
        'korea, democratic people\'s republic of': 'North Korea',
        'russian federation': 'Russia',
        # ... more mappings
    }
    
    country_lower = country.lower()
    if country_lower in SPECIAL_MAPS:
        return SPECIAL_MAPS[country_lower]
    
    # Not recognized, return as-is
    return country_str
```

## Configuration

### Institution Aliases (checks.py)

Add known institution name variations to `INSTITUTION_ALIASES`:

```python
INSTITUTION_ALIASES = {
    "rmit university": {
        "rmit university",
        "royal melbourne institute of technology",
        "rmit"
    },
    "the university of melbourne": {
        "the university of melbourne",
        "university of melbourne"
    },
    # Add more institutions as needed
}
```

**Format:**
- Key: canonical name (lowercase, normalized)
- Value: set of all known variations (lowercase, normalized)

**When to add:**
- Institution appears with multiple spellings/abbreviations in data
- High confidence that variations refer to same institution
- Prevents false positives from string similarity matching

### Institution Blacklist (checks.py)

Prevent specific institution pairs from merging:

```python
INSTITUTION_BLACKLIST = [
    {"rmit university", "the university of melbourne"},
    {"royal melbourne institute of technology", "the university of melbourne"},
    {"alibaba group", "ant group"},
    # Add more forbidden pairs as needed
]
```

**Format:**
- List of sets, each set contains 2+ institution names that should never merge
- Institution names should be lowercase, normalized

**When to add:**
- False positives discovered in validation output
- Institutions have similar names but are distinct entities
- Geographic proximity causes confusion (both in Melbourne, both use "melbourne" token)

### Email Domain Normalization (checks.py)

Add institutional subdomain prefixes:

```python
SUBDOMAIN_PREFIXES = [
    'student.', 'mail.', 'connect.', 'alumni.', 'staff.',
    'students.', 'email.', 'webmail.', 'my.', 'campus.'
]
```

**When to add:**
- Institution uses non-standard subdomain for email addresses
- Subdomain fragments affiliation statistics
- Verification: all subdomain users are from same parent institution

### Public Email Domains (checks.py)

Exclude consumer email providers and generic services from email domain matching:

```python
PUBLIC_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com',
    'qq.com', 'foxmail.com', '163.com', '126.com', '139.com', 'sina.com',
    'sohu.com', 'yeah.net', 'mail.com', 'aol.com', 'icloud.com',
    'protonmail.com', 'zoho.com', 'yandex.com', 'gmx.com', 'mail.ru',
    'acm.org'  # Generic email service for ACM members, not affiliation-specific
}
```

**Why exclude:**
- Public domains don't indicate institutional affiliation
- gmail.com users could be from any institution worldwide
- acm.org is a generic email service that some authors use, unrelated to their actual affiliation
- Would create massive false positive groups if used for matching

### Country Name Mappings (statistics.py)

Add special country name mappings:

```python
SPECIAL_COUNTRY_MAPPINGS = {
    'korea, republic of': 'South Korea',
    'korea, democratic people\'s republic of': 'North Korea',
    'russian federation': 'Russia',
    # Add more mappings as needed
}
```

**When to add:**
- Official ISO name is not commonly used
- Want consistent reporting name across datasets
- Regional or political naming preferences
