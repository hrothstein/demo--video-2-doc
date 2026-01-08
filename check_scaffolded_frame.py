#!/usr/bin/env python3
"""Check which frames show scaffolded project and why they're being missed"""

import os
from processor import extract_frames
from frame_selector import select_key_frames

video_path = "tmp/doctest.mp4"

print("=" * 80)
print("CHECKING SCAFFOLDED FRAME SELECTION")
print("=" * 80)
print()

# Extract frames
frame_paths = extract_frames(video_path)
print(f"Total frames: {len(frame_paths)}")
print()

# Select key frames
key_frame_paths = select_key_frames(frame_paths, max_embed=18)
selected_indices = set()
for kf_path in key_frame_paths:
    basename = os.path.basename(kf_path)
    frame_num = int(basename.replace('frame_', '').replace('.jpg', ''))
    selected_indices.add(frame_num)

print("Frames that show scaffolded/completed project (typically frames 40-50):")
print()
for i in range(40, min(51, len(frame_paths) + 1)):
    frame_name = f"frame_{i:04d}.jpg"
    frame_path = os.path.join(os.path.dirname(frame_paths[0]), frame_name)
    is_selected = i in selected_indices
    status = "✓ SELECTED" if is_selected else "✗ MISSED"
    
    # Check if frame exists
    exists = os.path.exists(frame_path)
    if exists:
        print(f"  Frame {i}: {status}")
    else:
        print(f"  Frame {i}: NOT FOUND")

print()
print("=" * 80)
print("ANALYSIS:")
print("=" * 80)
print(f"Selected frames in range 40-50: {[i for i in range(40, 51) if i in selected_indices]}")
print(f"Missing frames in range 40-50: {[i for i in range(40, 51) if i not in selected_indices]}")
print()

# The scaffolded frame is likely around frame 40-46 based on typical workflow
# Let's check if we're missing frames in that critical range
critical_range = list(range(40, 47))
missing_critical = [i for i in critical_range if i not in selected_indices]
if missing_critical:
    print(f"⚠️  CRITICAL: Missing frames {missing_critical} which likely show scaffolded project!")
    print("   These frames should be prioritized for selection.")
else:
    print("✓ All critical frames (40-46) are selected")

