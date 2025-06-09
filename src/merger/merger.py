import os
import re
import subprocess # Still needed for get_video_duration if kept local, but it was moved.
from pathlib import Path
import logging # For logger type hinting and direct use if needed

from core.ffmpeg_utils import run_ffmpeg, has_ffmpeg_errors, preserve_timestamp, get_video_duration
from core.log_utils import setup_logging

# Initialize logger for this module
# Using a generic name, specific functions might create child loggers or use this one.
# Log path for module-level logger can be defined or configured elsewhere.
# For now, let's assume setup_logging handles the path if not fully specified.
# This top-level logger can be used by functions directly or they can create children.
logger = setup_logging("logs/merger.log", 'media_merger')


# Removed local run_ffmpeg and has_ffmpeg_errors, preserve_timestamp as they are imported from core.ffmpeg_utils
# Removed local get_video_duration as it's imported from core.ffmpeg_utils

def create_ffmpeg_filter_script(sequence_files, output_file, trim_duration=0.5, crossfade_duration=1.0, mode="trim", parent_logger=None):
    """
    Create a complex filter script for merging videos.
    Mode can be either "trim" or "crossfade".
    """
    current_logger = parent_logger or logger
    current_logger.info(f"Creating '{mode}' script for {len(sequence_files)} files...")

    if mode == "crossfade":
        filter_complex_parts = []
        # Variables to hold the last processed video and audio stream labels for crossfade
        last_v_stream = None
        last_a_stream = None

        for i, file_path in enumerate(sequence_files):
            duration = get_video_duration(Path(file_path)) # Ensure file_path is a Path object
            if duration is None:
                current_logger.error(f"Could not determine duration for {file_path}. Cannot create crossfade script.")
                return None, None # Indicate failure

            # Define current video and audio stream labels based on input index
            current_v = f"[{i}:v]"
            current_a = f"[{i}:a]"

            # Reset PTS for current streams
            processed_v = f"[v{i}pts]"
            processed_a = f"[a{i}pts]"
            filter_complex_parts.append(f"{current_v}setpts=PTS-STARTPTS{processed_v};")
            filter_complex_parts.append(f"{current_a}asetpts=PTS-STARTPTS{processed_a};")

            if i == 0: # First file
                last_v_stream = processed_v
                last_a_stream = processed_a
            else: # Subsequent files, apply crossfade with the previous stream
                # Offset for the crossfade is the duration of the *previous* segment for xfade
                # This needs careful calculation based on cumulative duration if complex overlaps are desired.
                # For simple sequential crossfades, ff_duration is the duration of the current segment's fade-in.
                # The 'offset' for xfade is from the start of the *second* video.
                # A common approach is to make the previous video fade out while the current fades in.
                # Let's assume crossfade_duration is the total length of the transition.
                # The actual offset for the xfade filter is relative to the start of the *second* video in the pair.
                # For simplicity, let's assume a standard crossfade where the second video starts fading in
                # as the first one fades out.

                # To chain xfades, the output of one becomes the input of the next.
                # Example: [v_prev][v_curr]xfade[v_out]; [v_out][v_next]xfade[v_final_out]

                faded_v = f"[vfade{i}]"
                faded_a = f"[afade{i}]"

                # Get duration of the *previous* segment to calculate offset for this fade
                # This assumes files are processed in order and durations are known.
                # The offset for xfade is tricky: it's from the beginning of the second stream.
                # To make a video of length D1 fade into a video of length D2 over XF seconds:
                # The first video plays for D1-XF, then XF of fade. Second video starts at D1-XF, first XF is fade.
                # This interpretation of xfade's `offset` is critical.
                # Let's simplify: use previous file's duration minus crossfade duration as offset.
                # This means the current video will start fading in `crossfade_duration` seconds before the previous one ends.

                # This part needs get_video_duration for the *previous* file in the xfade context.
                # The `duration` variable here is for the *current* file.
                # We need the duration of `sequence_files[i-1]`.
                prev_file_duration = get_video_duration(Path(sequence_files[i-1]))
                if prev_file_duration is None:
                    current_logger.error(f"Could not get duration for previous file {sequence_files[i-1]} in crossfade.")
                    return None, None

                offset = prev_file_duration - crossfade_duration
                if offset < 0:
                    current_logger.warning(f"Crossfade duration {crossfade_duration}s is too long for file {sequence_files[i-1]} (duration {prev_file_duration}s). Adjusting offset to 0.")
                    offset = 0

                filter_complex_parts.append(
                    f"{last_v_stream}{processed_v}xfade=transition=fade:duration={crossfade_duration}:offset={offset}{faded_v};"
                )
                filter_complex_parts.append(
                    f"{last_a_stream}{processed_a}acrossfade=d={crossfade_duration}{faded_a};"
                )
                last_v_stream = faded_v
                last_a_stream = faded_a

        # The final output streams are the last `last_v_stream` and `last_a_stream`
        # The map command will use these labels (e.g. [vfadeN], [afadeN])
        return "".join(filter_complex_parts), last_v_stream, last_a_stream

    elif mode == "trim": # Standard concat using filter_complex
        filter_complex_parts = []
        for i, _ in enumerate(sequence_files):
            filter_complex_parts.extend([
                f'[{i}:v]setpts=PTS-STARTPTS[v{i}];',
                f'[{i}:a]asetpts=PTS-STARTPTS[a{i}];'
            ])

        v_streams = ''.join(f'[v{i}]' for i in range(len(sequence_files)))
        a_streams = ''.join(f'[a{i}]' for i in range(len(sequence_files)))
        filter_complex_parts.extend([
            f'{v_streams}concat=n={len(sequence_files)}:v=1:a=0[vout];',
            f'{a_streams}concat=n={len(sequence_files)}:v=0:a=1[aout]'
        ])
        # For trim mode, the output streams of the concat filter are [vout] and [aout]
        return "".join(filter_complex_parts), "[vout]", "[aout]"
    else:
        current_logger.error(f"Unknown merge mode for filter script: {mode}")
        return None, None, None


# Removed preserve_timestamp as it's imported from core.ffmpeg_utils
# Removed convert_to_mkv function

def find_sequences(folder_path: Path, parent_logger=None):
    """Find sequences of video files (e.g., base_name_1.ext, base_name_2.ext) in a folder."""
    current_logger = parent_logger or logger
    current_logger.info(f"Scanning for sequences in: {folder_path}")

    # More generic pattern for various extensions
    # Will match base_name_XX.ext or base_nameXX.ext
    pattern = re.compile(r'(.+?)_?(\d+)\.(mkv|mp4|avi|mov|ts|mts|mpg|mpeg|vob)$', re.IGNORECASE)

    sequences = {}
    files_in_folder = [p for p in folder_path.iterdir() if p.is_file()]

    for file in files_in_folder:
        match = pattern.match(file.name)
        if match:
            base_name = match.group(1)
            seq_num = int(match.group(2))
            # ext = match.group(3) # Extension, currently not used for grouping but available

            if base_name not in sequences:
                sequences[base_name] = []
            sequences[base_name].append((seq_num, file))

    merge_candidates = {}
    for base_name, seq_files in sequences.items():
        if len(seq_files) > 1:
            sorted_files = sorted(seq_files, key=lambda x: x[0])
            nums = [x[0] for x in sorted_files]

            # Check if sequence numbers are consecutive (e.g., 1, 2, 3, not 1, 3, 4)
            if nums == list(range(min(nums), max(nums) + 1)):
                files_to_merge = [sf[1] for sf in sorted_files] # Get Path objects

                # Check all files in sequence for errors before adding to candidates
                has_errors_in_sequence = False
                for f_path in files_to_merge:
                    if has_ffmpeg_errors(f_path): # Using core utility
                        current_logger.warning(f"File {f_path.name} in sequence '{base_name}' has errors. Skipping this sequence.")
                        has_errors_in_sequence = True
                        break

                if not has_errors_in_sequence:
                    merge_candidates[base_name] = files_to_merge
                    current_logger.info(f"Found valid sequence for '{base_name}': {[f.name for f in files_to_merge]}")
            else:
                current_logger.warning(f"Sequence for '{base_name}' is not consecutive: {nums}. Skipping.")
        else:
            current_logger.debug(f"Only one file found for potential sequence '{base_name}', not a sequence.")

    return merge_candidates


def merge_sequence(sequence_files: list[Path], output_file: Path, mode="trim",
                   trim_duration=0.5, crossfade_duration=1.0, parent_logger=None) -> tuple[bool, Path | None]:
    """
    Merge a sequence of video files.
    Returns a tuple: (success_boolean, path_to_output_file_if_successful_or_None).
    """
    current_logger = parent_logger or logger
    current_logger.info(f"Starting merge for sequence into {output_file} using mode '{mode}'.")

    # Initial check for errors in input files (optional, find_sequences might do this)
    for file_path in sequence_files:
        if has_ffmpeg_errors(file_path):
            current_logger.error(f"Input file {file_path} has errors. Aborting merge for {output_file.name}.")
            return False, None # Indicate failure

    # Generate filter script
    if mode == "crossfade":
        filter_script, map_v_out, map_a_out = create_ffmpeg_filter_script(
            [str(f) for f in sequence_files], # create_ffmpeg_filter_script expects string paths for get_video_duration
            str(output_file),
            crossfade_duration=crossfade_duration,
            mode="crossfade",
            parent_logger=current_logger
        )
    elif mode == "trim":
         filter_script, map_v_out, map_a_out = create_ffmpeg_filter_script(
            [str(f) for f in sequence_files],
            str(output_file),
            trim_duration=trim_duration, # trim_duration is not directly used by 'trim' mode filter generation in this setup
            mode="trim",
            parent_logger=current_logger
        )
    else:
        current_logger.error(f"Unknown merge mode: {mode}")
        return False, None

    if filter_script is None:
        current_logger.error(f"Failed to create FFmpeg filter script for {output_file.name}.")
        return False, None

    input_args = []
    for f_path in sequence_files:
        input_args.extend(['-i', str(f_path)])

    # Common output options
    output_options = [
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
        '-c:a', 'aac', '-b:a', '192k',
        '-max_muxing_queue_size', '9999',
        '-avoid_negative_ts', 'make_zero'
    ]

    cmd = [
        'ffmpeg', '-y', # Overwrite output files without asking
        *input_args,
        '-filter_complex', filter_script,
        '-map', map_v_out, # Use the video output label from script generator
        '-map', map_a_out, # Use the audio output label from script generator
        *output_options,
        str(output_file)
    ]

    merge_log_file = output_file.parent / "logs" / f"{output_file.stem}_merge.log"
    merge_log_file.parent.mkdir(parents=True, exist_ok=True)

    current_logger.info(f"Executing FFmpeg command for {output_file.name}: {' '.join(cmd)}")
    success = run_ffmpeg(cmd, merge_log_file) # Using core utility

    if not success:
        current_logger.error(f"FFmpeg command failed for {output_file.name}. See log: {merge_log_file}")
        return False, output_file # Return False, but still provide path as file might exist

    current_logger.info(f"FFmpeg command completed for {output_file.name}.")

    # Check the merged file for errors
    if has_ffmpeg_errors(output_file):
        current_logger.error(f"Merged file {output_file.name} has errors. Check {merge_log_file}.")
        # Do not delete the file, but report failure for this merge
        return False, output_file

    preserve_timestamp(sequence_files[0], output_file) # Using core utility
    current_logger.info(f"Merge successful for {output_file.name}. Timestamp preserved from {sequence_files[0].name}.")
    return True, output_file


def find_and_merge_sequences_in_folder(folder_path: Path, output_dir: Path,
                                       merge_mode='trim', trim_duration=0.5,
                                       crossfade_duration=1.0, parent_logger=None):
    """
    Finds sequences in a folder and merges them.
    """
    current_logger = parent_logger or logger
    current_logger.info(f"Starting to find and merge sequences in '{folder_path}' to '{output_dir}'. Mode: '{merge_mode}'.")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True) # Ensure log directory for merge logs

    sequences = find_sequences(folder_path, parent_logger=current_logger)

    if not sequences:
        current_logger.info(f"No mergeable sequences found in '{folder_path}'.")
        return

    merged_files_count = 0
    failed_merges_count = 0

    for base_name, files in sequences.items():
        output_file = output_dir / f"{base_name}_merged.mkv" # Output is always MKV
        current_logger.info(f"Processing sequence '{base_name}' with files: {[f.name for f in files]}. Output: {output_file.name}")

        success, _ = merge_sequence(
            files,
            output_file,
            mode=merge_mode,
            trim_duration=trim_duration,
            crossfade_duration=crossfade_duration,
            parent_logger=current_logger
        )

        if success:
            current_logger.info(f"Successfully merged sequence '{base_name}' to {output_file.name}.")
            merged_files_count += 1
        else:
            current_logger.error(f"Failed to merge sequence '{base_name}'. Check logs for details.")
            failed_merges_count +=1

    current_logger.info(f"Finished processing folder '{folder_path}'. Successfully merged: {merged_files_count} sequences. Failed merges: {failed_merges_count}.")

# Removed old main block and if __name__ == "__main__":
