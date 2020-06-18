# Media folder

Here's the deal:

1. video files go in this folder, with the filename `UID.{mp4,mkv,mov}`

2. run the script

3. when complete (might take a while) the output will be in
   `processed/output.mkv`

## TODO

- [ ] pull the actual artist & title of the piece (from `papers.csv`) rather
      than the current "artist"/"title" placeholders

- [ ] make it automatically create the `media/{processed,titlecard}` folders if
      they don't exist (because it currently bails out opaquely, which isn't a
      great look)

- [ ] provide a way of specifying the order of the pieces in a session

- [ ] handle audio-only pieces (add the title card, but leave it up for the
      whole thing)
