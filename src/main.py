import argparse
import logging
import shutil # For copying files in process command
from pathlib import Path
from typing import Optional

from scanner.scanner import MediaScanner
# from scanner.progress_tracker import ProgressTracker # Not directly used by CLI yet
from repair.repairer import repair_media_file
from merger.merger import find_and_merge_sequences_in_folder
from core.log_utils import setup_logging # Renamed import alias for clarity
from core.ffmpeg_utils import has_ffmpeg_errors # For process command and potentially others
from reporter import print_error_tree, parse_and_filter_errors_from_json

# Global variable for the main CLI logger
cli_logger: Optional[logging.Logger] = None

# Define common video extensions like in handle_repair
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.mpg', '.mpeg', '.vob', '.ts', '.mts']

def ensure_dir_exists(path: Path):
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)

# Command Handlers
def handle_scan(args):
    cli_logger.info(f"Executing 'scan' command for directory: {args.input_path}")
    ensure_dir_exists(args.log_path)
    # MediaScanner's logger is configured internally, but it uses the log_path
    scanner = MediaScanner(media_path=args.input_path, log_path=args.log_path, is_non_interactive=args.non_interactive)
    scanner.scan_directory()
    scanner.print_summary()
    cli_logger.info("'scan' command completed.")

def handle_report_errors(args):
    cli_logger.info(f"Executing 'report-errors' for log file: {args.log_file_path}")
    if not args.log_file_path.exists():
        cli_logger.error(f"Log file not found: {args.log_file_path}")
        print(f"Error: Log file not found: {args.log_file_path}")
        return

    error_tree = parse_and_filter_errors_from_json(args.log_file_path)
    if error_tree is not None:
        print_error_tree(error_tree, cli_logger)
    else:
        cli_logger.error("Failed to parse errors or no errors to report.")
    cli_logger.info("'report-errors' command completed.")

def handle_repair(args):
    cli_logger.info(f"Executing 'repair' command for: {args.input_path_or_file}")
    ensure_dir_exists(args.output_path)
    ensure_dir_exists(args.log_path) # Repairer also logs

    input_path = Path(args.input_path_or_file)
    output_dir = Path(args.output_path)

    files_to_repair = []
    if input_path.is_file():
        if input_path.suffix.lower() in VIDEO_EXTENSIONS:
            files_to_repair.append(input_path)
        else:
            cli_logger.warning(f"Skipping non-video file: {input_path}")
    elif input_path.is_dir():
        cli_logger.info(f"Scanning directory {'recursively' if args.recursive else 'non-recursively'}: {input_path}")
        glob_pattern = '**/*' if args.recursive else '*'
        for item in input_path.glob(glob_pattern):
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS:
                files_to_repair.append(item)
    else:
        cli_logger.error(f"Input path is not a valid file or directory: {input_path}")
        return

    if not files_to_repair:
        cli_logger.info("No video files found to repair.")
        return

    repaired_count = 0
    failed_count = 0
    for file_to_repair in files_to_repair:
        cli_logger.info(f"Attempting to repair: {file_to_repair}")
        # The repair_media_file function sets up its own specific logger.
        # We pass the main CLI logger's name so it can create a child or related logger.
        repaired_file_path = repair_media_file(file_to_repair, output_dir, parent_logger_name=cli_logger.name)
        if repaired_file_path:
            cli_logger.info(f"Successfully repaired '{file_to_repair.name}' to '{repaired_file_path}'")
            repaired_count += 1
        else:
            cli_logger.error(f"Failed to repair '{file_to_repair.name}'. See repairer logs for details.")
            failed_count += 1

    cli_logger.info(f"'repair' command completed. Repaired: {repaired_count}, Failed: {failed_count}.")

def handle_merge(args):
    cli_logger.info(f"Executing 'merge' command for directory: {args.input_path}")
    ensure_dir_exists(args.output_path)
    ensure_dir_exists(args.log_path) # Merger also logs

    # Merger functions use their own logger, but we pass the main CLI logger's name for context/hierarchy
    find_and_merge_sequences_in_folder(
        folder_path=Path(args.input_path),
        output_dir=Path(args.output_path),
        merge_mode=args.merge_mode,
        trim_duration=args.trim_duration, # Not used by current filter script version for trim
        crossfade_duration=args.crossfade_duration,
        parent_logger=cli_logger
    )
    cli_logger.info("'merge' command completed.")

def handle_process(args):
    cli_logger.info(f"Executing 'process' pipeline for directory: {args.input_path}")
    ensure_dir_exists(args.log_path)
    ensure_dir_exists(args.output_path)

    # === Part 1: Scan ===
    cli_logger.info("Process Step 1: Scanning for media files and errors...")
    scanner = MediaScanner(media_path=args.input_path, log_path=args.log_path, is_non_interactive=args.non_interactive)
    scanner.scan_directory()
    scanner.print_summary()

    # Collect files that need repair and files that are okay
    # ProgressTracker saves to logs/progress.json by default
    # MediaScanner uses a ProgressTracker instance.
    # We need to access the results of the scan.
    # The scanner logs errors to a specific JSON file. We can parse this, or access progress_tracker.

    # For simplicity, let's find all scannable files from input_path again.
    # Then, for each, decide if it needs repair based on has_ffmpeg_errors (or use scan results).
    # The scan already logged errors. We can use the progress file.

    # Let's assume for now: repair all files that are found by scan and *might* have errors,
    # or just copy all files to output_path and then repair them in place if error is detected.
    # The task says: "repair all scannable files from input_path into output_path"
    # "Then it will run merge operations on output_path."
    # "This means files without errors will also be copied to output_path"

    cli_logger.info(f"Process Step 2: Copying/Repairing files from {args.input_path} to {args.output_path}...")

    # files_for_merging_in_output = []

    # Iterate through all files in input_path that scanner would find
    # This is a simplified approach. A more robust way would be to parse scan logs.

    processed_for_repair_count = 0
    copied_ok_count = 0

    glob_pattern = '**/*' # Assuming recursive processing for 'process' command
    for item_path in args.input_path.glob(glob_pattern):
        if item_path.is_file() and item_path.suffix.lower() in VIDEO_EXTENSIONS:
            processed_for_repair_count +=1
            target_file_in_output = args.output_path / item_path.name # Simple copy to top-level of output_path

            # Check for errors before deciding to repair or copy
            # This is a bit redundant if scan already did this, but makes repair decision explicit here.
            if has_ffmpeg_errors(item_path):
                cli_logger.info(f"File {item_path.name} has errors, attempting repair into output directory.")
                repaired_path = repair_media_file(item_path, args.output_path, parent_logger_name=cli_logger.name)
                if repaired_path:
                    cli_logger.info(f"Repaired {item_path.name} to {repaired_path.name}")
                    # Merging should use the repaired file
                    # files_for_merging_in_output.append(repaired_path) # Not used yet, find_sequences works on dir
                else:
                    cli_logger.warning(f"Could not repair {item_path.name}. It will be skipped for merging if it's part of sequence requiring it.")
                    # Decide if original (but faulty) should be copied, or skipped. For now, skip.
            else:
                # No errors, just copy to output_path for potential merging
                cli_logger.info(f"File {item_path.name} has no errors. Copying to output directory.")
                try:
                    shutil.copy2(item_path, target_file_in_output)
                    copied_ok_count +=1
                    # files_for_merging_in_output.append(target_file_in_output) # Not used yet
                except Exception as e:
                    cli_logger.error(f"Failed to copy {item_path.name} to {target_file_in_output}: {e}")

    cli_logger.info(f"Repair/Copy step finished. Files processed for repair attempt: {processed_for_repair_count-copied_ok_count}. Files copied without repair: {copied_ok_count}.")

    # === Part 3: Merge ===
    cli_logger.info(f"Process Step 3: Merging sequences in output directory: {args.output_path}")
    find_and_merge_sequences_in_folder(
        folder_path=args.output_path, # Merge from the output_path
        output_dir=args.output_path,  # Merge results also go into output_path (e.g., output/seq_merged.mkv)
        merge_mode=args.merge_mode,
        crossfade_duration=args.crossfade_duration,
        parent_logger=cli_logger
    )

    cli_logger.info("'process' pipeline completed.")


def main():
    global cli_logger # Allow assignment to global cli_logger

    parser = argparse.ArgumentParser(description="Media Processing and Management Tool")
    parser.add_argument('--log-path', type=Path, default=Path('logs'), help="Directory for log files.")
    parser.add_argument('--output-path', type=Path, default=Path('output'), help="Directory for processed output files (repair, merge).")
    parser.add_argument('--non-interactive', action='store_true', help="Run in non-interactive mode (e.g., for scripts).")
    # Add --debug flag for verbose logging?

    subparsers = parser.add_subparsers(dest='command', required=True, help="Available commands")

    # Scan command
    scan_parser = subparsers.add_parser('scan', help="Scan a directory for media file errors.")
    scan_parser.add_argument('input_path', type=Path, help="Directory to scan for media files.")
    scan_parser.set_defaults(func=handle_scan)

    # Repair command
    repair_parser = subparsers.add_parser('repair', help="Repair a media file or files in a directory.")
    repair_parser.add_argument('input_path_or_file', type=Path, help="Media file or directory of media files to repair.")
    repair_parser.add_argument('--recursive', action='store_true', help="Process directories recursively.")
    repair_parser.set_defaults(func=handle_repair)

    # Merge command
    merge_parser = subparsers.add_parser('merge', help="Merge sequences of media files in a directory.")
    merge_parser.add_argument('input_path', type=Path, help="Directory containing media file sequences.")
    merge_parser.add_argument('--merge-mode', type=str, choices=['trim', 'crossfade'], default='trim', help="Merge mode ('trim' or 'crossfade').")
    merge_parser.add_argument('--trim-duration', type=float, default=0.5, help="Overlap/trim duration for 'trim' mode (not directly used by current filter).")
    merge_parser.add_argument('--crossfade-duration', type=float, default=1.0, help="Duration of crossfade in seconds for 'crossfade' mode.")
    merge_parser.set_defaults(func=handle_merge)

    # Process command
    process_parser = subparsers.add_parser('process', help="Full pipeline: Scan -> Repair -> Merge.")
    process_parser.add_argument('input_path', type=Path, help="Input directory for the full processing pipeline.")
    process_parser.add_argument('--merge-mode', type=str, choices=['trim', 'crossfade'], default='trim', help="Merge mode for the merge step.")
    # Removed trim_duration from process command as it's not directly used in current merge trim logic
    process_parser.add_argument('--crossfade-duration', type=float, default=1.0, help="Crossfade duration for the merge step.")
    process_parser.set_defaults(func=handle_process)

    # Report-errors command
    report_parser = subparsers.add_parser('report-errors', help="Parse and display errors from a JSON scan log.")
    report_parser.add_argument('log_file_path', type=Path, help="Path to the JSON log file from a scan.")
    report_parser.set_defaults(func=handle_report_errors)

    args = parser.parse_args()

    # Ensure common paths exist (idempotent)
    ensure_dir_exists(args.log_path)
    ensure_dir_exists(args.output_path)

    # Setup main CLI logger (after log_path is confirmed from args)
    cli_logger = setup_logging(args.log_path / "main_cli.log", "main_cli", is_json_format=False)
    cli_logger.info(f"CLI started with arguments: {vars(args)}") # Log arguments as a dictionary

    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()
        cli_logger.warning("No command provided or handler not set up correctly.")

if __name__ == '__main__':
    main()
