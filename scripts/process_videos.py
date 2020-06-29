import subprocess
import csv
import json
from pathlib import Path
import re
from jinja2 import Template


media_extensions = [".mkv", ".mov", ".mp4", ".avi", ".m4v", ".wav", ".aif"]
media_path = Path("media")
output_path = media_path / "processed"
tmp_path = output_path / "tmp"
# ensure all the required folders are all there
tmp_path.mkdir(parents=True, exist_ok=True)

# the length of this file determines the length of the titlecard
silence_file_path = media_path / "silence.wav"
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


def make_titlecard(uid):
    """ok, let's do it with reveal.js (and decktape)
    """

    output_path = tmp_path / f"{uid}-titlecard.mkv"

    typeface="Lato" # same font as ACMC website, needs Thin & Black weights
    info = info_from_uid(uid)
    title = info["title"].strip() # to not bork the stringly passing of args
    artist = info["authors"].strip()

    # a heuristic about title/subtitles using ':'
    if ":" in title:
        parts = title.split(":")
        title = parts[0].strip()
        subtitle = parts[1].strip()
    else:
        subtitle = None

    template = Template(open("media/reveal.js/index.j2").read())
    template.stream(title=title, subtitle=subtitle, artist=artist).dump("media/reveal.js/index.html")

    # ok, now run decktape to get the png
    proc = subprocess.run(
        # the path to index.html is a bit gross, but otherwise decktape insists on polluting the top-level with pdf files
        ["npx", "decktape", "--size", "1920x1080", "--screenshots", "--screenshots-directory", "." , "../../reveal.js/index.html", f"{uid}-titlecard.pdf"],
        cwd = tmp_path
    )

    # this is the output filename that Decktape will give the png
    titlecard_path = tmp_path / f"{uid}-titlecard_1_1920x1080.png"

    # now, make the titlecard video
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            # titlecard png as an input source
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-loop", "1", "-i", titlecard_path, "-t", "10", "-c:v", "copy", "-shortest",
            output_path
        ]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    return output_path


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
        ["ffmpeg", "-y",
         "-i", tc,
         "-i", tmp,
         "-filter_complex", "[0:v] [0:a] [1:v] [1:a] concat=n=2:v=1:a=1 [v] [a]",
         "-map", "[v]", "-map", "[a]", of
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
        ["ffmpeg", "-y",
         "-i", tc,
         "-i", mp,
         "-filter_complex", "[0:v] [0:a] [1:v] [1:a] concat=n=2:v=1:a=1 [v] [a]",
         "-map", "[v]", "-map", "[a]", of
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
        ["ffmpeg", "-y"] +
        ffmpeg_input_args +
        [
            "-filter_complex",
            filter_string,
            "-map", "[v]", "-map", "[a]", output_path / output_filename,
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
