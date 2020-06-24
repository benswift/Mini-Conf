#!/bin/bash
for file in *.png
do
  echo "${file%.*}"
  magick convert "$file" "${file%.*}".jpg
done

echo "done!"
