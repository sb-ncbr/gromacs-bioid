#!/usr/bin/env python3
"""
Build mdfind backup index from PostgreSQL database.
One-time build - no refresh needed.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Paths
DB_READONLY_SCRIPT = Path('/home/tomsko/work/bat3/validation/example_mdfind/db_readonly.py')
OUTPUT_DIR = Path('/home/tomsko/work/bat3/validation/data')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / 'mdfind_backup_index.json'

def run_query(query: str) -> list:
    """Execute query via db_readonly.py and return JSON results"""
    result = subprocess.run(
        [sys.executable, str(DB_READONLY_SCRIPT), '-q', query, '--no-confirm'],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"ERROR: db_readonly.py failed: {result.stderr}")
        sys.exit(1)
    
    # Parse the output - it's in table format, need to extract data
    # For now, use --export to get JSON
    return []

def export_query(query: str, output_file: Path) -> list:
    """Export query results to JSON file"""
    result = subprocess.run(
        [sys.executable, str(DB_READONLY_SCRIPT), 
         '-q', query, 
         '--export', str(output_file),
         '--no-confirm'],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        return []
    
    # Read exported JSON
    try:
        with open(output_file) as f:
            return json.load(f)
    except:
        return []

def main():
    print("=" * 80)
    print("Building mdfind backup index")
    print("=" * 80)
    
    temp_dir = Path('/tmp/mdfind_index_build')
    temp_dir.mkdir(exist_ok=True)
    
    # Step 1: Export datasets
    print("\n[1/4] Exporting datasets...")
    datasets_file = temp_dir / 'datasets.json'
    datasets = export_query("""
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
    """, datasets_file)
    print(f"  ✓ Exported {len(datasets)} datasets")
    
    # Step 2: Export files with URLs
    print("\n[2/4] Exporting files with URLs...")
    files_file = temp_dir / 'files.json'
    files = export_query("""
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
    """, files_file)
    print(f"  ✓ Exported {len(files)} files with URLs")
    
    # Step 3: Group files by dataset
    print("\n[3/4] Building index structure...")
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
    files_with_urls = 0
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
            files_with_urls += 1
    
    # Convert to list
    datasets_list = list(datasets_dict.values())
    
    # Calculate stats
    datasets_with_files = sum(1 for d in datasets_list if len(d['files']) > 0)
    total_files = sum(len(d['files']) for d in datasets_list)
    
    # Step 4: Build final index
    print("\n[4/4] Writing index file...")
    index = {
        'built_at': datetime.now().isoformat(),
        'source': 'mdfind PostgreSQL database',
        'connection': 'db.mdfind.dyn.cloud.e-infra.cz:5432/mydb',
        'stats': {
            'total_datasets': len(datasets_list),
            'datasets_with_files': datasets_with_files,
            'total_files': total_files,
            'files_with_urls': files_with_urls
        },
        'url_patterns': {
            'mddbr': 'https://mmb.mddbr.eu/api/rest/v1/projects/{dataset_id}/files/{filename}',
            'zenodo': 'https://zenodo.org/api/records/{record_id}/files/{filename}/content',
            'osf': 'https://osf.io/download/{file_id}/',
            'other': 'Various (see index for exact URLs)'
        },
        'datasets': datasets_list
    }
    
    # Write index
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(index, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 80)
    print("Index built successfully!")
    print("=" * 80)
    print(f"\nOutput file: {OUTPUT_FILE}")
    print(f"\nStatistics:")
    print(f"  Total datasets: {len(datasets_list):,}")
    print(f"  Datasets with files: {datasets_with_files:,}")
    print(f"  Total files: {total_files:,}")
    print(f"  Files with URLs: {files_with_urls:,}")
    print(f"\nURL patterns found:")
    
    # Count URL patterns
    url_patterns = defaultdict(int)
    for ds in datasets_list:
        for file in ds['files']:
            url = file.get('s3_url', '')
            if 'mmb.mddbr.eu' in url:
                url_patterns['mmb.mddbr.eu (MDDBR)'] += 1
            elif 'zenodo.org' in url:
                url_patterns['zenodo.org'] += 1
            elif 'osf.io' in url:
                url_patterns['osf.io'] += 1
            elif 'ndownloader' in url:
                url_patterns['ndownloader (Figshare)'] += 1
            else:
                url_patterns['other'] += 1
    
    for pattern, count in sorted(url_patterns.items(), key=lambda x: -x[1]):
        print(f"  {pattern}: {count:,} files")
    
    # Cleanup temp files
    import shutil
    shutil.rmtree(temp_dir)
    
    print("\n✓ Done!")
    print("=" * 80)

if __name__ == '__main__':
    main()
