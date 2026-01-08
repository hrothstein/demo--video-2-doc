#!/usr/bin/env python3
"""Compare V1 and V2 outputs"""

import re

def extract_frame_refs(text):
    """Extract all frame references"""
    return re.findall(r'\[FRAME:\d+\]', text)

def analyze_output(file_path, version):
    """Analyze an output file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    title = lines[0] if lines else "No title"
    
    # Count steps
    steps = [line for line in lines if line.startswith('### Step')]
    
    # Extract frame references
    frame_refs = extract_frame_refs(content)
    invalid_refs = [ref for ref in frame_refs if int(re.search(r'\d+', ref).group()) > 18]
    valid_refs = [ref for ref in frame_refs if int(re.search(r'\d+', ref).group()) <= 18]
    
    return {
        'version': version,
        'title': title,
        'step_count': len(steps),
        'total_frame_refs': len(frame_refs),
        'valid_frame_refs': len(valid_refs),
        'invalid_frame_refs': len(invalid_refs),
        'invalid_refs_list': invalid_refs[:10]  # First 10
    }

print("=" * 80)
print("COMPARISON: V1 vs V2 Updated")
print("=" * 80)
print()

v1 = analyze_output('tmp/test_output_v1.md', 'V1')
v2 = analyze_output('tmp/test_output_v2_updated.md', 'V2 Updated')

print(f"V1 Output:")
print(f"  Title: {v1['title']}")
print(f"  Steps: {v1['step_count']}")
print(f"  Frame references: {v1['total_frame_refs']} (all in text, not tags)")
print()

print(f"V2 Updated Output:")
print(f"  Title: {v2['title']}")
print(f"  Steps: {v2['step_count']}")
print(f"  Frame references: {v2['total_frame_refs']} total")
print(f"    Valid (1-18): {v2['valid_frame_refs']}")
print(f"    Invalid (>18): {v2['invalid_frame_refs']}")
if v2['invalid_refs_list']:
    print(f"    Invalid examples: {', '.join(v2['invalid_refs_list'])}")
print()

print("=" * 80)
print("KEY DIFFERENCES:")
print("=" * 80)
print(f"1. Title: V1 focuses on 'Implement an API Specification', V2 on 'Creating a Mule Project'")
print(f"2. Steps: V1 has {v1['step_count']} steps, V2 has {v2['step_count']} steps")
print(f"3. Detail: V1 includes verification steps (Step 12, 13)")
print(f"4. Frame refs: V2 has {v2['invalid_frame_refs']} invalid frame references that need fixing")

