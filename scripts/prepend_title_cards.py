import subprocess
from pathlib import Path
import re

conference="ACMC 2020"
typeface="AlegreyaSans" # use a font with Thin, Regular & Bold weights
titlecard_length_sec = 3


media_path = Path("media")
output_path = media_path / "processed"

def make_titlecard(artist, title, UID):
    titlecard_path = media_path / "titlecards" / f"{UID}-titlecard.mkv"
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            # add blank audio
            "-i", "anullsrc", "-t", str(titlecard_length_sec),
            # set bg colour, video size & duration
            "-f", "lavfi",
            # select virtual input video device
            "-i", f"color=c=black:s=1920x1080:d={titlecard_length_sec}",
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
        m = re.search('([0-9]+).(mp4|mkv|mov)', p.name)
        if m:
            videos.append("-i")
            videos.append(make_titlecard("artist", "title", m.group(1)))
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
