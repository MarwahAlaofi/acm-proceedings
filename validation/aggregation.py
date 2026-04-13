"""
Helper functions for aggregating statistics across multiple XML files.
Used by validate_acm_xml.py when multiple files are provided.
"""

from collections import defaultdict, Counter


def merge_statistics(all_stats):
    """
    Merge statistics from multiple XML files with author identity merging.

    When aggregating across files, re-merges author identities to handle cases
    where the same author appears with different name formats across different files.

    Args:
        all_stats: List of stats_data dictionaries from each file

    Returns:
        dict: Aggregated statistics with merged author identities
    """
    # Import merge function
    from validation.checks import merge_author_identities

    merged = {
        "papers_by_track": defaultdict(int),
        "papers_by_type": defaultdict(int),
        "author_paper_count": defaultdict(list),
        "affiliation_authors": defaultdict(set),  # affiliation -> set of unique author_keys
        "affiliation_papers": defaultdict(set),
        "country_authors": defaultdict(set),  # country -> set of unique author_keys
        "country_papers": defaultdict(set)
    }

    # First pass: collect all data without merging
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

        # Merge affiliation authors (union of author sets)
        for affiliation, author_set in stats.get("affiliation_authors", {}).items():
            merged["affiliation_authors"][affiliation].update(author_set)

        # Merge affiliation papers (union of paper sets)
        for affiliation, paper_set in stats.get("affiliation_papers", {}).items():
            merged["affiliation_papers"][affiliation].update(paper_set)

        # Merge country authors (union of author sets)
        for country, author_set in stats.get("country_authors", {}).items():
            merged["country_authors"][country].update(author_set)

        # Merge country papers (union of paper sets)
        for country, paper_set in stats.get("country_papers", {}).items():
            merged["country_papers"][country].update(paper_set)

    # Second pass: Re-merge author identities across files
    # This handles cases like "Charles Clarke" in file1 and "Charles L. A. Clarke" in file2
    all_author_keys = list(merged["author_paper_count"].keys())
    canonical_author_map = merge_author_identities(all_author_keys)

    # Rebuild author_paper_count with merged identities
    merged_author_paper_count = defaultdict(list)
    for author_key, papers in merged["author_paper_count"].items():
        canonical = canonical_author_map.get(author_key, author_key)
        merged_author_paper_count[canonical].extend(papers)

    # Deduplicate papers for each canonical author
    for canonical_author in merged_author_paper_count:
        seen_papers = {}
        for paper_id, paper_type in merged_author_paper_count[canonical_author]:
            if paper_id not in seen_papers:
                seen_papers[paper_id] = paper_type
        merged_author_paper_count[canonical_author] = [(pid, ptype) for pid, ptype in seen_papers.items()]

    merged["author_paper_count"] = merged_author_paper_count

    # Rebuild affiliation_authors and country_authors with merged identities
    merged_affiliation_authors = defaultdict(set)
    for affiliation, author_set in merged["affiliation_authors"].items():
        for author_key in author_set:
            canonical = canonical_author_map.get(author_key, author_key)
            merged_affiliation_authors[affiliation].add(canonical)
    merged["affiliation_authors"] = merged_affiliation_authors

    merged_country_authors = defaultdict(set)
    for country, author_set in merged["country_authors"].items():
        for author_key in author_set:
            canonical = canonical_author_map.get(author_key, author_key)
            merged_country_authors[country].add(canonical)
    merged["country_authors"] = merged_country_authors

    # Convert author sets to counts for easier consumption
    merged["affiliation_count"] = Counter({aff: len(authors) for aff, authors in merged["affiliation_authors"].items()})
    merged["country_count"] = Counter({country: len(authors) for country, authors in merged["country_authors"].items()})

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
