import subprocess
import csv
import json
from pathlib import Path
import re

conference="ACMC 2020"
titlecard_length_sec = 10


media_path = Path("media")
media_extensions = [".mkv", ".mov", ".mp4", ".wav"]
output_path = media_path / "processed"

PAPERS = list(csv.DictReader(open("sitedata/papers.csv")))

# transform a couple of columns to integer
for p in PAPERS:
    p["UID"] = int(p["UID"])

    # for session position, just let the "TBA" ones slide for now
    try:
        p["session_position"] = int(p["session_position"])
    except ValueError:
        pass

# paper/session order helpers

def title_and_artist_from_uid(uid):
    for p in PAPERS:
        if p["UID"] == uid:
            return (p["title"], p["authors"])


def all_sessions():
    return set(p["session_name"] for p in PAPERS)


def get_session_schedule(session_name):
    schedule = []
    for p in PAPERS:
        if p["session_name"] == session_name:
            schedule.append((p["UID"], p["session_position"]))

    return sorted(schedule, key = lambda p: p[1])


# FFmpeg helpers

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


def titlecard_drawtext_filter(uid):

    typeface="Lato" # use a font with Thin, Regular & Bold weights
    title, artist = title_and_artist_from_uid(uid)

    return [
        "-vf", f"drawtext=fontfile='{typeface}\:style=Thin':fontsize=160:fontcolor=#EEEEEE:x=100:y=h-500:text='{title}', " +
        # artist
        f"drawtext=fontfile='{typeface}\:style=Bold':fontsize=70:fontcolor=#EEEEEE:x=100:y=h-280:text='{artist}', " +
        # conference
        f"drawtext=fontfile='{typeface}\:style=Bold':fontsize=50:fontcolor=#EEEEEE:x=100:y=h-200:text='{conference}'",
    ]


def make_titlecard(uid):

    titlecard_path = output_path / "tmp" / f"{uid}-titlecard.mkv"
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
        ] +
        # title
        titlecard_drawtext_filter(uid) +
        # output file
        [titlecard_path]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    return titlecard_path


def make_audio(uid):

    mp = get_media_path(uid)
    assert is_audio_only(mp)

    # make the titlecard (no audio, just 10s)
    tc = make_titlecard(uid)

    # attach the titlecard to the actual audio file
    tmp = output_path / "tmp" / f"{uid}-audio-with-titlecard.mkv"

    # make the
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            # add blank audio
            "-i", mp,
            # set bg colour, video size & duration
            "-f", "lavfi",
            # select virtual input video device
            "-i", f"color=c=#222222:s=1920x1080:d={titlecard_length_sec}",
        ] +
        # title
        titlecard_drawtext_filter(uid) +
        # output file
        [tmp]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    of = output_path / f"{uid}.mkv"
    # now smoosh it on to the front

    proc = subprocess.run(
        ["ffmpeg",
         "-i", tc,
         "-i", tmp,
         "-filter_complex", "[0:v] [0:a] [1:v] [1:a] concat=n=2:v=1:a=1 [v] [a]",
         "-map", "[v]", "-map", "[a]",
         "-y", of
        ]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    return of


def make_video(uid):

    mp = get_media_path(uid)
    of = output_path / f"{uid}.mkv"

    assert not is_audio_only(mp)
    # now smoosh it on to the front

    tc = make_titlecard(uid)

    proc = subprocess.run(
        ["ffmpeg",
         "-i", tc,
         "-i", mp,
         "-filter_complex", "[0:v] [0:a] [1:v] [1:a] concat=n=2:v=1:a=1 [v] [a]",
         "-map", "[v]", "-map", "[a]",
         "-y", of
        ]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    return of


def make_media(uid):

    mp = get_media_path(uid)

    if is_audio_only(mp):
        return make_audio(uid)
    else:
        return make_video(uid)


def make_session(output_filename, uid_list):

    ffmpeg_input_args = []

    # prepare the input file args
    for uid in uid_list:
        ffmpeg_input_args.append("-i")
        ffmpeg_input_args.append(make_media(uid))

    # construct the filter command
    n = len(uid_list)
    filter_string = f"concat=n={n}:v=1:a=1 [v] [a]"
    for i in reversed(range(n)):
        filter_string = f"[{i}:v] [{i}:a] " + filter_string

    # it's showtime!
    proc = subprocess.run(
        ["ffmpeg"] +
        ffmpeg_input_args +
        [
            "-filter_complex",
            filter_string,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-y",
            output_path / output_filename,
        ]
    )


def print_video_program_status():

    # do we have a media file
    print("## Presentations with no media file\n")
    for p in PAPERS:
        try:
            get_media_path(p["UID"])
        except ValueError as e:
            print(f"{p['UID']}: '{p['title']}' by {p['authors']} ({p['session_name']})")
    print()

    print("## Presentations with no session position\n")
    for p in PAPERS:
        if not isinstance(p["session_position"], int):
            print(f"{p['UID']}: '{p['title']}' by {p['authors']} ({p['session_name']})")
    print()

if __name__ == '__main__':

    print_video_program_status()
