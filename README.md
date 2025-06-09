# Unified Media Processing CLI

A versatile command-line tool for scanning, repairing, merging, and processing media files. This tool consolidates and enhances the functionality of previous individual scripts into a unified interface, leveraging FFmpeg for robust media operations.

## Overview

This Python-based CLI application provides a suite of tools to manage your media library:

- **Scan:** Detect corruptions and errors in various media file formats.
- **Repair:** Attempt to fix detected errors through remuxing or re-encoding to MKV.
- **Merge:** Combine sequences of media files (e.g., `video_part1.mp4`, `video_part2.mp4`) into a single MKV file, with options for trimming or crossfading.
- **Process:** An automated pipeline that scans a directory, attempts to repair erroneous files, and then merges sequences from the processed (repaired or copied) files.
- **Report Errors:** Generate a structured, human-readable report of errors from scan logs.

It's designed to be run either locally or via Docker, with support for a wide range of video formats.

## Features

- Comprehensive media file scanning using FFmpeg.
- Automated repair attempts for corrupted files (remux to original format, re-encode to MKV).
- Flexible sequence merging with 'trim' and 'crossfade' modes.
- Full processing pipeline: Scan -> Repair -> Merge.
- Detailed JSON logging for all operations, segregated by module (scanner, repairer, merger, CLI).
- Error reporting utility to parse scan logs and display a hierarchical view of problematic files.
- Support for most common video formats (MP4, MKV, AVI, MOV, WMV, FLV, M4V, MPG, MPEG, M2TS, VOB, TS, MTS).
- Configurable log and output paths.
- Progress tracking for scan operations (skips already scanned files).
- Non-interactive mode for scripting and automation.

## Prerequisites

- **FFmpeg & ffprobe:** Essential for all media operations. These must be installed and accessible in your system's PATH if running locally, or are included in the provided Docker image.
- **Python 3.9+:** Required for local execution.
- **Pip:** For installing Python dependencies if running locally.

## Setup and Installation

### Using Docker (Recommended)

The easiest way to run the Unified Media Processing CLI is with Docker and Docker Compose.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hexxone/simple-media-scanner.git
   cd simple-media-scanner
   ```
2. **Build and Run with Docker Compose:**
   To build the image and run a container in detached mode:

   ```bash
   docke compose up -d --build
   ```

   This will start the service defined in `docke compose.yml`. By default, it's configured to run the `process` command on the `/media` directory.

3. **Accessing the CLI in a Running Container:**
   If you want to run ad-hoc commands or interact with the CLI directly:
   ```bash
   docke compose exec unified-media-processor bash
   ```
   (Note: `unified-media-processor` should match the `container_name` in your `docke compose.yml`. The original `docke compose.yml` used `simple-media-scanner`, this should be updated for consistency if desired.)
   Inside the container, you can then run `python src/main.py --help`.

### Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hexxone/simple-media-scanner.git
   cd simple-media-scanner
   ```
2. **Install Python 3.9 or higher.**
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Ensure FFmpeg and ffprobe are installed and in your PATH.**

## Usage

The CLI is invoked via `src/main.py`.

**General Syntax:**

```bash
python src/main.py [COMMON_OPTIONS] <command> [COMMAND_SPECIFIC_OPTIONS]
```

### Common Options

- `--log-path <path>`: Directory for log files (default: `logs/`). All modules will create their specific log files (e.g., `main_cli.log`, `media_scanner_*.log`) here.
- `--output-path <path>`: Directory for output files from `repair` and `merge` commands, and the `process` pipeline (default: `output/`).
- `--non-interactive`: Run in non-interactive mode. Suppresses confirmations and enables script-friendly output (where applicable).

### Commands

#### `scan`

Scans all media files in the specified directory for errors.

**Syntax:**

```bash
python src/main.py scan <input_directory>
```

- `<input_directory>`: Path to the directory containing media files to scan.

**Description:**
This command iterates through media files, uses FFmpeg to detect stream errors or container issues, and logs any problems found to a JSON log file in the directory specified by `--log-path` (e.g., `logs/media_scanner_YYYYMMDD_HHMMSS.log`). It also tracks progress in `logs/progress.json`.

#### `repair`

Attempts to repair a single media file or all media files in a directory.

**Syntax:**

```bash
python src/main.py repair <input_file_or_directory> [--recursive]
```

- `<input_file_or_directory>`: Path to a single media file or a directory containing media files.
- `--recursive` (optional): If `<input_file_or_directory>` is a directory, process it recursively.

**Description:**
The repair process involves multiple steps:

1. **Remux:** Tries to remux the file into the same container format. If successful and error-free, this is the output.
2. **Re-encode to MKV:** If remuxing fails or the file is of an older/problematic format (e.g., AVI, WMV, FLV) or still has errors, it's re-encoded to an MKV container with standard codecs (H.264, AAC).
   Repaired files are saved in the directory specified by `--output-path`. Timestamps from original files are preserved.

#### `merge`

Finds and merges sequences of media files in a directory (e.g., `file_01.mp4`, `file_02.mp4`).

**Syntax:**

```bash
python src/main.py merge <input_directory> [--merge-mode <mode>] [--trim-duration <sec>] [--crossfade-duration <sec>]
```

- `<input_directory>`: Directory containing sequences of media files.
- `--merge-mode [trim|crossfade]` (optional): Merging strategy (default: `trim`).
  - `trim`: Simple concatenation.
  - `crossfade`: Files are merged with a crossfade transition.
- `--trim-duration <seconds>` (optional): Duration for overlap/trim in `trim` mode (currently informational, filter logic is simple concat). Default: `0.5`.
- `--crossfade-duration <seconds>` (optional): Duration of the crossfade effect in `crossfade` mode. Default: `1.0`.

**Description:**
This command identifies file sequences based on naming patterns (e.g., `basename_1.ext`, `basename_2.ext`). It then merges these sequences into a single MKV file in the `--output-path`. The timestamp of the first file in the sequence is applied to the merged output.

#### `process`

Performs a full pipeline: scans files, attempts repairs, and then merges sequences.

**Syntax:**

```bash
python src/main.py process <input_directory> [--merge-mode <mode>] [--crossfade-duration <sec>]
```

- `<input_directory>`: The root directory for processing.
- `--merge-mode`, `--crossfade-duration`: As defined in the `merge` command, to be applied during the merge stage of the pipeline.

**Description:**

1. **Scan:** Recursively scans `<input_directory>` for media errors (similar to the `scan` command).
2. **Copy/Repair:**
   - Error-free files are copied directly from `<input_directory>` to `--output-path`.
   - Files with detected errors are processed by the repair logic (`repair_media_file`), with repaired versions saved to `--output-path`. If a file cannot be repaired, it might be skipped for the merge stage.
3. **Merge:** The `find_and_merge_sequences_in_folder` logic is run on the `--output-path` (which now contains a mix of original error-free files and repaired files) to combine any identified sequences.

#### `report-errors`

Parses a JSON scan log file and prints a hierarchical tree of errors.

**Syntax:**

```bash
python src/main.py report-errors <path_to_scan_log.json>
```

- `<path_to_scan_log.json>`: Path to a specific JSON log file generated by the `scan` command (e.g., `logs/media_scanner_YYYYMMDD_HHMMSS.log`).

**Description:**
This utility helps in quickly identifying which files had errors during a scan, organized by their directory structure.

## Docker Usage Example

Assuming your `docke compose.yml` is configured (see `docke compose.yml.example` or the one provided in the repo):

1. **Place your media files** in the directory you've mapped to `/media` in the container (e.g., `./media/` on your host).
2. **Run the processing pipeline:**

   ```bash
   docke compose run --rm unified-media-processor process /media --output-path /app/output --log-path /app/logs
   ```

   (Adjust `unified-media-processor` if you've named your service differently in `docke compose.yml`.)

   This command will:

   - Start a new container.
   - Execute the `process` command on the `/media` directory within the container.
   - Scanner logs will appear in `./logs/` on your host.
   - Repaired files, copied originals, and merged files will appear in `./output/` on your host.
   - The `--rm` flag ensures the container is removed after the command completes.

3. **To run other commands,** simply change the command part:

   ```bash
   # Example: Scan only
   docke compose run --rm unified-media-processor scan /media

   # Example: Generate an error report from a specific log file
   # (Assuming 'scan_log.json' is the name of your scanner's output log file in the mapped ./logs directory)
   docke compose run --rm unified-media-processor report-errors /app/logs/scan_log.json
   ```

## Project Structure (Simplified)

```
.
├── docke compose.yml
├── Dockerfile
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py         # Main CLI entry point
│   ├── core/           # Core utilities (ffmpeg, logging)
│   │   ├── __init__.py
│   │   ├── ffmpeg_utils.py
│   │   └── log_utils.py
│   ├── scanner/        # Media scanning module
│   │   ├── __init__.py
│   │   ├── scanner.py
│   │   └── progress_tracker.py
│   ├── repair/         # Media repair module
│   │   ├── __init__.py
│   │   └── repairer.py
│   ├── merger/         # Media merging module
│   │   ├── __init__.py
│   │   └── merger.py
│   └── reporter.py     # Error reporting utility
├── tests/              # Unit tests
│   ├── __init__.py
│   └── test_ffmpeg_utils.py
├── logs/               # Default directory for log files (created automatically)
│   └── .gitkeep
└── output/             # Default directory for processed files (created automatically)
    └── .gitkeep
```

## Contributing

Contributions are welcome! Please feel free to fork the repository, make your changes, and submit a pull request. For major changes, please open an issue first to discuss what you would like to change.

Ensure any new code includes appropriate tests and adheres to existing coding styles (e.g., run a linter).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details (assuming a LICENSE file exists or will be added).

## Author

- [hexxone](https://github.com/hexxone) (Adapted from original simple-media-scanner)
