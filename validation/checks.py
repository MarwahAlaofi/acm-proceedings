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


def extract_email_domain(email):
    """
    Extract domain from email address, excluding common public email providers.

    Public email domains (gmail, yahoo, qq, etc.) are not useful for affiliation
    matching since authors from different institutions may use the same public
    email service.

    Args:
        email: Email address string

    Returns:
        str: Domain part of email (lowercase), or empty string if invalid/public
    """
    # Common public email domains that should NOT be used for affiliation matching
    PUBLIC_DOMAINS = {
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com',
        'qq.com', 'foxmail.com', '163.com', '126.com', '139.com', 'sina.com',
        'sohu.com', 'yeah.net', 'mail.com', 'aol.com', 'icloud.com',
        'protonmail.com', 'zoho.com', 'yandex.com', 'gmx.com', 'mail.ru'
    }

    if not email or "@" not in email:
        return ""

    try:
        domain = email.split("@")[1].lower().strip()
        # Exclude public domains
        if domain in PUBLIC_DOMAINS:
            return ""
        return domain
    except:
        return ""


def find_similar_affiliations(root, similarity_threshold=0.8):
    """
    Find similar affiliations that might be duplicates or typos.

    Uses email domain as primary signal, then string similarity as fallback.
    Authors from the same institution typically share the same email domain.

    Args:
        root: XML root element
        similarity_threshold: Minimum similarity ratio (0-1) to flag

    Returns:
        list: List of similar affiliation groups with paper/author details
    """
    # Collect all unique affiliations with their occurrences and email domains
    affiliation_data = defaultdict(list)  # affiliation -> [(paper_id, paper_title, author_name)]
    affiliation_domains = defaultdict(set)  # affiliation -> set of email domains

    for paper in root.findall("paper"):
        paper_id = paper.findtext("event_tracking_number", "unknown")
        paper_title = paper.findtext("paper_title", "")

        authors = paper.findall(".//author")
        for author in authors:
            first_name = author.findtext("first_name", "").strip()
            last_name = author.findtext("last_name", "").strip()
            author_name = f"{first_name} {last_name}"
            email = author.findtext("email_address", "").strip()
            email_domain = extract_email_domain(email)

            affiliations = author.findall(".//affiliation")
            for aff in affiliations:
                institution = aff.findtext("institution", "").strip()
                if institution:
                    affiliation_data[institution].append((paper_id, paper_title[:50], author_name))
                    if email_domain:
                        affiliation_domains[institution].add(email_domain)

    # Find similar affiliations
    affiliations = list(affiliation_data.keys())
    similar_groups = []
    processed = set()

    # Step 1: Group by email domain first (primary signal)
    # But only when affiliations are also string-similar (to avoid false positives)
    domain_to_affiliations = defaultdict(set)
    for aff in affiliations:
        domains = affiliation_domains.get(aff, set())
        for domain in domains:
            domain_to_affiliations[domain].add(aff)

    # Create groups from email domain matches
    for domain, affs_with_domain in domain_to_affiliations.items():
        if len(affs_with_domain) > 1:
            # Multiple affiliations share this email domain
            # Verify they are similar institutions (not just same domain by chance)
            affs_list = [aff for aff in affs_with_domain if aff not in processed]

            if len(affs_list) > 1:
                # Check if affiliations have high string similarity or share distinctive tokens
                # This prevents matching "Peking University" with "Px Securities" just because
                # someone uses @pku.edu.cn email

                # Build similarity graph: find all pairs that are similar
                similar_pairs = []
                for i, aff1 in enumerate(affs_list):
                    for j, aff2 in enumerate(affs_list):
                        if i >= j:
                            continue

                        # Check string similarity
                        norm1 = normalize_affiliation(aff1)
                        norm2 = normalize_affiliation(aff2)
                        sim = string_similarity(norm1, norm2)

                        # More lenient threshold since we have email domain confirmation
                        # Also check for shared distinctive tokens
                        tokens1 = get_distinctive_tokens(aff1)
                        tokens2 = get_distinctive_tokens(aff2)

                        if tokens1 and tokens2:
                            common_tokens = tokens1 & tokens2
                            has_common_tokens = len(common_tokens) > 0
                        else:
                            has_common_tokens = False

                        # Match if: high similarity (0.5+) OR shared distinctive tokens
                        if sim >= 0.5 or has_common_tokens:
                            similar_pairs.append((aff1, aff2))

                # Group connected affiliations using union-find approach
                if similar_pairs:
                    affiliation_groups = []
                    affiliation_to_group = {}

                    for aff1, aff2 in similar_pairs:
                        group1 = affiliation_to_group.get(aff1)
                        group2 = affiliation_to_group.get(aff2)

                        if group1 is None and group2 is None:
                            # Create new group
                            new_group = {aff1, aff2}
                            affiliation_groups.append(new_group)
                            affiliation_to_group[aff1] = new_group
                            affiliation_to_group[aff2] = new_group
                        elif group1 is None:
                            # Add aff1 to aff2's group
                            group2.add(aff1)
                            affiliation_to_group[aff1] = group2
                        elif group2 is None:
                            # Add aff2 to aff1's group
                            group1.add(aff2)
                            affiliation_to_group[aff2] = group1
                        elif group1 != group2:
                            # Merge two groups
                            group1.update(group2)
                            for aff in group2:
                                affiliation_to_group[aff] = group1
                            affiliation_groups.remove(group2)

                    # Create a group for each connected component
                    for similar_subset in affiliation_groups:
                        if len(similar_subset) > 1:
                            for aff in similar_subset:
                                processed.add(aff)
                            group = {
                                "affiliations": sorted(similar_subset),
                                "details": {aff: affiliation_data[aff] for aff in similar_subset},
                                "match_type": "email_domain",
                                "email_domain": domain
                            }
                            similar_groups.append(group)

    # Step 2: String similarity for remaining affiliations (secondary signal)
    remaining_affiliations = [aff for aff in affiliations if aff not in processed]

    for i, aff1 in enumerate(remaining_affiliations):
        if aff1 in processed:
            continue

        # Check if this affiliation is similar to any other
        similar = [aff1]
        for j, aff2 in enumerate(remaining_affiliations):
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
                "details": {aff: affiliation_data[aff] for aff in similar},
                "match_type": "string_similarity"
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


def find_similar_affiliations_multi_file(roots, similarity_threshold=0.8):
    """
    Find similar affiliations across multiple XML files.

    Args:
        roots: List of XML root elements from multiple files
        similarity_threshold: Minimum similarity ratio (0-1) to flag

    Returns:
        list: List of similar affiliation groups with paper/author details
    """
    import xml.etree.ElementTree as ET

    # Create a temporary combined root
    combined_root = ET.Element("proceedings")

    # Merge all papers from all roots
    for root in roots:
        for paper in root.findall("paper"):
            combined_root.append(paper)

    # Use the single-file function on the combined root
    return find_similar_affiliations(combined_root, similarity_threshold)


def print_similar_affiliations(similar_groups):
    """Print similar affiliation groups."""
    if not similar_groups:
        print("  ✓ No similar affiliations detected")
        return

    # Count by match type
    email_domain_matches = sum(1 for g in similar_groups if g.get("match_type") == "email_domain")
    string_similarity_matches = sum(1 for g in similar_groups if g.get("match_type") == "string_similarity")

    print(f"  ⚠ {len(similar_groups)} group(s) of similar affiliations detected:")
    print(f"     {email_domain_matches} matched by email domain, {string_similarity_matches} by string similarity")

    for i, group in enumerate(similar_groups[:10], 1):  # Show first 10 groups
        match_type = group.get("match_type", "unknown")
        if match_type == "email_domain":
            domain = group.get("email_domain", "")
            print(f"\n    Group {i} (email domain: @{domain}):")
        else:
            print(f"\n    Group {i} (string similarity):")

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
