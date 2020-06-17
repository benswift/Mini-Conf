import subprocess

conference="ACMC'20"
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
            # draw artist name
            "-vf", f"drawtext=fontfile=AlegreyaSans-Light.otf:fontsize=120:fontcolor=#EEEEEE:x=100:y=h-400:text='{title}', " +
            f"drawtext=fontfile=AlegreyaSans-Black.otf:fontsize=80:fontcolor=#BBBBBB:x=100:y=h-280:text='{artist}'",
            f"{output_path}/{UID}-titlecard.mkv"
        ]
    )

if __name__ == '__main__':
    artist="Ben Swift"
    title="Untitled #3"
    UID = 123

    make_title_card(artist, title, UID)
