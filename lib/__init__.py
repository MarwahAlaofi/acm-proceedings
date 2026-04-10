"""
EasyChair to ACM Converter Library
===================================

This package contains the core modules for the EasyChair to ACM converter
with Pydantic validation support.

Modules:
- easychair_models: Pydantic data models with validation
- easychair_loader: Data loading and validation
- easychair_exporters: Export to XML, TXT, and MD formats

Usage:
    from lib.easychair_loader import load_easychair_data
    from lib.easychair_exporters import export_to_xml

    export = load_easychair_data("data.xlsx")
    export_to_xml(export, "output.xml")
"""

from .easychair_models import (
    Author,
    Paper,
    Track,
    ProceedingsExport,
    ValidationIssue,
    validate_author_name_consistency,
    validate_proceedings_export,
)

from .easychair_loader import load_easychair_data

from .easychair_exporters import (
    export_to_xml,
    export_to_text,
    print_summary,
)

__all__ = [
    # Models
    "Author",
    "Paper",
    "Track",
    "ProceedingsExport",
    "ValidationIssue",
    # Validation functions
    "validate_author_name_consistency",
    "validate_proceedings_export",
    # Loader
    "load_easychair_data",
    # Exporters
    "export_to_xml",
    "export_to_text",
    "print_summary",
]

__version__ = "2.0.0"
