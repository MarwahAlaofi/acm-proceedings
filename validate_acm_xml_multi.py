"""
Helper functions for aggregating statistics across multiple XML files.
Used by validate_acm_xml.py when multiple files are provided.
"""

from collections import defaultdict, Counter


def merge_statistics(all_stats):
    """
    Merge statistics from multiple XML files.

    Args:
        all_stats: List of stats_data dictionaries from each file

    Returns:
        dict: Aggregated statistics
    """
    merged = {
        "papers_by_track": defaultdict(int),
        "papers_by_type": defaultdict(int),
        "author_paper_count": defaultdict(list),
        "affiliation_count": Counter(),
        "country_count": Counter()
    }

    for stats in all_stats:
        # Merge papers by track
        for track, count in stats["papers_by_track"].items():
            merged["papers_by_track"][track] += count

        # Merge papers by type
        for ptype, count in stats["papers_by_type"].items():
            merged["papers_by_type"][ptype] += count

        # Merge author counts
        for author_key, papers in stats["author_paper_count"].items():
            merged["author_paper_count"][author_key].extend(papers)

        # Merge affiliation counts
        merged["affiliation_count"].update(stats["affiliation_count"])

        # Merge country counts
        merged["country_count"].update(stats["country_count"])

    return merged


def merge_quality_stats(all_quality_stats):
    """
    Merge quality statistics from multiple XML files.

    Args:
        all_quality_stats: List of quality_stats dictionaries

    Returns:
        dict: Aggregated quality statistics
    """
    merged = {
        "total_papers": 0,
        "total_authors": 0,
        "missing_emails": 0,
        "missing_affiliations": 0,
        "missing_first_names": 0,
        "missing_last_names": 0,
        "papers_with_missing_data": 0
    }

    for stats in all_quality_stats:
        for key in merged:
            merged[key] += stats.get(key, 0)

    return merged
