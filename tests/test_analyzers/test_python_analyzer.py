import pytest
from tools.code_analysis import detect_code_smells, calculate_cyclomatic_complexity
import os

def test_detect_long_function(tmp_path):
    """Test detection of overly long functions."""
    test_file = tmp_path / "long.py"
    # Create a function with 60+ lines
    content = "def long_func():\n" + "\n".join([f"    x = {i}" for i in range(70)])
    test_file.write_text(content)
    
    # We call the tool directly for testing
    smells = detect_code_smells.invoke({"file_path": str(test_file)})
    
    long_func_findings = [f for f in smells if f['type'] == 'long_function']
    assert len(long_func_findings) > 0
    assert "70 lines" in long_func_findings[0]['message']

def test_calculate_complexity(tmp_path):
    """Test cyclomatic complexity calculation."""
    test_file = tmp_path / "complex.py"
    complex_code = """
def complex_function(x):
    if x > 10:
        if x > 20:
            if x > 30:
                return "high"
            return "medium-high"
        return "medium"
    return "low"
"""
    test_file.write_text(complex_code)
    
    result = calculate_cyclomatic_complexity.invoke({"file_path": str(test_file)})
    comp_data = result.get("complexity_data", [])
    
    assert len(comp_data) > 0
    assert comp_data[0]['complexity'] >= 4
