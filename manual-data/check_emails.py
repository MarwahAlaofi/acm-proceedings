import re
import xml.etree.ElementTree as ET


# ----------------------------
# Email validation
# ----------------------------
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email):
    if not email:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


# ----------------------------
# Main validation
# ----------------------------
def validate_authors(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    issues = []
    contact_lastname_issues = []

    for paper in root.findall("paper"):
        title = paper.findtext("paper_title", default="UNKNOWN TITLE")
        tracking = paper.findtext("event_tracking_number", default="UNKNOWN ID")

        authors = paper.find("authors").findall("author")

        contact_authors = []
        all_authors = []

        for author in authors:
            first = author.findtext("first_name", "").strip()
            middle = author.findtext("middle_name", "").strip()
            last = author.findtext("last_name", "").strip()

            name = " ".join(filter(None, [first, middle, last]))
            email = author.findtext("email_address", "").strip()
            is_contact = author.findtext("contact_author", "").strip().upper() == "Y"

            author_info = {
                "name": name if name else "UNKNOWN NAME",
                "first": first,
                "last": last,
                "email": email,
                "is_contact": is_contact
            }

            all_authors.append(author_info)

            if is_contact:
                contact_authors.append(author_info)

        # ----------------------------
        # Contact author checks
        # ----------------------------
        if len(contact_authors) == 0:
            issues.append({
                "tracking": tracking,
                "title": title,
                "type": "CONTACT",
                "issue": "No contact author"
            })

        elif len(contact_authors) > 1:
            issues.append({
                "tracking": tracking,
                "title": title,
                "type": "CONTACT",
                "issue": "Multiple contact authors"
            })

        for author in contact_authors:
            # Email check
            if not is_valid_email(author["email"]):
                issues.append({
                    "tracking": tracking,
                    "title": title,
                    "type": "CONTACT",
                    "issue": f"Invalid email: '{author['email']}'",
                    "author": author["name"]
                })

            # First name check
            if not author["first"]:
                issues.append({
                    "tracking": tracking,
                    "title": title,
                    "type": "CONTACT",
                    "issue": "Missing first name",
                    "author": author["name"]
                })

            # Last name check (general)
            if not author["last"]:
                issues.append({
                    "tracking": tracking,
                    "title": title,
                    "type": "CONTACT",
                    "issue": "Missing last name",
                    "author": author["name"]
                })

                # Special list (clean reporting for you)
                contact_lastname_issues.append({
                    "tracking": tracking,
                    "title": title,
                    "author": author["name"]
                })

        # ----------------------------
        # All authors checks
        # ----------------------------
        for author in all_authors:
            # Email check
            if not is_valid_email(author["email"]):
                issues.append({
                    "tracking": tracking,
                    "title": title,
                    "type": "AUTHOR",
                    "issue": f"Invalid email: '{author['email']}'",
                    "author": author["name"]
                })

            # First name check
            if not author["first"]:
                issues.append({
                    "tracking": tracking,
                    "title": title,
                    "type": "AUTHOR",
                    "issue": "Missing first name",
                    "author": author["name"]
                })

            # Last name check
            if not author["last"]:
                issues.append({
                    "tracking": tracking,
                    "title": title,
                    "type": "AUTHOR",
                    "issue": "Missing last name",
                    "author": author["name"]
                })

    return issues, contact_lastname_issues


# ----------------------------
# Reporting
# ----------------------------
def print_report(issues, contact_lastname_issues):
    if not issues:
        print("All authors have valid emails and names ✅")
    else:
        print(f"Found {len(issues)} issue(s):\n")

        for i, issue in enumerate(issues, 1):
            print(f"{i}. [{issue['tracking']}] {issue['title']}")
            print(f"   Type: {issue['type']}")
            print(f"   Issue: {issue['issue']}")
            if "author" in issue:
                print(f"   Author: {issue['author']}")
            print()

    # ----------------------------
    # Clean summary for contact authors (important)
    # ----------------------------
    print("\n=== Contact Authors Missing Last Names ===\n")

    if not contact_lastname_issues:
        print("All contact authors have last names ✅")
    else:
        for item in contact_lastname_issues:
            print(f"[{item['tracking']}] {item['title']}")
            print(f"   Author: {item['author']}\n")

# ----------------------------
# Usage
# ----------------------------
if __name__ == "__main__":
    xml_file = "sigir26-short-sheridan.xml"  # update path

    issues, contact_lastname_issues = validate_authors(xml_file)
    print_report(issues, contact_lastname_issues)