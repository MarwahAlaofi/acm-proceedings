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


def clean_affiliation_string(affiliation_str):
    """
    Clean affiliation string by stripping whitespace and leading/trailing punctuation.

    Handles common data quality issues like:
    - ", Tsinghua University" → "Tsinghua University"
    - "MIT, " → "MIT"
    - " , Stanford University" → "Stanford University"

    Args:
        affiliation_str: Raw affiliation string from XML

    Returns:
        str: Cleaned affiliation string
    """
    if not affiliation_str:
        return affiliation_str

    # Strip whitespace
    cleaned = affiliation_str.strip()

    # Strip leading/trailing punctuation (commas, semicolons, periods, etc.)
    # Keep stripping until no more leading/trailing punctuation+whitespace
    while cleaned and cleaned[0] in '.,;:-_':
        cleaned = cleaned[1:].strip()
    while cleaned and cleaned[-1] in '.,;:-_':
        cleaned = cleaned[:-1].strip()

    return cleaned


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


# Known institution aliases and blacklist
INSTITUTION_ALIASES = {
    # Key: canonical name, Value: set of variations (all lowercase)
    "rmit university": {
        "rmit university",
        "royal melbourne institute of technology"
    },
    "the university of melbourne": {
        "the university of melbourne",
        "university of melbourne"
    },
    "tsinghua university": {
        "tsinghua university",
        "tsinghua univ",
        "tsinghua univ."
    },
    "peking university": {
        "peking university",
        "pku",
        "beijing university"
    },
    "chinese academy of sciences": {
        "chinese academy of sciences",
        "cas"
    },
}

# Institutions that should NEVER be merged with each other
# Each tuple/set contains institutions that are distinct despite similarities
INSTITUTION_BLACKLIST = [
    {"rmit university", "the university of melbourne"},
    {"royal melbourne institute of technology", "the university of melbourne"},
    {"rmit university", "university of melbourne"},
    {"royal melbourne institute of technology", "university of melbourne"},
    {"alibaba group", "ant group"},  # Related but separate companies
]


def should_never_merge(aff1, aff2):
    """
    Check if two affiliations should never be merged together.

    Args:
        aff1, aff2: Affiliation strings

    Returns:
        bool: True if these affiliations are blacklisted from merging
    """
    aff1_lower = aff1.lower().strip()
    aff2_lower = aff2.lower().strip()

    for blacklist_set in INSTITUTION_BLACKLIST:
        if aff1_lower in blacklist_set and aff2_lower in blacklist_set:
            return True

    return False


def get_canonical_affiliation(affiliation):
    """
    Get canonical name for an affiliation if it's a known alias.

    Args:
        affiliation: Affiliation string

    Returns:
        str: Canonical name, or original affiliation if not in alias list
    """
    aff_lower = affiliation.lower().strip()

    for canonical, aliases in INSTITUTION_ALIASES.items():
        if aff_lower in aliases:
            return canonical

    return affiliation


def extract_email_domain(email):
    """
    Extract domain from email address, excluding common public email providers.

    Public email domains (gmail, yahoo, qq, etc.) are not useful for affiliation
    matching since authors from different institutions may use the same public
    email service.

    Generic institutional services like acm.org are also excluded because they
    provide email addresses to members regardless of their actual affiliation.

    Args:
        email: Email address string

    Returns:
        str: Domain part of email (lowercase), or empty string if invalid/public

    Examples:
        - "user@rmit.edu.au" → "rmit.edu.au" (institutional domain)
        - "user@gmail.com" → "" (public domain, excluded)
        - "user@acm.org" → "" (generic service, excluded)
    """
    # Common public email domains that should NOT be used for affiliation matching
    PUBLIC_DOMAINS = {
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com',
        'qq.com', 'foxmail.com', '163.com', '126.com', '139.com', 'sina.com',
        'sohu.com', 'yeah.net', 'mail.com', 'aol.com', 'icloud.com',
        'protonmail.com', 'zoho.com', 'yandex.com', 'gmx.com', 'mail.ru',
        'acm.org'
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


def normalize_email_domain(domain):
    """
    Normalize email domain for comparison.

    Treats student subdomains as equivalent to main domain:
    - student.rmit.edu.au -> rmit.edu.au
    - student.unimelb.edu.au -> unimelb.edu.au
    - mail.neu.edu.cn -> neu.edu.cn
    - connect.ust.hk -> ust.hk

    Args:
        domain: Email domain string (e.g., "student.rmit.edu.au")

    Returns:
        str: Normalized domain
    """
    if not domain:
        return domain

    # Common subdomain prefixes that should be normalized to main domain
    subdomain_prefixes = [
        'student.', 'mail.', 'connect.', 'alumni.', 'staff.',
        'students.', 'email.', 'webmail.', 'my.', 'campus.'
    ]

    for prefix in subdomain_prefixes:
        if domain.startswith(prefix):
            return domain[len(prefix):]

    return domain


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
    affiliation_domains = defaultdict(set)  # affiliation -> set of normalized email domains

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
                institution = clean_affiliation_string(aff.findtext("institution", ""))
                if institution:
                    affiliation_data[institution].append((paper_id, paper_title[:50], author_name))
                    if email_domain:
                        # Normalize domain (e.g., student.rmit.edu.au -> rmit.edu.au)
                        normalized_domain = normalize_email_domain(email_domain)
                        affiliation_domains[institution].add(normalized_domain)

    # Find similar affiliations
    affiliations = list(affiliation_data.keys())
    similar_groups = []
    processed = set()

    # Step 0: Group known aliases first (highest confidence)
    alias_to_canonical = {}
    for canonical, aliases in INSTITUTION_ALIASES.items():
        for aff in affiliations:
            if aff.lower().strip() in aliases:
                alias_to_canonical[aff] = canonical

    # Group affiliations by their canonical name
    canonical_groups = {}
    for aff, canonical in alias_to_canonical.items():
        if canonical not in canonical_groups:
            canonical_groups[canonical] = []
        canonical_groups[canonical].append(aff)

    # Create groups for aliases (only if multiple variations found)
    for canonical, affs_list in canonical_groups.items():
        if len(affs_list) > 1:
            for aff in affs_list:
                processed.add(aff)
            group = {
                "affiliations": sorted(affs_list),
                "details": {aff: affiliation_data[aff] for aff in affs_list},
                "match_type": "known_alias",
                "canonical": canonical
            }
            similar_groups.append(group)

    # Step 1: Group by exact email domain match (primary signal)
    # Affiliations that share the exact same normalized institutional email domain
    # are merged if they are not blacklisted AND meet a basic similarity check
    domain_to_affiliations = defaultdict(set)
    for aff in affiliations:
        if aff in processed:
            continue
        domains = affiliation_domains.get(aff, set())
        for domain in domains:
            domain_to_affiliations[domain].add(aff)

    # Create groups from exact email domain matches
    for domain, affs_with_domain in domain_to_affiliations.items():
        if len(affs_with_domain) > 1:
            # Multiple affiliations share this exact normalized email domain
            affs_list = [aff for aff in affs_with_domain if aff not in processed]

            if len(affs_list) > 1:
                # Apply blacklist filter and basic similarity check
                # Use union-find to create groups while respecting constraints
                affiliation_groups = []
                affiliation_to_group = {}

                for i, aff1 in enumerate(affs_list):
                    for j, aff2 in enumerate(affs_list):
                        if i >= j:
                            continue

                        # Skip if blacklisted
                        if should_never_merge(aff1, aff2):
                            continue

                        # Check if they're known aliases (always merge if true)
                        canonical1 = get_canonical_affiliation(aff1)
                        canonical2 = get_canonical_affiliation(aff2)
                        if canonical1 == canonical2 and canonical1 != aff1:
                            # Known aliases - definitely merge
                            should_merge = True
                        else:
                            # Basic similarity check to avoid merging completely unrelated institutions
                            # (e.g., "City University of Hong Kong" and "University of Science and Technology of China"
                            # both using @ustc.edu.cn due to dual affiliations)

                            # Check if they share distinctive tokens
                            tokens1 = get_distinctive_tokens(aff1)
                            tokens2 = get_distinctive_tokens(aff2)

                            if tokens1 and tokens2:
                                common_tokens = tokens1 & tokens2
                                # Require at least one common distinctive token
                                has_common_tokens = len(common_tokens) > 0
                            else:
                                has_common_tokens = False

                            # Also check string similarity as fallback
                            norm1 = normalize_affiliation(aff1)
                            norm2 = normalize_affiliation(aff2)
                            sim = string_similarity(norm1, norm2)

                            # Merge if: shared distinctive tokens OR reasonable string similarity (0.4+)
                            should_merge = has_common_tokens or sim >= 0.4

                        if should_merge:
                            # Merge these two affiliations
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

            # Check blacklist first
            if should_never_merge(aff1, aff2):
                continue

            # Check if they're known aliases
            canonical1 = get_canonical_affiliation(aff1)
            canonical2 = get_canonical_affiliation(aff2)
            if canonical1 == canonical2 and canonical1 != aff1:
                similar.append(aff2)
                processed.add(aff2)
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


def choose_representative_affiliation(affiliations):
    """
    Choose the best representative name from a group of similar affiliations.

    Prefers:
    1. Shorter names (base institution over department-level)
    2. Names without common department prefixes
    3. Among equal quality, alphabetically first

    Examples:
    - ["Tsinghua University", "School of Software, Tsinghua University"] → "Tsinghua University"
    - ["RMIT University", "Royal Melbourne Institute of Technology"] → "RMIT University" (shorter)
    - ["MIT", "Massachusetts Institute of Technology"] → "MIT" (shorter)

    Args:
        affiliations: List of affiliation name strings

    Returns:
        str: Best representative affiliation name
    """
    if not affiliations:
        return ""

    # Department/school prefixes that indicate more specific affiliations
    department_indicators = [
        "department of", "dept of", "dept.", "school of", "college of",
        "faculty of", "institute of", "division of", "center for", "centre for"
    ]

    def affiliation_score(aff):
        """
        Score an affiliation for being a good representative.
        Lower score = better representative.

        Score components:
        1. Has department prefix: +1000 (deprioritize department-level)
        2. Length in characters (shorter is better)
        3. Number of commas (fewer is better, each comma adds 100)
        """
        aff_lower = aff.lower()
        score = 0

        # Penalize department-level affiliations
        if any(prefix in aff_lower for prefix in department_indicators):
            score += 1000

        # Penalize longer names (base length score)
        score += len(aff)

        # Penalize names with commas (usually indicate "Department, Institution")
        score += aff.count(',') * 100

        return score

    # Sort by score (lower is better), then alphabetically
    sorted_affs = sorted(affiliations, key=lambda a: (affiliation_score(a), a))
    return sorted_affs[0]


def merge_similar_affiliation_counts(affiliation_count, affiliation_papers, similar_groups, affiliation_authors=None):
    """
    Merge affiliation counts based on similar affiliation groups.

    Args:
        affiliation_count: Counter of affiliation -> unique author count
        affiliation_papers: dict of affiliation -> set of paper IDs
        similar_groups: List of similar affiliation groups from find_similar_affiliations()
        affiliation_authors: Optional dict of affiliation -> set of author_keys for accurate merging

    Returns:
        tuple: (merged_author_counts, merged_paper_counts) as Counters
               Keys are canonical affiliation names (chosen by choose_representative_affiliation)
    """
    from collections import Counter

    # Create mapping from affiliation to canonical name
    affiliation_to_canonical = {}
    for group in similar_groups:
        # Choose best representative instead of just first alphabetically
        canonical = choose_representative_affiliation(group["affiliations"])
        for aff in group["affiliations"]:
            affiliation_to_canonical[aff] = canonical

    # Merge counts
    merged_author_counts = Counter()
    merged_paper_counts = {}

    # Track unique authors and papers for each canonical affiliation
    canonical_authors = {}
    canonical_papers = {}

    # If we have author sets, merge them properly to avoid double-counting
    if affiliation_authors:
        for affiliation, author_set in affiliation_authors.items():
            canonical = affiliation_to_canonical.get(affiliation, affiliation)

            # Merge author sets (handles same author appearing in multiple variations)
            if canonical not in canonical_authors:
                canonical_authors[canonical] = set()
            canonical_authors[canonical].update(author_set)

            # Merge paper sets
            if canonical not in canonical_papers:
                canonical_papers[canonical] = set()
            canonical_papers[canonical].update(affiliation_papers.get(affiliation, set()))

        # Convert author sets to counts
        merged_author_counts = Counter({canonical: len(authors) for canonical, authors in canonical_authors.items()})
    else:
        # Fallback: use counts directly (less accurate if same author in multiple variations)
        for affiliation, author_count in affiliation_count.items():
            canonical = affiliation_to_canonical.get(affiliation, affiliation)
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


def complete_author_fields(root):
    """
    Complete missing author fields across papers for the same author.

    When an author appears in multiple papers, fills missing information from
    other papers where that information exists. Uses author identity merging
    to determine which authors are the same person.

    Rules:
    - Only fills EMPTY fields (never overwrites existing values)
    - Handles multiple affiliations/countries (authors can legitimately have different ones)
    - Preserves all existing information
    - Fills: affiliations, countries, department (within affiliation)

    Args:
        root: XML root element (will be modified in place)

    Returns:
        dict: Statistics about completions {
            'authors_processed': int,
            'affiliations_added': int,
            'countries_added': int,
            'departments_added': int
        }

    Example:
        Paper 1: John Smith, MIT, USA
        Paper 2: John Smith (same email), MIT, no country
        → After completion: Paper 2 will have USA filled in
    """
    # Step 1: Collect all author occurrences with their XML elements
    author_occurrences = []  # [(author_key, paper_id, author_element)]

    for paper in root.findall("paper"):
        paper_id = paper.findtext("event_tracking_number", "unknown")

        for author in paper.findall(".//author"):
            first_name = author.findtext("first_name", "")
            last_name = author.findtext("last_name", "")
            email = author.findtext("email_address", "")

            author_key = (first_name, last_name, email)
            author_occurrences.append((author_key, paper_id, author))

    # Step 2: Identify canonical authors
    all_author_keys = [key for key, _, _ in author_occurrences]
    canonical_map = merge_author_identities(all_author_keys)

    # Step 3: Collect all information for each canonical author
    canonical_info = defaultdict(lambda: {
        'affiliations': set(),  # Set of (institution, department, country) tuples
        'occurrences': []  # List of (paper_id, author_element) tuples
    })

    for author_key, paper_id, author_elem in author_occurrences:
        canonical = canonical_map[author_key]

        # Collect existing affiliations
        for aff_elem in author_elem.findall(".//affiliation"):
            institution = clean_affiliation_string(aff_elem.findtext("institution", ""))
            department = aff_elem.findtext("department", "").strip()
            country = aff_elem.findtext("country", "").strip()

            # Store as tuple (only store if institution exists)
            # Note: We store all variations (even incomplete ones) because we need
            # to know the full set of affiliations. The filling logic will prefer
            # complete information when available.
            if institution:
                canonical_info[canonical]['affiliations'].add((institution, department, country))

        # Track occurrences
        canonical_info[canonical]['occurrences'].append((paper_id, author_elem))

    # Step 4: Fill missing information
    stats = {
        'authors_processed': len(canonical_info),
        'affiliations_added': 0,
        'countries_added': 0,
        'departments_added': 0
    }

    for canonical, info in canonical_info.items():
        available_affiliations = info['affiliations']

        # Skip if no affiliation information available
        if not available_affiliations:
            continue

        # Process each occurrence of this author
        for paper_id, author_elem in info['occurrences']:
            existing_affiliations = []

            # Get existing affiliations for this occurrence
            for aff_elem in author_elem.findall(".//affiliation"):
                institution = clean_affiliation_string(aff_elem.findtext("institution", ""))
                department = aff_elem.findtext("department", "").strip()
                country = aff_elem.findtext("country", "").strip()
                existing_affiliations.append((institution, department, country, aff_elem))

            # If no affiliations at all, add all known affiliations
            if not existing_affiliations or all(not inst for inst, dept, ctry, elem in existing_affiliations):
                for institution, department, country in available_affiliations:
                    # Create new affiliation element
                    import xml.etree.ElementTree as ET
                    aff_elem = ET.SubElement(author_elem, "affiliation")
                    if institution:
                        ET.SubElement(aff_elem, "institution").text = institution
                    if department:
                        ET.SubElement(aff_elem, "department").text = department
                    if country:
                        ET.SubElement(aff_elem, "country").text = country
                    stats['affiliations_added'] += 1
            else:
                # Fill missing fields in existing affiliations
                for inst, dept, ctry, aff_elem in existing_affiliations:
                    if not inst:
                        continue  # Skip empty affiliations

                    # Find matching affiliation info (same institution)
                    # Collect all matching affiliations and prefer ones with non-empty fields
                    matching_affs = [
                        (known_inst, known_dept, known_ctry)
                        for known_inst, known_dept, known_ctry in available_affiliations
                        if inst == known_inst
                    ]

                    # For each field, find the best source (prefer non-empty)
                    best_dept = None
                    best_ctry = None

                    for _, known_dept, known_ctry in matching_affs:
                        if not best_dept and known_dept:
                            best_dept = known_dept
                        if not best_ctry and known_ctry:
                            best_ctry = known_ctry

                    # Fill missing department
                    if not dept and best_dept:
                        dept_elem = aff_elem.find("department")
                        if dept_elem is None:
                            import xml.etree.ElementTree as ET
                            ET.SubElement(aff_elem, "department").text = best_dept
                        elif not dept_elem.text or not dept_elem.text.strip():
                            dept_elem.text = best_dept
                        stats['departments_added'] += 1

                    # Fill missing country
                    if not ctry and best_ctry:
                        ctry_elem = aff_elem.find("country")
                        if ctry_elem is None:
                            import xml.etree.ElementTree as ET
                            ET.SubElement(aff_elem, "country").text = best_ctry
                        elif not ctry_elem.text or not ctry_elem.text.strip():
                            ctry_elem.text = best_ctry
                        stats['countries_added'] += 1

    return stats


def merge_author_identities(author_keys):
    """
    Merge author identities based on email and name matching.

    Rules (in priority order):
    1. Exact email match (non-empty, case-insensitive) → same author (highest confidence)
    2. Exact full name match + at least one missing email → same author (medium confidence)
    3. Same name + different non-empty emails → different people (NOT merged)

    This prevents counting the same person multiple times when they:
    - Use same email with name variations (initials, typos)
    - Appear with email in some papers, without email in others
    - Appear multiple times without email

    Args:
        author_keys: Iterable of (first_name, last_name, email) tuples

    Returns:
        dict: author_key -> canonical_author_key mapping

    Examples:
        MERGED (same email):
        - ("John", "Smith", "john@mit.edu")
        - ("J.", "Smith", "john@mit.edu")
        - ("J", "Smith", "JOHN@MIT.EDU")
        → All map to same canonical

        MERGED (same name, missing email):
        - ("Alice", "Johnson", "alice@cmu.edu")
        - ("Alice", "Johnson", "")
        → Both map to ("Alice", "Johnson", "alice@cmu.edu")

        NOT MERGED (same name, different emails):
        - ("Jane", "Doe", "jane@stanford.edu")
        - ("Jane", "Doe", "jane@berkeley.edu")
        → Map to themselves (likely different people)
    """
    # Build email to authors mapping (for non-empty emails, normalized to lowercase)
    email_to_authors = defaultdict(list)
    name_to_authors = defaultdict(list)

    for author_key in author_keys:
        first, last, email = author_key
        full_name = f"{first} {last}".strip()

        # Group by normalized email (case-insensitive)
        if email and email.strip():
            email_lower = email.strip().lower()
            email_to_authors[email_lower].append(author_key)

        # Group by full name
        if full_name:
            name_to_authors[full_name].append(author_key)

    # Build canonical mapping
    canonical_map = {}
    processed = set()

    # Step 1: Merge by email (highest confidence)
    # Only mark as processed if multiple authors share the same email
    for email_normalized, authors in email_to_authors.items():
        if len(authors) > 1:
            # Multiple authors with same email → merge them
            # Choose canonical author deterministically
            # Sort by name first, then by original email to ensure consistency
            canonical = sorted(authors, key=lambda x: (x[0], x[1], x[2]))[0]

            # Map all authors with this normalized email to the canonical
            for author_key in authors:
                canonical_map[author_key] = canonical
                processed.add(author_key)

    # Step 2: Merge by name (medium confidence)
    # Only merge authors not already processed by email matching
    # IMPORTANT: Only merge if at least one author has missing email
    # (same name + different emails = likely different people)
    for full_name, authors in name_to_authors.items():
        # Filter out already processed authors
        remaining = [a for a in authors if a not in processed]

        if len(remaining) > 1:
            # Multiple authors with same name not already merged by email
            authors_with_email = [a for a in remaining if a[2] and a[2].strip()]
            authors_without_email = [a for a in remaining if not a[2] or not a[2].strip()]

            # Only merge if at least one author has missing email
            # This prevents merging different people with same name but different emails
            if authors_without_email:
                # At least one author has missing email → safe to merge
                if authors_with_email:
                    # Prefer author with email as canonical
                    canonical = sorted(authors_with_email, key=lambda x: (x[0], x[1], x[2]))[0]
                else:
                    # All without email, pick first alphabetically
                    canonical = sorted(authors_without_email, key=lambda x: (x[0], x[1]))[0]

                for author_key in remaining:
                    canonical_map[author_key] = canonical
                    processed.add(author_key)
            else:
                # All authors have emails, but different emails
                # Don't merge - likely different people with same name
                # Map each to itself
                for author_key in remaining:
                    canonical_map[author_key] = author_key
                    processed.add(author_key)
        elif len(remaining) == 1:
            # Single author with this name not merged by email
            # Map to itself (no duplicate)
            author_key = remaining[0]
            canonical_map[author_key] = author_key
            processed.add(author_key)

    # Step 3: Identity mapping for authors not merged
    for author_key in author_keys:
        if author_key not in canonical_map:
            canonical_map[author_key] = author_key

    return canonical_map


def print_similar_affiliations(similar_groups):
    """Print similar affiliation groups."""
    if not similar_groups:
        print("  ✓ No similar affiliations detected")
        return

    # Count by match type
    known_alias_matches = sum(1 for g in similar_groups if g.get("match_type") == "known_alias")
    email_domain_matches = sum(1 for g in similar_groups if g.get("match_type") == "email_domain")
    string_similarity_matches = sum(1 for g in similar_groups if g.get("match_type") == "string_similarity")

    print(f"  ⚠ {len(similar_groups)} group(s) of similar affiliations detected:")
    print(f"     {known_alias_matches} known aliases, {email_domain_matches} matched by email domain, {string_similarity_matches} by string similarity")

    for i, group in enumerate(similar_groups[:10], 1):  # Show first 10 groups
        match_type = group.get("match_type", "unknown")
        if match_type == "known_alias":
            canonical = group.get("canonical", "")
            print(f"\n    Group {i} (known alias: {canonical}):")
        elif match_type == "email_domain":
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
