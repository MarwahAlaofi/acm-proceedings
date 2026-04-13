#!/usr/bin/env python3
"""
Quick test to verify author identity merging logic.
Simple, standalone test with colored output for quick verification.
For comprehensive tests, see test_validation.py.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from validation import merge_author_identities


def test_author_merging():
    """Test author identity merging with various scenarios."""

    # Test data
    author_keys = [
        # Same email, different names (should merge)
        ("John", "Smith", "john@mit.edu"),
        ("J.", "Smith", "john@mit.edu"),
        ("J", "Smith", "JOHN@MIT.EDU"),  # Case-insensitive email

        # Same name, different emails (should NOT merge - different people)
        ("Jane", "Doe", "jane@stanford.edu"),
        ("Jane", "Doe", "jane@berkeley.edu"),

        # Same name, one with email, one without (should merge by name)
        ("Alice", "Johnson", "alice@cmu.edu"),
        ("Alice", "Johnson", ""),

        # Same name, both without email (should merge by name)
        ("Bob", "Brown", ""),
        ("Bob", "Brown", ""),

        # Unique author
        ("Charlie", "Davis", "charlie@oxford.ac.uk"),
    ]

    # Merge identities
    canonical_map = merge_author_identities(author_keys)

    # Analyze results
    print("=" * 80)
    print("AUTHOR IDENTITY MERGING TEST")
    print("=" * 80)
    print(f"Total author entries: {len(author_keys)}")
    print(f"Unique canonical authors: {len(set(canonical_map.values()))}")
    print()

    # Group by canonical identity
    identity_groups = {}
    for author_key in author_keys:
        canonical = canonical_map[author_key]
        if canonical not in identity_groups:
            identity_groups[canonical] = []
        identity_groups[canonical].append(author_key)

    # Print results
    print("MERGED GROUPS:")
    print("-" * 80)
    for canonical, identities in sorted(identity_groups.items()):
        first, last, email = canonical
        print(f"\nCanonical: {first} {last} ({email if email else 'no email'})")

        if len(identities) > 1:
            print(f"  Merged {len(identities)} identities:")
            for f, l, e in identities:
                if (f, l, e) != canonical:
                    print(f"    → {f} {l} ({e if e else 'no email'})")
        else:
            print(f"  No duplicates (unique author)")

    # Validation checks
    print()
    print("=" * 80)
    print("VALIDATION CHECKS:")
    print("=" * 80)

    # Check 1: John Smith variations should merge (all with email john@mit.edu / JOHN@MIT.EDU)
    john_smith_variants = [
        ("John", "Smith", "john@mit.edu"),
        ("J.", "Smith", "john@mit.edu"),
        ("J", "Smith", "JOHN@MIT.EDU"),
    ]
    # They should all map to the same canonical
    john_smith_canonicals = set(canonical_map[k] for k in john_smith_variants)
    print(f"✓ John Smith merging: {len(john_smith_variants)} identities → {len(john_smith_canonicals)} canonical (expected 1)")
    assert len(john_smith_canonicals) == 1, "John Smith variants should merge to single canonical identity"

    # Check 2: Jane Doe should NOT merge (different emails = different people)
    jane_doe_variants = [
        ("Jane", "Doe", "jane@stanford.edu"),
        ("Jane", "Doe", "jane@berkeley.edu"),
    ]
    jane_doe_canonicals = set(canonical_map[k] for k in jane_doe_variants)
    print(f"✓ Jane Doe NOT merged: {len(jane_doe_variants)} identities → {len(jane_doe_canonicals)} canonicals (expected 2)")
    assert len(jane_doe_canonicals) == 2, "Jane Doe with different emails should have 2 separate canonical identities"

    # Check 3: Alice Johnson should merge (same name, one with email, one without)
    alice_johnson_variants = [
        ("Alice", "Johnson", "alice@cmu.edu"),
        ("Alice", "Johnson", ""),
    ]
    alice_johnson_canonicals = set(canonical_map[k] for k in alice_johnson_variants)
    print(f"✓ Alice Johnson merging: {len(alice_johnson_variants)} identities → {len(alice_johnson_canonicals)} canonical (expected 1)")
    assert len(alice_johnson_canonicals) == 1, "Alice Johnson should merge to single canonical identity"

    # Check 4: Bob Brown should merge (same name, both without email)
    bob_brown_variants = [
        ("Bob", "Brown", ""),
        ("Bob", "Brown", ""),
    ]
    bob_brown_canonicals = set(canonical_map[k] for k in bob_brown_variants)
    print(f"✓ Bob Brown merging: {len(bob_brown_variants)} identities → {len(bob_brown_canonicals)} canonical (expected 1)")
    assert len(bob_brown_canonicals) == 1, "Bob Brown should merge to single canonical identity"

    # Check 5: Charlie Davis should be unique (no duplicates)
    charlie_davis_variants = [
        ("Charlie", "Davis", "charlie@oxford.ac.uk"),
    ]
    charlie_davis_canonicals = set(canonical_map[k] for k in charlie_davis_variants)
    print(f"✓ Charlie Davis unique: {len(charlie_davis_variants)} identity → {len(charlie_davis_canonicals)} canonical (expected 1)")
    assert len(charlie_davis_canonicals) == 1, "Charlie Davis should have 1 identity"

    print()
    print("=" * 80)
    print("ALL TESTS PASSED ✓")
    print("=" * 80)


if __name__ == "__main__":
    test_author_merging()
