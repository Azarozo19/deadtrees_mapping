import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.errors import NodataShadowWarning
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box

from deadwood.InferenceDataset import InferenceDataset
from deadwood.common import (
    filter_polygons_by_area,
    image_reprojector,
    mask_to_polygons,
    merge_polygon_parts,
    normalize_polygons,
)


class GeometryPostprocessingTests(unittest.TestCase):
    def test_merge_polygon_parts_dissolves_a_tile_seam(self):
        merged = merge_polygon_parts([box(0, 0, 1, 1), box(1, 0, 2, 1)])

        self.assertEqual(len(merged), 1)
        self.assertAlmostEqual(merged[0].area, 2.0)
        self.assertTrue(merged[0].is_valid)

    def test_vectorized_tiles_join_on_pixel_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grid.tif"
            profile = {
                "driver": "GTiff",
                "width": 10,
                "height": 5,
                "count": 1,
                "dtype": "uint8",
                "crs": "EPSG:32632",
                "transform": from_origin(0, 5, 1, 1),
            }
            with rasterio.open(path, "w", **profile) as destination:
                destination.write(np.zeros((1, 5, 10), dtype=np.uint8))

            left_mask = np.zeros((5, 5), dtype=bool)
            right_mask = np.zeros((5, 5), dtype=bool)
            left_mask[1:4, 3:5] = True
            right_mask[1:4, 0:2] = True
            with rasterio.open(path) as source:
                pieces = mask_to_polygons(left_mask, source)
                pieces.extend(mask_to_polygons(right_mask, source, offset_x=5))

            merged = merge_polygon_parts(pieces)
            self.assertEqual(len(merged), 1)
            self.assertAlmostEqual(merged[0].area, 12.0)

    def test_single_pixel_is_vectorized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grid.tif"
            profile = {
                "driver": "GTiff",
                "width": 2,
                "height": 2,
                "count": 1,
                "dtype": "uint8",
                "crs": "EPSG:32632",
                "transform": from_origin(0, 2, 1, 1),
            }
            with rasterio.open(path, "w", **profile) as destination:
                destination.write(np.zeros((1, 2, 2), dtype=np.uint8))
            mask = np.array([[True, False], [False, False]])

            with rasterio.open(path) as source:
                polygons = mask_to_polygons(mask, source)

            self.assertEqual(len(polygons), 1)
            self.assertAlmostEqual(polygons[0].area, 1.0)

    def test_normalize_polygons_repairs_self_intersection(self):
        bow_tie = Polygon([(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)])

        repaired = normalize_polygons([bow_tie])

        self.assertTrue(repaired)
        self.assertTrue(all(polygon.is_valid for polygon in repaired))

    def test_area_filter_returns_polygon_with_small_hole_removed(self):
        polygon = Polygon(
            box(0, 0, 10, 10).exterior.coords,
            holes=[
                box(1, 1, 1.5, 1.5).exterior.coords,
                box(5, 5, 7, 7).exterior.coords,
            ],
        )

        filtered = filter_polygons_by_area([polygon], min_area=1.0)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(len(filtered[0].interiors), 1)
        self.assertAlmostEqual(filtered[0].area, 96.0)


class AlphaMaskTests(unittest.TestCase):
    def test_alpha_mask_is_preserved_without_nodata_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rgba.tif"
            profile = {
                "driver": "GTiff",
                "width": 4,
                "height": 4,
                "count": 4,
                "dtype": "uint8",
                "crs": "EPSG:32632",
                "transform": from_origin(500000, 5700000, 0.2, 0.2),
                "nodata": 0,
            }
            pixels = np.full((4, 4, 4), 100, dtype=np.uint8)
            pixels[3] = 255
            pixels[3, :2, :2] = 0
            with rasterio.open(path, "w", **profile) as destination:
                destination.colorinterp = (
                    ColorInterp.red,
                    ColorInterp.green,
                    ColorInterp.blue,
                    ColorInterp.alpha,
                )
                destination.write(pixels)

            vrt = image_reprojector(path)
            try:
                self.assertIsNone(vrt.nodata)
                dataset = InferenceDataset(vrt, tile_size=4, padding=1)
                with warnings.catch_warnings():
                    warnings.simplefilter("error", NodataShadowWarning)
                    dataset[0]
            finally:
                vrt.close()


if __name__ == "__main__":
    unittest.main()
