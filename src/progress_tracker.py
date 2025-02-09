import json
import os
from datetime import datetime

class ProgressTracker:
    def __init__(self, progress_file="logs/progress.json"):
        self.progress_file = progress_file
        self.scanned_files = self._load_progress()

    def _load_progress(self):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_progress(self):
        os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
        with open(self.progress_file, 'w') as f:
            json.dump(self.scanned_files, f, indent=2)

    def is_file_scanned(self, file_path):
        return file_path in self.scanned_files

    def mark_file_scanned(self, file_path, status="ok"):
        self.scanned_files[file_path] = {
            "last_scan": datetime.now().isoformat(),
            "status": status
        }
        self.save_progress()