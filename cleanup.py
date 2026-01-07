import os
from datetime import datetime, timedelta

# Track file creation times for cleanup
file_timestamps = {}

def record_file_creation(file_path: str):
    """Record when a file was created for cleanup tracking"""
    file_timestamps[file_path] = datetime.now()

def cleanup_old_files():
    """Clean up files older than 1 hour"""
    now = datetime.now()
    cutoff = now - timedelta(hours=1)
    
    files_to_delete = []
    for file_path, created_at in list(file_timestamps.items()):
        if created_at < cutoff:
            files_to_delete.append(file_path)
    
    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            del file_timestamps[file_path]
        except Exception as e:
            print(f"Error cleaning up {file_path}: {e}")

def cleanup_frames_immediately(frame_paths: list[str]):
    """Clean up frame files immediately after PDF generation"""
    for frame_path in frame_paths:
        try:
            if os.path.exists(frame_path):
                os.remove(frame_path)
        except Exception as e:
            print(f"Error cleaning up frame {frame_path}: {e}")
    
    # Also try to remove the frames directory if empty
    if frame_paths:
        frame_dir = os.path.dirname(frame_paths[0])
        try:
            if os.path.exists(frame_dir) and not os.listdir(frame_dir):
                os.rmdir(frame_dir)
        except Exception:
            pass  # Directory might not be empty or already deleted

def cleanup_failed_job(job_data: dict):
    """Clean up files associated with a failed job immediately"""
    # Clean up video file
    if "video_path" in job_data and os.path.exists(job_data["video_path"]):
        try:
            os.remove(job_data["video_path"])
        except Exception as e:
            print(f"Error cleaning up video {job_data['video_path']}: {e}")
    
    # Clean up frames if they exist
    if "frame_paths" in job_data:
        cleanup_frames_immediately(job_data["frame_paths"])

