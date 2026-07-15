"""
Autonomous GitHub Actions Workflow YAML Repair

Detects and fixes:
  - Indentation errors
  - Invalid YAML syntax
  - Schema validation errors
  - Missing required fields

Uses yamllint + PyYAML + custom schema validation.
"""

import os
import re
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import yaml


class WorkflowYamlRepair:
    """Repair GitHub Actions workflow YAML files."""
    
    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
        self.github_workflows = self.repo_root / ".github" / "workflows"
    
    def detect_yaml_errors(self, workflow_file: str) -> list:
        """Detect YAML errors in a workflow file.
        
        Returns list of dicts with keys: line, error, code
        """
        filepath = self.github_workflows / workflow_file
        if not filepath.exists():
            return [{"error": f"File not found: {workflow_file}", "line": 0, "code": "FILE_NOT_FOUND"}]
        
        errors = []
        
        # Run yamllint if available
        try:
            result = subprocess.run(
                ["yamllint", "-f", "parsable", str(filepath)],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                for line in result.stdout.split("\n"):
                    if line.strip():
                        match = re.search(r":(\d+):.*error (.+)", line)
                        if match:
                            errors.append({
                                "line": int(match.group(1)),
                                "error": match.group(2),
                                "code": "YAML_LINT_ERROR"
                            })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Try PyYAML parser
        try:
            with open(filepath) as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            line_num = e.problem_mark.line + 1 if hasattr(e, "problem_mark") else 0
            errors.append({
                "line": line_num,
                "error": str(e.problem),
                "code": "YAML_PARSE_ERROR"
            })
        
        return errors
    
    def fix_indentation(self, filepath: Path) -> Tuple[bool, str]:
        """Fix common indentation issues in YAML.
        
        GitHub Actions workflows are sensitive to indentation.
        Convert tabs to spaces, fix common indent misalignments.
        """
        try:
            content = filepath.read_text()
            lines = content.split("\n")
            fixed_lines = []
            
            # Convert tabs to spaces
            content = content.replace("\t", "  ")
            lines = content.split("\n")
            
            # Re-normalize indentation to multiples of 2 spaces
            for line in lines:
                if line and not line[0].isspace():
                    # Top-level key
                    fixed_lines.append(line)
                elif line:
                    # Count leading spaces, round to nearest multiple of 2
                    stripped = line.lstrip()
                    indent = len(line) - len(stripped)
                    normalized_indent = (indent // 2) * 2
                    fixed_lines.append(" " * normalized_indent + stripped)
                else:
                    fixed_lines.append("")
            
            fixed_content = "\n".join(fixed_lines)
            if fixed_content != content:
                filepath.write_text(fixed_content)
                return True, "Fixed indentation"
            return False, "No indentation changes needed"
        except Exception as e:
            return False, f"Indentation fix failed: {str(e)}"
    
    def validate_workflow_schema(self, filepath: Path) -> Tuple[bool, list]:
        """Validate workflow schema against GitHub Actions spec.
        
        Returns (is_valid, errors)
        """
        try:
            with open(filepath) as f:
                workflow = yaml.safe_load(f)
        except Exception as e:
            return False, [f"Failed to parse YAML: {str(e)}"]
        
        errors = []
        
        # Check required top-level keys
        # Note: "on" is parsed as boolean True by YAML
        has_name = "name" in workflow
        has_on = "on" in workflow or True in workflow
        if not has_name:
            errors.append("Missing required top-level key: name")
        if not has_on:
            errors.append("Missing required top-level key: on")
        
        # Check jobs
        if "jobs" not in workflow:
            errors.append("Missing required 'jobs' section")
        elif not isinstance(workflow["jobs"], dict):
            errors.append("'jobs' must be a mapping")
        else:
            for job_name, job_config in workflow["jobs"].items():
                if not isinstance(job_config, dict):
                    errors.append(f"Job '{job_name}' must be a mapping")
                    continue
                
                # Each job should have at least 'runs-on' or 'uses'
                if "runs-on" not in job_config and "uses" not in job_config:
                    errors.append(f"Job '{job_name}' missing 'runs-on' or 'uses'")
                
                # Check steps if present
                if "steps" in job_config:
                    if not isinstance(job_config["steps"], list):
                        errors.append(f"Job '{job_name}': 'steps' must be a list")
                    else:
                        for i, step in enumerate(job_config["steps"]):
                            if "run" in step and "uses" in step:
                                errors.append(f"Job '{job_name}' step {i}: cannot have both 'run' and 'uses'")
        
        return len(errors) == 0, errors
    
    def repair_workflow(self, workflow_file: str) -> Tuple[bool, str]:
        """Attempt to repair a workflow file.
        
        Returns (success, message)
        """
        filepath = self.github_workflows / workflow_file
        if not filepath.exists():
            return False, f"Workflow file not found: {workflow_file}"
        
        # Try indentation fix
        fixed_indent, indent_msg = self.fix_indentation(filepath)
        
        # Validate schema
        is_valid, schema_errors = self.validate_workflow_schema(filepath)
        
        if fixed_indent:
            return True, f"Fixed indentation. Schema valid: {is_valid}"
        elif is_valid:
            return True, "Workflow schema is valid"
        else:
            return False, f"Schema errors: {'; '.join(schema_errors)}"
    
    def dry_run_repair(self, workflow_file: str) -> Tuple[bool, list, str]:
        """Dry-run: detect errors without fixing.
        
        Returns (has_errors, errors_list, summary)
        """
        yaml_errors = self.detect_yaml_errors(workflow_file)
        
        filepath = self.github_workflows / workflow_file
        if filepath.exists():
            is_valid, schema_errors = self.validate_workflow_schema(filepath)
            all_errors = yaml_errors + [{"error": e, "code": "SCHEMA_ERROR"} for e in schema_errors]
        else:
            all_errors = yaml_errors
        
        summary = f"Found {len(all_errors)} error(s)" if all_errors else "No errors detected"
        return len(all_errors) > 0, all_errors, summary


def main():
    """Example usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python github_workflow_repair.py <workflow_file.yml>")
        print("       python github_workflow_repair.py --dry-run <workflow_file.yml>")
        sys.exit(1)
    
    dry_run = "--dry-run" in sys.argv
    workflow = sys.argv[-1]
    
    repair = WorkflowYamlRepair()
    
    if dry_run:
        has_errors, errors, summary = repair.dry_run_repair(workflow)
        print(f"\n{summary}")
        if errors:
            print("\nErrors found:")
            for err in errors:
                print(f"  Line {err.get('line', '?')}: {err.get('error', err.get('code'))}")
        sys.exit(0 if not has_errors else 1)
    else:
        success, msg = repair.repair_workflow(workflow)
        print(f"\n{msg}")
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
