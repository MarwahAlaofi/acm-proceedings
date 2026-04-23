import xml.etree.ElementTree as ET

def compare_tracking_numbers(file1, file2, output_file):
    tree1 = ET.parse(file1)
    tree2 = ET.parse(file2)

    papers1 = tree1.findall(".//paper")
    papers2 = tree2.findall(".//paper")

    with open(output_file, "w", encoding="utf-8") as out:
        for p1, p2 in zip(papers1, papers2):
            t1 = p1.findtext("event_tracking_number")
            t2 = p2.findtext("event_tracking_number")

            if t1 != t2:
                title = p1.findtext("paper_title")
                out.write(f"{title}\n")
                out.write(f"  OLD: {t1}\n")
                out.write(f"  NEW: {t2}\n\n")


# Usage
compare_tracking_numbers(
    "sigir26-short-sheridan.xml",
    "sigir26-short-sp-sheridan.xml",
    "tracking_diff.txt"
)