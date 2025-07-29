"""
Convert whisper transcript CSV to LSL (Lab Streaming Layer) compatible format
with absolute timestamps and multi-modal analysis support.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
from parse_video_filename import parse_video_filename
from typing import Optional, Union

def add_absolute_timestamps(csv_path: Union[str, Path], 
                          video_filename: Optional[str] = None) -> pd.DataFrame:
    """
    Parse transcript CSV and add absolute datetime timestamps.
    
    Args:
        csv_path: Path to the whisper transcript CSV file
        video_filename: Video filename to parse date from. If None, inferred from csv_path.
        
    Returns:
        DataFrame with absolute datetime columns added
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path, names=['text', 'start', 'end'])
    
    # Remove empty rows (whisper adds blank lines between segments)
    df = df.dropna(subset=['text'])
    df = df[df['text'].str.strip() != '']
    
    # Get video filename from CSV path if not provided
    if video_filename is None:
        video_filename = csv_path.stem  # removes .csv extension
        if video_filename.endswith('.mp4'):
            video_filename = video_filename[:-4]  # remove .mp4 if present
    
    # Parse the base datetime from video filename
    try:
        base_datetime = parse_video_filename(video_filename)
    except ValueError as e:
        raise ValueError(f"Could not parse datetime from filename '{video_filename}': {e}")
    
    # Convert relative timestamps to absolute datetimes
    df['absolute_start'] = df['start'].apply(
        lambda t: base_datetime + timedelta(seconds=t)
    )
    df['absolute_end'] = df['end'].apply(
        lambda t: base_datetime + timedelta(seconds=t)
    )
    
    return df

def create_lsl_stream_data(df: pd.DataFrame, 
                          stream_name: str = "whisper_transcript",
                          source_id: str = "whisper") -> dict:
    """
    Create LSL-compatible stream data structure from transcript DataFrame.
    
    Args:
        df: DataFrame with transcript data and absolute timestamps
        stream_name: Name for the LSL stream
        source_id: Source identifier for the stream
        
    Returns:
        Dictionary containing LSL stream metadata and data
    """
    
    # Create LSL stream info
    stream_info = {
        "name": stream_name,
        "type": "Markers",
        "channel_count": 1,
        "nominal_srate": 0,  # Irregular sampling
        "channel_format": "string",
        "source_id": source_id,
        "created_at": datetime.now().isoformat(),
        "session_id": f"{source_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }
    
    # Create data samples with timestamps
    samples = []
    for _, row in df.iterrows():
        # Each sample contains the text and timing info
        sample = {
            "timestamp": row['absolute_start'].timestamp(),
            "data": {
                "text": row['text'],
                "duration": row['end'] - row['start'],
                "start_offset": row['start'],
                "end_offset": row['end'],
                "confidence": getattr(row, 'confidence', None)  # if available
            }
        }
        samples.append(sample)
    
    return {
        "stream_info": stream_info,
        "samples": samples,
        "total_samples": len(samples),
        "start_time": df['absolute_start'].min().isoformat(),
        "end_time": df['absolute_end'].max().isoformat()
    }

def save_lsl_stream(stream_data: dict, output_path: Union[str, Path]) -> None:
    """Save LSL stream data to JSON file."""
    output_path = Path(output_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stream_data, f, indent=2, ensure_ascii=False)

def process_transcript_to_lsl(csv_path: Union[str, Path], 
                             output_dir: Optional[Union[str, Path]] = None,
                             video_filename: Optional[str] = None) -> tuple[pd.DataFrame, dict]:
    """
    Complete pipeline: CSV transcript -> absolute timestamps -> LSL stream data.
    
    Args:
        csv_path: Path to whisper transcript CSV
        output_dir: Directory to save LSL JSON file (if None, saves next to CSV)
        video_filename: Video filename for datetime parsing
        
    Returns:
        Tuple of (DataFrame with absolute timestamps, LSL stream data dict)
    """
    csv_path = Path(csv_path)
    
    # Process timestamps
    df = add_absolute_timestamps(csv_path, video_filename)
    
    # Create LSL stream
    stream_name = f"transcript_{csv_path.stem}"
    lsl_data = create_lsl_stream_data(df, stream_name)
    
    # Save LSL stream data
    if output_dir is None:
        output_dir = csv_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / f"{csv_path.stem}.lsl.json"
    save_lsl_stream(lsl_data, output_path)
    
    print(f"Processed {len(df)} transcript segments")
    print(f"Time range: {df['absolute_start'].min()} to {df['absolute_end'].max()}")
    print(f"LSL stream data saved to: {output_path}")
    
    return df, lsl_data

# Example usage and CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python transcript_to_lsl.py <csv_path> [output_dir] [video_filename]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    video_filename = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        df, lsl_data = process_transcript_to_lsl(csv_path, output_dir, video_filename)
        print(f"\nSuccess! Processed {len(df)} transcript segments")
        print("LSL stream data ready for multi-modal analysis")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
