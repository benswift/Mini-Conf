# Media folder

## requirements

- [Decktape](https://github.com/astefanutti/decktape) (for making the titlecards)
- [FFmpeg](http://ffmpeg.org/) for the video stuff

## use

1. audio/video files go in this folder, with the filename `UID.{mp4,mkv,mov,m4v,avi,wav,aif}`

2. run the `process_videos.py` script, calling the desired function (e.g.
   `make_media()` or `make_session_video()` as appropriate)

3. when complete (might take a while) the output will be in `processed/`
