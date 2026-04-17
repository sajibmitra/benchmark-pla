#!/bin/bash

set -e

echo "======================================="
echo "Downloading Benchmark Dataset (FOLDER MODE)"
echo "======================================="

mkdir -p benchmarks

# install gdown if needed
if ! command -v gdown &> /dev/null
then
    echo "[INFO] Installing gdown..."
    pip install gdown
fi

FOLDER_URL="https://drive.google.com/drive/folders/1Bdn2Tp76YtzjLn_w-fs0XIPxXt47GYCi"

echo "[INFO] Downloading full folder into benchmarks/ ..."
echo "[INFO] Expected layout includes benchmarks/epfl, benchmarks/mcnc,"
echo "       and benchmarks/classic/classic (see README.md)."

gdown --folder "$FOLDER_URL" -O benchmarks/

echo "======================================="
echo "Done!"
echo "======================================="