import subprocess
import os
from dotenv import load_dotenv

load_dotenv()

FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL", 2))
MAX_FRAMES = int(os.getenv("MAX_FRAMES", 50))

def extract_frames(video_path: str) -> list[str]:
    """Extract frames from video at specified interval, downscaled to max 1920px width"""
    
    # Create output directory
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_dir = f"temp/frames/{video_name}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Run ffmpeg with downscaling: fps=1/FRAME_INTERVAL and scale=1920:-1 (maintain aspect ratio)
    result = subprocess.run([
        "ffmpeg", "-i", video_path,
        "-vf", f"fps=1/{FRAME_INTERVAL},scale=1920:-1",
        "-q:v", "2",  # High quality JPEG
        f"{output_dir}/frame_%04d.jpg",
        "-y"  # Overwrite
    ], capture_output=True, text=True)
    
    # Check if ffmpeg failed
    if result.returncode != 0:
        error_msg = result.stderr or "Unknown ffmpeg error"
        raise RuntimeError(f"Frame extraction failed: {error_msg}")
    
    # Get list of frames
    frames = sorted([
        os.path.join(output_dir, f) 
        for f in os.listdir(output_dir) 
        if f.endswith('.jpg')
    ])
    
    # Validate minimum 3 frames
    if len(frames) < 3:
        raise ValueError(f"Video too short. Only {len(frames)} frames extracted. Please upload a recording at least 10 seconds long.")
    
    # Cap at MAX_FRAMES by sampling evenly
    if len(frames) > MAX_FRAMES:
        step = len(frames) / MAX_FRAMES
        sampled = [frames[int(i * step)] for i in range(MAX_FRAMES)]
        
        # Delete non-sampled frames
        for f in frames:
            if f not in sampled:
                os.remove(f)
        
        frames = sampled
    
    return frames

