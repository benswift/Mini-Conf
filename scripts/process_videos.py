import subprocess
import csv
import yaml
import json
from pathlib import Path
import re
from jinja2 import Template


media_extensions = [".mkv", ".mov", ".mp4", ".avi", ".m4v", ".wav", ".aif", ".mp3", ".m4a"]
# tweak as necessary for your platform, or use an empty list for defaults
ffmpeg_encoder_args = ["-vcodec", "h264_nvenc", "-preset", "slow", "-b:v", "10M", "-maxrate", "10M", "-bufsize", "2M", "-c:a", "aac", "-b:a", "256k"]


# paths - tweak `media_path` as necessary for your setup
media_path = Path("/media/storage/ben/media")
tmp_path = media_path / "tmp"
processed_output_path = media_path / "processed"

if not media_path.exists():
    raise FileNotFoundError(f"no media folder found at {media_path}, exiting.")


# ensure all the required folders are all there
tmp_path.mkdir(parents=True, exist_ok=True)
processed_output_path.mkdir(parents=True, exist_ok=True)
## don't even ask me why this is necessary unless you want to see RAGE face.
decktape_tmp_path = Path("tmp")
decktape_tmp_path.mkdir(parents=True, exist_ok=True)


# read in the data about the sessions & performances
PAPERS = list(csv.DictReader(open("sitedata/papers.csv")))
SESSIONS = list(yaml.safe_load(open("sitedata/sessions.yml")))


# transform a couple of columns to integer
for p in PAPERS:
    p["UID"] = int(p["UID"])
    try:
        p["session_position"] = int(p["session_position"])
    except:
        print(f"warning: {p['UID']} has no session position")


def info_from_uid(uid):
    for p in PAPERS:
        if p["UID"] == uid:
            return p

    raise KeyError(f"no paper found with UID {uid}")


def get_session_schedule(session_uid):
    schedule = []
    for p in PAPERS:
        if p["session_name"] == session_uid:
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


def video_bitrate(filename):
    for stream in probe(filename)["streams"]:
        if stream["codec_type"] == "video":
            return (int(stream["bit_rate"]))

    raise ValueError(f"no video streams found in {filename}")


def video_fps(filename):
    for stream in probe(filename)["streams"]:
        if stream["codec_type"] == "video":
            # this eval is gross, and a huge security hole, but ffmpeg reports it as a ratio
            return (eval(stream["r_frame_rate"]))

    raise ValueError(f"no video streams found in {filename}")


def audio_channels(filename):
    for stream in probe(filename)["streams"]:
        if stream["codec_type"] == "audio":
            return int(stream["channels"])

    raise ValueError(f"no audio streams found in {filename}")


def audio_bits_per_sample(filename):
    for stream in probe(filename)["streams"]:
        if stream["codec_type"] == "audio":
            return int(stream["bits_per_sample"])

    raise ValueError(f"no audio streams found in {filename}")


def get_media_path(uid):

    files = list(media_path.glob(f"{uid}.*"))

    if len(files) > 1:
        raise ValueError(f"too many media files found for UID {uid} ({files})")

    for mf in files:
        if mf.suffix in media_extensions:
            return mf

    raise ValueError(f"no media file found for UID {uid}")


def has_media_file(uid):
    try:
        get_media_path(uid)
        return True
    except ValueError:
        return False


def ffmpeg_encode_yt_recommended(uid):
    """re-encode file at HD, 30fps

    with recommended settings according to
    https://developers.google.com/media/vp9/settings/vod

    """
    input_file = get_media_path(uid)
    output_file = media_path / "yt-recommended" / f"{uid}.webm"

    print(f"encoding {uid} according to YouTube recommended settings (pass 1)...")
    proc = subprocess.run(
        ["ffmpeg", "-v", "warning", "-i", input_file, "-vf", "fps=30/1, scale=1920:1080, setsar=sar=1/1", "-b:v", "3000k", "-minrate", "1500k", "-maxrate", "5000k", "-tile-columns", "2", "-g", "240", "-threads", "8", "-quality", "good", "-crf", "25", "-c:v", "libvpx-vp9", "-b:a", "256k", "-c:a", "libopus", "-pass", "1", "-speed", "4", "-y", output_file]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    print(f"encoding {uid} according to YouTube recommended settings (pass 2)...")
    proc = subprocess.run(
        ["ffmpeg", "-v", "warning", "-i", input_file, "-vf", "fps=30/1, scale=1920:1080, setsar=sar=1/1", "-b:v", "3000k", "-minrate", "1500k", "-maxrate", "5000k", "-tile-columns", "3", "-g", "240", "-threads", "8", "-quality", "good", "-crf", "25", "-c:v", "libvpx-vp9", "-b:a", "256k", "-c:a", "libopus", "-pass", "2", "-speed", "4", "-y", output_file]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)
    print("done")


def render_revealjs_index_html(title, subtitle, artist):

    template = Template(open("scripts/reveal.js/index.j2").read())
    template.stream(title=title, subtitle=subtitle, artist=artist).dump("scripts/reveal.js/index.html")


def make_titlecard(uid):
    """ok, let's do it with reveal.js (and decktape)
    """

    output_path = tmp_path / f"{uid}-titlecard.mp4"

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

    render_revealjs_index_html(title, subtitle, artist)

    # ok, now run decktape to get the png
    proc = subprocess.run(
        # the path to index.html is a bit gross, but otherwise decktape insists on polluting the top-level with pdf files
        ["npx", "decktape", "--size", "1920x1080", "--screenshots", "--screenshots-directory", "." , "../scripts/reveal.js/index.html", f"{uid}-titlecard.pdf"],
        cwd = decktape_tmp_path
    )

    # this is the output filename that Decktape will give the png
    titlecard_path = decktape_tmp_path / f"{uid}-titlecard_1_1920x1080.png"

    # now, make the titlecard video
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            # titlecard png as an input source
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000", "-loop", "1", "-i", titlecard_path, "-t", "10", "-c:a", "aac", "-c:v", "copy", "-shortest",
            *ffmpeg_encoder_args,
            output_path
        ]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    return output_path


def make_audio(uid):

    mp = get_media_path(uid)
    assert is_audio_only(mp)

    # make the titlecard video
    titlecard_path = make_titlecard(uid)

    # attach the titlecard to the actual audio file
    tmpfile = tmp_path / f"{uid}-audio-with-titlecard.mp4"

    # make the
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", titlecard_path,
            "-i", mp,
            "-af", "aresample=out_sample_fmt=s16:out_sample_rate=48000",
            *ffmpeg_encoder_args,
            "-map", "0:v", "-c:v", "copy", "-map", "1:a", tmpfile
        ]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    output_path = tmp_path / f"{uid}.mp4"
    # now smoosh it on to the front

    proc = subprocess.run(
        ["ffmpeg", "-y",
         "-i", titlecard_path,
         "-i", tmpfile,
         "-filter_complex", "[0:v] [0:a] [1:v] [1:a] concat=n=2:v=1:a=1 [v] [a]",
         *ffmpeg_encoder_args,
         "-map", "[v]", "-map", "[a]", output_path
        ]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    return output_path


def make_video(uid):

    mp = get_media_path(uid)
    output_path = tmp_path / f"{uid}.mp4"

    assert not is_audio_only(mp)
    # now smoosh it on to the front

    titlecard_path = make_titlecard(uid)

    proc = subprocess.run(
        ["ffmpeg", "-y",
         "-i", titlecard_path,
         "-i", mp,
         # this is where we set all the videos to a consistent fps/size/aspect ratio
         "-filter_complex", "[1:v] fps=30/1, scale=1920:1080, setsar=sar=1/1 [v]; [0:v] [0:a] [v] [1:a] concat=n=2:v=1:a=1",
         *ffmpeg_encoder_args,
         output_path
        ]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    return output_path


def make_media(uid, overwrite):

    mp = get_media_path(uid)

    # if overwrite is False, check if a processed file already exists, and if
    # so just use that
    output_path = tmp_path / f"{uid}.mp4"
    if not overwrite and output_path.exists():
        return output_path

    if is_audio_only(mp):
        return make_audio(uid)
    else:
        return make_video(uid)


def make_session_titlecard(session_uid):
    """NOTE: this is mostly copy-pasted from above

    should refactor, but can't be arsed right now

    """

    session_data = None
    for s in SESSIONS:
        if s["UID"] == session_uid:
            session_data = s
            break

    if not session_data:
        raise ValueError(f"no session found for UID {session_uid}")

    output_path = tmp_path / f"{session_uid}-titlecard.mp4"

    chair = s['chair']
    if chair:
        render_revealjs_index_html(s["title"], s["date"], f"session chair: {chair}")
    else:
        render_revealjs_index_html(s["title"], s["date"], None)

    # ok, now run decktape to get the png
    proc = subprocess.run(
        # the path to index.html is a bit gross, but otherwise decktape insists on polluting the top-level with pdf files
        ["npx", "decktape", "--size", "1920x1080", "--screenshots", "--screenshots-directory", "." , "../scripts/reveal.js/index.html", f"{session_uid}-titlecard.pdf"],
        cwd = decktape_tmp_path
    )

    # this is the output filename that Decktape will give the png
    titlecard_path = decktape_tmp_path / f"{session_uid}-titlecard_1_1920x1080.png"

    # now, make the titlecard video
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            # titlecard png as an input source
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000", "-loop", "1", "-i", titlecard_path, "-t", "10", "-c:v", "copy", "-shortest",
            *ffmpeg_encoder_args,
            output_path
        ]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    return output_path


def is_live_session(session_uid):
    # a dirty heuristic, but it'll do
    return "_live" in session_uid


def make_session_video(session_uid, skip_missing, overwrite):

    ffmpeg_input_args = ["-i", make_session_titlecard(session_uid)]

    uid_list = get_session_schedule(session_uid)

    # filter out the missing ones, if you want to
    if skip_missing:
        uid_list = [uid for uid, pos in uid_list if has_media_file(uid)]

    print(f"making {session_uid} session video with UIDs: {uid_list}")

    for uid in uid_list:
        ffmpeg_input_args.append("-i")
        ffmpeg_input_args.append(make_media(uid, overwrite))

    # construct the filter command
    n = int(len(ffmpeg_input_args)/2)
    filter_string = f"concat=n={n}:v=1:a=1 [v] [a]"
    for i in reversed(range(n)):
        filter_string = f"[{i}:v] [{i}:a] " + filter_string

    # it's showtime!
    proc = subprocess.run(
        ["ffmpeg", "-y",
         *ffmpeg_input_args,
         "-filter_complex",
         filter_string,
         *ffmpeg_encoder_args,
         "-map", "[v]", "-map", "[a]", processed_output_path / f"{session_uid}.mp4",
        ]
    )


def make_all_acmc_session_videos(skip_missing, overwrite):
    for s in SESSIONS:
        session_uid = s["UID"]
        if not is_live_session(session_uid):
            make_session_video(session_uid, skip_missing, overwrite)


def print_video_program_status():

    # do we have a media file

    problems = {"file": {}, "bad_resolution": {}, "bad_num_channels": {}, "no_session_assigned": {}, "no_session_position_assigned": {}}

    for p in PAPERS:
        uid = p["UID"]

        if not isinstance(p["session_name"], str):
            problems["no_session_assigned"][uid] = f"no session name assigned"

        if not isinstance(p["session_position"], int):
            problems["no_session_position_assigned"][uid] = f"no position in session {p['session_name']}"

        # live performances won't have videos
        if is_live_session(p["session_name"]):
            continue

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
                problems["bad_resolution"][uid] = f"video dimensions {width}x{height} (aspect ratio {width/height:.2f})"

    # ok, now print out the problems
    def print_problems(problem_type):
        pr = problems[problem_type]
        print(f"## Found {len(pr)} **{problem_type}** problems\n")
        for uid in pr.keys():
            info = info_from_uid(uid)
            print(f"- {uid}: {info['authors']} in session {info['session_name']}, pos {info['session_position']} ({pr[uid]})")
        print()

    print_problems("file")
    # print_problems("bad_resolution")
    # print_problems("bad_num_channels")
    # print_problems("no_session_assigned")
    # print_problems("no_session_position_assigned")


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

    print_video_program_status()
    # make_session_video("C1_Monday", True)
    pass
