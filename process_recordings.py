import os
# import sys
# import argparse
import json
from pathlib import Path

from whisper.utils import str2bool, optional_float, optional_int
import whisper_timestamped as whisper
from whisper_timestamped.transcribe import write_csv, flatten, remove_keys

try:
    # Old whisper version # Before https://github.com/openai/whisper/commit/da600abd2b296a5450770b872c3765d0a5a5c769
    from whisper.utils import write_txt, write_srt, write_vtt
    write_tsv = lambda transcript, file: write_csv(transcript, file, sep="\t", header=True, text_first=False, format_timestamps=lambda x: round(1000 * x))

except ImportError:
    # New whisper version
    from whisper.utils import get_writer

    def do_write(transcript, file, output_format):
        writer = get_writer(output_format, os.path.curdir)
        try:
            return writer.write_result({"segments": list(transcript)}, file, {
                "highlight_words": False,
                "max_line_width": None,
                "max_line_count": None,
            })
        except TypeError:
            # Version <= 20230314
            return writer.write_result({"segments": transcript}, file)
    def get_do_write(output_format):
        return lambda transcript, file: do_write(transcript, file, output_format)

    write_txt = get_do_write("txt")
    write_srt = get_do_write("srt")
    write_vtt = get_do_write("vtt")
    write_tsv = get_do_write("tsv")
    




def write_results(result, output_dir: Path, base_name: str, output_formats = ['json', 'csv', 'srt', 'vtt', 'txt']):
    """ Writes the results object out to disk
    base_name = video_file.stem
    output_files = write_results(result, output_dir=output_dir, base_name=base_name)

    """
    # Generate output filenames
    output_file_path: Path = output_dir.joinpath(base_name) ## with no suffix
    print(F'building output files for output_file_path: "{output_file_path.as_posix()}"')
    output_files = {k:dict() for k in output_formats} #{'json': {}, 'srt': {}, 'csv': {}}

    ## Save JSON:
    if "json" in output_formats:
        try:
            # save JSON
            a_file = output_file_path.with_suffix(".words.json")
            with open(a_file, "w", encoding="utf-8") as js:
                json.dump(result, js, indent=2, ensure_ascii=False)
            output_files['.'.join([k.removeprefix('.') for k in a_file.suffixes])][base_name] = a_file
            print(f"  ✓ Saved: {a_file.name}")
        except Exception as e:
            print(f"  ✗ Error saving JSON: {str(e)}")

    # save CSV
    if "csv" in output_formats:
        try:
            a_file = output_file_path.with_suffix(".csv")
            with open(a_file, "w", encoding="utf-8") as csv:
                write_csv(result["segments"], file=csv, header=True)
            output_files['.'.join([k.removeprefix('.') for k in a_file.suffixes])][base_name] = a_file
            print(f"  ✓ Saved: {a_file.name}")
        except Exception as e:
            print(f"  ✗ Error saving CSV: {str(e)}")

        try:
            a_file = output_file_path.with_suffix(".words.csv")
            with open(a_file, "w", encoding="utf-8") as csv:
                write_csv(flatten(result["segments"], "words"), file=csv, header=True)
            output_files['.'.join([k.removeprefix('.') for k in a_file.suffixes])][base_name] = a_file
            print(f"  ✓ Saved: {a_file.name}")
        except Exception as e:
            print(f"  ✗ Error saving words CSV: {str(e)}")

    # save TXT
    if "txt" in output_formats:
        try:
            a_file = output_file_path.with_suffix(".txt")
            with open(a_file, "w", encoding="utf-8") as txt:
                write_txt(result["segments"], file=txt)
            output_files['.'.join([k.removeprefix('.') for k in a_file.suffixes])][base_name] = a_file
            print(f"  ✓ Saved: {a_file.name}")
        except Exception as e:
            print(f"  ✗ Error saving TXT: {str(e)}")

    # save VTT
    if "vtt" in output_formats:
        try:
            a_file = output_file_path.with_suffix(".vtt")
            with open(a_file, "w", encoding="utf-8") as vtt:
                write_vtt(remove_keys(result["segments"], "words"), file=vtt)
            output_files['.'.join([k.removeprefix('.') for k in a_file.suffixes])][base_name] = a_file
            print(f"  ✓ Saved: {a_file.name}")
        except Exception as e:
            print(f"  ✗ Error saving VTT: {str(e)}")

        try:
            a_file = output_file_path.with_suffix(".words.vtt")
            with open(a_file, "w", encoding="utf-8") as vtt:
                write_vtt(flatten(result["segments"], "words"), file=vtt)
            output_files['.'.join([k.removeprefix('.') for k in a_file.suffixes])][base_name] = a_file
            print(f"  ✓ Saved: {a_file.name}")
        except Exception as e:
            print(f"  ✗ Error saving words VTT: {str(e)}")

    # save SRT
    if "srt" in output_formats:
        try:
            a_file = output_file_path.with_suffix(".srt")
            with open(a_file, "w", encoding="utf-8") as srt:
                write_srt(remove_keys(result["segments"], "words"), file=srt)
            output_files['.'.join([k.removeprefix('.') for k in a_file.suffixes])][base_name] = a_file
            print(f"  ✓ Saved: {a_file.name}")
        except Exception as e:
            print(f"  ✗ Error saving SRT: {str(e)}")

        try:
            a_file = output_file_path.with_suffix(".words.srt")
            with open(a_file, "w", encoding="utf-8") as srt:
                write_srt(flatten(result["segments"], "words"), file=srt)
            output_files['.'.join([k.removeprefix('.') for k in a_file.suffixes])][base_name] = a_file
            print(f"  ✓ Saved: {a_file.name}")
        except Exception as e:
            print(f"  ✗ Error saving words SRT: {str(e)}")

    # save TSV
    if "tsv" in output_formats:
        try:
            a_file = output_file_path.with_suffix(".tsv")
            with open(a_file, "w", encoding="utf-8") as csv:
                write_tsv(result["segments"], file=csv)
            output_files['.'.join([k.removeprefix('.') for k in a_file.suffixes])][base_name] = a_file
            print(f"  ✓ Saved: {a_file.name}")
        except Exception as e:
            print(f"  ✗ Error saving TSV: {str(e)}")

        try:
            a_file = output_file_path.with_suffix(".words.tsv")
            with open(a_file, "w", encoding="utf-8") as csv:
                write_tsv(flatten(result["segments"], "words"), file=csv)
            output_files['.'.join([k.removeprefix('.') for k in a_file.suffixes])][base_name] = a_file
            print(f"  ✓ Saved: {a_file.name}")
        except Exception as e:
            print(f"  ✗ Error saving words TSV: {str(e)}")

    return output_files


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
    
    output_files = {'json': {}, 'srt': {}, 'csv': {}}
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
            curr_output_files_dict = write_results(result, output_dir=output_dir, base_name=base_name)
            ## add outputted files to the output_files dict
            for k, curr_out_files_dict in curr_output_files_dict.items():
                if k not in output_files:
                    output_files[k] = dict() ## initialize a new dict
                output_files[k].update(**curr_out_files_dict)
            
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
