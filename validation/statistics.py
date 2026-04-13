"""
Statistics generation and reporting for ACM XML validation.

Functions for generating comprehensive statistics from XML files including:
- Papers per track/type
- Author counts and prolific authors
- Affiliation and country distributions
- Merged affiliation statistics
"""

from collections import defaultdict, Counter

try:
    import pycountry
    PYCOUNTRY_AVAILABLE = True
except ImportError:
    PYCOUNTRY_AVAILABLE = False


# =============================================================================
# PAPER TYPE SCORING CONFIGURATION
# =============================================================================
# Weights for calculating author scores based on paper types.
# Higher weights indicate more prestigious/impactful publication types.
#
# To modify: Change the weight values below. The scoring formula is:
#            score = 1 + (weight / 10)
#
# Examples:
#   weight=5 → score=1.5 points per paper
#   weight=3 → score=1.3 points per paper
#   weight=2 → score=1.2 points per paper
#   weight=1 → score=1.1 points per paper
#   weight=0 → score=1.0 points per paper
#
# Default weights:
PAPER_TYPE_WEIGHTS = {
    "Full Research Paper": 5,    # 1.5 points
    "Full Paper": 5,              # 1.5 points (variant name)
    "Perspective Paper": 5,       # 1.5 points
    "Doctoral Abstract": 1,       # 1.1 points
    "Tutorial Paper": 2,          # 1.2 points
    "Workshop Summary": 2,        # 1.2 points
    # Papers not listed above use DEFAULT_PAPER_WEIGHT
}

# Default weight for paper types not explicitly listed (Short, Demo, Industry, Resource, Reproducibility, etc.)
DEFAULT_PAPER_WEIGHT = 3  # 1.3 points
# =============================================================================


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


def normalize_country_name(country_str):
    """
    Normalize country names and codes to standard full country names.

    Handles:
    - ISO 3166-1 alpha-2 codes (US, CN, GB, etc.)
    - ISO 3166-1 alpha-3 codes (USA, CHN, GBR, etc.)
    - Full country names (United States, China, etc.)
    - Common variations and aliases (U.S., U.S.A., U.K., P.R.C., etc.)

    Special territories are handled according to ISO 3166-1 official designations:
    - Taiwan (TW/TWN) → "Taiwan, Province of China" (ISO 3166-1 official name)
    - Hong Kong (HK) → "Hong Kong"
    - Macao (MO) → "Macao"

    Args:
        country_str: Country name or code

    Returns:
        str: Standardized full country name, or original string if not found
    """
    if not PYCOUNTRY_AVAILABLE or not country_str:
        return country_str

    country_str = country_str.strip()

    # Preprocess: Remove periods and extra spaces for common abbreviations
    # This handles U.S. -> US, U.K. -> UK, U.A.E. -> UAE, etc.
    normalized_input = country_str.replace(".", "").replace(" ", "").upper()

    # Common variants that map to ISO codes or standard names
    # Handles abbreviations with/without periods, alternate spellings
    common_variants = {
        # United States variants
        "US": "US",
        "USA": "USA",
        "UNITEDSTATES": "US",
        "UNITEDSTATESOFAMERICA": "US",
        # United Kingdom variants
        "UK": "GB",
        "UNITEDKINGDOM": "GB",
        "GREATBRITAIN": "GB",
        # United Arab Emirates variants
        "UAE": "AE",
        "UNITEDARABEMIRATES": "AE",
        # China variants
        "PRC": "CN",
        "PEOPLESREPUBLICOFCHINA": "CN",
        # South Korea variants
        "SOUTHKOREA": "KR",
        "REPUBLICOFKOREA": "KR",
        # North Korea variants
        "NORTHKOREA": "KP",
        "DPR": "KP",
        "DPRK": "KP",
        # Vietnam variants
        "VIETNAM": "VN",
        # Russia variants
        "RUSSIA": "RU",
        "RUSSIANFEDERATION": "RU",
        # Netherlands variants
        "THENETHERLANDS": "NL",
    }

    # Check common variants first
    if normalized_input in common_variants:
        iso_code = common_variants[normalized_input]
        # If it's already an ISO code, use it; otherwise look it up
        if len(iso_code) == 2:
            country = pycountry.countries.get(alpha_2=iso_code)
        else:
            country = pycountry.countries.get(alpha_3=iso_code)
        if country:
            # Apply name overrides
            name_overrides = {
                "Korea, Republic of": "South Korea",
                "Korea, Democratic People's Republic of": "North Korea",
                "Russian Federation": "Russia",
                "Iran, Islamic Republic of": "Iran",
                "Venezuela, Bolivarian Republic of": "Venezuela",
                "Moldova, Republic of": "Moldova",
                "Tanzania, United Republic of": "Tanzania",
                "Bolivia, Plurinational State of": "Bolivia",
                "Viet Nam": "Vietnam",
            }
            return name_overrides.get(country.name, country.name)

    # Special cases for territories and regions
    # Note: Taiwan uses official ISO 3166-1 designation
    special_cases = {
        "HK": "Hong Kong",
        "HONGKONG": "Hong Kong",
        "HONGKONGSAR": "Hong Kong",
        "TW": "Taiwan, Province of China",
        "TWN": "Taiwan, Province of China",
        "TAIWAN": "Taiwan, Province of China",
        "TAIWANPROVINCEOFCHINA": "Taiwan, Province of China",
        "MO": "Macao",
        "MACAO": "Macao",
        "MACAU": "Macao",
    }

    if normalized_input in special_cases:
        return special_cases[normalized_input]

    # Map official ISO names to more common names
    name_overrides = {
        "Korea, Republic of": "South Korea",
        "Korea, Democratic People's Republic of": "North Korea",
        "Russian Federation": "Russia",
        "Iran, Islamic Republic of": "Iran",
        "Venezuela, Bolivarian Republic of": "Venezuela",
        "Moldova, Republic of": "Moldova",
        "Tanzania, United Republic of": "Tanzania",
        "Bolivia, Plurinational State of": "Bolivia",
        "Viet Nam": "Vietnam",
    }

    try:
        # Try matching by alpha-2 code (2 letters: US, CN, etc.)
        # Use normalized_input to handle U.S., US, us, etc.
        if len(normalized_input) == 2:
            country = pycountry.countries.get(alpha_2=normalized_input)
            if country:
                return name_overrides.get(country.name, country.name)

        # Try matching by alpha-3 code (3 letters: USA, CHN, etc.)
        # Use normalized_input to handle U.S.A., USA, usa, etc.
        if len(normalized_input) == 3:
            country = pycountry.countries.get(alpha_3=normalized_input)
            if country:
                return name_overrides.get(country.name, country.name)

        # Try exact name match (case-insensitive) with original input
        country = pycountry.countries.get(name=country_str)
        if country:
            return name_overrides.get(country.name, country.name)

        # Check if input is already an overridden name
        if country_str in name_overrides.values():
            return country_str

        # Check if input is a key in name_overrides (official name used directly)
        if country_str in name_overrides:
            return name_overrides[country_str]

        # Try fuzzy name search with original input
        try:
            results = pycountry.countries.search_fuzzy(country_str)
            if results:
                return name_overrides.get(results[0].name, results[0].name)
        except LookupError:
            pass

    except (AttributeError, LookupError):
        pass

    # Return original if no match found
    return country_str


def generate_statistics(root):
    """
    Generate comprehensive statistics from XML with author identity merging.

    Authors are merged based on:
    1. Exact email match (non-empty) → same author
    2. Exact full name match → same author

    This prevents counting the same person multiple times when they use different
    emails or appear with missing email addresses.

    Args:
        root: XML root element

    Returns:
        dict: Statistics including papers per track, authors, affiliations, countries
    """
    # Import merge function
    from validation.checks import merge_author_identities

    papers_by_track = defaultdict(int)
    papers_by_type = defaultdict(int)
    author_paper_count = defaultdict(list)
    affiliation_authors = defaultdict(set)  # affiliation -> set of unique author_keys
    affiliation_papers = defaultdict(set)  # affiliation -> set of paper_ids
    country_authors = defaultdict(set)  # country -> set of unique author_keys
    country_papers = defaultdict(set)  # country -> set of paper_ids

    # First pass: collect all author keys for merging
    all_author_keys = set()
    for paper in root.findall("paper"):
        authors = paper.findall(".//author")
        for author in authors:
            first_name = author.findtext("first_name", "")
            last_name = author.findtext("last_name", "")
            email = author.findtext("email_address", "")
            author_key = (first_name, last_name, email)
            all_author_keys.add(author_key)

    # Build canonical author mapping
    canonical_author_map = merge_author_identities(all_author_keys)

    # Second pass: generate statistics with merged author identities
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

            # Get original author key
            author_key = (first_name, last_name, email)

            # Map to canonical author identity
            canonical_author = canonical_author_map.get(author_key, author_key)

            # Track papers by canonical author (prevents double-counting same person)
            author_paper_count[canonical_author].append((paper_id, paper_type))

            # Track affiliations with canonical author identity
            affiliations = author.findall(".//affiliation")
            for aff in affiliations:
                institution = clean_affiliation_string(aff.findtext("institution", ""))
                country = aff.findtext("country", "").strip()

                if institution:
                    # Track unique authors per affiliation (using canonical identity)
                    affiliation_authors[institution].add(canonical_author)
                    affiliation_papers[institution].add(paper_id)
                if country:
                    # Normalize country name/code to standard full name
                    normalized_country = normalize_country_name(country)
                    country_authors[normalized_country].add(canonical_author)
                    country_papers[normalized_country].add(paper_id)

    # Deduplicate papers for each author (same paper shouldn't count multiple times)
    for author_key in author_paper_count:
        # Keep first occurrence of each paper_id (preserve paper_type info)
        seen_papers = {}
        for paper_id, paper_type in author_paper_count[author_key]:
            if paper_id not in seen_papers:
                seen_papers[paper_id] = paper_type
        author_paper_count[author_key] = [(pid, ptype) for pid, ptype in seen_papers.items()]

    # Convert sets to counts for easier consumption
    affiliation_count = Counter({aff: len(authors) for aff, authors in affiliation_authors.items()})
    country_count = Counter({country: len(authors) for country, authors in country_authors.items()})

    return {
        "papers_by_track": dict(papers_by_track),
        "papers_by_type": dict(papers_by_type),
        "author_paper_count": author_paper_count,
        "affiliation_count": affiliation_count,
        "affiliation_authors": affiliation_authors,  # Keep for merging
        "affiliation_papers": affiliation_papers,
        "country_count": country_count,
        "country_authors": country_authors,  # Keep for merging
        "country_papers": country_papers
    }


def get_scoring_description():
    """
    Generate a human-readable scoring description based on configured weights.

    Returns:
        str: Description string showing paper types and their scores

    Example output: "Full/Perspective=1.5pts, Tutorial/Workshop=1.2pts, Doctoral=1.1pts, Others=1.3pts"
    """
    # Group paper types by their weights for compact display
    weight_groups = {}
    for paper_type, weight in PAPER_TYPE_WEIGHTS.items():
        score = 1.0 + (weight / 10.0)
        if score not in weight_groups:
            weight_groups[score] = []
        # Use short names for common types
        short_name = paper_type.replace(" Research Paper", "").replace(" Paper", "").replace(" Summary", "")
        weight_groups[score].append(short_name)

    # Sort by score (descending) for consistent display
    parts = []
    for score in sorted(weight_groups.keys(), reverse=True):
        types = weight_groups[score]
        # Group similar types (e.g., "Full" and "Full Research" -> "Full")
        unique_types = []
        seen_base = set()
        for t in types:
            base = t.split()[0] if ' ' in t else t
            if base not in seen_base:
                unique_types.append(t)
                seen_base.add(base)

        type_str = "/".join(sorted(set(unique_types)))
        parts.append(f"{type_str}={score:.1f}pts")

    # Add default score for unlisted types
    default_score = 1.0 + (DEFAULT_PAPER_WEIGHT / 10.0)
    parts.append(f"Others={default_score:.1f}pts")

    return ", ".join(parts)


def calculate_author_score(papers):
    """
    Calculate weighted score for an author based on paper types.

    Uses the global PAPER_TYPE_WEIGHTS configuration with formula: score = 1 + (weight / 10)

    Default scoring (with default weights):
    - Full Research Paper (weight=5): 1.5 points per paper
    - Perspective Paper (weight=5): 1.5 points per paper
    - Tutorial/Workshop (weight=2): 1.2 points per paper
    - Doctoral Abstract (weight=1): 1.1 points per paper
    - Other types (weight=3): 1.3 points per paper

    Args:
        papers: List of (paper_id, paper_type) tuples

    Returns:
        float: Total weighted score
    """
    total_score = 0.0
    for _, paper_type in papers:
        # Get weight from configuration (defaults to DEFAULT_PAPER_WEIGHT if not found)
        weight = PAPER_TYPE_WEIGHTS.get(paper_type, DEFAULT_PAPER_WEIGHT)
        # Apply formula: score = 1 + (weight / 10)
        score = 1.0 + (weight / 10.0)
        total_score += score
    return total_score


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
    affiliation_authors = stats_data.get("affiliation_authors", {})
    affiliation_papers = stats_data.get("affiliation_papers", {})
    country_count = stats_data["country_count"]
    country_authors = stats_data.get("country_authors", {})
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

    # Most prolific authors (weighted by paper type)
    print("\n" + "=" * 80)
    print("TOP 10 MOST PROLIFIC AUTHORS (WEIGHTED SCORE)")
    print("=" * 80)
    print(f"Scoring: {get_scoring_description()}")
    print("=" * 80)

    # Sort by weighted score, then by paper count as tiebreaker
    sorted_authors = sorted(
        author_paper_count.items(),
        key=lambda x: (calculate_author_score(x[1]), len(x[1])),
        reverse=True
    )[:10]

    for i, ((first, last, email), papers) in enumerate(sorted_authors, 1):
        score = calculate_author_score(papers)
        email_str = f" ({email})" if email else ""
        print(f"  {i}. {first} {last}{email_str}: {len(papers)} paper(s), {score} points")

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
                affiliation_count, affiliation_papers, similar_groups, affiliation_authors
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
