import json
from pathlib import Path


def parse_and_filter_errors_from_json(json_file_path: Path):
    """
    Parses a JSON file, extracts error entries, and organizes them by full path hierarchy.
    """
    tree = {}

    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)

        for filepath_str, file_info in data.items():
            # Only process entries with error status
            if file_info.get('status') == 'error':
                path = Path(filepath_str)
                parts = path.parts  # Get path components

                current_level = tree
                for part in parts[1:-1]:  # Iterate through directory parts
                    if part not in current_level:
                        current_level[part] = {}
                    current_level = current_level[part]

                # Add file details at the final level
                if '_files' not in current_level:
                    current_level['_files'] = []

                file_details = {
                    'filename': path.name,
                    'error_message': f"Status: {file_info.get('status', 'unknown')}",
                    'timestamp': file_info.get('last_scan', 'N/A')
                }
                current_level['_files'].append(file_details)

    except FileNotFoundError:
        print(f"Error: JSON file not found: {json_file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file {json_file_path}: {e}")
        return None
    except Exception as e:
        print(f"An error occurred while parsing JSON file: {e}")
        return None

    return tree


def print_error_tree(tree, cli_logger=None):
    """Prints the error tree to the console with recursive depth."""
    if not tree:
        if cli_logger:
            cli_logger.info("No errors found in the provided log or data.")
        else:
            print("No errors found.")
        return

    def print_level(node, depth=0):
        """Recursively print each level of the tree."""
        indent = "  " * depth

        for key, value in sorted(node.items()):
            if key == '_files':
                # Print files at this level
                for file_details in sorted(value, key=lambda x: x['filename']):
                    print(f"{indent}- {file_details['filename']} (Timestamp: {file_details['timestamp']})")
                    # Optionally print more details
                    # print(f"{indent}  Error: {file_details['error_message']}")
            else:
                # Print directory and recurse
                print(f"{indent}/{key}/")
                print_level(value, depth + 1)

    print_level(tree)
