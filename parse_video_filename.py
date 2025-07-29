from datetime import datetime
import re
from pathlib import Path

def parse_video_filename(filename: str) -> datetime:
    """
    Parse video filename like 'Debut_2025-07-01T113802.mp4' into datetime object.
    
    Args:
        filename: Video filename string
        
    Returns:
        datetime: Parsed datetime object
        
    Raises:
        ValueError: If filename doesn't match expected pattern
    """
    # Remove file extension and path if present
    filename = Path(filename).stem
    
    # Pattern: prefix_YYYY-MM-DDTHHMMSS
    pattern = r'.*_(\d{4}-\d{2}-\d{2}T\d{6})'
    match = re.search(pattern, filename)
    
    if not match:
        raise ValueError(f"Filename '{filename}' doesn't match expected pattern")
    
    datetime_str = match.group(1)
    return datetime.strptime(datetime_str, '%Y-%m-%dT%H%M%S')

# Example usage
if __name__ == "__main__":
    filename = 'Debut_2025-07-01T113802.mp4'
    dt = parse_video_filename(filename)
    print(f"Parsed: {dt}")
