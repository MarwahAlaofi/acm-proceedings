"""
EasyChair to ACM/Sheridan XML/Text/Markdown Converter (v2 with Pydantic Validation)
====================================================================================

This script converts EasyChair conference export data (Excel format) into
ACM/Sheridan XML format for proceedings submission, or into text/markdown
format for human-readable listings.

This version uses Pydantic models for runtime validation, ensuring data
integrity throughout the process.

Features:
- Runtime validation with Pydantic models
- Loads EasyChair Submissions and Authors sheets
- Filters accepted papers only
- Consolidates duplicate author entries and fills missing fields
- Detects potential typos (same email with different names, etc.)
- Cleans text fields (removes line feeds, extra whitespace)
- Maps EasyChair track names to ACM section names
- Auto-detects conference name from track data
- Generates detailed statistics and quality warnings
- Exports to XML, plain text, or markdown format

Requirements:
- pandas library for data processing
- pydantic library for data validation
- EasyChair Excel export with 'Submissions' and 'Authors' sheets

Usage:
    # XML format (for ACM submission)
    python easychair_to_acm_xml_v2.py \
        --input "path/to/easychair_export.xlsx" \
        --proceeding_id "2026-SIGIR" \
        --output "sigir2026.xml"

    # Text format (human-readable)
    python easychair_to_acm_xml_v2.py \
        --input "path/to/easychair_export.xlsx" \
        --format txt \
        --output "papers.txt"

    # Markdown format (human-readable)
    python easychair_to_acm_xml_v2.py \
        --input "path/to/easychair_export.xlsx" \
        --format md \
        --output "papers.md"

Author: Generated for ACM proceedings preparation
"""

import argparse
import logging
import subprocess
from pathlib import Path

from lib.easychair_loader import load_easychair_data
from lib.easychair_exporters import export_to_xml, export_to_text, print_summary


def setup_logging(log_file: str) -> logging.Logger:
    """
    Set up logging to both console and file.

    Console: INFO level and above
    File: All levels including DEBUG

    Args:
        log_file: Path to log file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("easychair_to_acm")
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    if logger.handlers:
        logger.handlers.clear()

    # Console handler - INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)

    # File handler - DEBUG and above
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def run_validation_test(
    excel_file: str,
    output_file: str,
    logger: logging.Logger
) -> None:
    """
    Run author order validation test.

    Args:
        excel_file: Path to Excel input
        output_file: Path to output file
        logger: Logger instance
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("RUNNING AUTHOR ORDER VALIDATION TEST")
    logger.info("=" * 80)

    try:
        test_script = "test_author_order.py"
        result = subprocess.run(
            ["python", test_script, excel_file, output_file],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.stdout:
            for line in result.stdout.splitlines():
                logger.info(line)

        if result.returncode == 0:
            logger.info("")
            logger.info("✓ Author order validation test PASSED")
        else:
            logger.error("")
            logger.error("✗ Author order validation test FAILED")
            logger.error("Please review the issues above and fix the data if needed")
            if result.stderr:
                logger.error("Test error output:")
                for line in result.stderr.splitlines():
                    logger.error(f"  {line}")

    except FileNotFoundError:
        logger.warning(f"Warning: Test script '{test_script}' not found - skipping validation")
    except subprocess.TimeoutExpired:
        logger.error("Error: Validation test timed out after 5 minutes")
    except Exception as e:
        logger.warning(f"Warning: Could not run validation test: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert EasyChair export to ACM/Sheridan XML, text, or markdown format (with Pydantic validation)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all tracks to XML with auto-detected paper types
  python easychair_to_acm_xml_v2.py --input export.xlsx --proceeding_id "2026-SIGIR" --output all.xml

  # Export to text format
  python easychair_to_acm_xml_v2.py --input export.xlsx --format txt --output papers.txt

  # Export to markdown format
  python easychair_to_acm_xml_v2.py --input export.xlsx --format md --output papers.md

  # Export only demo papers to XML
  python easychair_to_acm_xml_v2.py --input export.xlsx --proceeding_id "2026-SIGIR-Demo" \\
    --track "SIGIR 2026 Demo Papers Track" --output demos.xml

Note: Track name must be EXACT match (case-sensitive) from EasyChair's "Track name" column.
        """,
    )

    parser.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Path to EasyChair Excel export file (must contain 'Submissions' and 'Authors' sheets)",
    )

    parser.add_argument(
        "--format",
        choices=["xml", "txt", "md"],
        default="xml",
        help="Output format: xml (ACM/Sheridan XML), txt (plain text), or md (markdown). Default: xml",
    )

    parser.add_argument(
        "--proceeding_id",
        metavar="ID",
        help="ACM proceeding ID (e.g., '2026-SIGIR', '2018-1234.1234'). "
        "Required for XML format. Use different IDs for different tracks if submitting separately.",
    )

    parser.add_argument(
        "--source",
        default="EasyChair",
        help="Source system name for XML metadata (default: 'EasyChair'). Only used for XML format.",
    )

    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Output file name (default: 'acm_output.xml', 'acm_output.txt', or 'acm_output.md' based on format)",
    )

    parser.add_argument(
        "--track",
        default=None,
        metavar="NAME",
        help="Export ONLY papers from this specific track (all other tracks are excluded). "
        "Track name must be EXACT match (case-sensitive) from EasyChair's 'Track name' column. "
        "Examples: 'SIGIR 2026 Demo Papers Track', 'SIGIR 2026 Full Papers Track'.",
    )

    parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Skip running the validation test after export",
    )

    args = parser.parse_args()

    # Set default output filename based on format
    if args.output is None:
        if args.format == "xml":
            args.output = "acm_output.xml"
        elif args.format == "txt":
            args.output = "acm_output.txt"
        else:  # md
            args.output = "acm_output.md"

    # Validate proceeding_id for XML format
    if args.format == "xml" and args.proceeding_id is None:
        parser.error("--proceeding_id is required when --format is 'xml'")

    # Setup logging
    log_file = args.output + ".log"
    logger = setup_logging(log_file)

    logger.info("=" * 80)
    logger.info(f"EASYCHAIR TO {args.format.upper()} CONVERSION (Pydantic Validation)")
    logger.info("=" * 80)
    logger.info(f"Output file: {args.output}")
    logger.info(f"Log file: {log_file}")
    logger.info("")

    try:
        # Load and validate data
        export = load_easychair_data(
            excel_file_path=args.input,
            track_filter=args.track,
            proceeding_id=args.proceeding_id,
            logger=logger
        )

        # Export to appropriate format
        if args.format == "xml":
            export_to_xml(export, args.output, source=args.source, logger=logger)
        else:
            export_to_text(export, args.output, format_type=args.format, logger=logger)

        # Print summary
        print_summary(export, logger)

        logger.info(f"Log file saved to: {log_file}")

        # Run validation test
        if not args.no_validation:
            run_validation_test(args.input, args.output, logger)

        # Return exit code based on validation issues
        if export.has_errors:
            logger.error("")
            logger.error("Export completed with errors. Please review the log file.")
            return 1
        elif export.has_warnings:
            logger.warning("")
            logger.warning("Export completed with warnings. Please review the log file.")
            return 0
        else:
            logger.info("")
            logger.info("Export completed successfully!")
            return 0

    except Exception as e:
        logger.error("")
        logger.error(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
