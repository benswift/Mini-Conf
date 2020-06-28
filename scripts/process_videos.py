import subprocess
import csv
import json
from pathlib import Path
import re

conference="ACMC 2020"
titlecard_length_sec = 10


media_extensions = [".mkv", ".mov", ".mp4", ".avi", ".m4v", ".wav", ".aif"]
media_path = Path("media")
output_path = media_path / "processed"
tmp_path = output_path / "tmp"
# ensure all the required folders are all there
tmp_path.mkdir(parents=True, exist_ok=True)

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

def info_from_uid(uid):
    for p in PAPERS:
        if p["UID"] == uid:
            return p

    raise KeyError(f"no paper found with UID {uid}")


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


def audio_channels(filename):
    for stream in probe(filename)["streams"]:
        if stream["codec_type"] == "audio":
            return int(stream["channels"])

    raise ValueError(f"no audio streams found in {filename}")


def get_media_path(uid):

    files = list(media_path.glob(f"{uid}.*"))

    if len(files) > 1:
        raise ValueError(f"too many media files found for UID {uid} ({files})")

    for mf in files:
        if mf.suffix in media_extensions:
            return mf

    raise ValueError(f"no media file found for UID {uid}")


def titlecard_drawtext_filter(uid):

    # TODO for titlecards
    # - check which one is the real spreadsheet which populates papers.csv
    # - where possible, edit spreadsheet fields into sensible multi-line ones
    # - otherwise, just shrink font-size based on string length
    # - get non-ascii chars working (e.g. Chinese chars)

    typeface="Lato" # same font as ACMC website, needs Thin & Black weights
    info = info_from_uid(uid)
    title = info["title"].replace("'", "\u2019").strip() # to not bork the stringly passing of args
    artist = info["authors"].strip()

    # text positioning stuff
    left_margin = 50
    title_size = 120
    # a heuristic about title/subtitles using ':'
    if ":" in title:
        parts = title.split(":")
        title = parts[0].strip()
        subtitle = parts[1].strip()
    else:
        subtitle = ""

    return [
        # set bg colour, video size & duration
        "-f", "lavfi",
        # select virtual input video device
        "-i", f"color=c=#111111:s=1920x1080:d={titlecard_length_sec}",
        "-vf",
        # title
        f"drawtext=fontfile='{typeface}\:style=Thin':fontsize={title_size}:fontcolor=#EEEEEE:x={left_margin}:y=h-600:text='{title}', " +
        # subtitle (may be an empty string)
        f"drawtext=fontfile='{typeface}\:style=Thin':fontsize={title_size*0.5}:fontcolor=#EEEEEE:x={left_margin}:y=h-450:text='{subtitle}', " +
        # artist
        f"drawtext=fontfile='{typeface}\:style=Black':fontsize={title_size*0.4}:fontcolor=#EEEEEE:x={left_margin}:y=h-350:text='{artist}', " +
        # conference
        f"drawtext=fontfile='{typeface}\:style=Thin':fontsize={title_size*0.4}:fontcolor=#EEEEEE:x={left_margin}:y=h-100:text='{conference}'",
    ]


def make_titlecard(uid):

    titlecard_path = tmp_path / f"{uid}-titlecard.mkv"
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            # add blank audio
            "-i", f"anoisesrc=d={titlecard_length_sec}:c=pink:a=0.0",
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
            "-i", mp
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

    problems = {"file": {}, "bad_resolution": {}, "bad_num_channels": {}, "no_session_assigned": {}, "no_session_position_assigned": {}}

    for p in PAPERS:
        uid = p["UID"]
        try:
            mf = get_media_path(uid)
        except ValueError as e:
            problems["file"][uid] = str(e)
            continue

        channels = audio_channels(mf)
        if channels != 2:
            problems["bad_num_channels"][uid] = f"{channels} audio channels"

        if not is_audio_only(mf):
            width, height = video_dimensions(mf)
            if (width, height) != (1920, 1080):
                problems["bad_resolution"][uid] = f"video dimensions {width}x{height}"

        if not isinstance(p["session_position"], int):
            problems["no_session_position_assigned"][uid] = f"no position in session {p['session_name']}"

    # ok, now print out the problems
    def print_problems(problem_type):
        pr = problems[problem_type]
        print(f"## Found {len(pr)} **{problem_type}** problems\n")
        for uid in pr.keys():
            info = info_from_uid(uid)
            print(f"{uid}: _{info['title']}_ by {info['authors']} ({pr[uid]})")
        print()

    print_problems("file")
    print_problems("bad_num_channels")
    print_problems("bad_resolution")
    print_problems("no_session_position_assigned")


def check_string_lengths(uid):
    # filthy hack - copypasta'd from above
    info = info_from_uid(uid)
    title = info["title"].replace("'", "\u2019").strip() # to not bork the stringly passing of args
    artist = info["authors"].strip()

    # a heuristic about title/subtitles using ':'
    if ":" in title:
        parts = title.split(":")
        title = parts[0].strip()
        subtitle = parts[1].strip()
    else:
        subtitle = ""

    if len(title) > 30:
        print(f"long title (length {len(title)}) for {uid}: {title}")

    if len(subtitle) > 70:
        print(f"long subtitle (length {len(subtitle)}) for {uid}: {subtitle}")

    if len(artist) > 70:
        print(f"long artist (length {len(artist)}) for {uid}: {artist}")


if __name__ == '__main__':

    # print_video_program_status()
    make_session("test-session.mkv", [32, 39])

    # for p in PAPERS:
    #     # make_titlecard(p["UID"])
    #     check_string_lengths(p["UID"])
