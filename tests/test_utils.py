
import pytest

from libanaf.utils import sanitize_file_name


def test_sanitize_file_name_basic():
    """Test basic sanitization of a single string."""
    assert sanitize_file_name('  a/b c?d*e:f|g\\h<i>j"k<l>m  ') == 'a-b-c-d-e-f-g-h-i-j-k-l-m'

def test_sanitize_file_name_multiple_parts():
    """Test sanitization with multiple string parts."""
    assert sanitize_file_name(" part1/ ", " part2? ", " part3* ") == "part1_part2_part3"

def test_sanitize_file_name_leading_trailing_whitespace():
    """Test stripping of leading and trailing whitespace."""
    assert sanitize_file_name("  leading", "trailing  ", "  both  ") == "leading_trailing_both"

def test_sanitize_file_name_period_removal():
    """Test that periods are removed."""
    assert sanitize_file_name("file.name.with.dots") == "filenamewithdots"

def test_sanitize_file_name_custom_glue_and_replace():
    """Test with custom glue and replace characters."""
    assert sanitize_file_name("a/b", "c?d", glue="---", replace_char="!") == "a!b---c!d"

def test_sanitize_file_name_already_clean():
    """Test that already clean strings are not modified."""
    assert sanitize_file_name("clean", "strings") == "clean_strings"

def test_sanitize_file_name_empty_strings():
    """Test with empty string inputs."""
    assert sanitize_file_name("", "a", "") == "_a_"

def test_sanitize_file_name_with_consecutive_invalid_chars():
    """Test that consecutive invalid characters are collapsed."""
    assert sanitize_file_name("a//b??c**d") == "a-b-c-d"

def test_sanitize_file_name_with_mixed_dirty_and_clean():
    """Test a mix of clean and dirty parts."""
    assert sanitize_file_name("  dirty/part  ", "clean_part") == "dirty-part_clean_part"
