import os
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
from pythonjsonlogger import jsonlogger
from src.progress_tracker import ProgressTracker

class MediaScanner:
    def __init__(self, media_path, log_path):
        self.media_path = Path(media_path)
        self.log_path = Path(log_path)
        self.progress_tracker = ProgressTracker()
        self.setup_logging()
        self.media_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', 
            '.flv', '.m4v', '.mpg', '.mpeg', '.m2ts'
        }
        self.error_count = 0
        self.scanned_count = 0
        self.skipped_count = 0

    def setup_logging(self):
        if not os.path.exists(self.log_path):
            os.makedirs(self.log_path)
        log_file = self.log_path / f"media_scan_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.logger = logging.getLogger('media_scanner')
        self.logger.setLevel(logging.INFO)
        
        formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(message)s')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def scan_file(self, file_path):
        """Scan a single media file for errors using ffmpeg."""
        cmd = [
            'ffmpeg', '-v', 'error', '-i', str(file_path),
            '-f', 'null', '-'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.stderr:
                self.error_count += 1
                self.logger.error({
                    'file': str(file_path),
                    'error': result.stderr.strip()
                })
                self.progress_tracker.mark_file_scanned(str(file_path), "error")
                return False
            
            self.progress_tracker.mark_file_scanned(str(file_path), "ok")
            return True
            
        except subprocess.SubprocessError as e:
            self.error_count += 1
            self.logger.error({
                'file': str(file_path),
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
        
        with tqdm(total=len(media_files), desc="Scanning files") as pbar:
            for file_path in media_files:
                if self.progress_tracker.is_file_scanned(str(file_path)):
                    self.skipped_count += 1
                    pbar.update(1)
                    continue
                
                self.scan_file(file_path)
                self.scanned_count += 1
                pbar.update(1)

    def print_summary(self):
        """Print a summary of the scan results."""
        print("\nScan Summary:")
        print(f"Total files processed: {self.scanned_count + self.skipped_count}")
        print(f"Files scanned: {self.scanned_count}")
        print(f"Files skipped (already scanned): {self.skipped_count}")
        print(f"Files with errors: {self.error_count}")
        print(f"Error log location: {self.log_path}")

def main():
    media_path = os.getenv('MEDIA_PATH', '/media')
    log_path = os.getenv('LOG_PATH', 'logs')
    
    scanner = MediaScanner(media_path, log_path)
    scanner.scan_directory()
    scanner.print_summary()

if __name__ == "__main__":
    main()