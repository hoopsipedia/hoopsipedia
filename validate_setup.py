#!/usr/bin/env python3
"""
Validate that all scraper components are properly set up and ready to run.
"""

import json
import sys
from pathlib import Path


def check_file_exists(path: Path, description: str) -> bool:
    """Check if a required file exists."""
    exists = path.exists()
    status = "✓" if exists else "✗"
    size_info = f" ({path.stat().st_size:,} bytes)" if exists else ""
    print(f"  {status} {description:40} {path.name}{size_info}")
    return exists


def check_json_valid(path: Path, description: str) -> bool:
    """Check if a JSON file is valid."""
    if not path.exists():
        print(f"  ✗ {description:40} (file not found)")
        return False

    try:
        with open(path) as f:
            data = json.load(f)
        print(f"  ✓ {description:40} ({len(data)} entries)")
        return True
    except json.JSONDecodeError as e:
        print(f"  ✗ {description:40} (invalid JSON: {e})")
        return False


def check_python_file(path: Path, description: str) -> bool:
    """Check if a Python file is syntactically valid."""
    if not path.exists():
        print(f"  ✗ {description:40} (file not found)")
        return False

    try:
        with open(path) as f:
            compile(f.read(), path.name, 'exec')
        lines = path.stat().st_size
        print(f"  ✓ {description:40} (syntactically valid)")
        return True
    except SyntaxError as e:
        print(f"  ✗ {description:40} (syntax error: {e})")
        return False


def main():
    """Main validation function."""
    print("="*70)
    print("COLLEGE BASKETBALL SCRAPER - SETUP VALIDATION")
    print("="*70)

    base_dir = Path(__file__).parent
    checks = {
        'required': [],
        'optional': [],
    }

    print("\n1. REQUIRED PYTHON SCRIPTS")
    print("-" * 70)
    checks['required'].append(check_python_file(
        base_dir / 'compile_history.py',
        'Main compiler script'
    ))
    checks['required'].append(check_python_file(
        base_dir / 'test_scraper.py',
        'Test suite'
    ))

    print("\n2. OPTIONAL UTILITY SCRIPTS")
    print("-" * 70)
    checks['optional'].append(check_python_file(
        base_dir / 'generate_slug_mapping.py',
        'Slug mapping generator'
    ))
    checks['optional'].append(check_python_file(
        base_dir / 'check_references.py',
        'Reference checker'
    ))
    checks['optional'].append(check_python_file(
        base_dir / 'validate_setup.py',
        'Setup validator (this file)'
    ))

    print("\n3. REQUIRED DATA FILES")
    print("-" * 70)
    checks['required'].append(check_json_valid(
        base_dir / 'slug_mapping.json',
        'ESPN ID → slug mapping'
    ))
    checks['required'].append(check_file_exists(
        base_dir / 'data.json',
        'Team data source'
    ))

    print("\n4. DOCUMENTATION")
    print("-" * 70)
    checks['optional'].append(check_file_exists(
        base_dir / 'QUICK_START.md',
        'Quick start guide'
    ))
    checks['optional'].append(check_file_exists(
        base_dir / 'SCRAPER_SETUP.md',
        'Detailed setup guide'
    ))
    checks['optional'].append(check_file_exists(
        base_dir / 'README_SCRAPER.md',
        'README documentation'
    ))

    print("\n5. DEPENDENCIES CHECK")
    print("-" * 70)
    deps_ok = True
    try:
        import requests
        print(f"  ✓ requests module           (version {requests.__version__})")
    except ImportError:
        print("  ✗ requests module           (NOT INSTALLED)")
        deps_ok = False

    try:
        import bs4
        print(f"  ✓ beautifulsoup4 module    (version {bs4.__version__})")
    except ImportError:
        print("  ✗ beautifulsoup4 module    (NOT INSTALLED)")
        deps_ok = False

    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)

    required_ok = all(checks['required'])
    optional_ok = all(checks['optional'])
    all_ok = required_ok and deps_ok

    print(f"Required components: {'✓ PASS' if required_ok else '✗ FAIL'}")
    print(f"Optional components: {'✓ PASS' if optional_ok else '⚠ PARTIAL'}")
    print(f"Dependencies:        {'✓ PASS' if deps_ok else '✗ FAIL'}")
    print(f"\nOverall status:      {'✓ READY TO RUN' if all_ok else '✗ SETUP INCOMPLETE'}")

    if not required_ok:
        print("\n⚠ Missing required components. Cannot proceed.")
        print("  Install with: pip install requests beautifulsoup4")
        return 1

    if not all_ok:
        print("\n⚠ Some optional components missing, but scraper should work.")
        return 1 if not deps_ok else 0

    print("\n✓ All checks passed! Ready to run:")
    print("  1. python3 test_scraper.py")
    print("  2. python3 compile_history.py")

    return 0


if __name__ == '__main__':
    sys.exit(main())
