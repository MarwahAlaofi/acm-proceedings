# Multi-Affiliation Support

## Overview

The EasyChair to ACM converter (v2 with Pydantic) fully supports authors having **different affiliations, emails, and other information across different papers**. This is important because:

- Authors change institutions between papers
- Authors may use different email addresses for different collaborations
- Authors may have multiple affiliations or relocated to different countries

## How It Works

### 1. Field Consolidation (Smart Filling)

The system fills **ONLY empty fields** - it **NEVER overwrites** existing values.

**Rule:** If the same person (identified by name + email) has missing information in one paper but complete information in another, the missing fields are filled.

#### Example 1: Filling Empty Affiliation

```
Paper 1: John Doe, john@mit.edu, affiliation="MIT", country="USA"
Paper 2: John Doe, john@mit.edu, affiliation="", country=""

→ Paper 2 is filled:
Paper 2: John Doe, john@mit.edu, affiliation="MIT", country="USA"
```

**Why:** Paper 2 had empty fields, so we fill them from Paper 1.

#### Example 2: Preserving Different Affiliations

```
Paper 1: John Doe, john@mit.edu, affiliation="MIT", country="USA"
Paper 2: John Doe, john@mit.edu, affiliation="Stanford", country="USA"

→ BOTH papers remain unchanged
Paper 1: John Doe, john@mit.edu, affiliation="MIT", country="USA"
Paper 2: John Doe, john@mit.edu, affiliation="Stanford", country="USA"
```

**Why:** Both papers have values, so nothing is overwritten. This is legitimate - John moved from MIT to Stanford!

#### Example 3: Multiple Email Addresses

```
Paper 1: Jane Smith, jane@olduni.edu, affiliation="Old University"
Paper 2: Jane Smith, jane@newuni.edu, affiliation="New University"

→ BOTH papers remain unchanged
```

**Why:** Different email addresses mean they're treated as potentially different people (or the same person at different times). Both are preserved.

#### Example 4: Empty Field with Multiple Sources

```
Paper 1: Alice Brown, alice@uni1.edu, affiliation="University A", country="USA"
Paper 2: Alice Brown, alice@uni1.edu, affiliation="University B", country="Canada"
Paper 3: Alice Brown, alice@uni1.edu, affiliation="", country=""

→ Paper 3 gets filled from first non-empty value found:
Paper 3: Alice Brown, alice@uni1.edu, affiliation="University A", country="USA"
```

**Why:** Paper 3 was empty, so it gets filled with the first available value (from Paper 1).

### 2. Validation Levels

The validation system uses three severity levels:

| Severity | Icon | Meaning | Example |
|----------|------|---------|---------|
| **ERROR** | ✗ | Must be fixed | Paper with no authors |
| **WARNING** | ⚠ | Should review | Same email, different names (likely typo) |
| **INFO** | ℹ | Informational only | Same name, different emails (often legitimate) |

### 3. Validation Rules

#### ⚠ WARNING: Same Email, Different Names

```
⚠ Same email 'john@example.com' used with different names: 'John Doe', 'J. Doe'
```

**Why this is a WARNING:** This is likely a typo. The same email address should belong to the same person with the same name.

**Action:** Review and fix the name inconsistency.

#### ℹ INFO: Same Name, Different Emails

```
ℹ Same name 'John Doe' used with different emails:
  john@mit.edu (MIT), john@stanford.edu (Stanford)
  Note: Multiple emails can be legitimate if author changed institutions
```

**Why this is INFO:** This is often legitimate. People change email addresses when they change institutions.

**Action:** No action required. Just informational. Review if it seems unusual.

#### ✓ NO FLAG: Same Name, Different Affiliations

```
Paper 1: John Doe, john@mit.edu, "MIT"
Paper 2: John Doe, john@stanford.edu, "Stanford"
```

**Why NO flag:** This is completely normal and expected. Authors change institutions!

**Action:** None. This is working as intended.

## Implementation Details

### Code: Consolidation Function

Located in `easychair_loader.py`:

```python
def consolidate_duplicate_authors(authors_df, logger):
    """
    Fill missing fields for the same author across different papers.
    
    ONLY fills empty fields. NEVER overwrites existing values.
    """
    # Group by (first_name, last_name, email) across ALL papers
    # Find first non-empty value for each field
    # Fill only if current value is empty
```

**Key Point:** The function uses `(first_name, last_name, email)` as the key to identify the same person across papers.

### Code: Validation Function

Located in `easychair_models.py`:

```python
def validate_author_name_consistency(export):
    """
    Check for potential typos.
    
    - Same email, different names: WARNING (likely typo)
    - Same name, different emails: INFO (often legitimate)
    - Different affiliations: NOT FLAGGED (legitimate)
    """
```

## Use Cases

### Use Case 1: Author Changed Institution

**Scenario:** Dr. Smith moved from MIT to Stanford between papers.

**Data:**
```
Paper A (2024): Sarah Smith, sarah@mit.edu, "MIT"
Paper B (2025): Sarah Smith, sarah@stanford.edu, "Stanford"
```

**Result:** ✅ Both affiliations preserved. No warnings.

### Use Case 2: Author Uses Multiple Emails

**Scenario:** Dr. Johnson has both academic and company emails.

**Data:**
```
Paper A: Alice Johnson, alice@university.edu, "State University"
Paper B: Alice Johnson, alice@company.com, "Tech Company & State University"
```

**Result:** ✅ Both emails/affiliations preserved. INFO notice generated.

### Use Case 3: Missing Affiliation Data

**Scenario:** Paper submission missing affiliation for one author.

**Data:**
```
Paper A: Bob Lee, bob@uni.edu, "University"
Paper B: Bob Lee, bob@uni.edu, ""  (empty affiliation)
```

**Result:** ✅ Paper B affiliation filled with "University"

### Use Case 4: Data Entry Typo

**Scenario:** Same email but name spelled differently.

**Data:**
```
Paper A: John Smith, john@uni.edu, "University"
Paper B: Jon Smith, john@uni.edu, "University"  (typo: Jon vs John)
```

**Result:** ⚠ WARNING generated. User should fix the typo.

## Testing

Test suite in `test_pydantic_validation.py` includes:

```python
def test_different_affiliations_across_papers():
    """Test that authors can have different affiliations for different papers."""
    
    # Test 1: Different affiliations with same email → No error
    # Test 2: Different emails with same name → Info only
    # Test 3: Validation doesn't block export
```

**Run tests:**
```bash
python test_pydantic_validation.py
```

## Comparison: v1 vs v2

| Feature | v1 (Original) | v2 (Pydantic) |
|---------|---------------|---------------|
| Multiple affiliations | ✅ Supported | ✅ Supported |
| Fill empty fields | ✅ Yes | ✅ Yes |
| Overwrite existing | ❌ Could happen | ✅ Never overwrites |
| Validation | Basic logging | Structured (error/warning/info) |
| Testing | Manual review | Automated tests |

## Best Practices

### For Users

1. **Different affiliations are OK** - The system handles this correctly
2. **Review WARNING messages** - These likely indicate typos
3. **INFO messages are optional** - These are just for your awareness
4. **Empty fields will be filled** - If the same person has info in another paper

### For Developers

1. **Never overwrite existing values** - Only fill empty fields
2. **Use severity levels appropriately**:
   - ERROR: Blocks data quality
   - WARNING: Needs review
   - INFO: Just informational
3. **Test with real multi-affiliation data**
4. **Document validation behavior**

## Configuration

No configuration needed! The behavior is automatic and handles all cases correctly.

## FAQ

**Q: Will my different affiliations be merged?**  
A: No. Different affiliations are preserved. Only empty fields are filled.

**Q: What if an author has different emails for different papers?**  
A: Both emails are kept. You'll get an INFO notice, but it won't block export.

**Q: What if I really do have two different people with similar names?**  
A: Make sure they have different emails. The system uses (name + email) to identify people.

**Q: Can I turn off the INFO messages?**  
A: They appear in the log but don't affect the export. You can ignore them if they're not helpful.

**Q: What happens if Paper A has affiliation X and Paper B has affiliation Y?**  
A: Both X and Y are preserved. This is working as intended.

## Summary

✅ **Different affiliations per paper**: Fully supported  
✅ **Different emails per paper**: Fully supported  
✅ **Fill empty fields**: Automatic and smart  
✅ **Never overwrite existing data**: Guaranteed  
✅ **Three severity levels**: ERROR, WARNING, INFO  
✅ **Comprehensive testing**: All scenarios covered  

The system is designed to handle the real-world scenario where authors move between institutions, use different email addresses, and collaborate with different affiliations over time.
