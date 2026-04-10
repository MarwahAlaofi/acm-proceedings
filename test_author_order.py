"""
Author Order and Affiliation Validation Test
=============================================

This script validates that the generated ACM XML file correctly matches
the EasyChair export data:
- Author order matches the Submissions.Authors column
- Affiliations match the Authors sheet (no parsing/assumptions)
- Department field is empty (as expected)
- Institution field matches Affiliation field exactly
- Country field matches Country field exactly

Usage:
    python test_author_order.py <excel_file> <xml_file>

Returns:
    Exit code 0 if all validations pass
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


def clean_text(x):
    """Remove line feeds, tabs, and extra whitespace (same as in main script)."""
    if pd.isna(x):
        return ""
    return " ".join(str(x).split())


def validate_author_order(excel_file, xml_file):
    """
    Validate that author order and affiliations in XML match the data from Excel.

    Args:
        excel_file: Path to EasyChair Excel export
        xml_file: Path to generated ACM XML file

    Returns:
        tuple: (is_valid, mismatches) where is_valid is bool and mismatches is list of dicts
    """
    print("=" * 80)
    print("AUTHOR ORDER AND AFFILIATION VALIDATION TEST")
    print("=" * 80)
    print(f"Excel file: {excel_file}")
    print(f"XML file: {xml_file}")
    print()

    # Load Excel data
    print("Loading Excel data...")
    excel = pd.ExcelFile(excel_file)
    submissions_df = pd.read_excel(excel, "Submissions")
    authors_df = pd.read_excel(excel, "Authors")

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
    print("Validating author order and affiliations...")
    print("-" * 80)

    mismatches = []
    papers_checked = 0
    papers_by_prefix = defaultdict(int)
    affiliation_issues = 0

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
            continue

        # Validate affiliations
        # Get expected affiliations from Authors sheet
        expected_authors = authors_df[authors_df["Submission #"] == paper_id].copy()

        # Create mapping by parsing the correct order
        authors_str = str(accepted_submissions[accepted_submissions["#"] == paper_id].iloc[0].get("Authors", ""))
        authors_str = " ".join(authors_str.split())
        authors_str = authors_str.replace(" and ", ", ")
        author_names_order = [name.strip() for name in authors_str.split(",") if name.strip()]

        # Build expected affiliations in correct order
        # Apply same text cleaning as main script (clean line breaks, extra whitespace)
        expected_affiliations = []
        for expected_name in author_names_order:
            # Find matching author in expected_authors
            matched = False
            for _, exp_auth in expected_authors.iterrows():
                exp_full_name = f"{exp_auth['First name']} {exp_auth['Last name']}"
                if normalize_name(expected_name) == normalize_name(exp_full_name):
                    # Apply same cleaning as main script
                    affiliation = clean_text(exp_auth.get("Affiliation", ""))
                    country = clean_text(exp_auth.get("Country", ""))

                    expected_affiliations.append({
                        "name": exp_full_name,
                        "affiliation": affiliation,
                        "country": country,
                    })
                    matched = True
                    break

            if not matched:
                expected_affiliations.append({
                    "name": expected_name,
                    "affiliation": "",
                    "country": "",
                })

        # Check affiliations in XML
        for idx, author_xml in enumerate(authors_xml.findall("author")):
            if idx >= len(expected_affiliations):
                break

            expected_aff = expected_affiliations[idx]

            # Get affiliation from XML
            affiliations_xml = author_xml.find("affiliations")
            if affiliations_xml is not None:
                affiliation_xml = affiliations_xml.find("affiliation")
                if affiliation_xml is not None:
                    xml_dept = affiliation_xml.find("department").text or ""
                    xml_inst = affiliation_xml.find("institution").text or ""
                    xml_country = affiliation_xml.find("country").text or ""

                    # Department should be empty (not parsed)
                    if xml_dept.strip():
                        affiliation_issues += 1
                        mismatches.append({
                            "paper_id": paper_id,
                            "error": f"Affiliation validation: department field should be empty for author {expected_aff['name']}",
                            "detail": f"Expected: department='', Got: department='{xml_dept}'",
                            "expected": [],
                            "actual": [],
                        })
                        continue

                    # Institution should match Affiliation field exactly
                    if xml_inst.strip() != expected_aff["affiliation"]:
                        affiliation_issues += 1
                        mismatches.append({
                            "paper_id": paper_id,
                            "error": f"Affiliation mismatch for author {expected_aff['name']}",
                            "detail": f"Expected: institution='{expected_aff['affiliation']}', Got: institution='{xml_inst}'",
                            "expected": [],
                            "actual": [],
                        })
                        continue

                    # Country should match
                    if xml_country.strip() != expected_aff["country"]:
                        affiliation_issues += 1
                        mismatches.append({
                            "paper_id": paper_id,
                            "error": f"Country mismatch for author {expected_aff['name']}",
                            "detail": f"Expected: country='{expected_aff['country']}', Got: country='{xml_country}'",
                            "expected": [],
                            "actual": [],
                        })
                        continue

    # Print results
    print(f"Papers checked: {papers_checked}")
    print(f"Papers by type: {dict(papers_by_prefix)}")
    print()

    if mismatches:
        # Count different types of issues
        order_issues = sum(1 for m in mismatches if "order" in m["error"].lower())
        aff_issues = sum(1 for m in mismatches if "affiliation" in m["error"].lower() or "country" in m["error"].lower() or "department" in m["error"].lower())

        print("=" * 80)
        print(f"❌ VALIDATION FAILED: {len(mismatches)} issue(s) found")
        if order_issues > 0:
            print(f"   • Author order issues: {order_issues}")
        if aff_issues > 0:
            print(f"   • Affiliation issues: {aff_issues}")
        print("=" * 80)
        print()

        # Show first 10 mismatches in detail
        for i, mismatch in enumerate(mismatches[:10], 1):
            print(f"Paper #{mismatch['paper_id']}:")
            print(f"  Error: {mismatch['error']}")

            # Show detail field for affiliation issues
            if 'detail' in mismatch and mismatch['detail']:
                print(f"  {mismatch['detail']}")

            # Show expected/actual lists for author order issues
            if mismatch['expected'] and mismatch['actual']:
                if len(mismatch['expected']) > 0 and isinstance(mismatch['expected'][0], str):
                    print(f"  Expected order ({len(mismatch['expected'])} authors):")
                    for j, name in enumerate(mismatch['expected'], 1):
                        print(f"    {j}. {name}")

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
        print(f"✅ VALIDATION PASSED: All {papers_checked} papers have correct author order and affiliations")
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
