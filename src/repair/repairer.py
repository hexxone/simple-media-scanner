import os
# import subprocess # No longer directly used, core.ffmpeg_utils handles it
# import shutil # No longer used as process_folder is removed
from pathlib import Path
from core.ffmpeg_utils import run_ffmpeg, has_ffmpeg_errors, preserve_timestamp
from core.log_utils import setup_logging
import logging # For logger type hinting and direct use if needed

# Placeholder for old/problematic formats
OLD_FORMATS = ['.flv', '.wmv', '.avi', '.mpg', '.vob']

def repair_media_file(file_path: Path, output_dir: Path, parent_logger_name: str = 'media_repairer_parent'):
    """
    Attempts to repair a single media file through remuxing or re-encoding.
    Args:
        file_path (Path): Path to the media file to repair.
        output_dir (Path): Directory to save processed files.
        parent_logger_name (str): Name of the parent logger for context.
    Returns:
        Path: Path to the repaired file, or None if repair failed.
    """
    # Setup a specific logger for this repair instance, potentially as a child of a main repair logger
    # The log file will be named based on 'media_repairer.file_path_stem'
    logger_name = f"{parent_logger_name}.{file_path.stem}"
    # Log files will be in output_dir/logs relative to where repair_media_file is called
    # or pass a dedicated log directory if preferred.
    # For now, let's assume logs related to a specific file repair go into the output_dir/logs
    log_file_path = output_dir / "logs" / f"{file_path.stem}_repair.log"
    logger = setup_logging(log_file_path, logger_name, is_json_format=True)

    logger.info(f"Starting repair process for: {file_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True) # Ensure log directory exists

    # Step 1: Remux
    # Output: output_dir / (file_path.stem + "_remux" + file_path.suffix)
    remux_suffix = f"_remux{file_path.suffix}"
    remuxed_file = output_dir / (file_path.stem + remux_suffix)

    # Ensure we are not overwriting the source if it's in the output_dir already (unlikely with this naming)
    if file_path == remuxed_file:
        logger.warning(f"Skipping remux for {file_path} as output path is the same as input.")
    else:
        if remuxed_file.exists():
            logger.info(f"Removing existing remuxed file: {remuxed_file}")
            remuxed_file.unlink()

        remux_cmd = [
            'ffmpeg', '-y', '-i', str(file_path),
            '-c', 'copy',  # Copy all codecs
            '-map', '0',   # Map all streams
            '-err_detect', 'ignore_err', # Try to ignore errors during remux
            str(remuxed_file)
        ]
        remux_log = output_dir / "logs" / f"{file_path.stem}_remux.log"
        logger.info(f"Attempting to remux {file_path} to {remuxed_file}")
        if run_ffmpeg(remux_cmd, remux_log):
            logger.info(f"Remuxing successful for {file_path}.")
            preserve_timestamp(file_path, remuxed_file)
            if not has_ffmpeg_errors(remuxed_file):
                logger.info(f"Remuxed file {remuxed_file} has no errors. Repair successful.")
                return remuxed_file
            else:
                logger.warning(f"Remuxed file {remuxed_file} still has errors. Proceeding to re-encode.")
        else:
            logger.error(f"Remuxing failed for {file_path}. See log: {remux_log}")

    # Step 2: Re-encode to MKV (if remuxing failed or remuxed file has errors)
    # Output: output_dir / (file_path.stem + ".mkv")
    mkv_file = output_dir / (file_path.stem + ".mkv")

    # Condition for re-encoding: original file has errors OR is an old format
    needs_re_encode = False
    if file_path.suffix.lower() in OLD_FORMATS:
        logger.info(f"File {file_path} is in an old format ({file_path.suffix}). Marked for re-encoding.")
        needs_re_encode = True

    if not needs_re_encode and has_ffmpeg_errors(file_path):
        logger.info(f"File {file_path} has errors. Marked for re-encoding.")
        needs_re_encode = True

    if not needs_re_encode:
        logger.info(f"File {file_path} is not an old format and has no initial errors. "
                    "Re-encoding to MKV will be skipped unless remux failed.")
        # If remux was attempted and failed (or produced errors), then we should still try re-encoding.
        # The logic for this is implicitly handled by falling through to this step.
        # If remux was successful and error-free, this function would have returned already.
        # So, if we are here, either remux failed, or remuxed file had errors, or initial checks passed but we want MKV.
        # For now, the task implies we try to produce an MKV if remux isn't perfect.
        if not remuxed_file.exists() or has_ffmpeg_errors(remuxed_file): # Check if remux attempt was made and failed/had errors
             needs_re_encode = True


    if needs_re_encode:
        if mkv_file.exists():
            logger.info(f"Removing existing MKV file: {mkv_file}")
            mkv_file.unlink()

        # Robust FFmpeg command for re-encoding to MKV
        re_encode_cmd = [
            'ffmpeg', '-y', '-i', str(file_path),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', # Video codec
            '-c:a', 'aac', '-b:a', '192k', # Audio codec
            '-c:s', 'copy', # Copy subtitles
            '-map', '0', # Map all streams
            '-fflags', '+genpts', # Generate presentation timestamps
            '-max_muxing_queue_size', '9999', # Prevent muxing errors
            '-avoid_negative_ts', 'make_zero', # Fix negative timestamps
            str(mkv_file)
        ]
        re_encode_log = output_dir / "logs" / f"{file_path.stem}_reencode_mkv.log"
        logger.info(f"Attempting to re-encode {file_path} to {mkv_file}")
        if run_ffmpeg(re_encode_cmd, re_encode_log):
            logger.info(f"Re-encoding to MKV successful for {file_path}.")
            preserve_timestamp(file_path, mkv_file)
            if not has_ffmpeg_errors(mkv_file):
                logger.info(f"Re-encoded MKV file {mkv_file} has no errors. Repair successful.")
                return mkv_file
            else:
                logger.warning(f"Re-encoded MKV file {mkv_file} still has errors.")
        else:
            logger.error(f"Re-encoding to MKV failed for {file_path}. See log: {re_encode_log}")
    else:
        logger.info(f"Skipping re-encoding for {file_path} as it's not deemed necessary and remux was successful or not attempted.")
        # If remux was successful and error free, we would have returned.
        # If remux was not attempted (e.g. file_path == remuxed_file), and no errors and not old format, we might end up here.
        # In this case, the original file is considered "good enough".
        # However, the goal is to produce a repaired file in output_dir.
        # If the original file is fine and no operations were performed, what should be returned?
        # For now, let's assume if no operations improve the file, we return None from repair.
        # The CLI can decide to copy it if it was already fine.


    # Step 3: Extract Streams (Last Resort)
    logger.warning(f"All repair attempts (remux, re-encode) failed or resulted in files with errors for {file_path}.")
    logger.info("Stream extraction would be attempted here as a last resort (currently not implemented).")
    # Placeholder for stream extraction logic
    # e.g., ffmpeg -i input -vcodec copy video.h264 -acodec copy audio.aac

    return None

# Removed process_folder and if __name__ == "__main__":
