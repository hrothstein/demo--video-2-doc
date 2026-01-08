#!/usr/bin/env python3
"""Debug which frames are being selected"""

import os
from processor import extract_frames
from frame_selector import select_key_frames

video_path = "tmp/doctest.mp4"

print("=" * 80)
print("DEBUGGING FRAME SELECTION")
print("=" * 80)
print()

# Extract frames
print("Extracting frames...")
frame_paths = extract_frames(video_path)
print(f"Total frames extracted: {len(frame_paths)}")
print()

# Select key frames
print("Selecting key frames (max_embed=18)...")
key_frame_paths = select_key_frames(frame_paths, max_embed=18)
print(f"Key frames selected: {len(key_frame_paths)}")
print()

# Show which frames were selected
print("Selected frame indices:")
selected_indices = []
for kf_path in key_frame_paths:
    # Extract frame number from path
    basename = os.path.basename(kf_path)
    frame_num = int(basename.replace('frame_', '').replace('.jpg', ''))
    selected_indices.append(frame_num)
    print(f"  Frame {frame_num}: {basename}")

print()
print("=" * 80)
print("ANALYSIS:")
print("=" * 80)
print(f"Total frames: {len(frame_paths)}")
print(f"Selected frames: {len(key_frame_paths)}")
print(f"Last frame number: {len(frame_paths)}")
print(f"Last frame selected: {len(frame_paths) in selected_indices}")
print()

# Check if frames 40-53 are selected (likely where the final result is)
print("Frames 40-53 (likely final result area):")
for i in range(40, min(54, len(frame_paths) + 1)):
    frame_name = f"frame_{i:04d}.jpg"
    frame_path = os.path.join(os.path.dirname(frame_paths[0]), frame_name)
    is_selected = any(frame_name in kf for kf in key_frame_paths)
    status = "✓ SELECTED" if is_selected else "✗ MISSED"
    print(f"  {frame_name}: {status}")

