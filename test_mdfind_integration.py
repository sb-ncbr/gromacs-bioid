#!/usr/bin/env python3
"""Test mdfind fallback in realistic scenario"""

import sys
sys.path.insert(0, '/home/tomsko/work/bat3')

from pathlib import Path
from validation.src.db import get_session, MddbEntry, MddbFile
from validation.src.downloader import download_files, MdfindIndex
import tempfile

def test_mdfind_fallback():
    """Test downloading a file that exists in mdfind"""
    
    print("=" * 80)
    print("MDFIND FALLBACK INTEGRATION TEST")
    print("=" * 80)
    
    # Get a test entry that's in mdfind
    session = get_session()
    
    # Find an entry known to be in mdfind (e.g., A0001)
    entry = session.query(MddbEntry).filter(
        MddbEntry.project_local_accession == 'A0001'
    ).first()
    
    if not entry:
        print("❌ Entry A0001 not found in local DB")
        return False
    
    print(f"\n✓ Found entry: {entry.project_local_accession}")
    print(f"  Title: {entry.project_name[:60] if entry.project_name else 'N/A'}...")
    
    # Get files for this entry
    files = session.query(MddbFile).filter(MddbFile.entry_id == entry.id).all()
    
    if not files:
        print("❌ No files found for entry")
        return False
    
    print(f"✓ Found {len(files)} files")
    
    # Show first file
    first_file = files[0]
    print(f"\n  First file:")
    print(f"    Filename: {first_file.filename}")
    print(f"    URL: {first_file.url[:80] if first_file.url else 'N/A'}...")
    print(f"    MD5: {first_file.md5 or 'N/A'}")
    
    # Test download
    print(f"\nAttempting download...")
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # This should either:
            # 1. Download from MDDBR (if available)
            # 2. Fall back to mdfind S3 (if MDDBR down)
            downloaded = download_files(
                files=[first_file],
                dest_dir=tmpdir,
                verify=True,
                retry=2,
                use_mdfind_fallback=True,
                dataset_id=entry.project_local_accession
            )
            
            if downloaded:
                print(f"✓ Download successful!")
                print(f"  Saved to: {downloaded[0]}")
                print(f"  Size: {downloaded[0].stat().st_size / 1024:.1f} KB")
                return True
            else:
                print("❌ Download returned empty list")
                return False
                
        except Exception as e:
            print(f"❌ Download failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = test_mdfind_fallback()
    sys.exit(0 if success else 1)
