"""
Additional validation checks for ACM XML files.
Includes author name validation, email-name consistency, and affiliation similarity checks.
"""

import re
from difflib import SequenceMatcher
from collections import defaultdict


def check_name_capitalization(root):
    """
    Check if author names have proper capitalization (first letter capitalized).

    Returns:
        list: List of issues found (dicts with paper_id, author_name, issue)
    """
    issues = []

    for paper in root.findall("paper"):
        paper_id = paper.findtext("event_tracking_number", "unknown")
        paper_title = paper.findtext("paper_title", "")

        authors = paper.findall(".//author")
        for author in authors:
            first_name = author.findtext("first_name", "").strip()
            last_name = author.findtext("last_name", "").strip()

            # Check first name capitalization
            if first_name and not first_name[0].isupper():
                issues.append({
                    "paper_id": paper_id,
                    "paper_title": paper_title[:50],
                    "author_name": f"{first_name} {last_name}",
                    "field": "first_name",
                    "value": first_name,
                    "issue": "First name does not start with capital letter"
                })

            # Check last name capitalization
            if last_name and not last_name[0].isupper():
                issues.append({
                    "paper_id": paper_id,
                    "paper_title": paper_title[:50],
                    "author_name": f"{first_name} {last_name}",
                    "field": "last_name",
                    "value": last_name,
                    "issue": "Last name does not start with capital letter"
                })

    return issues


def check_email_name_consistency(root):
    """
    Check if same email address is used with different names.

    Returns:
        dict: Email -> list of (name, paper_id, paper_title) tuples
    """
    email_to_names = defaultdict(set)
    email_to_papers = defaultdict(list)

    for paper in root.findall("paper"):
        paper_id = paper.findtext("event_tracking_number", "unknown")
        paper_title = paper.findtext("paper_title", "")

        authors = paper.findall(".//author")
        for author in authors:
            first_name = author.findtext("first_name", "").strip()
            last_name = author.findtext("last_name", "").strip()
            email = author.findtext("email_address", "").strip().lower()

            if email and first_name and last_name:
                full_name = f"{first_name} {last_name}"
                email_to_names[email].add(full_name)
                email_to_papers[email].append((full_name, paper_id, paper_title[:50]))

    # Find emails with multiple names
    issues = {}
    for email, names in email_to_names.items():
        if len(names) > 1:
            issues[email] = email_to_papers[email]

    return issues


def normalize_affiliation(affiliation):
    """
    Normalize affiliation string for comparison.
    Removes common prefixes/suffixes and converts to lowercase.
    """
    aff = affiliation.lower().strip()

    # Remove common articles and prefixes
    prefixes = ["the ", "university of ", "université de ", "universität ", "universidad de "]
    for prefix in prefixes:
        if aff.startswith(prefix):
            aff = aff[len(prefix):]

    # Remove common suffixes
    suffixes = [" university", " college", " institute", " institution", " universität",
                " université", " universidad", " school", " academy"]
    for suffix in suffixes:
        if aff.endswith(suffix):
            aff = aff[:-len(suffix)]

    # Remove punctuation and extra spaces
    aff = re.sub(r'[^\w\s]', ' ', aff)
    aff = ' '.join(aff.split())

    return aff


def get_distinctive_tokens(affiliation):
    """
    Extract distinctive tokens from affiliation by removing common generic words.
    Used to avoid matching different institutions with similar generic patterns.

    Examples:
    - "Dalian University of Technology" -> {"dalian"}
    - "Delft University of Technology" -> {"delft"}
    - "Ant Group" -> {"ant", "group"}
    """
    aff = affiliation.lower().strip()

    # Remove punctuation
    aff = re.sub(r'[^\w\s]', ' ', aff)
    tokens = set(aff.split())

    # Remove generic words that don't distinguish institutions
    generic_words = {
        "the", "university", "of", "college", "institute", "institution",
        "school", "academy", "technology", "science", "sciences",
        "research", "center", "centre", "laboratory", "lab",
        "department", "dept", "faculty", "and"
    }

    distinctive = tokens - generic_words

    # If nothing left after removing generic words, return first token
    if not distinctive and tokens:
        return {list(tokens)[0]}

    return distinctive


def string_similarity(s1, s2):
    """
    Calculate similarity ratio between two strings using SequenceMatcher.
    Returns value between 0 and 1 (1 = identical).
    """
    return SequenceMatcher(None, s1, s2).ratio()


def find_similar_affiliations(root, similarity_threshold=0.8):
    """
    Find similar affiliations that might be duplicates or typos.

    Args:
        root: XML root element
        similarity_threshold: Minimum similarity ratio (0-1) to flag

    Returns:
        list: List of similar affiliation groups with paper/author details
    """
    # Collect all unique affiliations with their occurrences
    affiliation_data = defaultdict(list)  # affiliation -> [(paper_id, paper_title, author_name)]

    for paper in root.findall("paper"):
        paper_id = paper.findtext("event_tracking_number", "unknown")
        paper_title = paper.findtext("paper_title", "")

        authors = paper.findall(".//author")
        for author in authors:
            first_name = author.findtext("first_name", "").strip()
            last_name = author.findtext("last_name", "").strip()
            author_name = f"{first_name} {last_name}"

            affiliations = author.findall(".//affiliation")
            for aff in affiliations:
                institution = aff.findtext("institution", "").strip()
                if institution:
                    affiliation_data[institution].append((paper_id, paper_title[:50], author_name))

    # Find similar affiliations
    affiliations = list(affiliation_data.keys())
    similar_groups = []
    processed = set()

    for i, aff1 in enumerate(affiliations):
        if aff1 in processed:
            continue

        # Check if this affiliation is similar to any other
        similar = [aff1]
        for j, aff2 in enumerate(affiliations):
            if i >= j or aff2 in processed:
                continue

            # Normalize and compare
            norm1 = normalize_affiliation(aff1)
            norm2 = normalize_affiliation(aff2)

            # Skip if too different in length
            len_ratio = min(len(norm1), len(norm2)) / max(len(norm1), len(norm2))
            if len_ratio < 0.5:
                continue

            # Calculate similarity
            sim = string_similarity(norm1, norm2)
            if sim >= similarity_threshold:
                # Additional check: distinctive tokens must overlap significantly
                # This prevents grouping "Dalian University of Technology" with "Delft University of Technology"
                tokens1 = get_distinctive_tokens(aff1)
                tokens2 = get_distinctive_tokens(aff2)

                # Require at least one common distinctive token, or high token similarity
                if tokens1 and tokens2:
                    common_tokens = tokens1 & tokens2
                    all_tokens = tokens1 | tokens2
                    token_overlap = len(common_tokens) / len(all_tokens) if all_tokens else 0

                    # Require either common tokens, or very high string similarity (0.9+)
                    if token_overlap < 0.3 and sim < 0.9:
                        continue

                similar.append(aff2)
                processed.add(aff2)

        # If we found similar affiliations, add to results
        if len(similar) > 1:
            processed.add(aff1)
            group = {
                "affiliations": similar,
                "details": {aff: affiliation_data[aff] for aff in similar}
            }
            similar_groups.append(group)

    return similar_groups


def print_name_capitalization_issues(issues):
    """Print name capitalization issues."""
    if not issues:
        print("  ✓ All author names have proper capitalization")
        return

    print(f"  ⚠ {len(issues)} author name(s) with capitalization issues:")
    for issue in issues[:20]:  # Show first 20
        print(f"    • Paper {issue['paper_id']}: {issue['author_name']} - {issue['issue']}")
        print(f"      Title: {issue['paper_title']}...")
    if len(issues) > 20:
        print(f"    ... and {len(issues) - 20} more issues")


def print_email_name_consistency_issues(issues):
    """Print email-name consistency issues."""
    if not issues:
        print("  ✓ All email addresses are used consistently with same names")
        return

    print(f"  ⚠ {len(issues)} email address(es) used with different names:")
    for email, occurrences in list(issues.items())[:10]:  # Show first 10
        print(f"    • Email: {email}")
        names = set(name for name, _, _ in occurrences)
        for name in sorted(names):
            papers = [paper_id for n, paper_id, _ in occurrences if n == name]
            print(f"      - {name} (Papers: {', '.join(papers[:5])}{'...' if len(papers) > 5 else ''})")
    if len(issues) > 10:
        print(f"    ... and {len(issues) - 10} more emails")


def merge_similar_affiliation_counts(affiliation_count, affiliation_papers, similar_groups):
    """
    Merge affiliation counts based on similar affiliation groups.

    Args:
        affiliation_count: Counter of affiliation -> author count
        affiliation_papers: dict of affiliation -> set of paper IDs
        similar_groups: List of similar affiliation groups from find_similar_affiliations()

    Returns:
        tuple: (merged_author_counts, merged_paper_counts) as Counters
               Keys are canonical affiliation names (first in each group)
    """
    from collections import Counter

    # Create mapping from affiliation to canonical name
    affiliation_to_canonical = {}
    for group in similar_groups:
        canonical = group["affiliations"][0]  # Use first affiliation as canonical
        for aff in group["affiliations"]:
            affiliation_to_canonical[aff] = canonical

    # Merge counts
    merged_author_counts = Counter()
    merged_paper_counts = {}

    # Track which papers we've seen for each canonical affiliation
    canonical_papers = {}

    for affiliation, author_count in affiliation_count.items():
        canonical = affiliation_to_canonical.get(affiliation, affiliation)

        # Add author count
        merged_author_counts[canonical] += author_count

        # Merge paper sets
        if canonical not in canonical_papers:
            canonical_papers[canonical] = set()
        canonical_papers[canonical].update(affiliation_papers.get(affiliation, set()))

    # Convert paper sets to counts
    for canonical, paper_set in canonical_papers.items():
        merged_paper_counts[canonical] = len(paper_set)

    return merged_author_counts, merged_paper_counts


def print_similar_affiliations(similar_groups):
    """Print similar affiliation groups."""
    if not similar_groups:
        print("  ✓ No similar affiliations detected")
        return

    print(f"  ⚠ {len(similar_groups)} group(s) of similar affiliations detected:")
    for i, group in enumerate(similar_groups[:10], 1):  # Show first 10 groups
        print(f"\n    Group {i}:")
        for aff in group["affiliations"]:
            count = len(group["details"][aff])
            print(f"      • \"{aff}\" ({count} author(s))")
            # Show first few authors
            for paper_id, paper_title, author_name in group["details"][aff][:3]:
                print(f"        - {author_name} (Paper {paper_id}: {paper_title}...)")
            if count > 3:
                print(f"        ... and {count - 3} more author(s)")
    if len(similar_groups) > 10:
        print(f"    ... and {len(similar_groups) - 10} more groups")
