# Paper-to-Author Matching in easychair_to_acm_xml.py

## Data Structure

### Submissions Sheet
```
# | Track # | Track name | Title | Authors | Submitted | ...
7 | 8       | SIGIR 2026 Workshop Proposals | ... | "Philipp Christmann, Roxana Petcu, Sneha Singhania, Mohammad Aliannejadi, Marcel Gohsen and Svitlana Vakulenko" | ...
```

### Authors Sheet
```
Submission # | First name | Last name | Email | Country | Affiliation | Person # | Corresponding?
7            | Philipp    | Christmann | ... | Germany | CISPA... | 16 | ✔
7            | Roxana     | Petcu | ... | Netherlands | ... | 17 | ✔
7            | Sneha      | Singhania | ... | Germany | ... | 18 | ✔
7            | Mohammad   | Aliannejadi | ... | Netherlands | ... | 8 | ✔
7            | Marcel     | Gohsen | ... | Germany | ... | 19 | ✔
7            | Svitlana   | Vakulenko | ... | Austria | ... | 20 | ✔
```

## Matching Process

### Step 1: Filter Papers (Line 550-552)
```python
for _, submission in submissions_df.iterrows():
    submission_id = submission["#"]  # Get paper ID (e.g., 7)
```

### Step 2: Get Correct Author Order (Lines 554-564)
Parse the `Authors` column from Submissions sheet:
```python
authors_str = submission.get("Authors", "")
# Raw: "Philipp Christmann, Roxana Petcu, ..., Marcel Gohsen and Svitlana Vakulenko"

authors_str = " ".join(authors_str.split())  # Clean line breaks
# Clean: "Philipp Christmann, Roxana Petcu, ..., Marcel Gohsen and Svitlana Vakulenko"

authors_str = authors_str.replace(" and ", ", ")  # Normalize separators
# Normalized: "Philipp Christmann, Roxana Petcu, ..., Marcel Gohsen, Svitlana Vakulenko"

correct_order = [name.strip() for name in authors_str.split(",") if name.strip()]
# Result: ["Philipp Christmann", "Roxana Petcu", "Sneha Singhania", 
#          "Mohammad Aliannejadi", "Marcel Gohsen", "Svitlana Vakulenko"]
```

### Step 3: Match Papers to Authors (Lines 567-569)
```python
paper_authors_unsorted = authors_df[
    authors_df["Submission #"] == submission_id
].copy()
```

**Matching Key:** `Submission #` column

- **Submissions sheet:** Has column `#` (paper ID)
- **Authors sheet:** Has column `Submission #` (references paper ID)
- **Match:** `authors_df["Submission #"] == submission["#"]`

Example for Paper #7:
```
AUTHORS SHEET ROWS WHERE Submission # = 7:
Row 1: Submission #=7, Person #=16, Name="Philipp Christmann"
Row 2: Submission #=7, Person #=17, Name="Roxana Petcu"
Row 3: Submission #=7, Person #=18, Name="Sneha Singhania"
Row 4: Submission #=7, Person #=8,  Name="Mohammad Aliannejadi"  ← Person # out of order!
Row 5: Submission #=7, Person #=19, Name="Marcel Gohsen"
Row 6: Submission #=7, Person #=20, Name="Svitlana Vakulenko"
```

### Step 4: Determine Correct Sequence (Lines 571-603)
Build a mapping from author names to their correct position:
```python
name_to_position = {}
for idx, name in enumerate(correct_order):
    name_to_position[name.lower()] = idx

# Result:
# {
#   "philipp christmann": 0,
#   "roxana petcu": 1,
#   "sneha singhania": 2,
#   "mohammad aliannejadi": 3,
#   "marcel gohsen": 4,
#   "svitlana vakulenko": 5
# }
```

For each author row, assign correct sequence:
```python
def get_author_sequence(row):
    full_name = f"{row['First name']} {row['Last name']}".lower()
    
    # Try exact match
    if full_name in name_to_position:
        return name_to_position[full_name]  # Returns 0-5 for Paper #7
    
    # Try partial match (for middle initials, etc.)
    for correct_name, pos in name_to_position.items():
        if full_name in correct_name or correct_name in full_name:
            return pos
    
    # Fallback if name not found (data quality issue)
    return row["Person #"] + 1000
```

### Step 5: Sort Authors by Correct Sequence (Lines 605-608)
```python
paper_authors_unsorted["_sequence"] = paper_authors_unsorted.apply(
    get_author_sequence, axis=1
)
paper_authors = paper_authors_unsorted.sort_values("_sequence")
```

Result for Paper #7:
```
Before sorting (by Person #):
Person #8:  Mohammad Aliannejadi → _sequence=3
Person #16: Philipp Christmann   → _sequence=0
Person #17: Roxana Petcu         → _sequence=1
Person #18: Sneha Singhania      → _sequence=2
Person #19: Marcel Gohsen        → _sequence=4
Person #20: Svitlana Vakulenko   → _sequence=5

After sorting (by _sequence):
Person #16: Philipp Christmann   → _sequence=0 ✓
Person #17: Roxana Petcu         → _sequence=1 ✓
Person #18: Sneha Singhania      → _sequence=2 ✓
Person #8:  Mohammad Aliannejadi → _sequence=3 ✓
Person #19: Marcel Gohsen        → _sequence=4 ✓
Person #20: Svitlana Vakulenko   → _sequence=5 ✓
```

## Summary

**Matching Mechanism:**
- **Primary Key:** `Submission #` (Authors sheet) = `#` (Submissions sheet)
- **Sort Key:** Author names parsed from `Submissions.Authors` column

**Why Two Steps?**
1. **Matching:** EasyChair stores detailed author info (email, affiliation, country) in separate Authors sheet
2. **Ordering:** EasyChair's `Person #` doesn't reflect correct order; must use `Submissions.Authors` text

**Data Quality:**
- If author name in Authors sheet doesn't match Submissions.Authors → Warning logged, fallback to Person # + 1000
- This puts unmatched authors at end and flags the data issue
