# Media folder

## requirements

- [Decktape](https://github.com/astefanutti/decktape) (for making the titlecards)
- [FFmpeg](http://ffmpeg.org/) for the video stuff

## use

1. audio/video files go in this folder, with the filename `UID.{mp4,mkv,mov,m4v,avi,wav,aif}`

2. run the `process_videos.py` script, calling the desired function (e.g.
   `make_media()` or `make_session_video()` as appropriate)

3. when complete (might take a while) the output will be in `processed/`

### rclone

The media files are currently stored in a shared folder on cloudstor. If you've
got something like this in your `.config/rclone/rclone.conf`:

```config
[cloudstor]
type = webdav
url = https://cloudstor.aarnet.edu.au/plus/remote.php/webdav/
vendor = owncloud
user = <first.last>@anu.edu.au
pass = <access_token>
```

Then you can use `rclone` to pull the latest files:

    rclone copy --progress cloudstor:Shared/acmc media/

or, to push the your latest media files (note the directories are swapped):

    rclone copy --progress --exclude "{processed,tmp}/**" media/ cloudstor:Shared/acmc
