import openreview
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import os
import re
import argparse

load_dotenv()

# Map paper type to track abbreviation
track_map = {
    "Full Paper": "fp",
    "Short Paper": "sp",
    "N/A": "na"
}
# ----------------------------
# format/data helpers
# ----------------------------
def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def clean_affiliation_string(affiliation_str):
    """
    Clean affiliation string by stripping whitespace and leading/trailing punctuation.

    Handles common data quality issues like:
    - ", Tsinghua University" → "Tsinghua University"
    - "MIT, " → "MIT"
    - " , Stanford University" → "Stanford University"

    Args:
        affiliation_str: Raw affiliation string

    Returns:
        str: Cleaned affiliation string
    """
    if not affiliation_str:
        return ""

    # Strip whitespace
    cleaned = affiliation_str.strip()

    # Strip leading/trailing punctuation (commas, semicolons, periods, etc.)
    # Keep stripping until no more leading/trailing punctuation+whitespace
    while cleaned and cleaned[0] in '.,;:-_':
        cleaned = cleaned[1:].strip()
    while cleaned and cleaned[-1] in '.,;:-_':
        cleaned = cleaned[:-1].strip()

    return cleaned


# ----------------------------
# Name splitting: profile fields > TSV overrides > naive split
# ----------------------------
def load_name_splits(tsv_path):
    """Load manual name splits from a TSV file. Returns dict: profile_id -> (first, middle, last)."""
    splits = {}
    if not tsv_path or not os.path.exists(tsv_path):
        return splits
    with open(tsv_path) as f:
        header = f.readline()  # skip header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 5:
                splits[parts[0]] = (parts[2], parts[3], parts[4])
    return splits

def split_name_naive(full_name):
    """Fallback: first token = first, last token = last, rest = middle."""
    parts = full_name.strip().split()
    if len(parts) == 0:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return parts[0], " ".join(parts[1:-1]), parts[-1]

def get_author_name(profile, full_name, name_splits):
    """
    Get (first, middle, last) for an author.
    1. Use profile's explicit first/middle/last if available.
    2. Look up in name_splits TSV by profile ID (and all aliases).
    3. Fall back to naive whitespace split.
    """
    if profile:
        # Try profile's structured name fields
        name_entry = profile.content.get("names", [{}])[0]
        for ne in profile.content.get("names", []):
            if ne.get("preferred"):
                name_entry = ne
                break
        first = (name_entry.get("first") or "").strip()
        middle = (name_entry.get("middle") or "").strip()
        last = (name_entry.get("last") or "").strip()
        if first and last:
            return first, middle, last

        # Try TSV lookup by canonical ID and all aliases
        if profile.id in name_splits:
            return name_splits[profile.id]
        for ne in profile.content.get("names", []):
            un = ne.get("username", "")
            if un and un in name_splits:
                return name_splits[un]

    return split_name_naive(full_name)

# ----------------------------
# Safe helpers
# ----------------------------
def get_preferred_emails_bulk(client, venue_id):
    """
    Fetch all unmasked preferred emails for the venue in a single API call.
    Returns dict: profile_id -> email.
    """
    email_map = {}
    try:
        edges = client.get_grouped_edges(
            invitation=f"{venue_id}/-/Preferred_Emails",
            groupby="head", select="tail"
        )
        for group in edges:
            profile_id = group["id"]["head"]
            values = group.get("values", [])
            if values:
                email = values[0].get("tail", "")
                if email and not email.startswith("****"):
                    email_map[profile_id] = email
        print(f"  Fetched {len(email_map)} preferred emails via bulk API call")
    except Exception as e:
        print(f"  [WARNING] Could not fetch preferred emails: {e}")
    return email_map

def get_current_affiliations(profile, author_id=""):
    """
    Extracts all *current* affiliations from a profile.
    An affiliation is considered current if it has no 'end' date.
    Deduplicates identical institutions to prevent redundant XML blocks.
    """
    affiliations = []
    default_aff = {"department": "", "institution": "", "city": "", "state": "", "country": ""}

    try:
        if not profile:
            return [default_aff]

        content = getattr(profile, 'content', {})
        history = content.get("history", [])

        if not history:
            return [default_aff]

        # Filter for current affiliations (no end date)
        current_history = [h for h in history if not h.get("end")]

        # If no active found, fallback to the most recent one
        if not current_history:
            current_history = [history[0]]

        seen = set()

        for entry in current_history:
            inst = entry.get("institution", {})

            if isinstance(inst, str):
                inst_name = inst
                dept = city = state = country = ""
            else:
                inst_name = inst.get("name") or ""
                dept = inst.get("department") or ""
                city = inst.get("city") or ""
                state = inst.get("stateProvince") or ""
                country = inst.get("country") or ""

            key = (inst_name.lower(), dept.lower())

            if key not in seen and (inst_name or dept):
                seen.add(key)
                affiliations.append({
                    "department": dept,
                    "institution": inst_name,
                    "city": city,
                    "state": state,
                    "country": country
                })

        return affiliations if affiliations else [default_aff]

    except Exception as e:
        print(f"  [ERROR] affiliation parsing for {author_id}: {e}")
        return [default_aff]

# ----------------------------
# Profiles mapping (safe)
# Build a map from author IDs (both tilde IDs and emails) to profiles.
# Since submissions may contain emails but profiles are keyed by tilde IDs,
# we need to fetch profiles and build multiple lookup keys.
# ----------------------------
def get_profiles_map(client, author_ids):
    tilde_ids = [aid for aid in author_ids if aid.startswith("~")]
    email_ids = [aid for aid in author_ids if "@" in aid]

    print(f"  Tilde IDs: {len(tilde_ids)}, Email IDs: {len(email_ids)}")

    id2profile = {}

    # Fetch tilde ID profiles in batch
    if tilde_ids:
        try:
            print(f"  Fetching {len(tilde_ids)} tilde ID profiles...")
            profiles = openreview.tools.get_profiles(client, tilde_ids, with_publications=False)
            print(f"  Successfully fetched {len(profiles)} profiles")

            for p in profiles:
                # Map by canonical ID
                id2profile[p.id] = p
                # Map by all usernames (including aliases)
                for name_entry in p.content.get("names", []):
                    username = name_entry.get("username", "")
                    if username:
                        id2profile[username] = p
                # Map by all associated emails
                for email in p.content.get("emails", []):
                    id2profile[email] = p

        except Exception as e:
            print(f"  [ERROR] Failed to fetch tilde ID profiles: {e}")

    # For email-only IDs, we can attempt lookup, but they may not have profiles
    # Skip them since they're not in OpenReview
    if email_ids:
        print(f"  Note: {len(email_ids)} email-only author IDs without OpenReview profiles (skipped)")

    print(f"  Total mappings in id2profile: {len(id2profile)}")

    return id2profile

# ----------------------------
# Main export function
# ----------------------------
def export_acm_xml(venue_id, paper_type="Full Paper", output_file="acm_output.xml", submissions_file=None, name_splits_file=None, submission_date=None, approval_date=None):

    if paper_type not in ["Full Paper", "Short Paper", "N/A"]:
        raise ValueError("paper_type must be 'Full Paper', 'Short Paper', or 'N/A'")

    client = openreview.api.OpenReviewClient(
        baseurl="https://api2.openreview.net",
        username=os.getenv("OPENREVIEW_USERNAME"),
        password=os.getenv("OPENREVIEW_PASSWORD")
    )

    # Fetch unmasked preferred emails in one bulk API call
    preferred_emails = get_preferred_emails_bulk(client, venue_id)

    # Load manual name splits
    name_splits = load_name_splits(name_splits_file)
    if name_splits:
        print(f"  Loaded {len(name_splits)} manual name splits")

    if submissions_file:
        # Read submission IDs from file (one URL per line)
        note_ids = []
        with open(submissions_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = re.search(r'[?&]id=([A-Za-z0-9_-]+)', line)
                if m:
                    note_ids.append(m.group(1))
                else:
                    note_ids.append(line)  # assume bare ID
        print(f"Fetching {len(note_ids)} submissions from file...")
        submissions = [client.get_note(nid) for nid in note_ids]
        print(f"Fetched {len(submissions)} submissions")
    else:
        # Default: fetch all decisions and filter for accepted submissions
        print("Fetching all notes to find accepted submissions...")
        all_notes = list(client.get_all_notes(invitation=f"{venue_id}/-/Edit"))
        accepted_ids = []
        for n in all_notes:
            if any(inv.endswith("/-/Decision") and "/Submission" in inv for inv in n.invitations):
                if n.content.get("decision", {}).get("value", "") == "Accept":
                    accepted_ids.append(n.forum)
        print(f"Found {len(accepted_ids)} accepted submissions, fetching...")
        submissions = [client.get_note(nid) for nid in accepted_ids]
        print(f"Fetched {len(submissions)} submissions")

    print("Collecting author IDs...")
    author_ids = set()
    for s in submissions:
        ids = s.content.get("authorids", {}).get("value", [])
        for aid in ids:
            if aid and isinstance(aid, str):
                author_ids.add(aid)

    print(f"Found {len(author_ids)} unique author IDs")

    id2profile = get_profiles_map(client, list(author_ids))

    # ----------------------------
    # XML root
    # ----------------------------
    root = ET.Element("erights_record")

    parent = ET.SubElement(root, "parent_data")
    ET.SubElement(parent, "proceeding").text = venue_id
    ET.SubElement(parent, "volume").text = ""
    ET.SubElement(parent, "issue").text = ""
    ET.SubElement(parent, "issue_date").text = ""
    ET.SubElement(parent, "source").text = "OpenReview"

    paper_seq = 1

    for s in submissions:
        paper = ET.SubElement(root, "paper")

        # ----------------------------
        # Paper fields
        # ----------------------------
        ET.SubElement(paper, "paper_type").text = paper_type
        ET.SubElement(paper, "art_submission_date").text = submission_date
        ET.SubElement(paper, "art_approval_date").text = approval_date
        ET.SubElement(paper, "paper_title").text = s.content.get("title", {}).get("value", "")

        #  use sequence numbers as IDs, following the format: sp|fp000
        track_prefix = TRACK_MAP.get(paper_type, "na")
        tracking_id = f"{track_prefix}{paper_seq:03d}"
        #  test using event specific id numbers, following the format: sp|fp000
        tracking_id_test = f"{track_prefix}{s.number:03d}"

        ET.SubElement(paper, "event_tracking_number").text = tracking_id
        ET.SubElement(paper, "event_tracking_number_testing").text = tracking_id_test

        ET.SubElement(paper, "published_article_number").text = ""
        ET.SubElement(paper, "start_page").text = ""
        ET.SubElement(paper, "end_page").text = ""
        authors_xml = ET.SubElement(paper, "authors")

        ids = s.content.get("authorids", {}).get("value", [])
        names = s.content.get("authors", {}).get("value", [])

        for i, (name, aid) in enumerate(zip(names, ids), start=1):
            author_xml = ET.SubElement(authors_xml, "author")

            profile = id2profile.get(aid)
            first, middle, last = get_author_name(profile, name, name_splits)

            ET.SubElement(author_xml, "prefix").text = ""
            ET.SubElement(author_xml, "first_name").text = first
            ET.SubElement(author_xml, "middle_name").text = middle
            ET.SubElement(author_xml, "last_name").text = last
            ET.SubElement(author_xml, "suffix").text = ""

            affs_xml = ET.SubElement(author_xml, "affiliations")
            # Affiliations
            affiliations = get_current_affiliations(profile, aid)

            for seq_no, aff in enumerate(affiliations, start=1):
                aff_xml = ET.SubElement(affs_xml, "affiliation")

                ET.SubElement(aff_xml, "department").text = aff.get("department", "")
                ET.SubElement(aff_xml, "institution").text = clean_affiliation_string(aff.get("institution", ""))
                ET.SubElement(aff_xml, "city").text = aff.get("city", "")
                ET.SubElement(aff_xml, "state_province").text = aff.get("state", "")
                ET.SubElement(aff_xml, "country").text = aff.get("country", "")
                ET.SubElement(aff_xml, "sequence_no").text = str(seq_no)
            # Email: prefer bulk preferred emails, fall back to raw aid if it's an email
            email = ""
            if aid in preferred_emails:
                email = preferred_emails[aid]
            elif profile and profile.id in preferred_emails:
                email = preferred_emails[profile.id]
            elif "@" in aid:
                email = aid
            ET.SubElement(author_xml, "email_address").text = email

            ET.SubElement(author_xml, "sequence_no").text = str(i)
            # Contact author selection: OpenReview exports always use first author
            # NOTE: Unlike EasyChair (which has 3-tier priority with email validation),
            # OpenReview API does not provide "corresponding author" field, so we
            # simply designate the first author as contact author.
            ET.SubElement(author_xml, "contact_author").text = "Y" if i == 1 else "N"
            ET.SubElement(author_xml, "ACM_profile_id").text = ""
            ET.SubElement(author_xml, "ACM_client_no").text = ""
            orcid_raw = profile.content.get("orcid", "") if profile else ""
            # Extract ORCID ID from URL if present
            match = re.search(r'(\d{4}-\d{4}-\d{4}-\d{4})', orcid_raw)
            orcid = match.group(1) if match else orcid_raw
            ET.SubElement(author_xml, "ORCID").text = orcid
            ET.SubElement(author_xml, "role").text = "author"


        paper_seq += 1

    indent(root)

    tree = ET.ElementTree(root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)

    print(f"XML generated: {output_file}")

    # ========================================================================
    # VALIDATE OUTPUT
    # ========================================================================
    print("\n" + "=" * 80)
    print("VALIDATING OUTPUT")
    print("=" * 80)

    validation_passed = True
    issues = []

    # Validate exactly one contact author per paper
    for paper_elem in root.findall("paper"):
        paper_id = paper_elem.findtext("event_tracking_number", "unknown")
        authors = paper_elem.findall(".//author")
        contact_authors = [a for a in authors if a.findtext("contact_author") == "Y"]

        if len(contact_authors) == 0:
            issues.append(f"Paper {paper_id}: No contact author")
            validation_passed = False
        elif len(contact_authors) > 1:
            issues.append(f"Paper {paper_id}: Multiple contact authors ({len(contact_authors)})")
            validation_passed = False

    if validation_passed:
        print("✓ All papers have exactly one contact author")
        print("=" * 80)
    else:
        print(f"✗ Validation FAILED: {len(issues)} issue(s) found")
        for issue in issues[:10]:  # Show first 10 issues
            print(f"  {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more")
        print("=" * 80)
        print("WARNING: Output may not meet ACM requirements")

    return validation_passed


# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export OpenReview submissions to ACM/Sheridan XML format"
    )

    parser.add_argument(
        "--venue_id",
        required=True,
        help="OpenReview venue ID (e.g., ICLR.cc/2023/Conference)"
    )

    parser.add_argument(
        "--paper_type",
        default="N/A",
        choices=["Full Paper", "Short Paper", "N/A"],
        help='Type of paper ["Full Paper", "Short Paper"] (default: "N/A")'
    )

    parser.add_argument(
        "--output_file",
        default="acm_output.xml",
        help="Output XML file name (default: acm_output.xml)"
    )

    parser.add_argument(
        "--submissions",
        default=None,
        help="File with submission URLs (one per line), e.g. https://openreview.net/forum?id=JpspflvG6J"
    )

    parser.add_argument(
        "--manual_name_splits",
        default=None,
        help="TSV file with manual first/middle/last name splits for authors whose names "
             "cannot be split automatically (columns: profile, fullname, firstname, middlename, lastname)"
    )

    parser.add_argument(
        "--submission_date",
        required=True,
        help="Submission deadline for all papers, e.g. 22-JAN-2026"
    )

    parser.add_argument(
        "--approval_date",
        required=True,
        help="Notification/approval date for all papers, e.g. 02-APR-2026"
    )

    args = parser.parse_args()

    validation_passed = export_acm_xml(
        venue_id=args.venue_id,
        paper_type=args.paper_type,
        output_file=args.output_file,
        submissions_file=args.submissions,
        name_splits_file=args.manual_name_splits,
        submission_date=args.submission_date,
        approval_date=args.approval_date,
    )

    # Exit with error code if validation failed
    if not validation_passed:
        import sys
        sys.exit(1)
