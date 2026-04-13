# Tests

This directory contains test scripts for the EasyChair to ACM converter.

## Files

### Unit Tests

- **`test_pydantic_validation.py`** - Unit tests for Pydantic models
  - Tests Author validation (names, emails, fields)
  - Tests Paper validation (authors, title, contact author selection)
  - Tests contact author priority system (3 tiers)
  - Tests ProceedingsExport (issue tracking, statistics)
  - Tests multi-affiliation support
  - All scenarios covered with assertions

### Integration Tests

- **`test_author_order.py`** - Integration tests for output validation
  - Validates XML output format
  - Validates TXT output format
  - Validates MD output format
  - Checks author order preservation
  - Verifies affiliation matching
  - Auto-detects format by file extension

## Running Tests

### Run Unit Tests

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

### Unit Tests Coverage
- ✅ Author model validation
- ✅ Paper model validation
- ✅ Contact author priority system (3-tier)
- ✅ Track model validation
- ✅ ProceedingsExport validation
- ✅ Multi-affiliation scenarios
- ✅ Field consolidation rules
- ✅ Validation severity levels

### Integration Tests Coverage
- ✅ XML format validation
- ✅ TXT format validation
- ✅ MD format validation
- ✅ Author order preservation
- ✅ Affiliation matching
- ✅ Country matching
- ✅ Department field handling

## Test Scenarios

### Multi-Affiliation Tests
1. Same person, different affiliations → Both preserved ✓
2. Same person, different emails → Both preserved, info notice ✓
3. Same person, empty affiliation → Filled from other paper ✓
4. Same email, different names → Warning (likely typo) ✓

### Validation Tests
1. Empty name → ValidationError ✓
2. Invalid email → ValidationError ✓
3. Paper with no authors → ValidationError ✓
4. Empty title → ValidationError ✓
5. Contact author priority 1 (corresponding with email) → Passed ✓
6. Contact author priority 2 (first author with email) → Passed ✓
7. Contact author priority 3 (first author fallback) → Passed ✓
8. Exactly one contact author per paper → Passed ✓

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
