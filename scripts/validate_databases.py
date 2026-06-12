#!/usr/bin/env python3
"""
Validate downloaded BLAST databases.

Checks that each expected database exists and is readable by blastdbcmd.
Prints a summary table with database info and disk usage.

Usage:
    ./validate_databases.py [--target-dir DIR] [--databases LIST]

Options:
    --target-dir DIR   Directory containing database symlinks (default: /app/databases)
    --databases LIST   Comma-separated list of database names (default: nr,swissprot,pdbaa,pdbnt,core_nt,nt)
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate downloaded BLAST databases"
    )
    parser.add_argument(
        "--target-dir",
        default="/app/databases",
        help="Directory containing database symlinks (default: /app/databases)"
    )
    parser.add_argument(
        "--databases",
        default="nr,swissprot,pdbaa,pdbnt,core_nt,nt",
        help="Comma-separated list of database names (default: nr,swissprot,pdbaa,pdbnt,core_nt,nt)"
    )
    return parser.parse_args()


def get_disk_usage(path):
    """Get disk usage for a path using du -sh."""
    try:
        result = subprocess.run(
            ["du", "-sh", str(path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split()
            return parts[0] if parts else "unknown"
    except Exception:
        pass
    return "unknown"


def parse_blastdb_info(output):
    """Parse blastdbcmd -info output."""
    info = {
        "name": "",
        "sequences": 0,
        "residues": 0,
        "date": "",
        "description": "",
        "longest": 0,
        "shortest": 0
    }
    
    lines = output.strip().split("\n")
    for line in lines:
        line = line.strip()
        
        # Database name
        match = re.match(r"^Database:\s*(.+)$", line, re.IGNORECASE)
        if match:
            info["name"] = match.group(1).strip()
            continue
        
        # Number of sequences
        match = re.match(r"^\s*(\d+(?:,\d+)*)\s+sequences;", line, re.IGNORECASE)
        if match:
            info["sequences"] = int(match.group(1).replace(",", ""))
            continue
        
        # Total residues/bases
        match = re.match(r"^\s*(\d+(?:,\d+)*)\s+(?:total|combined)\s+(?:residues|bases)", line, re.IGNORECASE)
        if match:
            info["residues"] = int(match.group(1).replace(",", ""))
            continue
        
        # Date
        match = re.match(r"^\s*Date:\s*(.+)$", line, re.IGNORECASE)
        if match:
            info["date"] = match.group(1).strip()
            continue
        
        # Description (often on a line by itself after "Database:")
        if not info["description"] and line and not line.startswith(("!", "#", "Database:", "Number", "Total", "Date", "Longest", "Shortest")):
            # Check if it looks like a description
            if len(line) > 10 and not line[0].isdigit():
                info["description"] = line
                continue
        
        # Longest sequence
        match = re.match(r"^\s*Longest\s+(?:sequence|title):\s*(\d+)", line, re.IGNORECASE)
        if match:
            info["longest"] = int(match.group(1))
            continue
        
        # Shortest sequence
        match = re.match(r"^\s*Shortest\s+(?:sequence|title):\s*(\d+)", line, re.IGNORECASE)
        if match:
            info["shortest"] = int(match.group(1))
            continue
    
    return info


def validate_database(db_name, target_dir):
    """Validate a single database."""
    result = {
        "name": db_name,
        "valid": False,
        "error": "",
        "info": None,
        "size": "unknown"
    }
    
    db_path = Path(target_dir) / db_name
    
    # Check if path exists (could be symlink or directory)
    if not db_path.exists():
        result["error"] = "Path does not exist"
        return result
    
    # Get disk usage
    result["size"] = get_disk_usage(db_path)
    
    # Run blastdbcmd -info
    try:
        cmd_result = subprocess.run(
            ["blastdbcmd", "-db", str(db_path), "-info"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if cmd_result.returncode != 0:
            stderr_msg = cmd_result.stderr.strip() if cmd_result.stderr else "(no stderr)"
            result["error"] = f"blastdbcmd failed: {stderr_msg}"
            return result
        
        # Parse the output
        result["info"] = parse_blastdb_info(cmd_result.stdout)
        result["valid"] = True
        
    except subprocess.TimeoutExpired:
        result["error"] = "blastdbcmd timed out"
    except FileNotFoundError:
        result["error"] = "blastdbcmd not found in PATH"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def format_number(n):
    """Format a number with thousand separators."""
    return f"{n:,}"


def format_residues(n):
    """Format residue count in M (millions)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    else:
        return str(n)


def print_table(results):
    """Print validation results as a table."""
    # Header
    print(f"{'Database':<15} {'Sequences':>12} {'Residues':>10} {'Size':>8} {'Valid':>7} {'Info'}")
    print("-" * 80)
    
    for r in results:
        valid_str = "YES" if r["valid"] else "NO"
        
        if r["valid"] and r["info"]:
            seq_str = format_number(r["info"]["sequences"])
            res_str = format_residues(r["info"]["residues"])
            info_str = r["info"].get("description", "")[:40]
        else:
            seq_str = "-"
            res_str = "-"
            info_str = r["error"][:40] if r["error"] else "Unknown error"
        
        print(f"{r['name']:<15} {seq_str:>12} {res_str:>10} {r['size']:>8} {valid_str:>7} {info_str}")
    
    print("-" * 80)


def main():
    args = parse_args()
    
    target_dir = args.target_dir
    databases = [db.strip() for db in args.databases.split(",")]
    
    # Check target directory exists
    if not Path(target_dir).exists():
        print(f"ERROR: Target directory does not exist: {target_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Validating BLAST databases in: {target_dir}")
    print(f"Databases to check: {', '.join(databases)}")
    print()
    
    # Validate each database
    results = []
    for db_name in databases:
        result = validate_database(db_name, target_dir)
        results.append(result)
    
    # Print results table
    print_table(results)
    
    # Summary
    valid_count = sum(1 for r in results if r["valid"])
    total_count = len(results)
    
    print()
    print(f"Summary: {valid_count}/{total_count} databases valid")
    
    # Exit with error if any database is invalid
    if valid_count < total_count:
        print("\nWARNING: Some databases are invalid or missing!", file=sys.stderr)
        sys.exit(1)
    
    print("\nAll databases validated successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
