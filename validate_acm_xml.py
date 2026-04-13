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
- Outputs formatted reports with configurable top-k limits

Usage:
    python validate_acm_xml.py <xml_file>
    python validate_acm_xml.py acm_output.xml
    python validate_acm_xml.py acm_output.xml --output report --top_k 10
    python validate_acm_xml.py acm_output.xml --output report --top_k full

Output Files (when --output is specified):
    <prefix>_validation.txt - Validation results and data quality
    <prefix>_statistics.txt - Comprehensive statistics with top-k lists
    <prefix>_similar_affiliations.txt - Detailed similar affiliation groups

Returns:
    Exit code 0 if all validations pass
    Exit code 1 if critical issues are found
"""

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
import argparse
from pathlib import Path

# Import validation functions
from validation import (
    check_name_capitalization,
    check_email_name_consistency,
    find_similar_affiliations,
    find_similar_affiliations_multi_file,
    print_name_capitalization_issues,
    print_email_name_consistency_issues,
    print_similar_affiliations,
    generate_statistics,
    print_statistics,
    merge_statistics,
    merge_quality_stats,
    merge_similar_affiliation_counts
)

try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False


def write_validation_report(output_prefix, file_results, merged_quality, all_valid):
    """
    Write validation results to formatted text file.

    Args:
        output_prefix: Output file prefix
        file_results: List of (xml_file, is_valid, stats_data, quality_stats) tuples
        merged_quality: Merged quality statistics
        all_valid: Whether all files passed validation
    """
    if not TABULATE_AVAILABLE:
        print("Warning: tabulate not installed, skipping formatted output")
        return

    output_file = f"{output_prefix}_validation.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("ACM XML VALIDATION REPORT\n")
        f.write("=" * 100 + "\n\n")

        # Per-file validation summary
        f.write("PER-FILE VALIDATION SUMMARY\n")
        f.write("-" * 100 + "\n\n")

        table_data = []
        for xml_file, is_valid, _, quality_stats in file_results:
            status = "PASSED" if is_valid else "FAILED"
            if quality_stats:
                papers = quality_stats['total_papers']
                authors = quality_stats['total_authors']
                missing = quality_stats['papers_with_missing_data']
                table_data.append([Path(xml_file).name, status, papers, authors, missing])
            else:
                table_data.append([Path(xml_file).name, "PARSE ERROR", "-", "-", "-"])

        headers = ["File", "Status", "Papers", "Authors", "Papers with Missing Data"]
        f.write(tabulate(table_data, headers=headers, tablefmt="grid"))
        f.write("\n\n")

        # Aggregated data quality
        f.write("AGGREGATED DATA QUALITY\n")
        f.write("-" * 100 + "\n\n")

        quality_table = [
            ["Total files", len(file_results)],
            ["Total papers", merged_quality['total_papers']],
            ["Total authors", merged_quality['total_authors']],
            ["", ""],
            ["Missing emails", merged_quality['missing_emails']],
            ["Missing affiliations", merged_quality['missing_affiliations']],
            ["Missing first names", merged_quality['missing_first_names']],
            ["Missing last names", merged_quality['missing_last_names']],
            ["", ""],
            ["Papers with missing data", f"{merged_quality['papers_with_missing_data']} ({merged_quality['papers_with_missing_data']/merged_quality['total_papers']*100:.1f}%)"],
        ]

        f.write(tabulate(quality_table, tablefmt="plain"))
        f.write("\n\n")

        # Final validation summary
        f.write("=" * 100 + "\n")
        f.write("FINAL VALIDATION SUMMARY\n")
        f.write("=" * 100 + "\n\n")

        passed_count = sum(1 for _, is_valid, _, _ in file_results if is_valid)
        summary_table = [
            ["Files validated", len(file_results)],
            ["Files passed", passed_count],
            ["Files failed", len(file_results) - passed_count],
            ["", ""],
            ["Overall result", "PASSED - Ready for ACM submission" if all_valid else "FAILED - Issues need to be addressed"]
        ]

        f.write(tabulate(summary_table, tablefmt="plain"))
        f.write("\n")

    print(f"\n✓ Validation report written to: {output_file}")


def write_similar_affiliations_report(output_prefix, similar_groups):
    """
    Write detailed similar affiliations to formatted text file.

    Args:
        output_prefix: Output file prefix
        similar_groups: Similar affiliation groups
    """
    if not TABULATE_AVAILABLE:
        print("Warning: tabulate not installed, skipping formatted output")
        return

    output_file = f"{output_prefix}_similar_affiliations.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("SIMILAR AFFILIATIONS - DETAILED GROUPS\n")
        f.write("=" * 100 + "\n\n")

        if not similar_groups:
            f.write("No similar affiliations detected.\n")
            print(f"✓ Similar affiliations report written to: {output_file}")
            return

        # Count by match type
        known_alias_matches = sum(1 for g in similar_groups if g.get("match_type") == "known_alias")
        email_domain_matches = sum(1 for g in similar_groups if g.get("match_type") == "email_domain")
        string_similarity_matches = sum(1 for g in similar_groups if g.get("match_type") == "string_similarity")

        f.write(f"Total: {len(similar_groups)} group(s) detected\n")
        f.write(f"  - {known_alias_matches} known aliases\n")
        f.write(f"  - {email_domain_matches} matched by email domain\n")
        f.write(f"  - {string_similarity_matches} matched by string similarity\n\n")
        f.write("=" * 100 + "\n\n")

        # Write all groups
        for i, group in enumerate(similar_groups, 1):
            match_type = group.get("match_type", "unknown")
            if match_type == "known_alias":
                canonical = group.get("canonical", "")
                f.write(f"Group {i} (known alias: {canonical}):\n")
            elif match_type == "email_domain":
                domain = group.get("email_domain", "")
                f.write(f"Group {i} (email domain: @{domain}):\n")
            else:
                f.write(f"Group {i} (string similarity):\n")

            group_table = []
            for aff in group["affiliations"]:
                count = len(group["details"][aff])
                group_table.append([aff, count])

            f.write(tabulate(group_table, headers=["Affiliation", "Authors"], tablefmt="simple"))
            f.write("\n\n")

    print(f"✓ Similar affiliations report written to: {output_file}")


def write_statistics_report(output_prefix, merged_stats, similar_groups=None, top_k=20):
    """
    Write statistics to formatted text file.

    Args:
        output_prefix: Output file prefix
        merged_stats: Merged statistics dictionary
        similar_groups: Optional similar affiliation groups
        top_k: Number of items to show in top lists (or "full" for all)
    """
    if not TABULATE_AVAILABLE:
        print("Warning: tabulate not installed, skipping formatted output")
        return

    # Parse top_k
    if top_k == "full":
        limit = None
    else:
        try:
            limit = int(top_k)
        except (ValueError, TypeError):
            limit = 20  # default

    output_file = f"{output_prefix}_statistics.txt"

    papers_by_track = merged_stats["papers_by_track"]
    papers_by_type = merged_stats["papers_by_type"]
    author_paper_count = merged_stats["author_paper_count"]
    affiliation_count = merged_stats["affiliation_count"]
    affiliation_papers = merged_stats.get("affiliation_papers", {})
    country_count = merged_stats["country_count"]
    country_papers = merged_stats.get("country_papers", {})

    total_papers = sum(papers_by_track.values())

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("ACM XML STATISTICS REPORT\n")
        f.write("=" * 100 + "\n\n")

        # Papers by track/section
        f.write("PAPERS BY TRACK/SECTION\n")
        f.write("-" * 100 + "\n\n")

        track_table = []
        for track, count in sorted(papers_by_track.items(), key=lambda x: x[1], reverse=True):
            track_name = track if track else "(No section specified)"
            percentage = f"{count/total_papers*100:.1f}%"
            track_table.append([track_name, count, percentage])

        f.write(tabulate(track_table, headers=["Track/Section", "Papers", "Percentage"], tablefmt="grid"))
        f.write(f"\n\nTotal: {total_papers} papers\n\n")

        # Papers by type
        f.write("PAPERS BY TYPE\n")
        f.write("-" * 100 + "\n\n")

        type_table = []
        for ptype, count in sorted(papers_by_type.items(), key=lambda x: x[1], reverse=True):
            percentage = f"{count/total_papers*100:.1f}%"
            type_table.append([ptype, count, percentage])

        f.write(tabulate(type_table, headers=["Paper Type", "Papers", "Percentage"], tablefmt="grid"))
        f.write("\n\n")

        # Authors statistics
        f.write("AUTHOR STATISTICS\n")
        f.write("-" * 100 + "\n\n")

        total_author_entries = sum(len(papers) for papers in author_paper_count.values())
        unique_authors = len(author_paper_count)
        avg_papers_per_author = total_author_entries / unique_authors if unique_authors > 0 else 0
        avg_authors_per_paper = total_author_entries / total_papers if total_papers > 0 else 0

        author_stats_table = [
            ["Total author entries", total_author_entries],
            ["Unique authors", unique_authors],
            ["Average papers per author", f"{avg_papers_per_author:.2f}"],
            ["Average authors per paper", f"{avg_authors_per_paper:.1f}"]
        ]

        f.write(tabulate(author_stats_table, tablefmt="plain"))
        f.write("\n\n")

        # Most prolific authors
        sorted_authors = sorted(author_paper_count.items(), key=lambda x: len(x[1]), reverse=True)
        if limit is not None:
            f.write(f"TOP {limit} MOST PROLIFIC AUTHORS\n")
            sorted_authors = sorted_authors[:limit]
        else:
            f.write("MOST PROLIFIC AUTHORS (ALL)\n")
        f.write("-" * 100 + "\n\n")

        prolific_table = []

        for i, ((first, last, email), papers) in enumerate(sorted_authors, 1):
            name = f"{first} {last}"
            email_str = email if email else "N/A"
            num_papers = len(papers)

            # Paper types breakdown
            type_counts = Counter(ptype for _, ptype in papers)
            type_str = ", ".join(f"{count} {ptype}" for ptype, count in sorted(type_counts.items()))

            prolific_table.append([i, name, email_str, num_papers, type_str])

        f.write(tabulate(prolific_table, headers=["Rank", "Author", "Email", "Papers", "Types"], tablefmt="grid"))
        f.write("\n\n")

        # Top affiliations (unmerged)
        if limit is not None:
            f.write(f"TOP {limit} MOST COMMON AFFILIATIONS\n")
            aff_list = affiliation_count.most_common(limit)
        else:
            f.write("MOST COMMON AFFILIATIONS (ALL)\n")
            aff_list = affiliation_count.most_common()
        f.write("-" * 100 + "\n\n")

        aff_table = []
        for i, (affiliation, author_count) in enumerate(aff_list, 1):
            paper_count = len(affiliation_papers.get(affiliation, set()))
            aff_table.append([i, affiliation, author_count, paper_count])

        f.write(tabulate(aff_table, headers=["Rank", "Affiliation", "Authors", "Papers"], tablefmt="grid"))
        f.write("\n\n")

        # Top affiliations (merged) - if similar groups provided
        if similar_groups is not None:
            if limit is not None:
                f.write(f"TOP {limit} MOST COMMON AFFILIATIONS (AFTER MERGING SIMILAR)\n")
            else:
                f.write("MOST COMMON AFFILIATIONS (AFTER MERGING SIMILAR - ALL)\n")
            f.write("-" * 100 + "\n\n")

            if similar_groups:
                # Merge counts
                merged_author_counts, merged_paper_counts = merge_similar_affiliation_counts(
                    affiliation_count, affiliation_papers, similar_groups
                )

                if limit is not None:
                    merged_aff_list = merged_author_counts.most_common(limit)
                else:
                    merged_aff_list = merged_author_counts.most_common()

                merged_aff_table = []
                for i, (affiliation, author_count) in enumerate(merged_aff_list, 1):
                    paper_count = merged_paper_counts.get(affiliation, 0)
                    merged_aff_table.append([i, affiliation, author_count, paper_count])

                f.write(tabulate(merged_aff_table, headers=["Rank", "Affiliation", "Authors", "Papers"], tablefmt="grid"))
                f.write(f"\n\nNote: {len(similar_groups)} group(s) of similar affiliations were merged.\n")
                f.write(f"See {output_prefix}_similar_affiliations.txt for detailed groups.\n\n")
            else:
                f.write("No similar affiliations detected - counts remain unchanged\n\n")

        # Top countries
        if limit is not None:
            f.write(f"TOP {limit} MOST COMMON COUNTRIES\n")
            country_list = country_count.most_common(limit)
        else:
            f.write("MOST COMMON COUNTRIES (ALL)\n")
            country_list = country_count.most_common()
        f.write("-" * 100 + "\n\n")

        country_table = []
        for i, (country, author_count) in enumerate(country_list, 1):
            paper_count = len(country_papers.get(country, set()))
            country_table.append([i, country, author_count, paper_count])

        f.write(tabulate(country_table, headers=["Rank", "Country", "Authors", "Papers"], tablefmt="grid"))
        f.write("\n\n")

    print(f"✓ Statistics report written to: {output_file}")


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


def validate_xml_file(xml_file, show_header=True, output_prefix=None, top_k=20):
    """
    Main validation and analysis function.

    Args:
        xml_file: Path to XML file
        show_header: Whether to show full header (False for multi-file mode)
        output_prefix: Optional output file prefix for formatted reports
        top_k: Number of items to show in top lists (or "full" for all)

    Returns:
        tuple: (is_valid, stats_data, quality_stats, root) for aggregation
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
        return False, None, None, None

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
        print_statistics(stats_data, root=root)

    # Additional validation checks
    if show_header:
        print("\n" + "=" * 80)
        print("ADDITIONAL VALIDATION CHECKS")
        print("=" * 80)

        # Check name capitalization
        print("\nName Capitalization:")
        cap_issues = check_name_capitalization(root)
        print_name_capitalization_issues(cap_issues)

        # Check email-name consistency
        print("\nEmail-Name Consistency:")
        email_issues = check_email_name_consistency(root)
        print_email_name_consistency_issues(email_issues)

        # Check similar affiliations
        print("\nSimilar Affiliations:")
        similar_affs = find_similar_affiliations(root, similarity_threshold=0.8)
        print_similar_affiliations(similar_affs)

        print("=" * 80)

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

    # Write formatted output files if requested (single file mode)
    if output_prefix and show_header:
        file_results = [(xml_file, is_valid, stats_data, quality_stats)]
        write_validation_report(output_prefix, file_results, quality_stats, is_valid)

        # Find similar affiliations for statistics
        similar_groups = find_similar_affiliations(root, similarity_threshold=0.8)
        write_statistics_report(output_prefix, stats_data, similar_groups, top_k=top_k)

        # Write similar affiliations to separate file
        if similar_groups:
            write_similar_affiliations_report(output_prefix, similar_groups)

    return is_valid, stats_data, quality_stats, root


def validate_multiple_files(xml_files, output_prefix=None, top_k=20):
    """
    Validate multiple XML files and aggregate statistics.

    Args:
        xml_files: List of XML file paths
        output_prefix: Optional output file prefix for formatted reports
        top_k: Number of items to show in top lists (or "full" for all)

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
    all_roots = []
    file_results = []

    # Validate each file
    for xml_file in xml_files:
        is_valid, stats_data, quality_stats, root = validate_xml_file(xml_file, show_header=False)

        if stats_data is None:  # Parse error (XML couldn't be parsed)
            all_valid = False
            file_results.append((xml_file, False, None, None))
            continue

        all_valid = all_valid and is_valid
        all_stats.append(stats_data)
        all_quality_stats.append(quality_stats)
        all_roots.append(root)
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
        merged_stats = merge_statistics(all_stats)
        merged_quality = merge_quality_stats(all_quality_stats)

        # Find similar affiliations across all files
        similar_groups = None
        if all_roots:
            print("Computing similar affiliations across all files...")
            similar_groups = find_similar_affiliations_multi_file(all_roots, similarity_threshold=0.8)
            print(f"Found {len(similar_groups)} group(s) of similar affiliations\n")

        # Print aggregated statistics with merged affiliations
        print_statistics(merged_stats, similar_groups=similar_groups)

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

        # Similar affiliations (multi-file analysis)
        if similar_groups:
            print("\n" + "=" * 80)
            print("SIMILAR AFFILIATIONS (ACROSS ALL FILES)")
            print("=" * 80)
            print_similar_affiliations(similar_groups)
            print("=" * 80)

        # Write formatted output files if requested
        if output_prefix:
            write_validation_report(output_prefix, file_results, merged_quality, all_valid)
            write_statistics_report(output_prefix, merged_stats, similar_groups, top_k=top_k)

            # Write similar affiliations to separate file
            if similar_groups:
                write_similar_affiliations_report(output_prefix, similar_groups)

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

  # Validate single file and write formatted reports
  python validate_acm_xml.py acm_output.xml --output sigir2026_report

  # Validate with custom top_k (show top 10 instead of default 20)
  python validate_acm_xml.py acm_output.xml --output sigir2026_report --top_k 10

  # Validate and show all statistics (not just top items)
  python validate_acm_xml.py acm_output.xml --output sigir2026_report --top_k full

  # Validate multiple files with aggregated statistics
  python validate_acm_xml.py full_papers.xml short_papers.xml demo_papers.xml

  # Validate multiple files and write formatted reports
  python validate_acm_xml.py sigir2026-*.xml --output sigir2026_combined
        """
    )

    parser.add_argument(
        "xml_files",
        nargs="+",
        metavar="xml_file",
        help="Path(s) to ACM XML file(s) to validate"
    )

    parser.add_argument(
        "--output",
        "-o",
        metavar="PREFIX",
        help="Output file prefix for formatted reports. "
        "Creates <PREFIX>_validation.txt, <PREFIX>_statistics.txt, and <PREFIX>_similar_affiliations.txt. "
        "Requires tabulate library (pip install tabulate)."
    )

    parser.add_argument(
        "--top_k",
        "-k",
        metavar="N",
        default="20",
        help="Number of items to show in top lists (default: 20). Use 'full' to show all items sorted."
    )

    args = parser.parse_args()

    # Check if tabulate is available when output is requested
    if args.output and not TABULATE_AVAILABLE:
        print("Error: --output requires tabulate library. Install with: pip install tabulate", file=sys.stderr)
        sys.exit(1)

    try:
        if len(args.xml_files) == 1:
            # Single file mode - detailed output
            validation_passed, _, _, _ = validate_xml_file(
                args.xml_files[0],
                show_header=True,
                output_prefix=args.output,
                top_k=args.top_k
            )
            sys.exit(0 if validation_passed else 1)
        else:
            # Multiple files mode - aggregated statistics
            validation_passed = validate_multiple_files(
                args.xml_files,
                output_prefix=args.output,
                top_k=args.top_k
            )
            sys.exit(0 if validation_passed else 1)
    except Exception as e:
        print(f"\n✗ CRITICAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
