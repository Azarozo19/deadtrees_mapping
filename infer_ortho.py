import sys

import rasterio

from common.common import save_poly
from deadwood.deadwood_inference import DeadwoodInference


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python infer_ortho.py <input.tif> [output.gpkg]")

    filename = sys.argv[1]
    output_path = (
        sys.argv[2]
        if len(sys.argv) > 2
        else filename.rsplit(".tif", 1)[0] + "_deadwood.gpkg"
    )

    deadwood_inference = DeadwoodInference(
        config_path="deadwood_inference_config.json"
    )
    polygons = deadwood_inference.inference_deadwood(filename)
    save_poly(output_path, polygons, crs=rasterio.open(filename).crs)


if __name__ == "__main__":
    main()
