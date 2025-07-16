import whisper_timestamped as whisper
import json
from pathlib import Path

def process_recordings(recordings_dir: Path, output_dir=None, video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v']):
    # Define the recordings directory
    if isinstance(recordings_dir, str):
        recordings_dir = Path(recordings_dir).resolve()
    print(f'processing_recordings for recordings_dir: "{recordings_dir.as_posix()}"...')
    # Create output directory
    if output_dir is None:
        output_dir = recordings_dir.joinpath('transcriptions').resolve()
        # output_dir = Path("./transcriptions")
    if isinstance(output_dir, str):
        output_dir = Path(output_dir).resolve()

    output_dir.mkdir(exist_ok=True)
    print(f'\t transcriptions will output to output_dir: "{output_dir.as_posix()}"')
    
    # Load the model once
    print("Loading Whisper model...")
    model = whisper.load_model("medium")
    
    # Get all video files in the recordings directory
    
    video_files = []
    for ext in video_extensions:
        video_files.extend(recordings_dir.glob(f"*{ext}"))
        video_files.extend(recordings_dir.glob(f"*{ext.upper()}"))
    
    if not video_files:
        print(f"No video files found in {recordings_dir}")
        return
    
    print(f"Found {len(video_files)} video files to process")
    
    output_files = {'json': {}, 'srt': {}}
    # Process each video file
    for video_file in video_files:
        print(f"\nProcessing: {video_file.name}")
        
        try:
            # Load audio from video file
            audio = whisper.load_audio(str(video_file))
            
            # Transcribe with timestamps
            result = whisper.transcribe(
                model, 
                audio, 
                language="en"
            )
            
            # Generate output filenames
            base_name = video_file.stem
            json_file = output_dir / f"{base_name}.json"
            srt_file = output_dir / f"{base_name}.srt"
            
            # Save JSON output
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            output_files['json'][base_name] = json_file
            print(f"  ✓ Saved: {json_file.name}")

            # Save SRT output
            with open(srt_file, 'w', encoding='utf-8') as f:
                whisper.write_srt(result["segments"], f)
            output_files['srt'][base_name] = srt_file
            print(f"  ✓ Saved: {srt_file.name}")
            
        except Exception as e:
            print(f"  ✗ Error processing {video_file.name}: {str(e)}")
            continue
    
    print(f"\nProcessing complete! Output files saved to: {output_dir.resolve()}")
    return output_files

if __name__ == "__main__":
    # Format(s) of the output file(s). Possible formats are: txt, vtt, srt, tsv, csv, json. Several formats can be specified by using commas (ex: "json,vtt,srt"). By default ("all"), all available formats  
    recordings_dir = Path(r"M:\ScreenRecordings\EyeTrackerVR_Recordings").resolve()
    # video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v']
    video_extensions = ['.mp4']
    output_files = process_recordings(recordings_dir=recordings_dir, video_extensions=video_extensions)
    print(f'All processing complete! output_files: {output_files}\n\ndone.')
