import os
import subprocess
import shutil
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
    cmd = ['ffmpeg', '-v', 'error', '-i', str(file_path), '-f', 'null', '-']
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    err = bool(result.stderr.strip())
    if err:
        print("File has errors: " + result.stderr.decode(encoding="utf-8"))
    return err

def get_video_duration(file_path):
    """Get duration of video file in seconds"""
    cmd = [
        'ffmpeg', '-i', str(file_path),
        '-hide_banner'
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stderr.decode()

    # Look for duration in the output
    duration_match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})", output)
    if duration_match:
        hours, minutes, seconds, centiseconds = map(int, duration_match.groups())
        return hours * 3600 + minutes * 60 + seconds + centiseconds / 100
    return None

def create_trim_script(sequence_files, output_file, trim_duration=0.5, crossfade_duration=1.0, mode="trim"):
    """
    Create a complex filter script for merging videos
    mode can be either "trim" or "crossfade"
    """
    script_lines = []
    filter_complex = []
    inputs = []

    for i, file in enumerate(sequence_files):
        duration = get_video_duration(file)
        if duration is None:
            print(f"Could not determine duration for {file}")
            return None

        if mode == "trim" and i < len(sequence_files) - 1:
            # Trim the end of each clip except the last one
            trim_end = duration - trim_duration
            script_lines.append(f"file '{file}'")
            script_lines.append(f"duration {trim_end}")
        elif mode == "crossfade" and i < len(sequence_files) - 1:
            # For crossfade, we need to handle both video and audio transitions
            inputs.append(f"-i {file}")

            if i == 0:
                filter_complex.extend([
                    f"[{i}:v]setpts=PTS-STARTPTS[v{i}];",
                    f"[{i}:a]asetpts=PTS-STARTPTS[a{i}];"
                ])
            else:
                filter_complex.extend([
                    f"[{i}:v]setpts=PTS-STARTPTS[v{i}];",
                    f"[{i}:a]asetpts=PTS-STARTPTS[a{i}];",
                    f"[v{i-1}][v{i}]xfade=transition=fade:duration={crossfade_duration}:offset={duration-crossfade_duration}[v{i}out];",
                    f"[a{i-1}][a{i}]acrossfade=d={crossfade_duration}[a{i}out];"
                ])
        else:
            # Last file or trim mode
            script_lines.append(f"file '{file}'")

    if mode == "trim":
        # Create a simple concat script
        script_path = Path('concat_script.txt')
        with open(script_path, 'w') as f:
            f.write('\n'.join(script_lines))
        return script_path
    elif mode == "crossfade":
        # Create a complex filter script
        filter_script = ';'.join(filter_complex)
        return inputs, filter_script

def preserve_timestamp(source_file, target_file):
    """Copy the timestamp from source file to target file"""
    source_stat = os.stat(str(source_file))
    os.utime(str(target_file), (source_stat.st_atime, source_stat.st_mtime))

def convert_to_mkv(input_file):
    """Convert video file to MKV format"""
    input_path = Path(input_file)
    output_path = input_path.with_suffix('.mkv')

    # Skip if output file already exists
    if output_path.exists():
        print(f"Skipping {input_file} - MKV already exists")
        return None

    cmd = [
        'ffmpeg', '-y', '-i', str(input_path),
        '-c:v', 'copy', '-c:a', 'copy',
        str(output_path)
    ]

    print(f"Converting {input_path} to MKV...")
    if run_ffmpeg(cmd):
        preserve_timestamp(input_path, output_path)
        return output_path
    return None

def find_sequences(folder):
    """Find sequences of video files that should be merged"""
    folder = Path(folder)
    files = list(folder.glob('*.mkv'))

    # Group files by their base name (without sequence number)
    sequences = {}
    pattern = re.compile(r'(.+?)_?(\d+)\.mkv$')

    for file in files:
        match = pattern.match(file.name)
        if match and not has_ffmpeg_errors(file):
            base_name = match.group(1)
            seq_num = int(match.group(2))
            if base_name not in sequences:
                sequences[base_name] = []
            sequences[base_name].append((seq_num, file))

    # Filter and sort sequences
    merge_candidates = {}
    for base_name, seq_files in sequences.items():
        if len(seq_files) > 1:
            # Sort by sequence number
            sorted_files = sorted(seq_files, key=lambda x: x[0])
            # Check if sequence numbers are consecutive
            nums = [x[0] for x in sorted_files]
            if nums == list(range(min(nums), max(nums) + 1)):
                merge_candidates[base_name] = [x[1] for x in sorted_files]

    return merge_candidates

def merge_sequence(sequence_files, output_file, mode="trim", trim_duration=0.5, crossfade_duration=1.0):
    """Merge a sequence of video files with either trimming or crossfade"""
    if mode == "trim":
        script_path = create_trim_script(sequence_files, output_file, trim_duration)
        if script_path is None:
            return False

        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', str(script_path), '-c', 'copy', str(output_file)
        ]

        success = run_ffmpeg(cmd)
        script_path.unlink()  # Remove temporary script file
        return success and not has_ffmpeg_errors(output_file)

    elif mode == "crossfade":
        inputs, filter_script = create_trim_script(
            sequence_files, output_file,
            crossfade_duration=crossfade_duration,
            mode="crossfade"
        )

        cmd = [
            'ffmpeg', '-y'] + inputs.split() + [
            '-filter_complex', filter_script,
            '-map', '[v{}out]'.format(len(sequence_files)-1),
            '-map', '[a{}out]'.format(len(sequence_files)-1),
            str(output_file)
        ]

        return run_ffmpeg(cmd) and not has_ffmpeg_errors(output_file)

def process_folder(root_dir):
    root_dir = Path(root_dir)

    # First, convert all VOB and MPEG files to MKV
    for ext in ['*.vob', '*.VOB', '*.mpeg', '*.MPEG', '*.mpg', '*.MPG']:
        for video_file in root_dir.rglob(ext):
            if not convert_to_mkv(video_file):
                print("Failed to convert to MKV: " + video_file)

    # Then find and merge sequences
    sequences = find_sequences(root_dir)

    if sequences:
        print("\nFound the following sequences that could be merged:")
        for base_name, files in sequences.items():
            print(f"\nSequence '{base_name}':")
            for f in files:
                print(f"  {f.name}")

            while True:
                merge = input(f"\nDo you want to merge this sequence? (n/trim/crossfade): ").lower()
                if merge in ['n', 'trim', 'crossfade']:
                    break
                print("Please enter 'n', 'trim', or 'crossfade'")

            if merge != 'n':
                output_file = root_dir / f"{base_name}_merged.mkv"
                print(f"Merging to: {output_file}")

                if merge == 'trim':
                    trim_duration = float(input("Enter trim duration in seconds (default 0.5): ") or 0.5)
                    if merge_sequence(files, output_file, mode="trim", trim_duration=trim_duration) and not has_ffmpeg_errors(output_file):
                        preserve_timestamp(files[0], output_file)
                        print("Merge successful!")
                    else:
                        print("Merge failed!")
                else:  # crossfade
                    crossfade_duration = float(input("Enter crossfade duration in seconds (default 1.0): ") or 1.0)
                    if merge_sequence(files, output_file, mode="crossfade", crossfade_duration=crossfade_duration) and not has_ffmpeg_errors(output_file):
                        preserve_timestamp(files[0], output_file)
                        print("Merge successful!")
                    else:
                        print("Merge failed!")
    else:
        print("\nNo sequences found that need to be merged.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert videos to MKV and merge sequences")
    parser.add_argument("input_folder", help="Root folder to scan for video files")
    args = parser.parse_args()
    process_folder(args.input_folder)