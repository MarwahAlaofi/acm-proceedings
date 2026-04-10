# EasyChair to ACM Converter - Validation System

## Overview

The EasyChair to ACM converter now includes comprehensive runtime validation using **Pydantic models**. This ensures data integrity throughout the conversion process and catches issues early with clear error messages.

## Key Improvements

### 1. **Runtime Validation**
- Data is validated as soon as it's loaded from Excel
- Invalid data is caught immediately with descriptive error messages
- Type safety ensures correct data types throughout processing

### 2. **Structured Data Models**
- `Author`: Individual author with validation for names, emails, affiliations
- `Paper`: Conference paper with author list, title, and metadata
- `Track`: Collection of papers in a section
- `ProceedingsExport`: Complete export with statistics and validation issues

### 3. **Comprehensive Issue Tracking**
- All validation issues are tracked with severity levels (error, warning, info)
- Issues are categorized (e.g., "missing_affiliation", "email_consistency")
- Detailed reporting in logs with paper IDs and context

### 4. **Data Quality Checks**
- Empty names detection
- Invalid email format detection
- Missing affiliations tracking
- Author name consistency (same email with different names)
- Email consistency (same name with different emails)
- Author order validation

## Files

### Core Modules

- **`easychair_models.py`**: Pydantic models for data validation
- **`easychair_loader.py`**: Loads Excel data into validated models
- **`easychair_exporters.py`**: Exports validated models to XML/TXT/MD
- **`easychair_to_acm_xml_v2.py`**: Main script using Pydantic validation

### Legacy Files

- **`easychair_to_acm_xml.py`**: Original script (still functional)

### Test Files

- **`test_pydantic_validation.py`**: Unit tests for Pydantic models
- **`test_author_order.py`**: Integration tests for output validation

## Installation

```bash
# Install required dependencies
pip install -r requirements.txt
```

Requirements:
- pandas >= 2.0.0
- openpyxl >= 3.0.0
- pydantic >= 2.0.0
- email-validator >= 2.0.0

## Usage

### Basic Usage (Same as Before)

```bash
# Export to XML
python easychair_to_acm_xml_v2.py \
    --input export.xlsx \
    --proceeding_id "2026-SIGIR" \
    --output sigir2026.xml

# Export to text
python easychair_to_acm_xml_v2.py \
    --input export.xlsx \
    --format txt \
    --output papers.txt

# Export to markdown
python easychair_to_acm_xml_v2.py \
    --input export.xlsx \
    --format md \
    --output papers.md
```

### New Options

```bash
# Skip validation test after export
python easychair_to_acm_xml_v2.py \
    --input export.xlsx \
    --format txt \
    --output papers.txt \
    --no-validation
```

## Validation Features

### 1. Author Validation

**Validates:**
- First name and last name are not empty
- Email format is valid (if provided)
- Whitespace is stripped from all fields

**Example:**
```python
# Valid
author = Author(
    first_name="John",
    last_name="Doe",
    email="john.doe@example.com",
    affiliation="University of Example"
)

# Invalid - will raise ValidationError
author = Author(
    first_name="",  # ✗ Empty name
    last_name="Doe",
    email="not-an-email"  # ✗ Invalid format
)
```

### 2. Paper Validation

**Validates:**
- Paper has at least one author
- Title is not empty
- At least one corresponding author exists (auto-sets first author if needed)

**Example:**
```python
# Valid
paper = Paper(
    submission_id=123,
    title="Great Paper",
    authors=[author1, author2],
    track_name="Full Papers",
    section_name="Full Research Paper",
    paper_type="Full Research Paper"
)

# Invalid - will raise ValidationError
paper = Paper(
    submission_id=124,
    title="",  # ✗ Empty title
    authors=[],  # ✗ No authors
    ...
)
```

### 3. Data Quality Checks

The system automatically checks for:

- **Name Consistency**: Same email with different names
  ```
  ⚠ Same email 'john@example.com' used with different names: 'John Doe', 'J. Doe'
  ```

- **Email Consistency**: Same name with different emails
  ```
  ⚠ Same name 'John Doe' used with different emails: 'john@uni1.edu', 'john@uni2.edu'
  ```

- **Missing Data**: Authors without affiliations or emails
  ```
  ⚠ Paper #123 has at least one author with missing affiliation
  ```

## Testing

### Run Unit Tests

Test the Pydantic models directly:

```bash
python test_pydantic_validation.py
```

This will:
- Test Author validation (name, email, fields)
- Test Paper validation (authors, title, corresponding author)
- Test ProceedingsExport (issue tracking, statistics)

### Run Integration Tests

Test the complete conversion and validation:

```bash
# The validation test runs automatically after export
python easychair_to_acm_xml_v2.py --input export.xlsx --output test.xml

# Or run manually
python test_author_order.py export.xlsx test.xml
```

## Log Files

Each export creates a detailed log file: `<output_file>.log`

**Log Structure:**
1. **Loading Phase**: Excel loading, filtering, cleaning
2. **Consolidation Phase**: Duplicate author handling
3. **Validation Phase**: All validation checks
4. **Export Phase**: File generation
5. **Summary**: Statistics, track mapping, data quality issues
6. **Validation Test**: Author order verification

**Log Levels:**
- **DEBUG**: Detailed corrections, field updates (file only)
- **INFO**: Progress, statistics, successful operations (console + file)
- **WARNING**: Data quality issues, potential problems (console + file)
- **ERROR**: Critical errors, failed validations (console + file)

## Programmatic Usage

You can also use the validation system programmatically:

```python
from easychair_loader import load_easychair_data
from easychair_exporters import export_to_xml
from easychair_models import validate_proceedings_export

# Load and validate data
export = load_easychair_data("export.xlsx")

# Run additional validation
export = validate_proceedings_export(export)

# Check for issues
if export.has_errors:
    print(f"Found {export.error_count} errors")
    for issue in export.validation_issues:
        if issue.severity == "error":
            print(issue)

# Export if valid
if not export.has_errors:
    export_to_xml(export, "output.xml")
```

## Migration from v1

Both versions work side-by-side:

- **v1**: `easychair_to_acm_xml.py` (original, no Pydantic)
- **v2**: `easychair_to_acm_xml_v2.py` (new, with Pydantic)

Command-line interface is identical. To migrate:

1. Install new dependencies: `pip install -r requirements.txt`
2. Replace `easychair_to_acm_xml.py` with `easychair_to_acm_xml_v2.py` in your commands
3. Review validation warnings in the log files

## Benefits

### For Users
- **Early Error Detection**: Catch data issues during loading, not after export
- **Clear Error Messages**: Know exactly what's wrong and where
- **Better Data Quality**: Automatic consistency checks
- **Comprehensive Logs**: Detailed audit trail of all operations

### For Developers
- **Type Safety**: Pydantic ensures correct types
- **Easier Testing**: Models can be tested independently
- **Maintainability**: Clear data structures and validation rules
- **Extensibility**: Easy to add new validation rules

## Troubleshooting

### ValidationError on Load

If you see a ValidationError when loading data:

```
ValidationError: 1 validation error for Author
email
  Invalid email format: not-an-email
```

**Solution**: Check the Excel file and fix the invalid data, or the email validation in `easychair_models.py` if the format is actually valid.

### Missing Dependencies

```
ModuleNotFoundError: No module named 'pydantic'
```

**Solution**: Install dependencies: `pip install -r requirements.txt`

### Performance

The Pydantic validation adds minimal overhead (typically < 1 second for hundreds of papers). If you need maximum speed and have pre-validated data, you can use the v1 script without Pydantic.

## Contributing

When adding new validation rules:

1. Add validation logic to `easychair_models.py` (field validators or model validators)
2. Add corresponding tests to `test_pydantic_validation.py`
3. Update this README with the new validation behavior

## Support

For issues or questions:
- Check the log file for detailed error messages
- Run `test_pydantic_validation.py` to verify the installation
- Review validation issues in the export summary
