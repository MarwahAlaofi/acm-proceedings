"""
ACM XML Comprehensive Validation and Analysis
==============================================

This script performs comprehensive validation and statistical analysis on ACM XML files.

Features:
- Validates XML structure and data quality
- Checks contact author constraints (exactly one per paper)
- Generates detailed statistics (papers per track, authors, affiliations)
- Identifies most prolific authors, affiliations, and countries
- Reports missing data (emails, affiliations, etc.)

Usage:
    python validate_acm_xml.py <xml_file>
    python validate_acm_xml.py acm_output.xml

Returns:
    Exit code 0 if all validations pass
    Exit code 1 if critical issues are found
"""

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
import argparse


def validate_contact_authors(root):
    """
    Validate that each paper has exactly one contact author.

    Returns:
        tuple: (is_valid, issues) where is_valid is bool and issues is list of strings
    """
    issues = []

    for paper in root.findall("paper"):
        paper_id = paper.findtext("event_tracking_number", "unknown")
        paper_title = paper.findtext("paper_title", "")
        authors = paper.findall(".//author")
        contact_authors = [a for a in authors if a.findtext("contact_author") == "Y"]

        if len(contact_authors) == 0:
            issues.append(f"Paper {paper_id} ('{paper_title[:50]}...'): No contact author")
        elif len(contact_authors) > 1:
            issues.append(f"Paper {paper_id} ('{paper_title[:50]}...'): Multiple contact authors ({len(contact_authors)})")

    return len(issues) == 0, issues


def validate_data_quality(root):
    """
    Validate data quality (missing emails, affiliations, names).

    Returns:
        dict: Statistics about data quality issues
    """
    stats = {
        "total_papers": 0,
        "total_authors": 0,
        "missing_emails": 0,
        "missing_affiliations": 0,
        "missing_first_names": 0,
        "missing_last_names": 0,
        "papers_with_missing_data": 0
    }

    papers_with_issues = []

    for paper in root.findall("paper"):
        paper_id = paper.findtext("event_tracking_number", "unknown")
        paper_title = paper.findtext("paper_title", "")
        stats["total_papers"] += 1

        paper_has_issue = False
        authors = paper.findall(".//author")

        for author in authors:
            stats["total_authors"] += 1

            first_name = author.findtext("first_name", "").strip()
            last_name = author.findtext("last_name", "").strip()
            email = author.findtext("email_address", "").strip()

            # Check institution from all affiliations
            affiliations = author.findall(".//affiliation")
            has_affiliation = any(aff.findtext("institution", "").strip() for aff in affiliations)

            if not first_name:
                stats["missing_first_names"] += 1
                paper_has_issue = True
            if not last_name:
                stats["missing_last_names"] += 1
                paper_has_issue = True
            if not email:
                stats["missing_emails"] += 1
                paper_has_issue = True
            if not has_affiliation:
                stats["missing_affiliations"] += 1
                paper_has_issue = True

        if paper_has_issue:
            stats["papers_with_missing_data"] += 1
            papers_with_issues.append((paper_id, paper_title[:50]))

    return stats, papers_with_issues


def generate_statistics(root):
    """
    Generate comprehensive statistics from XML.

    Returns:
        dict: Statistics including papers per track, authors, affiliations, countries
    """
    papers_by_track = defaultdict(int)
    papers_by_type = defaultdict(int)
    author_paper_count = defaultdict(list)
    affiliation_count = Counter()
    country_count = Counter()

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
                if country:
                    country_count[country] += 1

    return {
        "papers_by_track": dict(papers_by_track),
        "papers_by_type": dict(papers_by_type),
        "author_paper_count": author_paper_count,
        "affiliation_count": affiliation_count,
        "country_count": country_count
    }


def print_validation_results(is_valid, issues):
    """Print validation results."""
    print("\n" + "=" * 80)
    print("VALIDATION: CONTACT AUTHORS")
    print("=" * 80)

    if is_valid:
        print("✓ PASSED: All papers have exactly one contact author")
    else:
        print(f"✗ FAILED: {len(issues)} issue(s) found")
        print("\nIssues:")
        for issue in issues[:20]:  # Show first 20
            print(f"  • {issue}")
        if len(issues) > 20:
            print(f"  ... and {len(issues) - 20} more issues")
    print("=" * 80)


def print_data_quality(stats, papers_with_issues):
    """Print data quality statistics."""
    print("\n" + "=" * 80)
    print("DATA QUALITY REPORT")
    print("=" * 80)
    print(f"Total papers: {stats['total_papers']}")
    print(f"Total authors: {stats['total_authors']}")
    print()
    print("Missing Data:")
    print(f"  • Missing emails: {stats['missing_emails']}")
    print(f"  • Missing affiliations: {stats['missing_affiliations']}")
    print(f"  • Missing first names: {stats['missing_first_names']}")
    print(f"  • Missing last names: {stats['missing_last_names']}")
    print()
    print(f"Papers with missing data: {stats['papers_with_missing_data']} ({stats['papers_with_missing_data']/stats['total_papers']*100:.1f}%)")

    if papers_with_issues and len(papers_with_issues) <= 10:
        print("\nPapers with issues:")
        for paper_id, title in papers_with_issues:
            print(f"  • {paper_id}: {title}...")
    elif papers_with_issues:
        print(f"\n(First 10 papers with issues)")
        for paper_id, title in papers_with_issues[:10]:
            print(f"  • {paper_id}: {title}...")
    print("=" * 80)


def print_statistics(stats_data):
    """Print comprehensive statistics."""
    papers_by_track = stats_data["papers_by_track"]
    papers_by_type = stats_data["papers_by_type"]
    author_paper_count = stats_data["author_paper_count"]
    affiliation_count = stats_data["affiliation_count"]
    country_count = stats_data["country_count"]

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
    for i, (affiliation, count) in enumerate(affiliation_count.most_common(20), 1):
        print(f"  {i}. {affiliation}: {count} author(s)")
    print("=" * 80)

    # Most common countries
    print("\n" + "=" * 80)
    print("TOP 20 MOST COMMON COUNTRIES")
    print("=" * 80)
    for i, (country, count) in enumerate(country_count.most_common(20), 1):
        print(f"  {i}. {country}: {count} author(s)")
    print("=" * 80)


def validate_xml_file(xml_file, show_header=True):
    """
    Main validation and analysis function.

    Args:
        xml_file: Path to XML file
        show_header: Whether to show full header (False for multi-file mode)

    Returns:
        tuple: (is_valid, stats_data, quality_stats) for aggregation
    """
    if show_header:
        print("=" * 80)
        print("ACM XML COMPREHENSIVE VALIDATION AND ANALYSIS")
        print("=" * 80)
        print(f"File: {xml_file}")
        print("=" * 80)
    else:
        print("\n" + "-" * 80)
        print(f"FILE: {xml_file}")
        print("-" * 80)

    # Parse XML
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        if show_header:
            print("✓ XML file parsed successfully")
    except Exception as e:
        print(f"✗ ERROR: Failed to parse XML file: {e}")
        return False, None, None

    # Validate contact authors
    is_valid, issues = validate_contact_authors(root)
    if show_header:  # Only print detailed results in single-file mode
        print_validation_results(is_valid, issues)
    else:
        # Brief summary for multi-file mode
        if is_valid:
            print("  ✓ Contact authors: PASSED")
        else:
            print(f"  ✗ Contact authors: FAILED ({len(issues)} issues)")

    # Data quality check
    quality_stats, papers_with_issues = validate_data_quality(root)
    if show_header:  # Only print detailed results in single-file mode
        print_data_quality(quality_stats, papers_with_issues)
    else:
        # Brief summary for multi-file mode
        print(f"  Papers: {quality_stats['total_papers']}, Authors: {quality_stats['total_authors']}")
        print(f"  Missing data: {quality_stats['papers_with_missing_data']} papers")

    # Generate statistics (but only print in single-file mode)
    stats_data = generate_statistics(root)
    if show_header:
        print_statistics(stats_data)

    # Final summary (only for single file mode)
    if show_header:
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        if is_valid:
            print("✓ Contact author validation: PASSED")
        else:
            print(f"✗ Contact author validation: FAILED ({len(issues)} issues)")

        print(f"  Data quality: {quality_stats['papers_with_missing_data']}/{quality_stats['total_papers']} papers have missing data")

        if is_valid:
            print("\n✓ XML file is valid and ready for ACM submission")
        else:
            print("\n✗ XML file has issues that should be addressed")
        print("=" * 80)

    return is_valid, stats_data, quality_stats


def validate_multiple_files(xml_files):
    """
    Validate multiple XML files and aggregate statistics.

    Args:
        xml_files: List of XML file paths

    Returns:
        bool: True if all files pass validation
    """
    print("=" * 80)
    print("ACM XML COMPREHENSIVE VALIDATION AND ANALYSIS")
    print(f"Validating {len(xml_files)} file(s)")
    print("=" * 80)

    all_valid = True
    all_stats = []
    all_quality_stats = []
    file_results = []

    # Validate each file
    for xml_file in xml_files:
        is_valid, stats_data, quality_stats = validate_xml_file(xml_file, show_header=False)

        if is_valid is False:  # Parse error
            all_valid = False
            file_results.append((xml_file, False, None, None))
            continue

        all_valid = all_valid and is_valid
        all_stats.append(stats_data)
        all_quality_stats.append(quality_stats)
        file_results.append((xml_file, is_valid, stats_data, quality_stats))

    # Print per-file summary
    print("\n" + "=" * 80)
    print("PER-FILE VALIDATION SUMMARY")
    print("=" * 80)
    for xml_file, is_valid, _, quality_stats in file_results:
        status = "✓ PASSED" if is_valid else "✗ FAILED"
        if quality_stats:
            print(f"{status}: {xml_file}")
            print(f"        Papers: {quality_stats['total_papers']}, Authors: {quality_stats['total_authors']}, Missing data: {quality_stats['papers_with_missing_data']} papers")
        else:
            print(f"{status}: {xml_file} (parse error)")
    print("=" * 80)

    # Aggregate and print statistics
    if all_stats:
        print("\n" + "=" * 80)
        print("AGGREGATED STATISTICS (ALL FILES)")
        print("=" * 80)

        # Merge statistics
        from validate_acm_xml_multi import merge_statistics, merge_quality_stats
        merged_stats = merge_statistics(all_stats)
        merged_quality = merge_quality_stats(all_quality_stats)

        # Print aggregated statistics
        print_statistics(merged_stats)

        # Aggregated quality summary
        print("\n" + "=" * 80)
        print("AGGREGATED DATA QUALITY")
        print("=" * 80)
        print(f"Total files: {len(xml_files)}")
        print(f"Total papers: {merged_quality['total_papers']}")
        print(f"Total authors: {merged_quality['total_authors']}")
        print()
        print("Missing Data (aggregated):")
        print(f"  • Missing emails: {merged_quality['missing_emails']}")
        print(f"  • Missing affiliations: {merged_quality['missing_affiliations']}")
        print(f"  • Missing first names: {merged_quality['missing_first_names']}")
        print(f"  • Missing last names: {merged_quality['missing_last_names']}")
        print()
        print(f"Papers with missing data: {merged_quality['papers_with_missing_data']} ({merged_quality['papers_with_missing_data']/merged_quality['total_papers']*100:.1f}%)")
        print("=" * 80)

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL VALIDATION SUMMARY")
    print("=" * 80)
    passed_count = sum(1 for _, is_valid, _, _ in file_results if is_valid)
    print(f"Files validated: {len(xml_files)}")
    print(f"Files passed: {passed_count}")
    print(f"Files failed: {len(xml_files) - passed_count}")

    if all_valid:
        print("\n✓ All XML files are valid and ready for ACM submission")
    else:
        print("\n✗ Some XML files have issues that should be addressed")
    print("=" * 80)

    return all_valid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Comprehensive validation and analysis of ACM XML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single file
  python validate_acm_xml.py acm_output.xml

  # Validate multiple files with aggregated statistics
  python validate_acm_xml.py full_papers.xml short_papers.xml demo_papers.xml
  python validate_acm_xml.py sigir2026-*.xml
        """
    )

    parser.add_argument(
        "xml_files",
        nargs="+",
        metavar="xml_file",
        help="Path(s) to ACM XML file(s) to validate"
    )

    args = parser.parse_args()

    try:
        if len(args.xml_files) == 1:
            # Single file mode - detailed output
            validation_passed, _, _ = validate_xml_file(args.xml_files[0], show_header=True)
            sys.exit(0 if validation_passed else 1)
        else:
            # Multiple files mode - aggregated statistics
            validation_passed = validate_multiple_files(args.xml_files)
            sys.exit(0 if validation_passed else 1)
    except Exception as e:
        print(f"\n✗ CRITICAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
