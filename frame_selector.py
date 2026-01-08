"""
Select which frames to embed in the PDF.
Not every frame needs to be included — pick frames that show distinct steps.
"""

import os
from PIL import Image
import numpy as np


def select_key_frames(frame_paths: list[str], max_embed: int = 10) -> list[str]:
    """
    Select key frames for PDF embedding.
    
    Strategy:
    1. Always include first and last frame
    2. Use image difference detection to find frames with significant UI changes
    3. Cap at max_embed frames
    
    Returns list of frame paths to embed.
    """
    if len(frame_paths) <= max_embed:
        return frame_paths
    
    # Calculate difference scores between consecutive frames
    differences = []
    prev_img = None
    
    for path in frame_paths:
        if not os.path.exists(path):
            differences.append(0)
            continue
            
        try:
            img = Image.open(path).convert('L').resize((320, 180))  # Grayscale, small
            img_array = np.array(img)
            
            if prev_img is not None:
                diff = np.mean(np.abs(img_array - prev_img))
                differences.append(diff)
            else:
                differences.append(0)
            
            prev_img = img_array
        except Exception:
            differences.append(0)
    
    # Select frames with highest difference scores
    indexed_diffs = list(enumerate(differences))
    indexed_diffs.sort(key=lambda x: x[1], reverse=True)
    
    # Always include first and last
    selected_indices = {0, len(frame_paths) - 1}
    
    # Add highest-change frames until we hit max
    for idx, _ in indexed_diffs:
        if len(selected_indices) >= max_embed:
            break
        selected_indices.add(idx)
    
    # Return in original order
    return [frame_paths[i] for i in sorted(selected_indices)]

