import sys
import os

import rasterio

from common.common import save_poly
from deadwood.deadwood_inference import DeadwoodInference


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python infer_ortho_batch.py <pathlist.txt>")

    pathlist = sys.argv[1]
    deadwood_inference = DeadwoodInference(
        config_path="deadwood_inference_config.json"
    )

    with open(pathlist) as file_handle:
        files = file_handle.readlines()

    for filename in files:
        try:
            tif_path = filename.strip()
            if not tif_path:
                continue

            print("processing", tif_path)
            outpath = os.path.basename(tif_path).replace(".tif", "_prediction.gpkg")

            if os.path.exists(outpath):
                print("skipping", tif_path)
                continue

            polygons = deadwood_inference.inference_deadwood(tif_path)
            save_poly(outpath, polygons, crs=rasterio.open(tif_path).crs)
        except Exception as exc:
            print("error", exc)
            continue


if __name__ == "__main__":
    main()
