# Overview

This project is to host scripts used to prepare an ACM proceedings from OpenReview following this XML format: https://cms.acm.org/paperLoad/paperLoadSAMPLE.xml. So far, it has the following (still under testing):

1. Export accepted papers from OpenReview into ACM/Sheridan XML format  
2. Convert the XML into an MS Word document listing titles and authors  


---

# Files

- `export_to_acm_xml.py`  
  Exports submissions from OpenReview into ACM-compatible XML  

- `acm_xml_to_ms_word.py`  
  Reads the XML and generates a formatted `.docx` file  

---

# Requirements

Install dependencies:

```bash
pip install openreview-py==1.30.0 python-docx python-dotenv
```

Create a `.env` file with your OpenReview credentials:

```
OPENREVIEW_USERNAME=your_email
OPENREVIEW_PASSWORD=your_password
```

---

# Export XML from OpenReview

Run the script with command-line arguments. Example to export ICLR'23 accepted papers:

```bash
python export_to_acm_xml.py \
  --venue_id "ICLR.cc/2023/Conference" \
  --paper_type "Full Paper" \
  --output_file "ICLR_acm_comp_output.xml"
```

Parameters:

- `--venue_id` (required): OpenReview venue ID  
- `--paper_type` (optional): "Full Paper" or "Short Paper" (default: N/A)  
- `--output_file` (optional): Output XML file (default: acm_output.xml)  

---

# Convert XML to Word

Run the script with command-line arguments. Example to convert the ICLR papers into an MS Word listing:

```bash
python acm_xml_to_ms_word.py \
  --input_xml "ICLR_acm_comp_output.xml" \
  --output_docx "ICLR_papers_list.docx"
```

Parameters:

- `--input_xml` (required): Path to input XML file  
- `--output_docx` (optional): Output Word file (default: papers_list.docx)  

# Notes and Assumptions

- **Author name parsing**
  - Author names are provided by OpenReview as a single string.
  - Names are split on white space:
    - First token → first name  
    - Last token → last name  
    - Middle tokens → middle name(s)  
  - This may not always be accurate for all naming conventions.

- **Author order**
  - The order of authors is preserved as provided by OpenReview.
  - The first author is assumed to be the **contact author**.

- **Affiliations**
  - Affiliations are extracted from OpenReview profiles (`profile.content["history"]`). 
  - Current affiliations are entries without an endDate (may not be accurate if not current but not filled by users) 
  - If no current affiliation is found, the most recent entry is used as a fallback.

- **Paper Submission and Decision Dates**
  - The **submission date** is taken from `tcdate` (true creation date), which reflects the original submission date.
  - The **approval date** is set to the last modification date (tmdate) as a proxy for the approval date. There might be a better more accurate way for this if it is important.