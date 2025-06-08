import json
from pathlib import Path
from collections import defaultdict

def parse_and_filter_errors_from_log(log_file_path: Path):
    """
    Parses a JSON log file where each line is a JSON object,
    extracts entries that represent errors, and organizes them by path.
    Assumes log format from core.log_utils (JSON objects per line).
    """
    tree = defaultdict(lambda: defaultdict(list))

    try:
        with open(log_file_path, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line)

                    # Check if the log entry indicates an error and has file information
                    if log_entry.get('level') == 'ERROR' and 'file' in log_entry:
                        filepath_str = log_entry['file']
                        path = Path(filepath_str)

                        # Using parent.name for main_folder and path.name for filename
                        # This structure might need adjustment based on desired output.
                        # For a structure like /MainFolder/SubFolder/file.txt
                        # parts[0] = / (or drive letter)
                        # parts[1] = MainFolder
                        # parts[2] = SubFolder
                        # ...
                        # parts[-1] = file.txt

                        parts = path.parts
                        if len(parts) >= 2: # e.g. /MainFolder/file.txt or MainFolder/file.txt
                            # Let's assume the "main_folder" is the direct parent of the file for simplicity here.
                            # And "sub_folder" could be the grandparent, or we simplify the tree.
                            # For the original structure: tree[main_folder][sub_folder].append(file_info)
                            # If path is /media/movies/action/movie.mkv
                            # parts[0]=/, parts[1]=media, parts[2]=movies, parts[3]=action, parts[4]=movie.mkv
                            # To match original: main_folder=parts[1], sub_folder=parts[2]

                            main_folder_name = parts[1] if len(parts) > 1 else "root" # e.g. 'media'
                            sub_folder_name = parts[2] if len(parts) > 2 else "root_sub" # e.g. 'movies'

                            file_info = {
                                'filename': path.name,
                                'error_message': log_entry.get('message', log_entry.get('error', 'No specific error message')),
                                'timestamp': log_entry.get('asctime', 'N/A')
                            }
                            tree[main_folder_name][sub_folder_name].append(file_info)
                        else: # File in root or very shallow path
                            main_folder_name = "root_direct"
                            file_info = {
                                'filename': path.name,
                                'error_message': log_entry.get('message', log_entry.get('error', 'No specific error message')),
                                'timestamp': log_entry.get('asctime', 'N/A')
                            }
                            tree[main_folder_name][path.stem].append(file_info) # Use stem if no subfolder

                except json.JSONDecodeError:
                    print(f"Warning: Skipping line, could not decode JSON: {line.strip()}")
                    continue
    except FileNotFoundError:
        print(f"Error: Log file not found: {log_file_path}")
        return None
    except Exception as e:
        print(f"An error occurred while parsing log file: {e}")
        return None

    return tree

def print_error_tree(tree, cli_logger=None):
    """Prints the error tree to the console."""
    if not tree:
        if cli_logger:
            cli_logger.info("No errors found in the provided log or data.")
        else:
            print("No errors found.")
        return

    for main_folder, subfolders in sorted(tree.items()):
        print(f"/{main_folder}/")
        for subfolder, files in sorted(subfolders.items()):
            print(f"  /{subfolder}/")
            for file_details in sorted(files, key=lambda x: x['filename']):
                print(f"    - {file_details['filename']} (Timestamp: {file_details['timestamp']})")
                # Optionally print more details like the error message
                # print(f"      Error: {file_details['error_message']}")
