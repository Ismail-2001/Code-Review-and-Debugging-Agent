"""
Code analysis tools for static analysis and linting.
"""

from langchain_core.tools import tool
from typing import List, Dict, Optional
import ast
import subprocess
import json
from pathlib import Path


@tool
def parse_python_ast(file_path: str) -> Dict:
    """
    Parse Python file into Abstract Syntax Tree.
    
    Args:
        file_path: Path to Python file
        
    Returns:
        Dict with AST information and statistics
    """
    try:
        with open(file_path, 'r') as f:
            source_code = f.read()
        
        tree = ast.parse(source_code, filename=file_path)
        
        # Collect statistics
        stats = {
            "functions": [],
            "classes": [],
            "imports": [],
            "total_lines": len(source_code.split('\n'))
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                stats["functions"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": [arg.arg for arg in node.args.args],
                    "decorators": [d.id if isinstance(d, ast.Name) else str(d) 
                                  for d in node.decorator_list]
                })
            elif isinstance(node, ast.ClassDef):
                stats["classes"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "methods": [m.name for m in node.body 
                               if isinstance(m, ast.FunctionDef)]
                })
            elif isinstance(node, ast.Import):
                stats["imports"].extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom):
                stats["imports"].append(node.module if node.module else "")
        
        return {
            "status": "success",
            "file": file_path,
            "statistics": stats
        }
    except SyntaxError as e:
        return {
            "status": "error",
            "file": file_path,
            "error": f"Syntax error at line {e.lineno}: {e.msg}"
        }
    except Exception as e:
        return {
            "status": "error",
            "file": file_path,
            "error": str(e)
        }


@tool
def run_pylint(file_path: str) -> List[Dict]:
    """
    Run pylint on Python file.
    
    Args:
        file_path: Path to Python file
        
    Returns:
        List of linting issues
    """
    try:
        result = subprocess.run(
            ['pylint', '--output-format=json', file_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.stdout:
            issues = json.loads(result.stdout)
            return [{
                "file": issue.get("path"),
                "line": issue.get("line"),
                "column": issue.get("column"),
                "severity": issue.get("type"),  # convention, refactor, warning, error
                "message": issue.get("message"),
                "message_id": issue.get("message-id"),
                "symbol": issue.get("symbol")
            } for issue in issues]
        return []
    except subprocess.TimeoutExpired:
        return [{"error": "Pylint timeout"}]
    except Exception as e:
        return [{"error": str(e)}]


@tool
def calculate_cyclomatic_complexity(file_path: str) -> Dict:
    """
    Calculate cyclomatic complexity using radon.
    
    Args:
        file_path: Path to Python file
        
    Returns:
        Dict with complexity metrics
    """
    try:
        result = subprocess.run(
            ['radon', 'cc', file_path, '-j'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.stdout:
            data = json.loads(result.stdout)
            return {
                "file": file_path,
                "complexity_data": data.get(file_path, [])
            }
        return {"file": file_path, "complexity_data": []}
    except Exception as e:
        return {"error": str(e)}


@tool
def detect_code_smells(file_path: str) -> List[Dict]:
    """
    Detect code smells using various heuristics.
    
    Args:
        file_path: Path to Python file
        
    Returns:
        List of detected code smells
    """
    smells = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            lines = content.split('\n')
        
        tree = ast.parse(content, filename=file_path)
        
        # Detect long functions (>50 lines)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Calculate function length
                if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                    length = node.end_lineno - node.lineno
                    if length > 50:
                        smells.append({
                            "type": "long_function",
                            "line": node.lineno,
                            "function": node.name,
                            "length": length,
                            "message": f"Function '{node.name}' is {length} lines long (>50)"
                        })
                
                # Detect too many parameters (>5)
                param_count = len(node.args.args)
                if param_count > 5:
                    smells.append({
                        "type": "too_many_parameters",
                        "line": node.lineno,
                        "function": node.name,
                        "parameter_count": param_count,
                        "message": f"Function '{node.name}' has {param_count} parameters (>5)"
                    })
            
            # Detect large classes (>500 lines)
            elif isinstance(node, ast.ClassDef):
                if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                    length = node.end_lineno - node.lineno
                    if length > 500:
                        smells.append({
                            "type": "god_class",
                            "line": node.lineno,
                            "class": node.name,
                            "length": length,
                            "message": f"Class '{node.name}' is {length} lines long (>500)"
                        })
        
        # Detect magic numbers
        for i, line in enumerate(lines, 1):
            if any(num in line for num in ['1000', '100', '86400', '3600']):
                smells.append({
                    "type": "magic_number",
                    "line": i,
                    "message": "Potential magic number detected"
                })
        
        return smells
    except Exception as e:
        return [{"error": str(e)}]
