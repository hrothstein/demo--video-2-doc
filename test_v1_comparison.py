#!/usr/bin/env python3
"""Test script to run V1 analyzer for comparison"""

import sys
import os
from processor import extract_frames
from analyzer import analyze_frames

def test_doctest_video_v1():
    """Test the doctest video with V1 prompt"""
    video_path = "tmp/doctest.mp4"
    
    if not os.path.exists(video_path):
        print(f"Error: Video not found at {video_path}")
        return
    
    print("=" * 80)
    print("Testing doctest video with V1 prompt")
    print("=" * 80)
    print()
    
    # Step 1: Extract frames
    print("Step 1: Extracting frames...")
    frame_paths = extract_frames(video_path)
    print(f"  Extracted {len(frame_paths)} frames")
    
    # Step 2: Analyze with GPT-4o (V1 - no key frame selection)
    print("Step 2: Analyzing with GPT-4o (V1 prompt)...")
    print("  This may take 30-60 seconds...")
    print()
    
    markdown_content = analyze_frames(frame_paths)
    
    print("=" * 80)
    print("MARKDOWN OUTPUT (V1):")
    print("=" * 80)
    print()
    print(markdown_content)
    print()
    print("=" * 80)
    print("Test complete!")
    print("=" * 80)
    
    # Save to file for comparison
    output_file = "tmp/test_output_v1.md"
    with open(output_file, "w") as f:
        f.write(markdown_content)
    print(f"\nOutput saved to: {output_file}")

if __name__ == "__main__":
    test_doctest_video_v1()

