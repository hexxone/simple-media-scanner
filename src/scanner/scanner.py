import os
import subprocess
import logging
from pathlib import Path
from tqdm import tqdm
# No longer needed directly, setup_logging from core.log_utils will handle json formatting
# from pythonjsonlogger import json
from .progress_tracker import ProgressTracker
from src.core.log_utils import setup_logging
from src.core.ffmpeg_utils import has_ffmpeg_errors


class MediaScanner:
    def __init__(self, media_path, log_path, is_non_interactive):
        self.media_path = Path(media_path)
        # log_path is now handled by setup_logging, but we might still want it for the summary
        self.log_dir = Path(log_path) # Renaming to avoid confusion with log_file from setup_logging
        self.is_non_interactive = is_non_interactive
        self.progress_tracker = ProgressTracker()
        # Use the new setup_logging from core.log_utils
        # The log_file path for the logger will be inside self.log_dir
        # Pass self.log_dir as the base path for logs.
        # setup_logging will create a file like 'media_scanner_YYYYMMDD_HHMMSS.log' in self.log_dir
        self.logger = setup_logging(self.log_dir / "media_scanner.log", 'media_scanner', is_json_format=True)
        self.media_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v',
            '.mpg', '.mpeg', '.m2ts', '.vob', '.ts', '.mts' # Added .ts and .mts
        }
        self.error_count = 0
        self.scanned_count = 0
        self.skipped_count = 0

    # def setup_logging(self): # Removed, using core.log_utils.setup_logging

    def scan_file(self, file_path):
        """Scan a single media file for errors using ffmpeg_utils.has_ffmpeg_errors."""
        try:
            # has_ffmpeg_errors returns True if errors are found, False otherwise.
            # It also prints details of the errors.
            # We need to capture the fact that an error occurred for logging and progress tracking.
            # The original has_ffmpeg_errors prints to stdout. We need to capture this for the log.
            # For now, we assume has_ffmpeg_errors will be modified or we adapt here.
            # Let's assume has_ffmpeg_errors is primarily for its boolean return and direct printing.
            # We will log a generic error message if it returns True.

            # To get the specific error message, has_ffmpeg_errors would need to return it.
            # For now, we'll make a generic log entry.
            # The `has_ffmpeg_errors` function in `core.ffmpeg_utils` already prints error details.
            # We just need to log that an error was found.
            if has_ffmpeg_errors(file_path): # This function now prints errors directly
                self.error_count += 1
                # Log a simplified message; detailed errors are printed by has_ffmpeg_errors
                self.logger.error({
                    'file': str(file_path),
                    'message': 'ffmpeg detected errors. See console output from has_ffmpeg_errors for details.'
                })
                self.progress_tracker.mark_file_scanned(str(file_path), "error")
                return False # Indicates an error was found

            self.progress_tracker.mark_file_scanned(str(file_path), "ok")
            return True # Indicates no error was found

        except Exception as e: # Catch any other exceptions during the scan process
            self.error_count += 1
            self.logger.error({
                'file': str(file_path),
                'error_type': type(e).__name__,
                'error': str(e)
            })
            self.progress_tracker.mark_file_scanned(str(file_path), "error")
            return False

    def find_media_files(self):
        """Find all media files in the given directory."""
        for root, _, files in os.walk(self.media_path):
            for file in files:
                if Path(file).suffix.lower() in self.media_extensions:
                    yield Path(root) / file

    def scan_directory(self):
        """Scan all media files in the directory."""
        print(f"Starting media scan in: {self.media_path}")

        media_files = list(self.find_media_files())
        print(f"Found: {len(media_files)} media files to scan.")

        with tqdm(total=len(media_files), desc="Scanning files") as pbar:
            if self.is_non_interactive:
                print(pbar)
            for file_path in media_files:
                if self.progress_tracker.is_file_scanned(str(file_path)):
                    self.skipped_count += 1
                    pbar.update(1)
                    if self.is_non_interactive:
                        print(pbar)
                    continue

                self.scan_file(file_path)
                self.scanned_count += 1
                pbar.update(1)
                if self.is_non_interactive:
                    print(pbar)

    def print_summary(self):
        """Print a summary of the scan results."""
        print("\nScan Summary:")
        print(f"Total files processed: {self.scanned_count + self.skipped_count}")
        print(f"Files scanned: {self.scanned_count}")
        print(f"Files skipped (already scanned): {self.skipped_count}")
        print(f"Files with errors: {self.error_count}")
        # Use self.log_dir to report log location
        print(f"Error log directory: {self.log_dir}")

# Removed main block and if __name__ == "__main__":
# def main():
#     media_path = os.getenv('MEDIA_PATH', '/media')
#     log_path = os.getenv('LOG_PATH', 'logs')
#     is_non_interactive = os.getenv("NON_INTERACTIVE", False)

#     if is_non_interactive:
#         print("Running in non-interactive mode.")

#     scanner = MediaScanner(media_path, log_path, is_non_interactive)
#     scanner.scan_directory()
#     scanner.print_summary()

# if __name__ == "__main__":
#     main()
