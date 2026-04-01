import openreview
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv
import os
import argparse

load_dotenv()

# ----------------------------
# format/data helpers
# ----------------------------
def format_date(timestamp):
    if not timestamp:
        return ""
    return datetime.utcfromtimestamp(timestamp / 1000).strftime("%d-%b-%Y").upper()

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

def get_submission_date(submission):
    timestamp = getattr(submission, "tcdate", None) or getattr(submission, "cdate", None)
    return format_date(timestamp)


# ----------------------------
# OpenReview stores author names as a single string.
# To match the ACM XML schema, we split the name into
# first, middle, and last components based on whitespace.
#
# Rules:
# - First token → first name
# - Last token → last name
# - Any tokens in between → middle name(s)
# ----------------------------
def split_name(full_name):
    parts = full_name.strip().split()

    if len(parts) == 0:
        return "", "", ""

    if len(parts) == 1:
        return parts[0], "", ""

    if len(parts) == 2:
        return parts[0], "", parts[1]

    first = parts[0]
    last = parts[-1]
    middle = " ".join(parts[1:-1])

    return first, middle, last

# ----------------------------
# Safe helpers
# ----------------------------
def get_preferred_email(profile):
    try:
        return profile.get_preferred_email()
    except:
        return ""

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

        # Filter for current affiliations (no endDate)
        current_history = [h for h in history if not h.get("endDate")]

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
                # Map by Tilde ID
                id2profile[p.id] = p
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
def export_acm_xml(venue_id, paper_type="Full Paper", output_file="acm_output.xml"):

    if paper_type not in ["Full Paper", "Short Paper"]:
        raise ValueError("paper_type must be 'Full Paper' or 'Short Paper'")

    client = openreview.api.OpenReviewClient(
        baseurl="https://api2.openreview.net",
        username=os.getenv("OPENREVIEW_USERNAME"),
        password=os.getenv("OPENREVIEW_PASSWORD")
    )

    print("Fetching submissions...")
    submissions = client.get_all_notes(content={"venueid": venue_id})
    print(f"Found {len(submissions)} submissions")

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
        ET.SubElement(paper, "art_submission_date").text = get_submission_date(s)
        # last modified which is an acceptable proxy for approval date
        approval_ts = getattr(s, "tmdate", None) or getattr(s, "cdate", None)
        ET.SubElement(paper, "art_approval_date").text = format_date(approval_ts)
        ET.SubElement(paper, "paper_title").text = s.content.get("title", {}).get("value", "")
        ET.SubElement(paper, "event_tracking_number").text = s.id
        ET.SubElement(paper, "published_article_number").text = ""
        ET.SubElement(paper, "start_page").text = ""
        ET.SubElement(paper, "end_page").text = ""
        authors_xml = ET.SubElement(paper, "authors")

        ids = s.content.get("authorids", {}).get("value", [])
        names = s.content.get("authors", {}).get("value", [])

        for i, (name, aid) in enumerate(zip(names, ids), start=1):
            author_xml = ET.SubElement(authors_xml, "author")

            first, middle, last = split_name(name)

            ET.SubElement(author_xml, "prefix").text = ""
            ET.SubElement(author_xml, "first_name").text = first
            ET.SubElement(author_xml, "middle_name").text = middle
            ET.SubElement(author_xml, "last_name").text = last
            ET.SubElement(author_xml, "suffix").text = ""

            profile = id2profile.get(aid)

            affs_xml = ET.SubElement(author_xml, "affiliations")
            # Affiliations
            affiliations = get_current_affiliations(profile, aid)

            for seq_no, aff in enumerate(affiliations, start=1):
                aff_xml = ET.SubElement(affs_xml, "affiliation")

                ET.SubElement(aff_xml, "department").text = aff.get("department", "")
                ET.SubElement(aff_xml, "institution").text = aff.get("institution", "")
                ET.SubElement(aff_xml, "city").text = aff.get("city", "")
                ET.SubElement(aff_xml, "state_province").text = aff.get("state", "")
                ET.SubElement(aff_xml, "country").text = aff.get("country", "")
                ET.SubElement(aff_xml, "sequence_no").text = str(seq_no)
            # Email
            email = get_preferred_email(profile) if profile else (aid if "@" in aid else "")
            ET.SubElement(author_xml, "email_address").text = email

            ET.SubElement(author_xml, "sequence_no").text = str(i)
            # assuming contact author is 1st author
            ET.SubElement(author_xml, "contact_author").text = "Y" if i == 1 else "N"
            ET.SubElement(author_xml, "ACM_profile_id").text = ""
            ET.SubElement(author_xml, "ACM_client_no").text = ""
            orcid = profile.content.get("orcid", "") if profile else ""
            ET.SubElement(author_xml, "ORCID").text = orcid
            ET.SubElement(author_xml, "role").text = "author"

        ET.SubElement(paper, "section").text = ""
        ET.SubElement(paper, "sequence_no").text = str(paper_seq)

        paper_seq += 1

    indent(root)

    tree = ET.ElementTree(root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)

    print(f"XML generated: {output_file}")


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

    args = parser.parse_args()

    export_acm_xml(
        venue_id=args.venue_id,
        paper_type=args.paper_type,
        output_file=args.output_file
    )
