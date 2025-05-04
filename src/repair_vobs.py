import os
import subprocess
import shutil
from pathlib import Path

def run_ffmpeg(cmd, log_file):
    try:
        with open(log_file, 'w') as log:
            result = subprocess.run(cmd, stdout=log, stderr=log)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {' '.join(cmd)}\n{e}")
        return False

def has_ffmpeg_errors(file_path):
    import subprocess
    cmd = [
        'ffmpeg', '-v', 'error', '-i', str(file_path), '-f', 'null', '-'
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return bool(result.stderr.strip())

def preserve_timestamp(source_file, target_file):
    """Copy the timestamp from source file to target file"""
    source_stat = os.stat(str(source_file))
    os.utime(str(target_file), (source_stat.st_atime, source_stat.st_mtime))

def process_vob(vob_path):
    vob_path = Path(vob_path)
    # Create output directory in the same folder as the VOB file
    output_dir = vob_path.parent / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    base = output_dir / vob_path.stem

    if not has_ffmpeg_errors(vob_path):
        print(f"Original file {vob_path} has no errors. Nothing to do...")
        return None

    # Step 1: Remux
    remuxed = base.with_suffix('.remux.vob')

    if vob_path == remuxed:
        print(f"Skipping file: '{vob_path}' because its in the output dir.")
        return None

    log1 = base.with_suffix('.remux.log')
    if remuxed.exists():
        remuxed.unlink()
    cmd1 = [
        'ffmpeg', '-y', '-err_detect', 'ignore_err', '-i', str(vob_path),
        '-c', 'copy', str(remuxed)
    ]
    print(f"Remuxing {vob_path} ...")
    if run_ffmpeg(cmd1, log1):
        preserve_timestamp(vob_path, remuxed)

    # Step 2: Check for errors in remuxed file
    if remuxed.exists() and remuxed.stat().st_size > 1*1024*1024:
        if not has_ffmpeg_errors(remuxed):
            print(f"Remuxed file {remuxed} has no errors.")
            return remuxed
        else:
            print(f"Remuxed file {remuxed} still has errors, re-encoding to MKV...")

    # Step 3: Re-encode to MKV
    mkv = base.with_suffix('.mkv')
    log2 = base.with_suffix('.mkv.log')
    if mkv.exists():
        mkv.unlink()
    cmd2 = [
        'ffmpeg', '-y', '-err_detect', 'ignore_err', '-i', str(vob_path),
        '-c:v', 'libx264', '-c:a', 'aac', str(mkv)
    ]
    if run_ffmpeg(cmd2, log2):
        preserve_timestamp(vob_path, mkv)

    if mkv.exists() and mkv.stat().st_size > 1*1024*1024:
        if not has_ffmpeg_errors(mkv):
            print(f"Re-encoded MKV {mkv} has no errors.")
            return mkv
        else:
            print(f"Re-encoded MKV {mkv} still has errors, extracting streams...")

    # Step 4: Extract streams as last resort
    m2v = base.with_suffix('.m2v')
    mp2 = base.with_suffix('.mp2')
    log3v = base.with_suffix('.m2v.log')
    log3a = base.with_suffix('.mp2.log')
    cmd3v = [
        'ffmpeg', '-y', '-err_detect', 'ignore_err', '-i', str(vob_path),
        '-map', '0:v:0', '-c', 'copy', str(m2v)
    ]
    cmd3a = [
        'ffmpeg', '-y', '-err_detect', 'ignore_err', '-i', str(vob_path),
        '-map', '0:a:0', '-c', 'copy', str(mp2)
    ]
    print(f"Extracting video stream from {vob_path} ...")
    if run_ffmpeg(cmd3v, log3v):
        preserve_timestamp(vob_path, m2v)
    print(f"Extracting audio stream from {vob_path} ...")
    if run_ffmpeg(cmd3a, log3a):
        preserve_timestamp(vob_path, mp2)
    print(f"Extracted streams: {m2v}, {mp2}")
    return None

def process_folder(root_dir):
    root_dir = Path(root_dir)

    extensions = ['*.VOB', '*.MPG']
    files = [f for ext in extensions for f in root_dir.rglob(ext)]

    # Process all video files in the directory and its subdirectories
    for vob_file in files:
        print(f"\nProcessing: {vob_file}")
        fixed_file = process_vob(vob_file)

        # If we got a successfully fixed file, move it to the parent directory
        if fixed_file and fixed_file.exists():
            parent_dir = vob_file.parent
            new_name = parent_dir / f"{vob_file.stem}_fixed{fixed_file.suffix}"

            # If a file with the same name exists in the parent directory, add a number
            counter = 1
            while new_name.exists():
                new_name = parent_dir / f"{vob_file.stem}_fixed_{counter}{fixed_file.suffix}"
                counter += 1

            print(f"Moving fixed file to: {new_name}")
            shutil.move(str(fixed_file), str(new_name))
            # Preserve the timestamp after moving the file
            preserve_timestamp(vob_file, new_name)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch repair VOB files using ffmpeg.")
    parser.add_argument("input_folder", help="Root folder to scan for VOB files")
    args = parser.parse_args()
    process_folder(args.input_folder)