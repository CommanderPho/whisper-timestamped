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
    
    patterns = [
        r'.*(\d{4}-\d{2}-\d{2}T\d{6})',           # e.g., Debut_2025-07-01T113802
        r'.*(\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2})' # e.g., 2024-09-11 15-27-36
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            datetime_str = match.group(1)
            try:
                return datetime.strptime(datetime_str, '%Y-%m-%dT%H%M%S')
            except ValueError:
                return datetime.strptime(datetime_str, '%Y-%m-%d %H-%M-%S')
    
    raise ValueError(f"Filename '{filename}' doesn't match expected patterns")


def build_EDF_compatible_video_filename(filename: str, patient_id: str = 1337) -> str:
    dt = parse_video_filename(filename)
    date_part = dt.strftime("%d-%b-%Y").replace(dt.strftime("%b"), dt.strftime("%b").upper())
    frac4 = dt.strftime("%f")[:4]
    time_part = f"{dt.strftime('%Hh%Mm%S')}.{frac4}s"

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    prefix = re.sub(r'\d{4}-\d{2}-\d{2}(T|\s)\d{6}|\d{2}-\d{2}-\d{2}', '', stem).rstrip('_')
    
    return f"{prefix}_{patient_id}_{date_part}_{time_part}{suffix}" if prefix else f"{date_part}_{time_part}{suffix}"

# Example usage
if __name__ == "__main__":
    filename = 'Debut_2025-07-01T113802.mp4'
    print(f'filename: {filename}')
    dt = parse_video_filename(filename)
    print(f"Parsed: {dt}")

    edf_filename = build_EDF_compatible_video_filename(filename=filename)
    print(f"edf_filename: {edf_filename}")

