# Tests

This directory contains test scripts for the EasyChair to ACM converter.

## Files

### Unit Tests

- **`test_pydantic_validation.py`** - Unit tests for Pydantic models (EasyChair export)
  - Tests Author validation (names, emails, fields)
  - Tests Paper validation (authors, title, contact author selection)
  - Tests contact author priority system (3 tiers)
  - Tests ProceedingsExport (issue tracking, statistics)
  - Tests multi-affiliation support
  - All scenarios covered with assertions

- **`test_validation.py`** - Unit tests for validation package (XML validation/analysis)
  - Tests author identity merging (email match → name match → no merge)
  - Tests author field completion (fills missing info across papers)
  - Tests affiliation similarity detection (three-tier matching)
  - Tests email domain normalization (student.X → X)
  - Tests public domain exclusion (gmail.com, acm.org, etc.)
  - Tests false positive prevention (distinctive tokens)
  - Tests integration with statistics generation
  - 20 test cases covering documented behavior
  - Uses unittest framework with detailed assertions

- **`test_author_merging_simple.py`** - Simple standalone test for author merging
  - Quick verification of author identity merging logic
  - Colored output for easy visual inspection
  - Tests all key scenarios (email match, name match, no merge)
  - Useful for quick verification during development

- **`test_affiliation_normalization.py`** - Tests affiliation string normalization
  - Tests trailing punctuation removal (periods, commas, etc.)
  - Tests leading punctuation removal
  - Tests whitespace handling
  - Ensures validation uses same normalization as export

### Integration Tests

- **`test_author_order.py`** - Integration tests for output validation
  - Validates XML output format
  - Validates TXT output format
  - Validates MD output format
  - Checks author order preservation
  - Verifies affiliation matching (normalized comparison)
  - Auto-detects format by file extension
  - Uses same normalization as export (strips trailing punctuation)

## Running Tests

### Run Unit Tests

**Pydantic validation tests (EasyChair export):**
```bash
# From project root directory
python tests/test_pydantic_validation.py
```

**Expected output:**
```
================================================================================
TEST RESULTS SUMMARY
================================================================================
  Author Validation: ✓ PASSED
  Paper Validation: ✓ PASSED
  ProceedingsExport Validation: ✓ PASSED
  Different Affiliations Across Papers: ✓ PASSED
================================================================================
🎉 All validation tests passed!
```

**Validation package tests (XML validation/analysis):**
```bash
# Comprehensive test suite (unittest)
python tests/test_validation.py

# Simple standalone test (quick verification)
python tests/test_author_merging_simple.py
```

**Expected output (test_validation.py):**
```
test_email_match_case_insensitive ... ok
test_same_name_different_emails_not_merged ... ok
test_same_name_with_missing_email_merged ... ok
test_complete_missing_country ... ok
test_complete_missing_affiliation ... ok
test_email_domain_matching ... ok
test_public_domain_excluded ... ok
test_false_positive_prevention ... ok
... (20 tests total)

----------------------------------------------------------------------
Ran 20 tests in 0.002s

OK
```

**Expected output (test_author_merging_simple.py):**
```
================================================================================
AUTHOR IDENTITY MERGING TEST
================================================================================
Total author entries: 10
Unique canonical authors: 6

✓ John Smith merging: 3 identities → 1 canonical (expected 1)
✓ Jane Doe NOT merged: 2 identities → 2 canonicals (expected 2)
✓ Alice Johnson merging: 2 identities → 1 canonical (expected 1)
✓ Bob Brown merging: 2 identities → 1 canonical (expected 1)
✓ Charlie Davis unique: 1 identity → 1 canonical (expected 1)

ALL TESTS PASSED ✓
```

**Affiliation normalization tests:**
```bash
python tests/test_affiliation_normalization.py
```

**Expected output:**
```
================================================================================
✅ All affiliation normalization tests passed!
================================================================================
```

### Run Integration Tests

```bash
# Test XML output
python tests/test_author_order.py data.xlsx output.xml

# Test TXT output
python tests/test_author_order.py data.xlsx output.txt

# Test MD output
python tests/test_author_order.py data.xlsx output.md
```

**Expected output:**
```
================================================================================
✅ VALIDATION PASSED: All papers have correct author order and affiliations
================================================================================
```

## Test Coverage

### Unit Tests Coverage (Pydantic/EasyChair)
- ✅ Author model validation
- ✅ Paper model validation
- ✅ Contact author priority system (3-tier)
- ✅ Track model validation
- ✅ ProceedingsExport validation
- ✅ Multi-affiliation scenarios
- ✅ Field consolidation rules
- ✅ Validation severity levels

### Unit Tests Coverage (Validation Package)
- ✅ Author identity merging
  - ✅ Email matching (case-insensitive)
  - ✅ Name matching with missing email
  - ✅ Same name + different emails NOT merged
  - ✅ Deterministic canonical selection
- ✅ Author field completion
  - ✅ Missing country filled from other papers
  - ✅ Missing affiliation added from other papers
  - ✅ Existing values never overwritten
  - ✅ Multiple affiliations preserved
- ✅ Affiliation similarity detection
  - ✅ Email domain matching (primary signal)
  - ✅ Subdomain normalization (student.X → X)
  - ✅ Public domain exclusion (gmail, acm.org, etc.)
  - ✅ String similarity + distinctive tokens
  - ✅ False positive prevention (Dalian ≠ Delft)
- ✅ Integration with statistics generation

### Integration Tests Coverage
- ✅ XML format validation
- ✅ TXT format validation
- ✅ MD format validation
- ✅ Author order preservation
- ✅ Affiliation matching (normalized comparison)
- ✅ Affiliation normalization (strips trailing punctuation)
- ✅ Country matching
- ✅ Department field handling

## Test Scenarios

### Multi-Affiliation Tests (EasyChair Export)
1. Same person, different affiliations → Both preserved ✓
2. Same person, different emails → Both preserved, info notice ✓
3. Same person, empty affiliation → Filled from other paper ✓
4. Same email, different names → Warning (likely typo) ✓

### Validation Tests (Pydantic Models)
1. Empty name → ValidationError ✓
2. Invalid email → ValidationError ✓
3. Paper with no authors → ValidationError ✓
4. Empty title → ValidationError ✓
5. Contact author priority 1 (corresponding with email) → Passed ✓
6. Contact author priority 2 (first author with email) → Passed ✓
7. Contact author priority 3 (first author fallback) → Passed ✓
8. Exactly one contact author per paper → Passed ✓

### Author Identity Merging Tests (Validation Package)
1. Same email (case-insensitive) → Merged ✓
2. Same email + name variations → Merged ✓
3. Same name + missing email → Merged ✓
4. Same name + both missing email → Merged ✓
5. Same name + different emails → NOT merged ✓
6. Canonical selection is deterministic → Passed ✓
7. Empty string treated as missing email → Passed ✓
8. Complex scenario (multiple merge types) → Passed ✓

### Affiliation Similarity Tests (Validation Package)
1. Same email domain → Merged ✓
2. Subdomain normalization (student.X → X) → Merged ✓
3. Public domains excluded (gmail, acm.org) → NOT merged ✓
4. String similarity + shared tokens → Merged ✓
5. Similar names + different tokens (Dalian vs Delft) → NOT merged ✓
6. Capitalization variations (JD.com vs JD.COM) → Merged ✓

### Field Completion Tests (Validation Package)
1. Missing country filled from other papers → Filled ✓
2. Missing affiliation added from other papers → Filled ✓
3. Existing values never overwritten → Preserved ✓
4. Multiple affiliations handled correctly → Preserved ✓

## Adding New Tests

To add a new test:

1. Add test function to appropriate file
2. Follow naming convention: `test_description()`
3. Include docstring explaining what is tested
4. Add assertions with clear error messages
5. Update this README with new coverage

## See Also

- Main README: [`../readme.md`](../readme.md)
- Library documentation: [`../lib/README.md`](../lib/README.md)
- Detailed docs: [`../docs/README.md`](../docs/README.md)
