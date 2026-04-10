"""
Author Order Validation Test
=============================

This script validates that the author order in the generated ACM XML file
matches the correct order from the EasyChair Submissions sheet.

Usage:
    python test_author_order.py <excel_file> <xml_file>

Returns:
    Exit code 0 if all papers have correct author order
    Exit code 1 if any mismatches are found
"""

import sys
import pandas as pd
import xml.etree.ElementTree as ET
from collections import defaultdict


def parse_authors_from_string(authors_str):
    """
    Parse author names from the Submissions.Authors column.

    Args:
        authors_str: Raw author string (e.g., "John Doe, Jane Smith and Bob Lee")

    Returns:
        List of author names in order
    """
    # Clean the text: remove line breaks and extra whitespace
    authors_str = " ".join(str(authors_str).split())

    # Replace " and " with ", " to normalize separators
    authors_str = authors_str.replace(" and ", ", ")

    # Split by comma
    authors = [name.strip() for name in authors_str.split(",") if name.strip()]

    return authors


def normalize_name(name):
    """Normalize name for comparison (lowercase, strip whitespace)."""
    return name.lower().strip()


def validate_author_order(excel_file, xml_file):
    """
    Validate that author order in XML matches the order from Excel.

    Args:
        excel_file: Path to EasyChair Excel export
        xml_file: Path to generated ACM XML file

    Returns:
        tuple: (is_valid, mismatches) where is_valid is bool and mismatches is list of dicts
    """
    print("=" * 80)
    print("AUTHOR ORDER VALIDATION TEST")
    print("=" * 80)
    print(f"Excel file: {excel_file}")
    print(f"XML file: {xml_file}")
    print()

    # Load Excel data
    print("Loading Excel data...")
    excel = pd.ExcelFile(excel_file)
    submissions_df = pd.read_excel(excel, "Submissions")

    # Filter accepted papers
    accepted_submissions = submissions_df[
        (submissions_df["Decision"] == "Accept paper/proposal")
        | (submissions_df["Decision"] == "tentatively accepted")
    ].copy()

    print(f"Found {len(accepted_submissions)} accepted submissions in Excel")

    # Build expected author order for each paper
    expected_orders = {}
    for _, submission in accepted_submissions.iterrows():
        paper_id = submission["#"]
        authors_str = submission.get("Authors", "")
        expected_orders[paper_id] = parse_authors_from_string(authors_str)

    # Load XML data
    print(f"Loading XML data...")
    tree = ET.parse(xml_file)
    root = tree.getroot()

    papers = root.findall("paper")
    print(f"Found {len(papers)} papers in XML")
    print()

    # Validate each paper
    print("Validating author order...")
    print("-" * 80)

    mismatches = []
    papers_checked = 0
    papers_by_prefix = defaultdict(int)

    for paper in papers:
        # Extract paper ID from event_tracking_number
        # Format: "fp123" -> paper ID 123, "de456" -> paper ID 456
        tracking_num = paper.find("event_tracking_number")
        if tracking_num is None or not tracking_num.text:
            continue

        # Extract numeric ID from tracking number (e.g., "fp123" -> 123)
        tracking_text = tracking_num.text
        paper_id = int(''.join(filter(str.isdigit, tracking_text)))

        # Track prefix usage
        prefix = ''.join(filter(str.isalpha, tracking_text))
        papers_by_prefix[prefix] += 1

        # Get expected order from Excel
        if paper_id not in expected_orders:
            mismatches.append({
                "paper_id": paper_id,
                "error": "Paper not found in Excel accepted submissions",
                "expected": [],
                "actual": [],
            })
            continue

        expected = expected_orders[paper_id]

        # Get actual order from XML
        authors_xml = paper.find("authors")
        if authors_xml is None:
            mismatches.append({
                "paper_id": paper_id,
                "error": "No authors section found in XML",
                "expected": expected,
                "actual": [],
            })
            continue

        actual = []
        for author_xml in authors_xml.findall("author"):
            first_name = author_xml.find("first_name")
            last_name = author_xml.find("last_name")
            if first_name is not None and last_name is not None:
                full_name = f"{first_name.text} {last_name.text}"
                actual.append(full_name)

        # Compare orders
        papers_checked += 1

        if len(expected) != len(actual):
            mismatches.append({
                "paper_id": paper_id,
                "error": f"Author count mismatch (expected {len(expected)}, got {len(actual)})",
                "expected": expected,
                "actual": actual,
            })
            continue

        # Check if order matches (case-insensitive comparison)
        order_matches = all(
            normalize_name(exp) == normalize_name(act)
            for exp, act in zip(expected, actual)
        )

        if not order_matches:
            mismatches.append({
                "paper_id": paper_id,
                "error": "Author order mismatch",
                "expected": expected,
                "actual": actual,
            })

    # Print results
    print(f"Papers checked: {papers_checked}")
    print(f"Papers by type: {dict(papers_by_prefix)}")
    print()

    if mismatches:
        print("=" * 80)
        print(f"❌ VALIDATION FAILED: {len(mismatches)} paper(s) with author order issues")
        print("=" * 80)
        print()

        # Show first 10 mismatches in detail
        for i, mismatch in enumerate(mismatches[:10], 1):
            print(f"Paper #{mismatch['paper_id']}:")
            print(f"  Error: {mismatch['error']}")

            if mismatch['expected']:
                print(f"  Expected order ({len(mismatch['expected'])} authors):")
                for j, name in enumerate(mismatch['expected'], 1):
                    print(f"    {j}. {name}")

            if mismatch['actual']:
                print(f"  Actual order ({len(mismatch['actual'])} authors):")
                for j, name in enumerate(mismatch['actual'], 1):
                    print(f"    {j}. {name}")

            print()

        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more paper(s) with issues")
            print()

        return False, mismatches
    else:
        print("=" * 80)
        print(f"✅ VALIDATION PASSED: All {papers_checked} papers have correct author order")
        print("=" * 80)
        return True, []


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_author_order.py <excel_file> <xml_file>")
        sys.exit(1)

    excel_file = sys.argv[1]
    xml_file = sys.argv[2]

    try:
        is_valid, mismatches = validate_author_order(excel_file, xml_file)
        sys.exit(0 if is_valid else 1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
