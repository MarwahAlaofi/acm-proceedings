# EasyChair to ACM Converter Library

This directory contains the core modules for the EasyChair to ACM converter with Pydantic validation support (v2).

## Files

### Core Modules

- **`easychair_models.py`** - Pydantic data models with validation
  - Author, Paper, Track, ProceedingsExport, ValidationIssue classes
  - Field validators for emails, names, affiliations
  - Model validators for complex rules (single contact author with 3-tier priority, etc.)
  - Consistency checking functions

- **`easychair_loader.py`** - Data loading and validation
  - Loads Excel data into validated Pydantic models
  - Smart field consolidation (fills only empty fields)
  - Automatic validation during loading
  - Tracks all validation issues

- **`easychair_exporters.py`** - Export formatting
  - Exports validated models to XML/TXT/MD formats
  - Format-specific logic isolated
  - Summary printing and statistics

- **`__init__.py`** - Package initialization
  - Exports public API
  - Version information

## Usage

```python
from lib.easychair_loader import load_easychair_data
from lib.easychair_exporters import export_to_xml, export_to_text

# Load and validate data
export = load_easychair_data("data.xlsx")

# Export to different formats
export_to_xml(export, "output.xml")
export_to_text(export, "output.txt", format_type="txt")
```

## Integration

These modules are used by:
- `easychair_to_acm_xml_v2.py` - Main script with Pydantic validation
- `tests/test_pydantic_validation.py` - Unit tests for validation

## Version

Version 2.0.0 - Enhanced with Pydantic validation and multi-affiliation support
