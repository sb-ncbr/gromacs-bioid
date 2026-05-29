#!/usr/bin/env python3
"""Diagnostic script for RCSB Search API."""

import json
import requests

url = "https://search.rcsb.org/rcsbsearch/v2/query"

payload = {
    "query": {
        "type": "group",
        "logical_operator": "and",
        "nodes": [
            {
                "type": "terminal",
                "service": "structure",
                "parameters": {
                    "value": {"url": "https://files.rcsb.org/download/1ABC.pdb", "format": "pdb"},
                    "similarity_type": "local",
                    "target_search_space": "assembly",
                    "number_of_candidates": 10000
                }
            },
            {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "attribute": "rcsb_entry_info.selected_polymer_entity_types",
                    "operator": "in",
                    "value": ["Protein (only)"]
                }
            }
        ]
    },
    "return_type": "entry"
}

print("=" * 60)
print("REQUEST JSON:")
print("=" * 60)
print(json.dumps(payload, indent=2))
print()

headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print("=" * 60)
    print(f"HTTP STATUS CODE: {response.status_code}")
    print("=" * 60)
    
    if response.status_code == 200:
        data = response.json()
        print("\nRequest succeeded!")
        result_set = data.get("result_set", [])
        if result_set:
            print(f"\nFirst few results:")
            for hit in result_set[:5]:
                identifier = hit.get("identifier", "N/A")
                score = hit.get("score", 0.0)
                print(f"  {identifier}: score={score:.4f}")
        else:
            print("\nNo results returned.")
    else:
        print(f"\nRequest failed with status {response.status_code}")
        print(f"\nResponse text (first 1000 chars):")
        print(response.text[:1000])
        
except requests.exceptions.Timeout:
    print("ERROR: Request timed out after 30 seconds")
except requests.exceptions.RequestException as e:
    print(f"ERROR: Request failed: {e}")
