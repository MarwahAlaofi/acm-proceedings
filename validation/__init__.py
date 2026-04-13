"""
ACM XML Validation Package
===========================

Provides comprehensive validation and analysis tools for ACM XML files.

Modules:
- checks: Author name, email, and affiliation validation
- aggregation: Multi-file statistics merging
- statistics: Statistics generation and reporting
"""

from validation.checks import (
    check_name_capitalization,
    check_email_name_consistency,
    find_similar_affiliations,
    find_similar_affiliations_multi_file,
    merge_similar_affiliation_counts,
    print_name_capitalization_issues,
    print_email_name_consistency_issues,
    print_similar_affiliations
)

from validation.aggregation import (
    merge_statistics,
    merge_quality_stats
)

from validation.statistics import (
    generate_statistics,
    print_statistics
)

__all__ = [
    # Validation checks
    'check_name_capitalization',
    'check_email_name_consistency',
    'find_similar_affiliations',
    'find_similar_affiliations_multi_file',
    'merge_similar_affiliation_counts',
    'print_name_capitalization_issues',
    'print_email_name_consistency_issues',
    'print_similar_affiliations',

    # Aggregation
    'merge_statistics',
    'merge_quality_stats',

    # Statistics
    'generate_statistics',
    'print_statistics',
]
