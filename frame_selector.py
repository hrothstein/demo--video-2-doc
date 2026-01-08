"""
Select which frames to embed in the PDF.
Not every frame needs to be included — pick frames that show distinct steps.
"""

import os
from PIL import Image
import numpy as np


def select_key_frames(frame_paths: list[str], max_embed: int = 18) -> list[str]:
    """
    Select key frames for PDF embedding with intent-aware heuristics.
    
    Strategy:
    1. Always include first and last frame
    2. Use image difference detection to find frames with significant UI changes
    3. Detect "stable result" frames (frames that stay similar after a change)
    4. Boost frames in last 30% (often show final outcomes)
    5. Ensure distribution throughout video
    6. Cap at max_embed frames
    
    Returns list of frame paths to embed.
    """
    if len(frame_paths) <= max_embed:
        return frame_paths
    
    # Calculate difference scores between consecutive frames
    differences = []
    images = []
    prev_img = None
    
    for path in frame_paths:
        if not os.path.exists(path):
            differences.append(0)
            images.append(None)
            continue
            
        try:
            img = Image.open(path).convert('L').resize((320, 180))  # Grayscale, small
            img_array = np.array(img)
            images.append(img_array)
            
            if prev_img is not None:
                diff = np.mean(np.abs(img_array - prev_img))
                differences.append(diff)
            else:
                differences.append(0)
            
            prev_img = img_array
        except Exception:
            differences.append(0)
            images.append(None)
    
    # Detect "stable result" frames: frames that stay similar for multiple frames after a change
    # This indicates a completed state/outcome
    stability_scores = []
    stability_window = 3  # Check if frame stays similar for next N frames
    
    for i in range(len(frame_paths)):
        if images[i] is None:
            stability_scores.append(0)
            continue
            
        # Check if this frame is followed by similar frames (stable result)
        if i + stability_window < len(frame_paths):
            future_diffs = []
            for j in range(1, stability_window + 1):
                if images[i + j] is not None:
                    future_diff = np.mean(np.abs(images[i] - images[i + j]))
                    future_diffs.append(future_diff)
            
            if future_diffs:
                # Low future differences = stable result frame
                avg_future_diff = np.mean(future_diffs)
                # Invert: lower future diff = higher stability score
                stability_score = max(0, 50 - avg_future_diff * 10)
                stability_scores.append(stability_score)
            else:
                stability_scores.append(0)
        else:
            # Last frames get stability boost (they're likely outcomes)
            stability_scores.append(30)
    
    # Combine difference scores with stability scores
    combined_scores = []
    for i in range(len(frame_paths)):
        diff_score = differences[i] if i < len(differences) else 0
        stability_score = stability_scores[i] if i < len(stability_scores) else 0
        combined_score = diff_score + stability_score
        combined_scores.append((i, combined_score))
    
    # Always include first and last (last frame often shows final result)
    # Also include last 5 frames AND frames in the "completion zone" (last 30%)
    # This is critical - outcome frames are the most important!
    last_frame_idx = len(frame_paths) - 1
    selected_indices = {0}  # Always include first
    
    # Always include last 5 frames (they show final results)
    for i in range(max(0, last_frame_idx - 4), last_frame_idx + 1):
        selected_indices.add(i)
    
    # Also ensure we capture completion/scaffolding frames (typically in last 30% of video)
    # This catches frames that show completed states before the very end
    # Be aggressive here - scaffolded/completion frames are critical!
    completion_zone_start = max(0, int(len(frame_paths) * 0.7))
    # Include every frame in completion zone (except last 5 which are already included)
    # This ensures we don't miss the scaffolded project frame
    for i in range(completion_zone_start, last_frame_idx - 4):  # Don't overlap with last 5
        selected_indices.add(i)
    
    # Boost scores for frames in the last 30% (often show final results/outcomes)
    # Also heavily boost the absolute last frames (last 10%) which almost always show outcomes
    last_30_percent_start = int(len(frame_paths) * 0.7)
    last_10_percent_start = int(len(frame_paths) * 0.9)
    boosted_scores = []
    for idx, score in combined_scores:
        # Heavy boost for last 10% (final outcomes)
        if idx >= last_10_percent_start:
            boosted_scores.append((idx, score * 2.0))
        # Moderate boost for last 30%
        elif idx >= last_30_percent_start:
            boosted_scores.append((idx, score * 1.5))
        else:
            boosted_scores.append((idx, score))
    
    # Sort by boosted scores
    boosted_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Select frames ensuring distribution throughout video
    # Divide video into segments and ensure we get frames from each segment
    num_segments = min(5, max_embed // 3)  # 3-5 segments depending on max_embed
    segment_size = len(frame_paths) // num_segments
    frames_per_segment = max_embed // num_segments
    
    # First pass: ensure distribution
    segment_counts = [0] * num_segments
    for idx, _ in boosted_scores:
        if len(selected_indices) >= max_embed:
            break
        segment = min(idx // segment_size, num_segments - 1)
        # Always prioritize first frame, last 3 frames, and frames in last 10%
        is_priority_frame = (idx == 0 or 
                           idx >= len(frame_paths) - 3 or 
                           idx >= int(len(frame_paths) * 0.9))
        if segment_counts[segment] < frames_per_segment or is_priority_frame:
            selected_indices.add(idx)
            segment_counts[segment] += 1
    
    # Second pass: fill remaining slots with highest-scoring frames
    for idx, _ in boosted_scores:
        if len(selected_indices) >= max_embed:
            break
        if idx not in selected_indices:
            selected_indices.add(idx)
    
    # Return in original order
    return [frame_paths[i] for i in sorted(selected_indices)]

