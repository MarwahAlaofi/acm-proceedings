import xml.etree.ElementTree as ET

def assign_tracking_numbers(xml_input, xml_output):
    tree = ET.parse(xml_input)
    root = tree.getroot()

    # Mapping paper types to prefixes
    type_map = {
        "Full Paper": "fp",
        "Short Paper": "sp"
    }

    for paper in root.findall("paper"):
        paper_type = paper.findtext("paper_type", "").strip()

        # Only process Full/Short papers
        if paper_type in type_map:
            prefix = type_map[paper_type]

            # Get sequence_no from the paper
            seq = paper.findtext("sequence_no")

            if seq:
                # Zero-pad to 3 digits
                new_tracking = f"{prefix}{int(seq):03d}"

                tracking_elem = paper.find("event_tracking_number")
                if tracking_elem is not None:
                    tracking_elem.text = new_tracking

    # Save output
    tree.write(xml_output, encoding="utf-8", xml_declaration=True)


# Usage
assign_tracking_numbers("sigir26-short-sheridan.xml", "sigir26-short-sp-sheridan.xml")