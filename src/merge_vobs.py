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
    print(f"Creating '{mode}' script for {len(sequence_files)} files...")

    if mode == "crossfade":
        filter_complex = []

        for i, file in enumerate(sequence_files):
            duration = get_video_duration(file)
            if duration is None:
                print(f"Could not determine duration for {file}")
                return None, None

            # Reset timestamps for each input
            filter_complex.extend([
                f'[{i}:v]setpts=PTS-STARTPTS[v{i}];',
                f'[{i}:a]asetpts=PTS-STARTPTS[a{i}];'
            ])

            # Add crossfade filters except for the first file
            if i > 0:
                filter_complex.extend([
                    f'[v{i-1}][v{i}]xfade=transition=fade:duration={crossfade_duration}:'
                    f'offset={duration-crossfade_duration}[v{i}out];',
                    f'[a{i-1}][a{i}]acrossfade=d={crossfade_duration}[a{i}out];'
                ])

        return "", ''.join(filter_complex)
    else:
        # For trim mode, just return the path (the actual work is done in merge_sequence)
        return Path('concat_script.txt'), None


# def create_trim_script(sequence_files, output_file, trim_duration=0.5, crossfade_duration=1.0, mode="trim"):
#     """
#     Create a complex filter script for merging videos
#     mode can be either "trim" or "crossfade"
#     """
#     script_lines = []
#     filter_complex = []
#     inputs = []
#
#
#     for i, file in enumerate(sequence_files):
#         duration = get_video_duration(file)
#         if duration is None:
#             print(f"Could not determine duration for {file}")
#             return None
#
#         if mode == "trim" and i < len(sequence_files) - 1:
#             # Trim the end of each clip except the last one
#             trim_end = duration - trim_duration
#             script_lines.append(f"file '{file}'")
#             script_lines.append(f"duration {trim_end}")
#         elif mode == "crossfade" and i < len(sequence_files) - 1:
#             # For crossfade, we need to handle both video and audio transitions
#             inputs.append(f"-i {file}")
#
#             if i == 0:
#                 filter_complex.extend([
#                     f"[{i}:v]setpts=PTS-STARTPTS[v{i}];",
#                     f"[{i}:a]asetpts=PTS-STARTPTS[a{i}];"
#                 ])
#             else:
#                 filter_complex.extend([
#                     f"[{i}:v]setpts=PTS-STARTPTS[v{i}];",
#                     f"[{i}:a]asetpts=PTS-STARTPTS[a{i}];",
#                     f"[v{i-1}][v{i}]xfade=transition=fade:duration={crossfade_duration}:offset={duration-crossfade_duration}[v{i}out];",
#                     f"[a{i-1}][a{i}]acrossfade=d={crossfade_duration}[a{i}out];"
#                 ])
#         else:
#             # Last file or trim mode
#             script_lines.append(f"file '{file}'")
#
#     if mode == "trim":
#         # Create a simple concat script
#         script_path = Path('concat_script.txt')
#         with open(script_path, 'w') as f:
#             f.write('\n'.join(script_lines))
#         return script_path
#     elif mode == "crossfade":
#         # Create a complex filter script
#         filter_script = ';'.join(filter_complex)
#         return inputs, filter_script

def preserve_timestamp(source_file, target_file):
    """Copy the timestamp from source file to target file"""
    source_stat = os.stat(str(source_file))
    os.utime(str(target_file), (source_stat.st_atime, source_stat.st_mtime))

def convert_to_mkv(input_file):
    """Convert video file to MKV format with error correction"""
    input_path = Path(input_file)
    output_path = input_path.with_suffix('.mkv')

    # Skip if output file already exists
    if output_path.exists():
        print(f"Skipping {input_file} - MKV already exists")
        return output_path

    # Advanced conversion with error correction
    cmd = [
        'ffmpeg', '-y',
        '-fflags', '+genpts',  # Generate presentation timestamps
        '-i', str(input_path),
        '-c:v', 'libx264',     # Re-encode video to fix potential issues
        '-preset', 'medium',
        '-crf', '23',
        '-c:a', 'aac',         # Re-encode audio to fix potential issues
        '-b:a', '192k',
        '-max_muxing_queue_size', '9999',  # Prevent muxing errors
        '-avoid_negative_ts', 'make_zero',  # Fix negative timestamps
        str(output_path)
    ]

    print(f"Converting {input_path} to MKV with error correction...")
    if run_ffmpeg(cmd):
        preserve_timestamp(input_path, output_path)

        # Verify the converted file
        if has_ffmpeg_errors(output_path):
            print(f"Converted file still has errors: {output_path}")
            output_path.unlink()  # Delete the failed conversion
            return None
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
        if match:
            base_name = match.group(1)
            seq_num = int(match.group(2))
            if base_name not in sequences:
                sequences[base_name] = []
            sequences[base_name].append((seq_num, file))

    # Filter and sort sequences, checking all files in a sequence for errors
    merge_candidates = {}
    for base_name, seq_files in sequences.items():
        if len(seq_files) > 1:
            # Sort by sequence number
            sorted_files = sorted(seq_files, key=lambda x: x[0])
            # Check if sequence numbers are consecutive
            nums = [x[0] for x in sorted_files]
            if nums == list(range(min(nums), max(nums) + 1)):
                # Check all files in sequence for errors
                files_with_errors = []
                for _, file in sorted_files:
                    if has_ffmpeg_errors(file):
                        files_with_errors.append(file.name)

                if files_with_errors:
                    print(f"\nSkipping sequence '{base_name}' due to errors in files:")
                    for error_file in files_with_errors:
                        print(f"  - {error_file}")
                else:
                    merge_candidates[base_name] = [x[1] for x in sorted_files]

    return merge_candidates

def merge_sequence(sequence_files, output_file, mode="trim", trim_duration=0.5, crossfade_duration=1.0):
    """Merge a sequence of video files with either trimming or crossfade"""
    # First verify all input files again
    for file in sequence_files:
        if has_ffmpeg_errors(file):
            print(f"Aborting merge due to errors in: {file}")
            return False

    if mode == "trim":
        script_path = create_trim_script(sequence_files, output_file, trim_duration)
        if script_path is None:
            return False

        # Create a complex filter for concatenation instead of using concat demuxer
        filter_complex = []
        for i, _ in enumerate(sequence_files):
            # Add input setpts filters to reset timestamps for each input
            filter_complex.extend([
                f'[{i}:v]setpts=PTS-STARTPTS[v{i}];',
                f'[{i}:a]asetpts=PTS-STARTPTS[a{i}];'
            ])

        # Concatenate all streams
        v_streams = ''.join(f'[v{i}]' for i in range(len(sequence_files)))
        a_streams = ''.join(f'[a{i}]' for i in range(len(sequence_files)))
        filter_complex.extend([
            f'{v_streams}concat=n={len(sequence_files)}:v=1:a=0[vout];',
            f'{a_streams}concat=n={len(sequence_files)}:v=0:a=1[aout]'
        ])

        input_args = []
        for f in sequence_files:
            input_args.extend(['-i', str(f)])

        cmd = [
            'ffmpeg', '-y',
            *input_args,
            '-filter_complex', ''.join(filter_complex),
            '-map', '[vout]',
            '-map', '[aout]',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-max_muxing_queue_size', '9999',
            '-avoid_negative_ts', 'make_zero',
            str(output_file)
        ]

        success = run_ffmpeg(cmd)
        script_path.unlink()  # Remove temporary script file

    elif mode == "crossfade":
        inputs, filter_script = create_trim_script(
            sequence_files,
            output_file,
            crossfade_duration=crossfade_duration,
            mode="crossfade"
        )

        if inputs is None or filter_script is None:
            return False

        # Similar approach for crossfade mode
        input_args = []
        for f in sequence_files:
            input_args.extend(['-i', str(f)])

        cmd = [
            'ffmpeg', '-y',
            *input_args,
            '-filter_complex', filter_script,
            '-map', f'[v{len(sequence_files)-1}out]',
            '-map', f'[a{len(sequence_files)-1}out]',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-max_muxing_queue_size', '9999',
            '-avoid_negative_ts', 'make_zero',
            str(output_file)
        ]

        success = run_ffmpeg(cmd)

    else:
        print(f"Unknown merge mode: {mode}")
        return False

    # Check the output file for errors regardless of merge mode
    if success and has_ffmpeg_errors(output_file):
        print("Merged file has errors - deleting output")
        output_file.unlink()
        return False

    return success

def process_folder(root_dir):
    root_dir = Path(root_dir)

    # First, convert all VOB and MPEG files to MKV
    for ext in ['*.vob', '*.VOB', '*.mpeg', '*.MPEG', '*.mpg', '*.MPG']:
        for video_file in root_dir.rglob(ext):
            if not convert_to_mkv(video_file):
                print("Failed to convert to MKV: " + video_file.name)

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