"""
Test affiliation normalization in validation.

This test ensures that the validation test normalizes affiliations
before comparing them, matching the behavior of the export process
which strips trailing punctuation.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_author_order import clean_affiliation_string


def test_clean_affiliation_string():
    """Test affiliation string cleaning logic."""
    print("=" * 80)
    print("AFFILIATION NORMALIZATION TEST")
    print("=" * 80)
    print()

    test_cases = [
        # (input, expected_output)
        ("Kuaishou Technology Co., Ltd.", "Kuaishou Technology Co., Ltd"),
        ("MIT, ", "MIT"),
        (", Stanford University", "Stanford University"),
        (" , Tsinghua University", "Tsinghua University"),
        ("Meta Platforms, Inc.", "Meta Platforms, Inc"),
        ("University of Washington.", "University of Washington"),
        ("..Amazon..", "Amazon"),
        ("Normal University", "Normal University"),
        ("", ""),
        (None, ""),
        ("  Harvard University  ", "Harvard University"),
    ]

    all_passed = True
    for i, (input_str, expected) in enumerate(test_cases, 1):
        result = clean_affiliation_string(input_str)
        passed = result == expected

        status = "✓" if passed else "✗"
        print(f"{status} Test {i}: clean_affiliation_string({repr(input_str)})")
        print(f"    Expected: {repr(expected)}")
        print(f"    Got:      {repr(result)}")

        if not passed:
            all_passed = False
            print(f"    FAILED!")

        print()

    print("=" * 80)
    if all_passed:
        print("✅ All affiliation normalization tests passed!")
    else:
        print("❌ Some tests failed!")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    passed = test_clean_affiliation_string()
    sys.exit(0 if passed else 1)
