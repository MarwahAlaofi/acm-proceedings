# Validation Package

This package provides comprehensive validation and analysis tools for ACM XML files.

## Structure

```
validation/
├── __init__.py         # Package initialization and exports
├── checks.py           # Author name, email, and affiliation validation
├── aggregation.py      # Multi-file statistics merging
├── statistics.py       # Statistics generation and reporting
└── README.md          # This file
```

## Modules

### checks.py

Validation checks for data quality issues:

- **check_name_capitalization()**: Validates that first and last names start with capital letters
- **check_email_name_consistency()**: Detects when the same email is used with different names
- **find_similar_affiliations()**: Identifies similar affiliations using string similarity (e.g., "JD.com", "JD.COM")
- **merge_similar_affiliation_counts()**: Merges author/paper counts for similar affiliations
- **print_name_capitalization_issues()**: Formats and prints name capitalization problems
- **print_email_name_consistency_issues()**: Formats and prints email-name inconsistencies
- **print_similar_affiliations()**: Formats and prints similar affiliation groups

### aggregation.py

Multi-file statistics aggregation:

- **merge_statistics()**: Merges statistics from multiple XML files
- **merge_quality_stats()**: Merges quality statistics from multiple files

### statistics.py

Statistics generation and reporting:

- **generate_statistics()**: Generates comprehensive statistics from a single XML file
  - Papers per track/type
  - Author counts and paper counts
  - Affiliation and country distributions
  - Prolific authors

- **print_statistics()**: Prints formatted statistics with optional similarity analysis
  - Supports merged affiliation statistics when XML root is provided

## Usage

### As a package (recommended)

```python
from validation import (
    check_name_capitalization,
    generate_statistics,
    print_statistics,
    merge_statistics
)

# Generate statistics
stats = generate_statistics(xml_root)

# Print with merged affiliations
print_statistics(stats, root=xml_root)

# Check for issues
issues = check_name_capitalization(xml_root)
```

### From main script

The `validate_acm_xml.py` script at the repository root uses this package:

```bash
# Single file validation
python validate_acm_xml.py file.xml

# Multiple file validation with aggregation
python validate_acm_xml.py file1.xml file2.xml file3.xml
```

## Key Features

### Similarity Detection

The checks module uses intelligent similarity detection that:
- Normalizes affiliations (removes "The", "University of", punctuation)
- Extracts distinctive tokens (ignores generic words like "technology", "science")
- Requires token overlap or very high string similarity (>0.9)
- Prevents false positives (e.g., "Dalian Univ. of Technology" vs "Delft Univ. of Technology")

### Paper Count Tracking

Statistics track both author counts AND unique paper counts:
- **Author count**: Total number of author entries (can include duplicates across papers)
- **Paper count**: Unique papers using set deduplication
- Reveals collaboration patterns (e.g., 45 authors on 3 papers = large teams)

### Multi-File Aggregation

When validating multiple files:
- Statistics are merged correctly (author counts sum, paper IDs deduplicate)
- Quality stats aggregate across all files
- Individual file results shown before combined statistics
