"""
Author Order and Affiliation Validation Test
=============================================

This script validates that the generated output file (XML, TXT, or MD)
correctly matches the EasyChair export data:
- Author order matches the Submissions.Authors column
- Affiliations match the Authors sheet

For XML format:
- Department field is empty (as expected)
- Institution field matches Affiliation field exactly
- Country field matches Country field exactly

For TXT/MD format:
- Author names and affiliations are correctly formatted
- Author order is preserved

Usage:
    python test_author_order.py <excel_file> <output_file>

Returns:
    Exit code 0 if all validations pass
    Exit code 1 if any mismatches are found
"""

import sys
import pandas as pd
import xml.etree.ElementTree as ET
from collections import defaultdict
import re


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


def validate_text_format(excel_file, text_file):
    """
    Validate that author order and affiliations in text/markdown file match Excel data.

    Args:
        excel_file: Path to EasyChair Excel export
        text_file: Path to generated text or markdown file

    Returns:
        tuple: (is_valid, mismatches) where is_valid is bool and mismatches is list of dicts
    """
    print("=" * 80)
    print("AUTHOR ORDER AND AFFILIATION VALIDATION TEST (TEXT FORMAT)")
    print("=" * 80)
    print(f"Excel file: {excel_file}")
    print(f"Text file: {text_file}")
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

    # Clean text fields
    submissions_df["Title"] = submissions_df["Title"].apply(clean_text)
    authors_df["First name"] = authors_df["First name"].apply(clean_text)
    authors_df["Last name"] = authors_df["Last name"].apply(clean_text)
    authors_df["Affiliation"] = authors_df["Affiliation"].apply(clean_text)

    # Build expected data structure
    expected_papers = {}
    for _, submission in accepted_submissions.iterrows():
        paper_id = submission["#"]
        title = clean_text(submission.get("Title", ""))

        # Get expected author order
        authors_str = submission.get("Authors", "")
        author_names = parse_authors_from_string(authors_str)

        # Get author details from Authors sheet
        paper_authors = authors_df[authors_df["Submission #"] == paper_id]

        # Match authors to get affiliations in correct order
        authors_with_aff = []
        for author_name in author_names:
            matched = False
            for _, auth_row in paper_authors.iterrows():
                auth_full = f"{auth_row['First name']} {auth_row['Last name']}"
                if normalize_name(author_name) == normalize_name(auth_full):
                    affiliation = clean_text(auth_row.get("Affiliation", ""))
                    authors_with_aff.append((auth_full, affiliation))
                    matched = True
                    break
            if not matched:
                authors_with_aff.append((author_name, ""))

        expected_papers[title] = {
            "paper_id": paper_id,
            "authors": authors_with_aff
        }

    # Read and parse text file
    print(f"Loading text file...")
    with open(text_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse text file to extract papers and authors
    # Detect format by checking for markdown headers
    is_markdown = "# " in content or "## " in content

    actual_papers = {}
    current_track = None
    current_paper_title = None
    current_authors = []

    lines = content.split("\n")
    for line in lines:
        line_stripped = line.strip()

        if not line_stripped:
            # Empty line - save current paper if any
            if current_paper_title and current_authors:
                actual_papers[current_paper_title] = current_authors
                current_authors = []
                current_paper_title = None
            continue

        if is_markdown:
            # Markdown format
            if line_stripped.startswith("# "):
                # Track header
                current_track = line_stripped[2:].strip()
                if current_paper_title and current_authors:
                    actual_papers[current_paper_title] = current_authors
                    current_authors = []
                current_paper_title = None
            elif line_stripped.startswith("## "):
                # Paper title
                if current_paper_title and current_authors:
                    actual_papers[current_paper_title] = current_authors
                    current_authors = []
                current_paper_title = line_stripped[3:].strip()
            else:
                # Author line
                if current_paper_title:
                    # Parse "Name, Affiliation" or just "Name"
                    if ", " in line_stripped:
                        parts = line_stripped.rsplit(", ", 1)
                        current_authors.append((parts[0], parts[1]))
                    else:
                        current_authors.append((line_stripped, ""))
        else:
            # Plain text format - need to differentiate between track, title, and author
            # Track lines don't start with capital followed by lowercase (heuristic)
            # Paper titles are followed by author lines with commas or are first after track
            # This is tricky - let's use a simple heuristic:
            # If previous line was empty or track, this might be title or track
            # If line contains comma after a name, it's likely an author

            # Simple approach: treat lines without commas as titles/tracks
            # Lines with ", " as authors
            if ", " in line_stripped:
                # Author line
                parts = line_stripped.rsplit(", ", 1)
                current_authors.append((parts[0], parts[1]))
            else:
                # Could be track, title, or author without affiliation
                # If we have a current paper with authors, save it
                if current_paper_title and current_authors:
                    actual_papers[current_paper_title] = current_authors
                    current_authors = []

                # Check if this looks like an author (name format) or a title/track
                # If it looks like "Firstname Lastname", treat as author
                # Otherwise, treat as title
                words = line_stripped.split()
                if len(words) >= 2 and all(w[0].isupper() for w in words[:2]):
                    # Could be author name
                    if current_paper_title:
                        # We have a paper, so this is an author
                        current_authors.append((line_stripped, ""))
                    else:
                        # No current paper, could be title or track
                        # Check if next iteration clarifies
                        current_paper_title = line_stripped
                else:
                    # Track or title
                    current_paper_title = line_stripped

    # Save last paper
    if current_paper_title and current_authors:
        actual_papers[current_paper_title] = current_authors

    print(f"Found {len(actual_papers)} papers in text file")
    print()

    # Compare
    print("Validating author order and affiliations...")
    print("-" * 80)

    mismatches = []
    papers_checked = 0

    for title, expected_data in expected_papers.items():
        if title not in actual_papers:
            mismatches.append({
                "paper_id": expected_data["paper_id"],
                "title": title,
                "error": "Paper not found in output file",
                "expected": expected_data["authors"],
                "actual": [],
            })
            continue

        actual_authors = actual_papers[title]
        expected_authors = expected_data["authors"]

        papers_checked += 1

        if len(expected_authors) != len(actual_authors):
            mismatches.append({
                "paper_id": expected_data["paper_id"],
                "title": title,
                "error": f"Author count mismatch (expected {len(expected_authors)}, got {len(actual_authors)})",
                "expected": expected_authors,
                "actual": actual_authors,
            })
            continue

        # Check author order and affiliations
        for idx, (exp_auth, act_auth) in enumerate(zip(expected_authors, actual_authors)):
            exp_name, exp_aff = exp_auth
            act_name, act_aff = act_auth

            if normalize_name(exp_name) != normalize_name(act_name):
                mismatches.append({
                    "paper_id": expected_data["paper_id"],
                    "title": title,
                    "error": f"Author #{idx+1} name mismatch",
                    "detail": f"Expected: '{exp_name}', Got: '{act_name}'",
                    "expected": expected_authors,
                    "actual": actual_authors,
                })
                break

            # Check affiliation (allow empty if both are empty)
            if exp_aff != act_aff:
                if exp_aff or act_aff:  # Only flag if at least one is non-empty
                    mismatches.append({
                        "paper_id": expected_data["paper_id"],
                        "title": title,
                        "error": f"Author '{exp_name}' affiliation mismatch",
                        "detail": f"Expected: '{exp_aff}', Got: '{act_aff}'",
                        "expected": [],
                        "actual": [],
                    })
                    break

    # Print results
    print(f"Papers checked: {papers_checked}")
    print()

    if mismatches:
        print("=" * 80)
        print(f"❌ VALIDATION FAILED: {len(mismatches)} issue(s) found")
        print("=" * 80)
        print()

        # Show first 10 mismatches in detail
        for i, mismatch in enumerate(mismatches[:10], 1):
            print(f"Paper #{mismatch['paper_id']}: {mismatch.get('title', 'N/A')}")
            print(f"  Error: {mismatch['error']}")

            if 'detail' in mismatch and mismatch['detail']:
                print(f"  {mismatch['detail']}")

            if mismatch['expected'] and mismatch['actual']:
                if len(mismatch['expected']) > 0:
                    print(f"  Expected authors ({len(mismatch['expected'])}):")
                    for j, (name, aff) in enumerate(mismatch['expected'], 1):
                        aff_str = f", {aff}" if aff else ""
                        print(f"    {j}. {name}{aff_str}")

                    print(f"  Actual authors ({len(mismatch['actual'])}):")
                    for j, (name, aff) in enumerate(mismatch['actual'], 1):
                        aff_str = f", {aff}" if aff else ""
                        print(f"    {j}. {name}{aff_str}")

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
    print("AUTHOR ORDER AND AFFILIATION VALIDATION TEST (XML FORMAT)")
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
        print("Usage: python test_author_order.py <excel_file> <output_file>")
        sys.exit(1)

    excel_file = sys.argv[1]
    output_file = sys.argv[2]

    try:
        # Detect file type by extension
        if output_file.endswith(".xml"):
            is_valid, mismatches = validate_author_order(excel_file, output_file)
        elif output_file.endswith(".txt") or output_file.endswith(".md"):
            is_valid, mismatches = validate_text_format(excel_file, output_file)
        else:
            print(f"❌ ERROR: Unsupported file format. Expected .xml, .txt, or .md")
            sys.exit(1)

        sys.exit(0 if is_valid else 1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
