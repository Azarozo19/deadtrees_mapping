##!/usr/bin/env bash
set -euo pipefail

INPUT_DIR="/rvt_mount/deadwood_clip_DE/data"
SHAPEFILE="/rvt_mount/3DTests/data/harm_data/shp_germany_border.shp"
OUTPUT_DIR="/rvt_mount/deadwood_clip_DE/output"
CUTLINE_LAYER="shp_germany_border"
NO_DATA="0"

mkdir -p "$OUTPUT_DIR"

for tif in "$INPUT_DIR"/*.tif; do
    [ -e "$tif" ] || continue

    base=$(basename "$tif" .tif)
    year="${base##*_}"
    out="$OUTPUT_DIR/germany_${base}.tif"

    echo "Processing $tif -> $out"

    gdalwarp \
        -cutline "$SHAPEFILE" \
        -cl "$CUTLINE_LAYER" \
        -crop_to_cutline \
        -dstnodata "$NO_DATA" \
        -multi \
        -wo NUM_THREADS=ALL_CPUS \
        -wm 4096 \
        -co TILED=YES \
        -co BLOCKXSIZE=512 \
        -co BLOCKYSIZE=512 \
        -co COMPRESS=DEFLATE \
        -co PREDICTOR=2 \
        -co BIGTIFF=YES \
        "$tif" \
        "$out"

    gdaladdo \
        -r average \
        "$out" \
        2 4 8 16 32

    echo "Finished $out"
done

echo "All rasters processed."