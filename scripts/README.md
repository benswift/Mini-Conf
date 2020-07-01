# Media folder

## requirements

- [Decktape](https://github.com/astefanutti/decktape) (for making the titlecards)
- [FFmpeg](http://ffmpeg.org/) for the video stuff

## use

1. audio/video files go in any folder with the filename
   `<UID>.{mp4,mkv,mov,m4v,avi,wav,aif}`, where `<UID>` is the paper/performance
   UID

2. change `media_path` at the top of `process_videos.py` to point to that folder

3. run the `process_videos.py` script, calling the desired function (e.g.
   `make_media()` or `make_session_video()` as appropriate)

4. when complete (might take a while) the output will be in `processed/`

### rclone

The media files are currently also stored in a shared folder on cloudstor. If
you've got something like this in your `.config/rclone/rclone.conf`:

```config
[cloudstor]
type = webdav
url = https://cloudstor.aarnet.edu.au/plus/remote.php/webdav/
vendor = owncloud
user = <first.last>@anu.edu.au
pass = <access_token>
```

Then you can use `rclone` to pull the latest files (run this command from the
directory one level up from your `media/` folder):

    rclone copy --progress cloudstor:Shared/acmc media/

or, to push the your latest media files (note the directories are swapped):

    rclone copy --progress --exclude "tmp/**" media/ cloudstor:Shared/acmc
