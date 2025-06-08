import os
import subprocess
from pathlib import Path
import re

def run_ffmpeg(cmd, log_file=None):
    try:
        if log_file:
            with open(log_file, 'w') as log:
                result = subprocess.run(cmd, stdout=log, stderr=log)
        else:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {' '.join(cmd)}\n{e}")
        return False

def has_ffmpeg_errors(file_path):
    """
    Thoroughly check a video file for various types of errors including:
    - Container errors
    - Stream errors
    - DTS/PTS errors
    - Audio/Video sync issues
    """
    # First check - basic error detection
    cmd1 = ['ffmpeg', '-v', 'error', '-i', str(file_path), '-f', 'null', '-']

    # Second check - specifically for DTS/PTS errors
    cmd2 = ['ffmpeg', '-i', str(file_path), '-c', 'copy', '-f', 'null', '-']

    errors = []

    # Run first check
    result1 = subprocess.run(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result1.stderr.strip():
        errors.append(f"Basic errors: {result1.stderr.decode('utf-8').strip()}")

    # Run second check
    result2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stderr = result2.stderr.decode('utf-8')
    if 'non monotonically increasing dts' in stderr or 'Invalid DTS/PTS' in stderr:
        errors.append(f"DTS/PTS errors: {stderr.strip()}")

    if errors:
        print(f"File has errors ({file_path}):")
        for error in errors:
            print(f"  - {error}")
        return True
    return False

def preserve_timestamp(source_file, target_file):
    """Copy the timestamp from source file to target file"""
    source_stat = os.stat(str(source_file))
    os.utime(str(target_file), (source_stat.st_atime, source_stat.st_mtime))


def get_video_duration(file_path: Path) -> float | None:
    """Get duration of video file in seconds using ffprobe."""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(file_path)
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        # Using print for direct feedback in case of ffprobe error, consider logging for library use
        print(f"Error getting duration for {file_path}: {e.stderr}")
        return None
    except ValueError:
        print(f"Could not parse duration from ffprobe output for {file_path}.")
        return None
