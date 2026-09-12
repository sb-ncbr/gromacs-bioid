#!/usr/bin/env python3
"""Debug test - check if mdfind fallback is being called"""

import sys
import logging
sys.path.insert(0, '/home/tomsko/work/bat3')

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

from validation.src.downloader import MdfindIndex, download_file, DownloadError
from validation.src.db import get_session, MddbFile
import tempfile
from pathlib import Path

print("=" * 80)
print("DEBUG: Testing mdfind fallback trigger")
print("=" * 80)

# Test 1: Check if index loads
print("\n[TEST 1] Loading mdfind index...")
index = MdfindIndex.get_instance()
if index:
    print("✓ Index loaded")
    stats = index.get_stats()
    print(f"  Files: {stats['total_files']:,}")
else:
    print("❌ Index NOT loaded")
    sys.exit(1)

# Test 2: Check if a specific file is in mdfind
print("\n[TEST 2] Checking if A0001 files are in mdfind...")
test_dataset = 'A0001'
if index.has_dataset(test_dataset):
    files = index.get_files(test_dataset)
    print(f"✓ Found {len(files)} files for {test_dataset}")
    if files:
        print(f"  First file: {files[0]['filename']}")
        print(f"  S3 URL: {files[0]['s3_url'][:80]}...")
else:
    print(f"❌ Dataset {test_dataset} NOT in mdfind")

# Test 3: Try to trigger fallback manually
print("\n[TEST 3] Testing fallback logic...")
session = get_session()

# Get a file record from DB
file_record = session.query(MddbFile).filter(
    MddbFile.entry_id == 1  # A0001 should be entry 1
).first()

if file_record:
    print(f"✓ Got file record: {file_record.filename}")
    print(f"  URL: {file_record.url[:80] if file_record.url else 'N/A'}...")
    
    # Try to download - this should fail and trigger fallback
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\nAttempting download (will timeout if MDDBR down)...")
        try:
            # Set a short timeout for testing
            import requests
            original_get = requests.get
            
            def quick_timeout_get(*args, **kwargs):
                kwargs['timeout'] = 3  # 3 second timeout for testing
                return original_get(*args, **kwargs)
            
            requests.get = quick_timeout_get
            
            path = download_file(file_record, Path(tmpdir), retry=1)
            print(f"✓ Download succeeded from primary: {path}")
            
        except DownloadError as e:
            print(f"✓ Primary failed (expected): {e}")
            print("  → Should trigger mdfind fallback now...")
            
            # The fallback should happen in download_files, not download_file
            # This is expected behavior
        finally:
            requests.get = original_get
else:
    print("❌ No file record found")

print("\n" + "=" * 80)
print("DEBUG TEST COMPLETE")
print("=" * 80)
