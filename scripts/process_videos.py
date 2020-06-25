import subprocess
import csv
import json
from pathlib import Path
import re

conference="ACMC 2020"
typeface="Lato" # use a font with Thin, Regular & Bold weights
titlecard_length_sec = 10


media_path = Path("media")
media_extensions = [".mkv", ".mov", ".mp4", ".wav"]
output_path = media_path / "processed"

PAPERS = list(csv.DictReader(open("sitedata/papers.csv")))


def title_and_artist_from_uid(uid):
    for p in PAPERS:
        if int(p["UID"]) == uid:
            return (p["title"], p["authors"])


def probe(media_filename):
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            media_filename,
        ],
        capture_output=True,
    )
    return json.loads(proc.stdout.decode("utf-8"))


def is_audio_only(media_filename):
    streams = [s["codec_type"] for s in probe(media_filename)["streams"]]
    return "video" not in streams


def video_dimensions(filename):
    for stream in probe(filename)["streams"]:
        if stream["codec_type"] == "video":
            return (int(stream["width"]), int(stream["height"]))

    raise ValueError(f"no video streams found in {filename}")


def get_media_path(uid):

    for mf in media_path.glob(f"{uid}.*"):
        if mf.suffix in media_extensions:
            return mf

    raise ValueError(f"No media file found for UID {uid}")
    title, artist = title_and_artist_from_uid(uid)
    titlecard_path = media_path / "titlecards" / f"{uid}-titlecard.mkv"
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            # add blank audio
            "-i", f"anoisesrc=d={titlecard_length_sec}:c=pink:a=0.0",
            # set bg colour, video size & duration
            "-f", "lavfi",
            # select virtual input video device
            "-i", f"color=c=#222222:s=1920x1080:d={titlecard_length_sec}",
            # title
            "-vf", f"drawtext=fontfile='{typeface}\:style=Thin':fontsize=160:fontcolor=#EEEEEE:x=100:y=h-500:text='{title}', " +
            # artist
            f"drawtext=fontfile='{typeface}\:style=Bold':fontsize=70:fontcolor=#EEEEEE:x=100:y=h-280:text='{artist}', " +
            # conference
            f"drawtext=fontfile='{typeface}\:style=Bold':fontsize=50:fontcolor=#EEEEEE:x=100:y=h-200:text='{conference}'",
            # output file
            titlecard_path
        ]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    return titlecard_path


def process_video():

    # accumulator variables
    videos = []
    filter_string = ""
    video_index = 0

    # build up the list of files & filters for the ffmpeg command
    for p in media_path.iterdir():
        uid = uid_from_filename(p.name)
        if uid:
            videos.append("-i")
            videos.append(make_titlecard(uid))
            videos.append("-i")
            videos.append(p)
            filter_string = filter_string + f"[{video_index}:v] [{video_index}:a] [{video_index+1}:v] [{video_index+1}:a] "
            video_index += 2

    if not videos:
        print("No valid videos found, aborting")
        exit(1)

    else:
        filter_string = filter_string + f"concat=n={video_index}:v=1:a=1 [v] [a]"

        print(filter_string)

        # it's showtime!
        subprocess.run(
            ["ffmpeg"] + videos
            + [
                "-filter_complex",
                filter_string,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-y",
                (output_path / "output.mkv").resolve(),
            ]
        )
        return True


if __name__ == '__main__':

    process_video()
