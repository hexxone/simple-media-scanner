import json
from pathlib import Path
from collections import defaultdict


def parse_and_filter_errors(json_data):
    # Create a nested defaultdict to store the tree structure
    tree = defaultdict(lambda: defaultdict(list))

    # Parse the JSON if it's a string, otherwise use the dict directly
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data

    # Filter and organize errors
    for filepath, info in data.items():
        if info['status'] == 'error':
            # Convert the path to a Path object for easier manipulation
            path = Path(filepath)

            # Get the main folder (first level) and subfolder (second level)
            parts = path.parts
            if len(parts) >= 3:  # Ensure we have enough parts
                main_folder = parts[1]  # Skip the leading slash
                sub_folder = parts[2]
                filename = path.name

                # Add to our tree structure
                tree[main_folder][sub_folder].append({
                    'filename': filename,
                    'last_scan': info['last_scan']
                })

    return tree


def print_error_tree(tree):
    for main_folder, subfolders in sorted(tree.items()):
        print(f"/{main_folder}/")
        for subfolder, files in sorted(subfolders.items()):
            print(f"  /{subfolder}/")
            for file in sorted(files, key=lambda x: x['filename']):
                print(f"    - {file['filename']}")
                # print(f"      Last scan: {file['last_scan']}")


if __name__ == "__main__":
    with open('C:/Users/dome/Downloads/progress.json', 'r') as f:
        data = json.load(f)
        error_tree = parse_and_filter_errors(data)

    # Print the results
    print_error_tree(error_tree)