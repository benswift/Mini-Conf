import subprocess

conference="ACMC 2020"
typeface="AlegreyaSans" # use a font with Thin, Regular & Bold weights

input_path = "."
output_path = "."

def make_titlecard(artist, title, UID):
    titlecard_path = f"{output_path}/{UID}-titlecard.mkv"
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            # select virtual input device
            "-f", "lavfi",
            # set bg colour, video size & duration
            "-i", "color=c=black:s=1920x1080:d=3",
            # title
            "-vf", f"drawtext=fontfile='{typeface}\:style=Thin':fontsize=160:fontcolor=#EEEEEE:x=100:y=h-500:text='{title}', " +
            # artist
            f"drawtext=fontfile='{typeface}\:style=Bold':fontsize=70:fontcolor=#EEEEEE:x=100:y=h-280:text='{artist}', " +
            # conference
            f"drawtext=fontfile='{typeface}\:style=Regular':fontsize=50:fontcolor=#EEEEEE:x=100:y=h-200:text='{conference}'",
            # output file
            titlecard_path
        ]
    )
    if proc.returncode != 0:
        raise ChildProcessError(proc.returncode)

    return titlecard_path

def process_video(artist, title, UID):

    titlecard_path = make_titlecard(artist, title, UID)

    # now just smoosh them together
    # TODO


if __name__ == '__main__':
    artist="Ben Swift"
    title="Untitled #3"
    UID = 123

    make_titlecard(artist, title, UID)
