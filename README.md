# Simple Media Scanner

A Docker-based Python application that uses FFmpeg to scan media files for corruptions and errors.

The scanner maintains progress between runs and provides detailed error logging for problematic files.

## Features

- **Automated Media Scanning**: Recursively scans directories for media files
- **Error Detection**: Uses FFmpeg to detect corruption and errors in media files
- **Progress Tracking**: Maintains scan progress between runs
- **Detailed Logging**: JSON-formatted logs for easy parsing and analysis
- **Docker Support**: Runs in a containerized environment
- **Progress Visualization**: Real-time progress bar during scanning
- **Skip Already Scanned**: Efficiently skips previously validated files
- **Summary Reports**: Provides detailed scan summary upon completion

## Supported Media Formats

- MP4 (.mp4)
- Matroska (.mkv)
- AVI (.avi)
- QuickTime (.mov)
- Windows Media (.wmv)
- Flash Video (.flv)
- M4V (.m4v)
- MPEG (.mpg, .mpeg)
- M2TS (.m2ts)

## Prerequisites

- Docker
- Docker Compose
- Sufficient disk space for media files
- Read access to media directory

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd simple-media-scanner
```

2. Build and run with Docker Compose:

```bash
docker compose up -d --build
```

## Configuration

### Environment Variables

The following environment variables can be configured in `docker-compose.yml`:

- `MEDIA_PATH`: Path to media directory inside container (default: `/media`)
- `LOG_PATH`: Path to log directory inside container (default: `/app/logs`)

### Volume Mounts

The default `docker-compose.yml` includes two volume mounts:
- `./media:/media` - Your media directory
- `./logs:/app/logs` - Local logs directory

Modify these in `docker-compose.yml` according to your needs.

## Project Structure

```
media-scanner/
├── docker-compose.yml
├── Dockerfile
├── README.md
├── requirements.txt
├── src/
│   ├── media_scanner.py
│   └── progress_tracker.py
└── logs/
    └── .gitkeep
```

## How It Works

1. **Initialization**
   - Loads progress from previous scans
   - Sets up JSON logging
   - Prepares FFmpeg environment

2. **File Discovery**
   - Recursively searches for media files
   - Filters by supported file extensions
   - Creates list of files to process

3. **Scanning Process**
   - Checks progress tracker for previously scanned files
   - Uses FFmpeg to analyze each file
   - Updates progress after each file
   - Logs errors for corrupted files

4. **Progress Tracking**
   - Maintains JSON file with scan history
   - Records timestamp of last scan
   - Tracks scan status for each file

5. **Error Logging**
   - Creates timestamped log files
   - Logs only problematic files
   - Uses JSON format for structured logging

## Logs

### Error Logs

Located in `logs/media_scan_errors_YYYYMMDD_HHMMSS.log`
```json
{
  "timestamp": "2024-02-09T12:00:00.000Z",
  "level": "ERROR",
  "file": "/media/example.mp4",
  "error": "Error detail message"
}
```

### Progress File

Located in `logs/progress.json`
```json
{
  "/media/example.mp4": {
    "last_scan": "2024-02-09T12:00:00.000Z",
    "status": "ok"
  }
}
```

## Output

The scanner provides real-time progress information and a summary upon completion:

```
Starting media scan in: /media
Scanning files: 100%|██████████| 150/150 [00:30<00:00, 5.00 files/s]

Scan Summary:
Total files processed: 150
Files scanned: 100
Files skipped (already scanned): 50
Files with errors: 3
Error log location: /app/logs
```

## Development

### Adding New Media Formats

To add support for additional media formats, modify the `media_extensions` set in `src/media_scanner.py`:

```python
self.media_extensions = {
    '.mp4', '.mkv', '.avi',  # existing formats
    '.new_format'  # add new format here
}
```

### Custom Error Checking

The FFmpeg error checking can be customized by modifying the `scan_file` method in `src/media_scanner.py`.

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Ensure proper read permissions on media directory
   - Check Docker user permissions

2. **FFmpeg Errors**
   - Verify FFmpeg installation in container
   - Check FFmpeg version compatibility

3. **Progress File Corruption**
   - Delete `logs/progress.json` to reset progress
   - Restart the container

### Debug Mode

To enable more detailed logging:

1. Modify the logging level in `src/media_scanner.py`:
```python
self.logger.setLevel(logging.DEBUG)
```

2. Rebuild and run the container:
```bash
docker compose up -d --build
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[MIT License](LICENSE)

## Author

- [hexxone](https://github.com/hexxone)
