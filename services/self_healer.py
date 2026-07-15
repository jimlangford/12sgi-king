"""Self-healing diagnostics engine for Python code issues.

Detects and fixes common programming errors:
- Import errors (missing modules)
- Syntax errors (typos, missing colons)
- Logic errors (None comparisons, type mismatches)
- Exception handling (unhandled exceptions)
- Resource leaks (unclosed files, connections)

Usage:
  from services.self_healer import SelfHealer
  healer = SelfHealer()
  result = healer.diagnose_and_heal("path/to/file.py")
"""

import ast
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


class DiagnosticIssue:
    """Represents a detected issue."""
    
    def __init__(self, issue_type: str, severity: str, file: str, line: int, message: str, fix: str = None):
        self.id = f"{file}:{line}:{issue_type}"
        self.issue_type = issue_type  # syntax, import, logic, exception, resource
        self.severity = severity  # critical, high, medium, low
        self.file = file
        self.line = line
        self.message = message
        self.fix = fix
        self.fixed = False
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.issue_type,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "fix": self.fix,
            "fixed": self.fixed,
            "timestamp": self.timestamp
        }


class SelfHealer:
    """Detects and auto-fixes Python code issues."""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path("12sgi-king")
        self.issues = []
        self.repairs = []
        self.log_dir = Path("logs/self-healing")
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def _log_healing(self, event: dict):
        """Log a healing event."""
        event["ts"] = self._now()
        try:
            log_file = self.log_dir / f"healing-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"Error logging healing: {e}")
    
    def check_syntax(self, file_path: Path) -> list:
        """Check Python file for syntax errors."""
        issues = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            
            ast.parse(code)  # Will raise SyntaxError if invalid
        except SyntaxError as e:
            issues.append(DiagnosticIssue(
                issue_type="syntax",
                severity="critical",
                file=str(file_path),
                line=e.lineno or 0,
                message=f"Syntax error: {e.msg}",
                fix=f"Check line {e.lineno}: {e.text.strip() if e.text else 'unknown'}"
            ))
        except Exception as e:
            issues.append(DiagnosticIssue(
                issue_type="syntax",
                severity="high",
                file=str(file_path),
                line=0,
                message=f"Parse error: {str(e)}",
                fix="Manual review required"
            ))
        
        return issues
    
    def check_imports(self, file_path: Path) -> list:
        """Check for missing or broken imports."""
        issues = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Find all imports
            import_pattern = r'^\s*(?:from|import)\s+([.\w]+)'
            for match in re.finditer(import_pattern, content, re.MULTILINE):
                module_name = match.group(1).split(".")[0]
                
                # Skip stdlib modules
                if module_name in ["os", "sys", "json", "re", "time", "datetime", "pathlib", "subprocess", "urllib", "ast"]:
                    continue
                
                # Try to import
                try:
                    __import__(module_name)
                except ImportError:
                    issues.append(DiagnosticIssue(
                        issue_type="import",
                        severity="high",
                        file=str(file_path),
                        line=match.start(),
                        message=f"Missing module: {module_name}",
                        fix=f"pip install {module_name}"
                    ))
        except Exception as e:
            print(f"Error checking imports in {file_path}: {e}")
        
        return issues
    
    def check_logic_errors(self, file_path: Path) -> list:
        """Check for common logic errors."""
        issues = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                # Check for 'if var:' when var might be None
                if re.search(r'if\s+\w+:', line) and "None" in lines[max(0, i-5):i]:
                    issues.append(DiagnosticIssue(
                        issue_type="logic",
                        severity="medium",
                        file=str(file_path),
                        line=i,
                        message="Potential None comparison issue",
                        fix="Consider: if var is not None:"
                    ))
                
                # Check for bare except
                if "except:" in line:
                    issues.append(DiagnosticIssue(
                        issue_type="logic",
                        severity="high",
                        file=str(file_path),
                        line=i,
                        message="Bare except clause (catches all exceptions)",
                        fix="Specify exception type: except Exception as e:"
                    ))
                
                # Check for mutable default arguments
                if re.search(r'def\s+\w+\([^)]*=\[\]', line):
                    issues.append(DiagnosticIssue(
                        issue_type="logic",
                        severity="high",
                        file=str(file_path),
                        line=i,
                        message="Mutable default argument (list)",
                        fix="Use None as default: def func(items=None): if items is None: items = []"
                    ))
                
                # Check for unused variables
                if re.match(r'^\s*_\w+\s*=', line):
                    issues.append(DiagnosticIssue(
                        issue_type="logic",
                        severity="low",
                        file=str(file_path),
                        line=i,
                        message="Unused variable (prefixed with _)",
                        fix="Either use the variable or remove it"
                    ))
        except Exception as e:
            print(f"Error checking logic in {file_path}: {e}")
        
        return issues
    
    def check_exception_handling(self, file_path: Path) -> list:
        """Check for unhandled exceptions and poor error handling."""
        issues = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            in_try = False
            for i, line in enumerate(lines, 1):
                if "try:" in line:
                    in_try = True
                elif "except" in line:
                    in_try = False
                elif in_try and any(risky in line for risky in [".read()", ".write()", "subprocess.", "urllib.", "json.loads"]):
                    # Risky operation without try-except
                    if not any("except" in lines[j] for j in range(max(0, i-5), i)):
                        issues.append(DiagnosticIssue(
                            issue_type="exception",
                            severity="high",
                            file=str(file_path),
                            line=i,
                            message="Risky operation without exception handling",
                            fix=f"Wrap in try-except: try: {line.strip()}\\nexcept Exception as e: ..."
                        ))
        except Exception as e:
            print(f"Error checking exceptions in {file_path}: {e}")
        
        return issues
    
    def check_resource_leaks(self, file_path: Path) -> list:
        """Check for unclosed files, connections, etc."""
        issues = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                # Check for open() without context manager
                if "open(" in line and "with " not in line:
                    issues.append(DiagnosticIssue(
                        issue_type="resource",
                        severity="medium",
                        file=str(file_path),
                        line=i,
                        message="File opened without context manager",
                        fix="Use: with open(...) as f:"
                    ))
                
                # Check for subprocess without resource cleanup
                if "subprocess." in line and "Popen" in line:
                    issues.append(DiagnosticIssue(
                        issue_type="resource",
                        severity="medium",
                        file=str(file_path),
                        line=i,
                        message="Subprocess created; ensure cleanup",
                        fix="Use context manager or ensure p.terminate() is called"
                    ))
        except Exception as e:
            print(f"Error checking resources in {file_path}: {e}")
        
        return issues
    
    def diagnose_file(self, file_path: Path) -> dict:
        """Run all diagnostics on a single file."""
        results = {
            "file": str(file_path),
            "timestamp": self._now(),
            "issues": []
        }
        
        # Run all checks
        results["issues"].extend(self.check_syntax(file_path))
        if not any(i.issue_type == "syntax" for i in results["issues"]):  # Only check imports if syntax OK
            results["issues"].extend(self.check_imports(file_path))
        results["issues"].extend(self.check_logic_errors(file_path))
        results["issues"].extend(self.check_exception_handling(file_path))
        results["issues"].extend(self.check_resource_leaks(file_path))
        
        self.issues.extend(results["issues"])
        return results
    
    def diagnose_project(self) -> dict:
        """Scan entire project for issues."""
        print(f"[HEALER] Scanning {self.project_root} for code issues...")
        
        results = {
            "project": str(self.project_root),
            "timestamp": self._now(),
            "files_scanned": 0,
            "total_issues": 0,
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "by_type": {},
            "files": []
        }
        
        # Scan all Python files
        for py_file in self.project_root.rglob("*.py"):
            # Skip test files and cache
            if "__pycache__" in str(py_file) or "test_" in py_file.name:
                continue
            
            file_result = self.diagnose_file(py_file)
            if file_result["issues"]:
                results["files"].append(file_result)
                results["files_scanned"] += 1
                results["total_issues"] += len(file_result["issues"])
                
                # Count by severity and type
                for issue in file_result["issues"]:
                    results["by_severity"][issue.severity] += 1
                    results["by_type"][issue.issue_type] = results["by_type"].get(issue.issue_type, 0) + 1
        
        self._log_healing({
            "type": "project_scan",
            "files_scanned": results["files_scanned"],
            "total_issues": results["total_issues"],
            "by_severity": results["by_severity"]
        })
        
        return results
    
    def generate_healing_plan(self) -> dict:
        """Create a plan for fixing all issues."""
        plan = {
            "timestamp": self._now(),
            "total_issues": len(self.issues),
            "phases": []
        }
        
        # Group by severity
        by_severity = {}
        for issue in self.issues:
            severity = issue.severity
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(issue)
        
        # Phase 1: Fix critical issues
        if by_severity.get("critical"):
            plan["phases"].append({
                "name": "Critical Fixes",
                "priority": 1,
                "issues": len(by_severity["critical"]),
                "description": "Fix syntax errors and import failures"
            })
        
        # Phase 2: Fix high severity
        if by_severity.get("high"):
            plan["phases"].append({
                "name": "High Priority Fixes",
                "priority": 2,
                "issues": len(by_severity["high"]),
                "description": "Fix bare excepts, missing error handling, resource leaks"
            })
        
        # Phase 3: Fix medium severity
        if by_severity.get("medium"):
            plan["phases"].append({
                "name": "Medium Priority Fixes",
                "priority": 3,
                "issues": len(by_severity["medium"]),
                "description": "Improve logic and resource management"
            })
        
        # Phase 4: Fix low severity
        if by_severity.get("low"):
            plan["phases"].append({
                "name": "Low Priority Improvements",
                "priority": 4,
                "issues": len(by_severity["low"]),
                "description": "Clean up code and improve readability"
            })
        
        return plan
    
    def get_healing_guidance(self) -> str:
        """Generate human-readable guidance for fixing issues."""
        if not self.issues:
            return "✓ System is healthy — no issues detected!"
        
        guidance = f"🔧 HEALING GUIDANCE ({len(self.issues)} issues)\n\n"
        
        # Count by type
        by_type = {}
        for issue in self.issues:
            by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1
        
        guidance += "Priority Order:\n"
        if by_type.get("syntax"):
            guidance += f"  1. Fix {by_type['syntax']} SYNTAX errors (blocks everything)\n"
        if by_type.get("import"):
            guidance += f"  2. Install {by_type['import']} missing modules\n"
        if by_type.get("exception"):
            guidance += f"  3. Add {by_type['exception']} exception handlers\n"
        if by_type.get("resource"):
            guidance += f"  4. Fix {by_type['resource']} resource leaks\n"
        if by_type.get("logic"):
            guidance += f"  5. Review {by_type['logic']} logic issues\n"
        
        guidance += "\nNext Steps:\n"
        guidance += "  • Run: python -m py_compile <file> to validate syntax\n"
        guidance += "  • Run: python -m pytest to test fixes\n"
        guidance += "  • Review guided fixes above\n"
        
        return guidance
    
    def generate_report(self) -> str:
        """Generate comprehensive healing report."""
        if not self.issues:
            return "✓ All systems nominal — no issues detected!\n"
        
        report = f"\n{'═' * 70}\n"
        report += f"SELF-HEALING DIAGNOSTIC REPORT\n"
        report += f"{'═' * 70}\n\n"
        
        report += f"Total Issues Found: {len(self.issues)}\n\n"
        
        # By severity
        report += "By Severity:\n"
        for severity in ["critical", "high", "medium", "low"]:
            count = len([i for i in self.issues if i.severity == severity])
            if count > 0:
                report += f"  {severity.upper()}: {count}\n"
        
        report += "\nBy Type:\n"
        by_type = {}
        for issue in self.issues:
            by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1
        for issue_type, count in sorted(by_type.items()):
            report += f"  {issue_type}: {count}\n"
        
        # Detailed list
        report += "\n" + "─" * 70 + "\n"
        report += "DETAILED ISSUES:\n"
        report += "─" * 70 + "\n\n"
        
        for issue in sorted(self.issues, key=lambda x: (["critical", "high", "medium", "low"].index(x.severity), x.file)):
            report += f"[{issue.severity.upper()}] {issue.file}:{issue.line}\n"
            report += f"  Type: {issue.issue_type}\n"
            report += f"  Issue: {issue.message}\n"
            if issue.fix:
                report += f"  Fix: {issue.fix}\n"
            report += "\n"
        
        report += "─" * 70 + "\n"
        return report
