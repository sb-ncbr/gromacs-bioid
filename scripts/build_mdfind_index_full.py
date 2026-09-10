#!/usr/bin/env python3
"""
Build complete mdfind backup index with pagination to bypass 10K row limit.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import time

DB_READONLY_SCRIPT = Path('/home/tomsko/work/bat3/validation/example_mdfind/db_readonly.py')
OUTPUT_DIR = Path('/home/tomsko/work/bat3/validation/data')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / 'mdfind_backup_index_full.json'

BATCH_SIZE = 5000  # Keep under 10K limit

def export_query_paginated(query: str, temp_dir: Path, prefix: str) -> list:
    """Export query results in batches and combine"""
    all_results = []
    offset = 0
    batch_num = 0
    
    while True:
        batch_file = temp_dir / f'{prefix}_batch_{batch_num}.json'
        
        paginated_query = f"{query} OFFSET {offset} LIMIT {BATCH_SIZE}"
        
        result = subprocess.run(
            [sys.executable, str(DB_READONLY_SCRIPT), 
             '-q', paginated_query, 
             '--export', str(batch_file),
             '--no-confirm'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"  ERROR batch {batch_num}: {result.stderr}")
            break
        
        # Read batch
        try:
            with open(batch_file) as f:
                batch_data = json.load(f)
            
            if not batch_data:
                break
            
            all_results.extend(batch_data)
            print(f"  Batch {batch_num}: {len(batch_data)} rows (offset {offset})")
            
            if len(batch_data) < BATCH_SIZE:
                break  # Last batch
            
            offset += BATCH_SIZE
            batch_num += 1
            time.sleep(0.5)  # Be nice to the database
            
        except Exception as e:
            print(f"  ERROR reading batch {batch_num}: {e}")
            break
    
    return all_results

def main():
    print("=" * 80)
    print("Building COMPLETE mdfind backup index (with pagination)")
    print("=" * 80)
    
    temp_dir = Path('/tmp/mdfind_index_full')
    temp_dir.mkdir(exist_ok=True)
    
    # Step 1: Export all datasets
    print("\n[1/3] Exporting all datasets...")
    datasets = export_query_paginated("""
        SELECT 
            dataset_id,
            dataset_origin,
            title,
            author,
            description,
            doi,
            date_creation,
            license,
            dataset_url
        FROM datasets
        ORDER BY dataset_id
    """, temp_dir, 'datasets')
    print(f"  ✓ Total: {len(datasets)} datasets")
    
    # Step 2: Export all files with URLs
    print("\n[2/3] Exporting all files with URLs...")
    files = export_query_paginated("""
        SELECT 
            f.file_id,
            f.dataset_id,
            f.file_name as filename,
            f.file_type,
            f.file_url as s3_url,
            f.file_md5 as md5,
            f.file_size as size_bytes
        FROM files f
        WHERE f.file_url IS NOT NULL
        ORDER BY f.dataset_id, f.file_name
    """, temp_dir, 'files')
    print(f"  ✓ Total: {len(files)} files")
    
    # Step 3: Build index structure
    print("\n[3/3] Building index structure...")
    datasets_dict = {}
    
    for ds in datasets:
        datasets_dict[ds['dataset_id']] = {
            'dataset_id': ds['dataset_id'],
            'dataset_origin': ds.get('dataset_origin'),
            'title': ds.get('title'),
            'author': ds.get('author'),
            'description': ds.get('description'),
            'doi': ds.get('doi'),
            'date_creation': ds.get('date_creation'),
            'license': ds.get('license'),
            'dataset_url': ds.get('dataset_url'),
            'files': []
        }
    
    # Add files to datasets
    for file in files:
        dataset_id = file['dataset_id']
        if dataset_id in datasets_dict:
            datasets_dict[dataset_id]['files'].append({
                'file_id': file['file_id'],
                'filename': file['filename'],
                'file_type': file.get('file_type'),
                's3_url': file['s3_url'],
                'md5': file.get('md5'),
                'size_bytes': file.get('size_bytes')
            })
    
    datasets_list = list(datasets_dict.values())
    datasets_with_files = sum(1 for d in datasets_list if len(d['files']) > 0)
    total_files = sum(len(d['files']) for d in datasets_list)
    
    # Build final index
    index = {
        'built_at': datetime.now().isoformat(),
        'source': 'mdfind PostgreSQL database (complete dump)',
        'connection': 'db.mdfind.dyn.cloud.e-infra.cz:5432/mydb',
        'notes': 'One-time build. No refresh scheduled. mdfind is backup for MDDB.',
        'stats': {
            'total_datasets': len(datasets_list),
            'datasets_with_files': datasets_with_files,
            'total_files': total_files
        },
        'url_patterns': {
            'mddbr': 'https://mmb.mddbr.eu/api/rest/v1/projects/{dataset_id}/files/{filename}',
            'zenodo': 'https://zenodo.org/api/records/{record_id}/files/{filename}/content',
            'osf': 'https://osf.io/download/{file_id}/',
            'figshare': 'https://ndownloader.figshare.com/...'
        },
        'datasets': datasets_list
    }
    
    # Write index
    print(f"\nWriting index to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(index, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 80)
    print("✓ Index built successfully!")
    print("=" * 80)
    print(f"\nOutput: {OUTPUT_FILE}")
    print(f"\nStatistics:")
    print(f"  Total datasets: {len(datasets_list):,}")
    print(f"  Datasets with files: {datasets_with_files:,}")
    print(f"  Total files: {total_files:,}")
    
    # URL pattern breakdown
    url_patterns = defaultdict(int)
    for ds in datasets_list:
        for file in ds['files']:
            url = file.get('s3_url', '')
            if 'mmb.mddbr.eu' in url or 'jsc.mddbr.eu' in url:
                url_patterns['MDDBR (mmb/jsc.mddbr.eu)'] += 1
            elif 'zenodo.org' in url:
                url_patterns['Zenodo'] += 1
            elif 'osf.io' in url:
                url_patterns['OSF'] += 1
            elif 'ndownloader' in url:
                url_patterns['Figshare'] += 1
            else:
                url_patterns['Other'] += 1
    
    print(f"\nURL patterns:")
    for pattern, count in sorted(url_patterns.items(), key=lambda x: -x[1]):
        pct = (count / total_files * 100) if total_files > 0 else 0
        print(f"  {pattern:30} {count:8,} files ({pct:5.1f}%)")
    
    # File size
    file_size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    print(f"\nIndex file size: {file_size_mb:.1f} MB")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    print("\n✓ Done!")
    print("=" * 80)

if __name__ == '__main__':
    main()
