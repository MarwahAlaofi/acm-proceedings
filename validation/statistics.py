"""
Statistics generation and reporting for ACM XML validation.

Functions for generating comprehensive statistics from XML files including:
- Papers per track/type
- Author counts and prolific authors
- Affiliation and country distributions
- Merged affiliation statistics
"""

from collections import defaultdict, Counter


def generate_statistics(root):
    """
    Generate comprehensive statistics from XML.

    Args:
        root: XML root element

    Returns:
        dict: Statistics including papers per track, authors, affiliations, countries
    """
    papers_by_track = defaultdict(int)
    papers_by_type = defaultdict(int)
    author_paper_count = defaultdict(list)
    affiliation_count = Counter()
    affiliation_papers = defaultdict(set)  # affiliation -> set of paper_ids
    country_count = Counter()
    country_papers = defaultdict(set)  # country -> set of paper_ids

    for paper in root.findall("paper"):
        paper_id = paper.findtext("event_tracking_number", "unknown")
        paper_type = paper.findtext("paper_type", "Unknown")
        section = paper.findtext("section", "Unknown")

        papers_by_track[section] += 1
        papers_by_type[paper_type] += 1

        authors = paper.findall(".//author")
        for author in authors:
            first_name = author.findtext("first_name", "")
            last_name = author.findtext("last_name", "")
            email = author.findtext("email_address", "")

            # Track author by (name, email) to handle same name different people
            author_key = (first_name, last_name, email)
            author_paper_count[author_key].append((paper_id, paper_type))

            # Track affiliations
            affiliations = author.findall(".//affiliation")
            for aff in affiliations:
                institution = aff.findtext("institution", "").strip()
                country = aff.findtext("country", "").strip()

                if institution:
                    affiliation_count[institution] += 1
                    affiliation_papers[institution].add(paper_id)
                if country:
                    country_count[country] += 1
                    country_papers[country].add(paper_id)

    return {
        "papers_by_track": dict(papers_by_track),
        "papers_by_type": dict(papers_by_type),
        "author_paper_count": author_paper_count,
        "affiliation_count": affiliation_count,
        "affiliation_papers": affiliation_papers,
        "country_count": country_count,
        "country_papers": country_papers
    }


def print_statistics(stats_data, root=None, similar_groups=None):
    """
    Print comprehensive statistics.

    Args:
        stats_data: Statistics dictionary from generate_statistics()
        root: Optional XML root element for similarity analysis (single file mode)
        similar_groups: Optional pre-computed similar affiliations (multi-file mode)
    """
    # Import here to avoid circular dependency
    from validation.checks import find_similar_affiliations, merge_similar_affiliation_counts

    papers_by_track = stats_data["papers_by_track"]
    papers_by_type = stats_data["papers_by_type"]
    author_paper_count = stats_data["author_paper_count"]
    affiliation_count = stats_data["affiliation_count"]
    affiliation_papers = stats_data.get("affiliation_papers", {})
    country_count = stats_data["country_count"]
    country_papers = stats_data.get("country_papers", {})

    # Papers by track
    print("\n" + "=" * 80)
    print("STATISTICS: PAPERS BY TRACK/SECTION")
    print("=" * 80)
    total_papers = sum(papers_by_track.values())
    for track, count in sorted(papers_by_track.items(), key=lambda x: x[1], reverse=True):
        track_name = track if track else "(No section specified)"
        print(f"  {track_name}: {count} papers ({count/total_papers*100:.1f}%)")
    print(f"\nTotal: {total_papers} papers")
    print("=" * 80)

    # Papers by type
    print("\n" + "=" * 80)
    print("STATISTICS: PAPERS BY TYPE")
    print("=" * 80)
    for ptype, count in sorted(papers_by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ptype}: {count} papers ({count/total_papers*100:.1f}%)")
    print("=" * 80)

    # Authors statistics
    print("\n" + "=" * 80)
    print("STATISTICS: AUTHORS")
    print("=" * 80)
    total_author_entries = sum(len(papers) for papers in author_paper_count.values())
    unique_authors = len(author_paper_count)
    avg_papers_per_author = total_author_entries / unique_authors if unique_authors > 0 else 0
    avg_authors_per_paper = total_author_entries / total_papers if total_papers > 0 else 0

    print(f"  Total author entries: {total_author_entries}")
    print(f"  Unique authors: {unique_authors}")
    print(f"  Average papers per author: {avg_papers_per_author:.2f}")
    print(f"  Average authors per paper: {avg_authors_per_paper:.1f}")
    print("=" * 80)

    # Most prolific authors
    print("\n" + "=" * 80)
    print("TOP 10 MOST PROLIFIC AUTHORS")
    print("=" * 80)
    sorted_authors = sorted(author_paper_count.items(), key=lambda x: len(x[1]), reverse=True)[:10]

    for i, ((first, last, email), papers) in enumerate(sorted_authors, 1):
        email_str = f" ({email})" if email else ""
        print(f"  {i}. {first} {last}{email_str}: {len(papers)} paper(s)")

        # Paper types breakdown
        type_counts = Counter(ptype for _, ptype in papers)
        type_str = ", ".join(f"{count} {ptype}" for ptype, count in sorted(type_counts.items()))
        print(f"     Types: {type_str}")

        # Show paper IDs if reasonable number
        if len(papers) <= 5:
            paper_ids = ", ".join(pid for pid, _ in papers)
            print(f"     Papers: {paper_ids}")
    print("=" * 80)

    # Most common affiliations
    print("\n" + "=" * 80)
    print("TOP 20 MOST COMMON AFFILIATIONS")
    print("=" * 80)
    for i, (affiliation, author_count) in enumerate(affiliation_count.most_common(20), 1):
        paper_count = len(affiliation_papers.get(affiliation, set()))
        print(f"  {i}. {affiliation}: {author_count} author(s), {paper_count} paper(s)")
    print("=" * 80)

    # Merged affiliations (if similar_groups provided or root available)
    if similar_groups is not None or root is not None:
        print("\n" + "=" * 80)
        print("TOP 20 MOST COMMON AFFILIATIONS (AFTER MERGING SIMILAR)")
        print("=" * 80)

        # Find similar affiliations if not provided
        if similar_groups is None:
            similar_groups = find_similar_affiliations(root, similarity_threshold=0.8)

        if similar_groups:
            # Merge counts
            merged_author_counts, merged_paper_counts = merge_similar_affiliation_counts(
                affiliation_count, affiliation_papers, similar_groups
            )

            # Print top 20
            for i, (affiliation, author_count) in enumerate(merged_author_counts.most_common(20), 1):
                paper_count = merged_paper_counts.get(affiliation, 0)
                print(f"  {i}. {affiliation}: {author_count} author(s), {paper_count} paper(s)")

            print()
            print(f"Note: {len(similar_groups)} group(s) of similar affiliations were merged.")
            print("      See 'Similar Affiliations' section for details.")
        else:
            print("  No similar affiliations detected - counts remain unchanged")

        print("=" * 80)

    # Most common countries
    print("\n" + "=" * 80)
    print("TOP 20 MOST COMMON COUNTRIES")
    print("=" * 80)
    for i, (country, author_count) in enumerate(country_count.most_common(20), 1):
        paper_count = len(country_papers.get(country, set()))
        print(f"  {i}. {country}: {author_count} author(s), {paper_count} paper(s)")
    print("=" * 80)
