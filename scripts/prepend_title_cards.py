import subprocess

conference="ACMC 2020"
typeface="AlegreyaSans" # use a font with Thin, Regular & Bold weights

input_path = "."
output_path = "."

def make_title_card(artist, title, UID):
    subprocess.run(
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
            f"{output_path}/{UID}-titlecard.mkv"
        ]
    )

if __name__ == '__main__':
    artist="Ben Swift"
    title="Untitled #3"
    UID = 123

    make_title_card(artist, title, UID)
