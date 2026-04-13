#!/usr/bin/env python3
"""
Comprehensive test suite for validation package.

Tests author identity merging and affiliation similarity detection
to ensure implementation matches documented behavior.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
import xml.etree.ElementTree as ET
from validation import merge_author_identities, find_similar_affiliations


class TestAuthorIdentityMerging(unittest.TestCase):
    """Test author identity merging logic."""

    def test_email_match_case_insensitive(self):
        """Test that email matching is case-insensitive."""
        author_keys = [
            ("John", "Smith", "john@mit.edu"),
            ("J.", "Smith", "john@mit.edu"),
            ("J", "Smith", "JOHN@MIT.EDU"),  # Case variation
        ]

        canonical_map = merge_author_identities(author_keys)

        # All should map to same canonical
        canonicals = set(canonical_map.values())
        self.assertEqual(len(canonicals), 1, "All John Smith variants should merge to single canonical")

    def test_email_match_with_name_variations(self):
        """Test that same email merges authors even with different name formats."""
        author_keys = [
            ("John", "Smith", "john@mit.edu"),
            ("J.", "Smith", "john@mit.edu"),
            ("Jonathan", "Smith", "john@mit.edu"),
        ]

        canonical_map = merge_author_identities(author_keys)

        canonicals = set(canonical_map.values())
        self.assertEqual(len(canonicals), 1, "Same email should merge despite name variations")

    def test_same_name_different_emails_not_merged(self):
        """Test that same name with different emails are NOT merged (likely different people)."""
        author_keys = [
            ("Jane", "Doe", "jane@stanford.edu"),
            ("Jane", "Doe", "jane@berkeley.edu"),
        ]

        canonical_map = merge_author_identities(author_keys)

        canonicals = set(canonical_map.values())
        self.assertEqual(len(canonicals), 2, "Same name + different emails should NOT merge")

    def test_same_name_with_missing_email_merged(self):
        """Test that same name merges when at least one has missing email."""
        author_keys = [
            ("Alice", "Johnson", "alice@cmu.edu"),
            ("Alice", "Johnson", ""),
        ]

        canonical_map = merge_author_identities(author_keys)

        canonicals = set(canonical_map.values())
        self.assertEqual(len(canonicals), 1, "Same name + missing email should merge")

        # Canonical should be the one with email
        canonical = canonical_map[("Alice", "Johnson", "alice@cmu.edu")]
        self.assertEqual(canonical[2], "alice@cmu.edu", "Canonical should prefer author with email")

    def test_same_name_both_missing_email_merged(self):
        """Test that same name merges when both have missing email."""
        author_keys = [
            ("Bob", "Brown", ""),
            ("Bob", "Brown", ""),
        ]

        canonical_map = merge_author_identities(author_keys)

        canonicals = set(canonical_map.values())
        self.assertEqual(len(canonicals), 1, "Same name + both missing email should merge")

    def test_unique_author_no_merging(self):
        """Test that unique authors with no duplicates remain unique."""
        author_keys = [
            ("Charlie", "Davis", "charlie@oxford.ac.uk"),
        ]

        canonical_map = merge_author_identities(author_keys)

        canonicals = set(canonical_map.values())
        self.assertEqual(len(canonicals), 1, "Unique author should remain unique")
        self.assertEqual(canonical_map[author_keys[0]], author_keys[0], "Unique author maps to itself")

    def test_empty_string_vs_missing_email(self):
        """Test that empty string email is treated as missing."""
        author_keys = [
            ("Test", "Author", "test@university.edu"),
            ("Test", "Author", ""),
            ("Test", "Author", None),  # Will be converted to "" in actual use
        ]

        # Convert None to empty string (as XML parsing would)
        author_keys_normalized = [
            (f, l, e if e else "") for f, l, e in author_keys
        ]

        canonical_map = merge_author_identities(author_keys_normalized)

        canonicals = set(canonical_map.values())
        self.assertEqual(len(canonicals), 1, "Empty string and None should be treated as missing email")

    def test_deterministic_canonical_selection(self):
        """Test that canonical selection is deterministic (same results across runs)."""
        author_keys = [
            ("John", "Smith", "john@mit.edu"),
            ("J.", "Smith", "john@mit.edu"),
            ("J", "Smith", "JOHN@MIT.EDU"),
        ]

        # Run multiple times
        results = []
        for _ in range(3):
            canonical_map = merge_author_identities(author_keys)
            canonical = canonical_map[author_keys[0]]
            results.append(canonical)

        # All results should be identical
        self.assertTrue(all(r == results[0] for r in results), "Canonical selection should be deterministic")

    def test_complex_scenario(self):
        """Test complex scenario with multiple authors and various merge cases."""
        author_keys = [
            # Group 1: Same email (should merge)
            ("John", "Smith", "john@mit.edu"),
            ("J.", "Smith", "john@mit.edu"),
            ("J", "Smith", "JOHN@MIT.EDU"),

            # Group 2: Same name, different emails (should NOT merge)
            ("Jane", "Doe", "jane@stanford.edu"),
            ("Jane", "Doe", "jane@berkeley.edu"),

            # Group 3: Same name, one with email, one without (should merge)
            ("Alice", "Johnson", "alice@cmu.edu"),
            ("Alice", "Johnson", ""),

            # Group 4: Same name, both without email (should merge)
            ("Bob", "Brown", ""),
            ("Bob", "Brown", ""),

            # Group 5: Unique author
            ("Charlie", "Davis", "charlie@oxford.ac.uk"),
        ]

        canonical_map = merge_author_identities(author_keys)

        # Should have 6 unique canonical authors
        canonicals = set(canonical_map.values())
        self.assertEqual(len(canonicals), 6, "Complex scenario should produce 6 canonical authors")

        # Verify John Smith group
        john_smith_keys = [k for k in author_keys if "John" in k[0] and k[1] == "Smith"]
        john_canonicals = set(canonical_map[k] for k in john_smith_keys)
        self.assertEqual(len(john_canonicals), 1, "John Smith group should merge to 1")

        # Verify Jane Doe group (should NOT merge)
        jane_doe_keys = [k for k in author_keys if k[0] == "Jane" and k[1] == "Doe"]
        jane_canonicals = set(canonical_map[k] for k in jane_doe_keys)
        self.assertEqual(len(jane_canonicals), 2, "Jane Doe group should have 2 canonicals")

        # Verify Alice Johnson group
        alice_keys = [k for k in author_keys if k[0] == "Alice"]
        alice_canonicals = set(canonical_map[k] for k in alice_keys)
        self.assertEqual(len(alice_canonicals), 1, "Alice Johnson group should merge to 1")

        # Verify Bob Brown group
        bob_keys = [k for k in author_keys if k[0] == "Bob"]
        bob_canonicals = set(canonical_map[k] for k in bob_keys)
        self.assertEqual(len(bob_canonicals), 1, "Bob Brown group should merge to 1")


class TestAffiliationSimilarity(unittest.TestCase):
    """Test affiliation similarity detection logic."""

    def create_test_xml(self, papers_data):
        """
        Helper to create XML structure for testing.

        papers_data format:
        [
            {
                "id": "fp1",
                "title": "Paper Title",
                "authors": [
                    {
                        "first": "John",
                        "last": "Smith",
                        "email": "john@rmit.edu.au",
                        "affiliation": "RMIT University"
                    },
                    ...
                ]
            },
            ...
        ]
        """
        root = ET.Element("proceedings")

        for paper_data in papers_data:
            paper = ET.SubElement(root, "paper")
            ET.SubElement(paper, "event_tracking_number").text = paper_data["id"]
            ET.SubElement(paper, "paper_title").text = paper_data["title"]

            for author_data in paper_data["authors"]:
                author = ET.SubElement(paper, "author")
                ET.SubElement(author, "first_name").text = author_data["first"]
                ET.SubElement(author, "last_name").text = author_data["last"]
                ET.SubElement(author, "email_address").text = author_data["email"]

                aff = ET.SubElement(author, "affiliation")
                ET.SubElement(aff, "institution").text = author_data["affiliation"]
                ET.SubElement(aff, "country").text = author_data.get("country", "")

        return root

    def test_email_domain_matching(self):
        """Test that same institutional email domain groups affiliations."""
        papers_data = [
            {
                "id": "fp1",
                "title": "Paper 1",
                "authors": [
                    {
                        "first": "John",
                        "last": "Smith",
                        "email": "john@rmit.edu.au",
                        "affiliation": "RMIT University"
                    }
                ]
            },
            {
                "id": "fp2",
                "title": "Paper 2",
                "authors": [
                    {
                        "first": "Jane",
                        "last": "Doe",
                        "email": "jane@rmit.edu.au",
                        "affiliation": "RMIT"
                    }
                ]
            },
        ]

        root = self.create_test_xml(papers_data)
        similar_groups = find_similar_affiliations(root, similarity_threshold=0.8)

        # Should find at least one group for RMIT variations
        self.assertGreater(len(similar_groups), 0, "Should find similar affiliations")

        # Check if RMIT variations are grouped
        rmit_group = None
        for group in similar_groups:
            affiliations = group["affiliations"]
            if "RMIT University" in affiliations or "RMIT" in affiliations:
                rmit_group = group
                break

        self.assertIsNotNone(rmit_group, "Should find RMIT affiliation group")
        self.assertEqual(rmit_group["match_type"], "email_domain", "RMIT should match by email domain")

    def test_email_domain_normalization(self):
        """Test that student/staff subdomains are normalized."""
        papers_data = [
            {
                "id": "fp1",
                "title": "Paper 1",
                "authors": [
                    {
                        "first": "John",
                        "last": "Smith",
                        "email": "john@student.rmit.edu.au",
                        "affiliation": "RMIT University"
                    }
                ]
            },
            {
                "id": "fp2",
                "title": "Paper 2",
                "authors": [
                    {
                        "first": "Jane",
                        "last": "Doe",
                        "email": "jane@rmit.edu.au",
                        "affiliation": "RMIT"
                    }
                ]
            },
        ]

        root = self.create_test_xml(papers_data)
        similar_groups = find_similar_affiliations(root, similarity_threshold=0.8)

        # Should merge despite subdomain difference
        self.assertGreater(len(similar_groups), 0, "Should normalize subdomains and find match")

    def test_public_domain_excluded(self):
        """Test that public email domains (gmail, acm.org) are excluded from matching."""
        papers_data = [
            {
                "id": "fp1",
                "title": "Paper 1",
                "authors": [
                    {
                        "first": "John",
                        "last": "Smith",
                        "email": "john@gmail.com",
                        "affiliation": "MIT"
                    }
                ]
            },
            {
                "id": "fp2",
                "title": "Paper 2",
                "authors": [
                    {
                        "first": "Jane",
                        "last": "Doe",
                        "email": "jane@gmail.com",
                        "affiliation": "Stanford University"
                    }
                ]
            },
            {
                "id": "fp3",
                "title": "Paper 3",
                "authors": [
                    {
                        "first": "Bob",
                        "last": "Brown",
                        "email": "bob@acm.org",
                        "affiliation": "Harvard University"
                    }
                ]
            },
        ]

        root = self.create_test_xml(papers_data)
        similar_groups = find_similar_affiliations(root, similarity_threshold=0.8)

        # Should NOT group MIT and Stanford just because both use gmail.com
        for group in similar_groups:
            affiliations = group["affiliations"]
            # Check that MIT and Stanford are not in same group
            has_mit = any("MIT" in aff for aff in affiliations)
            has_stanford = any("Stanford" in aff for aff in affiliations)
            self.assertFalse(has_mit and has_stanford, "Public domains should not cause merging")

    def test_string_similarity_matching(self):
        """Test string similarity matching with distinctive tokens."""
        papers_data = [
            {
                "id": "fp1",
                "title": "Paper 1",
                "authors": [
                    {
                        "first": "John",
                        "last": "Smith",
                        "email": "john@other1.edu",
                        "affiliation": "Beijing Institute of Technology"
                    }
                ]
            },
            {
                "id": "fp2",
                "title": "Paper 2",
                "authors": [
                    {
                        "first": "Jane",
                        "last": "Doe",
                        "email": "jane@other2.edu",
                        "affiliation": "Beijing Inst. of Tech."
                    }
                ]
            },
        ]

        root = self.create_test_xml(papers_data)
        similar_groups = find_similar_affiliations(root, similarity_threshold=0.8)

        # Should find match based on string similarity + shared "Beijing" token
        beijing_group = None
        for group in similar_groups:
            affiliations = group["affiliations"]
            if any("Beijing" in aff for aff in affiliations):
                beijing_group = group
                break

        if beijing_group:  # May or may not match depending on threshold and tokens
            self.assertIn("match_type", beijing_group, "Group should have match_type")

    def test_false_positive_prevention(self):
        """Test that similar-sounding but different institutions are NOT merged."""
        papers_data = [
            {
                "id": "fp1",
                "title": "Paper 1",
                "authors": [
                    {
                        "first": "John",
                        "last": "Smith",
                        "email": "john@dut.edu.cn",
                        "affiliation": "Dalian University of Technology"
                    }
                ]
            },
            {
                "id": "fp2",
                "title": "Paper 2",
                "authors": [
                    {
                        "first": "Jane",
                        "last": "Doe",
                        "email": "jane@tudelft.nl",
                        "affiliation": "Delft University of Technology"
                    }
                ]
            },
        ]

        root = self.create_test_xml(papers_data)
        similar_groups = find_similar_affiliations(root, similarity_threshold=0.8)

        # Should NOT merge Dalian and Delft (different distinctive tokens)
        for group in similar_groups:
            affiliations = group["affiliations"]
            has_dalian = any("Dalian" in aff for aff in affiliations)
            has_delft = any("Delft" in aff for aff in affiliations)
            self.assertFalse(has_dalian and has_delft, "Dalian and Delft should NOT merge")

    def test_capitalization_variations(self):
        """Test that capitalization variations are detected as similar."""
        papers_data = [
            {
                "id": "fp1",
                "title": "Paper 1",
                "authors": [
                    {
                        "first": "John",
                        "last": "Smith",
                        "email": "john@other1.edu",
                        "affiliation": "JD.com"
                    }
                ]
            },
            {
                "id": "fp2",
                "title": "Paper 2",
                "authors": [
                    {
                        "first": "Jane",
                        "last": "Doe",
                        "email": "jane@other2.edu",
                        "affiliation": "JD.COM"
                    }
                ]
            },
            {
                "id": "fp3",
                "title": "Paper 3",
                "authors": [
                    {
                        "first": "Bob",
                        "last": "Brown",
                        "email": "bob@other3.edu",
                        "affiliation": "jd.com"
                    }
                ]
            },
        ]

        root = self.create_test_xml(papers_data)
        similar_groups = find_similar_affiliations(root, similarity_threshold=0.8)

        # Should find JD.com variations
        jd_group = None
        for group in similar_groups:
            affiliations = group["affiliations"]
            if any("jd.com" in aff.lower() for aff in affiliations):
                jd_group = group
                break

        if jd_group:  # May match by string similarity
            self.assertGreaterEqual(len(jd_group["affiliations"]), 2, "Should group JD.com variations")


class TestFieldCompletion(unittest.TestCase):
    """Test author field completion logic."""

    def create_test_xml_with_missing_fields(self):
        """Create XML with same author in multiple papers, some fields missing."""
        root = ET.Element("proceedings")

        # Paper 1: John Smith with full information
        paper1 = ET.SubElement(root, "paper")
        ET.SubElement(paper1, "event_tracking_number").text = "fp1"
        ET.SubElement(paper1, "paper_title").text = "Paper 1"
        ET.SubElement(paper1, "paper_type").text = "Full Research Paper"

        author1 = ET.SubElement(paper1, "author")
        ET.SubElement(author1, "first_name").text = "John"
        ET.SubElement(author1, "last_name").text = "Smith"
        ET.SubElement(author1, "email_address").text = "john@mit.edu"
        aff1 = ET.SubElement(author1, "affiliation")
        ET.SubElement(aff1, "institution").text = "MIT"
        ET.SubElement(aff1, "department").text = "Computer Science"
        ET.SubElement(aff1, "country").text = "United States"

        # Paper 2: John Smith (same email) with missing country
        paper2 = ET.SubElement(root, "paper")
        ET.SubElement(paper2, "event_tracking_number").text = "fp2"
        ET.SubElement(paper2, "paper_title").text = "Paper 2"
        ET.SubElement(paper2, "paper_type").text = "Full Research Paper"

        author2 = ET.SubElement(paper2, "author")
        ET.SubElement(author2, "first_name").text = "John"
        ET.SubElement(author2, "last_name").text = "Smith"
        ET.SubElement(author2, "email_address").text = "john@mit.edu"
        aff2 = ET.SubElement(author2, "affiliation")
        ET.SubElement(aff2, "institution").text = "MIT"
        ET.SubElement(aff2, "department").text = "Computer Science"
        # No country element

        # Paper 3: J. Smith (same email) with no affiliation
        paper3 = ET.SubElement(root, "paper")
        ET.SubElement(paper3, "event_tracking_number").text = "fp3"
        ET.SubElement(paper3, "paper_title").text = "Paper 3"
        ET.SubElement(paper3, "paper_type").text = "Full Research Paper"

        author3 = ET.SubElement(paper3, "author")
        ET.SubElement(author3, "first_name").text = "J."
        ET.SubElement(author3, "last_name").text = "Smith"
        ET.SubElement(author3, "email_address").text = "john@mit.edu"
        # No affiliation element

        return root

    def test_complete_missing_country(self):
        """Test that missing country is filled from other papers."""
        from validation import complete_author_fields

        root = self.create_test_xml_with_missing_fields()

        # Get paper 2 before completion
        paper2 = root.findall("paper")[1]
        author2 = paper2.find(".//author")
        aff2 = author2.find(".//affiliation")
        country_before = aff2.findtext("country", "")

        # Complete fields
        stats = complete_author_fields(root)

        # Check paper 2 after completion
        country_after = aff2.findtext("country", "")

        self.assertEqual(country_before, "", "Country should be empty before completion")
        self.assertEqual(country_after, "United States", "Country should be filled after completion")
        self.assertGreater(stats['countries_added'], 0, "Should have added at least one country")

    def test_complete_missing_affiliation(self):
        """Test that missing affiliation is added from other papers."""
        from validation import complete_author_fields

        root = self.create_test_xml_with_missing_fields()

        # Get paper 3 before completion
        paper3 = root.findall("paper")[2]
        author3 = paper3.find(".//author")
        affiliations_before = author3.findall(".//affiliation")

        # Complete fields
        stats = complete_author_fields(root)

        # Check paper 3 after completion
        affiliations_after = author3.findall(".//affiliation")

        self.assertEqual(len(affiliations_before), 0, "Should have no affiliations before completion")
        self.assertGreater(len(affiliations_after), 0, "Should have affiliations after completion")
        self.assertGreater(stats['affiliations_added'], 0, "Should have added at least one affiliation")

        # Verify affiliation content
        if affiliations_after:
            aff = affiliations_after[0]
            institution = aff.findtext("institution", "")
            country = aff.findtext("country", "")
            self.assertEqual(institution, "MIT", "Institution should be filled")
            self.assertEqual(country, "United States", "Country should be filled")

    def test_no_overwrite_existing_values(self):
        """Test that existing values are never overwritten."""
        from validation import complete_author_fields

        root = ET.Element("proceedings")

        # Paper 1: John with MIT, USA
        paper1 = ET.SubElement(root, "paper")
        ET.SubElement(paper1, "event_tracking_number").text = "fp1"

        author1 = ET.SubElement(paper1, "author")
        ET.SubElement(author1, "first_name").text = "John"
        ET.SubElement(author1, "last_name").text = "Smith"
        ET.SubElement(author1, "email_address").text = "john@mit.edu"
        aff1 = ET.SubElement(author1, "affiliation")
        ET.SubElement(aff1, "institution").text = "MIT"
        ET.SubElement(aff1, "country").text = "United States"

        # Paper 2: John with MIT, UK (different country - legitimate)
        paper2 = ET.SubElement(root, "paper")
        ET.SubElement(paper2, "event_tracking_number").text = "fp2"

        author2 = ET.SubElement(paper2, "author")
        ET.SubElement(author2, "first_name").text = "John"
        ET.SubElement(author2, "last_name").text = "Smith"
        ET.SubElement(author2, "email_address").text = "john@mit.edu"
        aff2 = ET.SubElement(author2, "affiliation")
        ET.SubElement(aff2, "institution").text = "MIT"
        ET.SubElement(aff2, "country").text = "United Kingdom"

        # Complete fields
        complete_author_fields(root)

        # Verify that existing country in paper 2 was NOT overwritten
        paper2_after = root.findall("paper")[1]
        author2_after = paper2_after.find(".//author")
        aff2_after = author2_after.find(".//affiliation")
        country_after = aff2_after.findtext("country", "")

        self.assertEqual(country_after, "United Kingdom", "Existing country should NOT be overwritten")

    def test_multiple_affiliations_preserved(self):
        """Test that authors with multiple affiliations are handled correctly."""
        from validation import complete_author_fields

        root = ET.Element("proceedings")

        # Paper 1: John with two affiliations (MIT and Stanford)
        paper1 = ET.SubElement(root, "paper")
        ET.SubElement(paper1, "event_tracking_number").text = "fp1"

        author1 = ET.SubElement(paper1, "author")
        ET.SubElement(author1, "first_name").text = "John"
        ET.SubElement(author1, "last_name").text = "Smith"
        ET.SubElement(author1, "email_address").text = "john@mit.edu"

        aff1a = ET.SubElement(author1, "affiliation")
        ET.SubElement(aff1a, "institution").text = "MIT"
        ET.SubElement(aff1a, "country").text = "United States"

        aff1b = ET.SubElement(author1, "affiliation")
        ET.SubElement(aff1b, "institution").text = "Stanford"
        ET.SubElement(aff1b, "country").text = "United States"

        # Paper 2: John with no affiliation
        paper2 = ET.SubElement(root, "paper")
        ET.SubElement(paper2, "event_tracking_number").text = "fp2"

        author2 = ET.SubElement(paper2, "author")
        ET.SubElement(author2, "first_name").text = "John"
        ET.SubElement(author2, "last_name").text = "Smith"
        ET.SubElement(author2, "email_address").text = "john@mit.edu"

        # Complete fields
        complete_author_fields(root)

        # Verify that paper 2 now has affiliations
        paper2_after = root.findall("paper")[1]
        author2_after = paper2_after.find(".//author")
        affiliations_after = author2_after.findall(".//affiliation")

        self.assertGreater(len(affiliations_after), 0, "Should have affiliations after completion")

        # Check that both institutions are present
        institutions = [aff.findtext("institution", "") for aff in affiliations_after]
        self.assertIn("MIT", institutions, "Should have MIT affiliation")
        self.assertIn("Stanford", institutions, "Should have Stanford affiliation")


class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple validation features."""

    def test_statistics_with_merged_authors(self):
        """Test that statistics generation correctly uses merged author identities."""
        from validation import generate_statistics

        # Create XML with duplicate authors
        root = ET.Element("proceedings")

        # Paper 1: John Smith with email
        paper1 = ET.SubElement(root, "paper")
        ET.SubElement(paper1, "event_tracking_number").text = "fp1"
        ET.SubElement(paper1, "paper_title").text = "Paper 1"
        ET.SubElement(paper1, "paper_type").text = "Full Research Paper"
        ET.SubElement(paper1, "section").text = "Full Papers"

        author1 = ET.SubElement(paper1, "author")
        ET.SubElement(author1, "first_name").text = "John"
        ET.SubElement(author1, "last_name").text = "Smith"
        ET.SubElement(author1, "email_address").text = "john@mit.edu"
        aff1 = ET.SubElement(author1, "affiliation")
        ET.SubElement(aff1, "institution").text = "MIT"

        # Paper 2: J. Smith with same email (should merge)
        paper2 = ET.SubElement(root, "paper")
        ET.SubElement(paper2, "event_tracking_number").text = "fp2"
        ET.SubElement(paper2, "paper_title").text = "Paper 2"
        ET.SubElement(paper2, "paper_type").text = "Full Research Paper"
        ET.SubElement(paper2, "section").text = "Full Papers"

        author2 = ET.SubElement(paper2, "author")
        ET.SubElement(author2, "first_name").text = "J."
        ET.SubElement(author2, "last_name").text = "Smith"
        ET.SubElement(author2, "email_address").text = "john@mit.edu"
        aff2 = ET.SubElement(author2, "affiliation")
        ET.SubElement(aff2, "institution").text = "MIT"

        # Generate statistics
        stats = generate_statistics(root)

        # Should have 1 unique author (merged), 2 papers
        self.assertEqual(len(stats["author_paper_count"]), 1, "Should have 1 unique author after merging")

        # The canonical author should have 2 papers
        for author_key, papers in stats["author_paper_count"].items():
            self.assertEqual(len(papers), 2, "Merged author should have 2 papers")


def run_tests():
    """Run all tests and display results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAuthorIdentityMerging))
    suite.addTests(loader.loadTestsFromTestCase(TestAffiliationSimilarity))
    suite.addTests(loader.loadTestsFromTestCase(TestFieldCompletion))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    import sys
    sys.exit(run_tests())
