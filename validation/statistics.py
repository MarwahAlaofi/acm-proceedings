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
                    # Normalize country name/code to standard full name
                    normalized_country = normalize_country_name(country)
                    country_count[normalized_country] += 1
                    country_papers[normalized_country].add(paper_id)

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
