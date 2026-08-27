# deadtrees_mapping

Inference code for mapping deadwood polygons from RGB orthophotos.

The repository loads a trained segmentation model, runs tiled inference on an input orthophoto, converts the predicted mask to polygons, filters small polygons, and writes the result as a GeoPackage in the original CRS of the input raster.

## Repository contents

- `infer_ortho.py`: main entry point for running inference on one orthophoto.
- `infer_ortho_batch.py`: batch runner that reads a text file with one raster path per line.
- `deadwood/`: deadwood inference code, model loading, tiling, and postprocessing.
- `common/`: shared raster/vector helper functions.
- `deadwood_inference_config.json`: runtime configuration, including the model name expected in `data/`.
- `requirements.txt`: Python dependencies.
- `data/`: local folder for model weights. This folder is intentionally not tracked in Git.

## Model setup

The model weights are not stored in this repository.

Download the model file:

`https://data2.deadtrees.earth/assets/v1/segformer_b5_full_epoch_100.safetensors`

Create the local `data/` folder and place the file here:

`data/segformer_b5_full_epoch_100.safetensors`

This filename must match the `model_name` field in `deadwood_inference_config.json`.

## Installation

Create an environment and install the dependencies from `requirements.txt`.

Example:

```bash
conda create -n deadtrees python=3.11
conda activate deadtrees
cd /path/to/deadtrees_mapping_
pip install -r requirements.txt
```

The code uses PyTorch and will run on GPU if available, otherwise on CPU.

## How it works

`infer_ortho.py` creates a `DeadwoodInference` instance from `deadwood_inference_config.json`.

The workflow is:

1. Open the input orthophoto.
2. Reproject it internally if needed to the minimum inference resolution from the config.
3. Split the raster into overlapping tiles.
4. Run the segmentation model tile by tile.
5. Merge tile predictions into a full mask.
6. Convert the mask to polygons.
7. Filter polygons by minimum area.
8. Reproject the polygons back to the CRS of the input raster.
9. Save the output as a GeoPackage.

## Run inference on one orthophoto

```bash
python infer_ortho.py /path/to/input.tif
```

This writes:

`/path/to/input_deadwood.gpkg`

You can also provide an explicit output path:

```bash
python infer_ortho.py /path/to/input.tif /path/to/output.gpkg
```

## Run batch inference

Create a text file with one `.tif` path per line, for example:

```text
/path/to/ortho_01.tif
/path/to/ortho_02.tif
/path/to/ortho_03.tif
```

Then run:

```bash
python infer_ortho_batch.py pathlist.txt
```

For each input raster, the script writes a GeoPackage in the current working directory with the pattern:

`<input_filename>_prediction.gpkg`

## Configuration

The main runtime settings are in `deadwood_inference_config.json`:

- `model_name`: base filename of the model stored in `data/`
- `probabilty_threshold`: threshold applied to the model output mask
- `deadwood_minimum_inference_resolution`: minimum raster resolution used for inference
- `batch_size`: number of tiles processed together
- `minimum_polygon_area`: minimum polygon area kept in the result
- `mask_tiling_threshold`: threshold for tiled vectorization of very large masks

If you change `model_name`, the file in `data/` must use the same name plus the `.safetensors` extension.

## Notes

- `treecover/` is present from the source repository, but that workflow is currently not maintained here.
- `data/` and generated outputs such as `.gpkg` files are ignored by Git on purpose.
