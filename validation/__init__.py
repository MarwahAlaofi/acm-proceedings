"""
ACM XML Validation Package
===========================

Provides comprehensive validation and analysis tools for ACM XML files.

Features:
- Author identity merging (prevents double-counting same person)
- Affiliation similarity detection (three-tier matching)
- Data quality validation (names, emails, consistency)
- Statistics generation with merged identities
- Multi-file aggregation

Modules:
- checks: Author identity merging, name/email/affiliation validation
- aggregation: Multi-file statistics merging
- statistics: Statistics generation and reporting with author merging
"""

from validation.checks import (
    check_name_capitalization,
    check_email_name_consistency,
    complete_author_fields,
    find_similar_affiliations,
    find_similar_affiliations_multi_file,
    find_merged_authors,
    merge_similar_affiliation_counts,
    merge_author_identities,
    print_name_capitalization_issues,
    print_email_name_consistency_issues,
    print_similar_affiliations,
    print_merged_authors
)

from validation.aggregation import (
    merge_statistics,
    merge_quality_stats
)

from validation.statistics import (
    calculate_author_score,
    clean_affiliation_string,
    generate_statistics,
    get_scoring_description,
    print_statistics
)

__all__ = [
    # Validation checks
    'check_name_capitalization',
    'check_email_name_consistency',
    'complete_author_fields',
    'find_similar_affiliations',
    'find_similar_affiliations_multi_file',
    'find_merged_authors',
    'merge_similar_affiliation_counts',
    'merge_author_identities',
    'print_name_capitalization_issues',
    'print_email_name_consistency_issues',
    'print_similar_affiliations',
    'print_merged_authors',

    # Aggregation
    'merge_statistics',
    'merge_quality_stats',

    # Statistics
    'calculate_author_score',
    'clean_affiliation_string',
    'generate_statistics',
    'get_scoring_description',
    'print_statistics',
]
