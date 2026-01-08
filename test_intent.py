#!/usr/bin/env python3
"""Test script to compare intent capture with updated V2 prompt"""

import sys
import os
from processor import extract_frames
from frame_selector import select_key_frames
from analyzer import analyze_frames_v2

def test_doctest_video():
    """Test the doctest video with updated prompt"""
    video_path = "tmp/doctest.mp4"
    
    if not os.path.exists(video_path):
        print(f"Error: Video not found at {video_path}")
        return
    
    print("=" * 80)
    print("Testing doctest video with updated V2 prompt")
    print("=" * 80)
    print()
    
    # Step 1: Extract frames
    print("Step 1: Extracting frames...")
    frame_paths = extract_frames(video_path)
    print(f"  Extracted {len(frame_paths)} frames")
    
    # Step 2: Select key frames
    print("Step 2: Selecting key frames...")
    key_frame_paths = select_key_frames(frame_paths, max_embed=18)
    print(f"  Selected {len(key_frame_paths)} key frames")
    
    # Step 3: Analyze with GPT-4o
    print("Step 3: Analyzing with GPT-4o (updated prompt)...")
    print("  This may take 30-60 seconds...")
    print()
    
    markdown_content = analyze_frames_v2(frame_paths, key_frame_paths)
    
    print("=" * 80)
    print("MARKDOWN OUTPUT:")
    print("=" * 80)
    print()
    print(markdown_content)
    print()
    print("=" * 80)
    print("Test complete!")
    print("=" * 80)
    
    # Save to file for comparison
    output_file = "tmp/test_output_v2_updated.md"
    with open(output_file, "w") as f:
        f.write(markdown_content)
    print(f"\nOutput saved to: {output_file}")

if __name__ == "__main__":
    test_doctest_video()

