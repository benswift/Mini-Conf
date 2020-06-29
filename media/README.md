# Media folder

## requirements

- [Decktape](https://github.com/astefanutti/decktape) (for making the titlecards)
- [FFmpeg](http://ffmpeg.org/) for the video stuff
- [sox](http://sox.sourceforge.net/) (optional, handy for creating the silent
  audio file)

## use

1. make sure there's an (silent) audio file called `silence.wav` in this folder,
   with whatever duration you want for the titlecards

       # e.g. you can create a 10sec silent file with
       you sox -n -r 48000 -c 2 silence.wav trim 0.0 10.0

2. audio/video files go in this folder, with the filename `UID.{mp4,mkv,mov,m4v,avi,wav,aif}`

3. run the `process_videos.py` script (TODO check the right function is called
   at the bottom)

4. when complete (might take a while) the output will be in `processed/`
