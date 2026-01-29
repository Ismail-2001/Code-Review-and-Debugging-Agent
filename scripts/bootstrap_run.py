"""
CodeGuardian Bootstrap - Standard Library Only
This script demonstrates the code review flow without external dependencies.
"""
import os
import json
import uuid
import time

def simulate_review(path):
    print(f"🚀 CodeGuardian (Bootstrap) Analysis Starting for: {path}")
    print("[1/4] Scanning Files...")
    time.sleep(1)
    python_files = []
    for root, _, files in os.walk(path):
        if 'node_modules' in root or '.git' in root or '.gemini' in root:
            continue
        for f in files:
            if f.endswith('.py'):
                python_files.append(os.path.join(root, f))
    
    print(f"Found {len(python_files)} Python files.")
    
    print("[2/4] Analyzing Patterns...")
    findings = []
    for f in python_files[:10]: # Sample first 10
        # print(f"  Analyzing {f}...")
        try:
            with open(f, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Simple heuristic analysis
            if 'import os' in content and 'os.system' in content:
                 findings.append({
                    "id": str(uuid.uuid4()),
                    "file": f,
                    "severity": "high",
                    "category": "security",
                    "title": "Unsafe system call",
                    "description": "Possible shell injection vulnerability using os.system"
                })
            
            if '"""' not in content and "'''" not in content and len(content) > 10:
                findings.append({
                    "id": str(uuid.uuid4()),
                    "file": f,
                    "severity": "low",
                    "category": "style",
                    "title": "Missing docstring",
                    "description": "File or function is missing a docstring."
                })
        except Exception:
            continue

    print("[3/4] Synthesizing Results...")
    time.sleep(1)
    
    summary = {
        "critical": len([f for f in findings if f['severity'] == 'critical']),
        "high": len([f for f in findings if f['severity'] == 'high']),
        "medium": len([f for f in findings if f['severity'] == 'medium']),
        "low": len([f for f in findings if f['severity'] == 'low']),
    }
    
    print("\nAnalysis Summary")
    print("================")
    print(f"Total Issues: {len(findings)}")
    print(f"🔴 Critical: {summary['critical']}")
    print(f"🟠 High: {summary['high']}")
    print(f"🟢 Low: {summary['low']}")
    
    print("\n[4/4] Generating Report...")
    report = "# CodeGuardian Report\n\n## Findings\n"
    for f in findings:
        report += f"### {f['title']} ({f['severity'].upper()})\n"
        report += f"- **File**: {f['file']}\n"
        report += f"- **Description**: {f['description']}\n\n"
    
    with open('bootstrap_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    print("\n✓ Report saved to: bootstrap_report.md")

if __name__ == "__main__":
    simulate_review(".")
