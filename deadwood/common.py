import json

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.warp
import shapely
import utm
from rasterio.enums import ColorInterp
from rasterio.features import shapes
from rasterio.vrt import WarpedVRT
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, shape
from tqdm import tqdm


def get_utm_string_from_latlon(lat, lon):
    zone = utm.from_latlon(lat, lon)
    utm_code = 32600 + zone[2]
    if lat < 0:
        utm_code -= 100

    return f"EPSG:{utm_code}"


def _polygon_parts(geometry):
    """Yield only polygonal parts from any Shapely geometry."""
    if geometry is None or geometry.is_empty:
        return
    if isinstance(geometry, Polygon):
        yield geometry
    elif isinstance(geometry, (MultiPolygon, GeometryCollection)):
        for part in geometry.geoms:
            yield from _polygon_parts(part)


def normalize_polygons(polygons):
    """Repair geometries and return a flat list of valid polygons."""
    normalized = []
    for geometry in polygons:
        normalized.extend(_polygon_parts(shapely.make_valid(geometry)))
    return normalized


def merge_polygon_parts(polygons):
    """Dissolve touching polygon pieces, including vectorization tile seams."""
    normalized = normalize_polygons(polygons)
    if not normalized:
        return []
    return list(_polygon_parts(shapely.union_all(normalized)))


def mask_to_polygons(mask, dataset_reader, offset_x=0, offset_y=0):
    """
    this function takes a numpy mask as input and returns a list of polygons
    that are in the crs of the passed dataset reader
    """

    if not np.any(mask):
        return []

    # rasterio traces pixel edges, so independently vectorized tiles meet at
    # the exact same coordinate and can be dissolved without a one-pixel gap.
    transform = dataset_reader.window_transform(
        rasterio.windows.Window(offset_x, offset_y, mask.shape[1], mask.shape[0])
    )
    valid_mask = mask if mask.dtype == np.bool_ else mask.astype(bool)
    polygon_shapes = (
        shape(geometry)
        for geometry, value in shapes(
            mask.astype(np.uint8),
            mask=valid_mask,
            connectivity=8,
            transform=transform,
        )
        if value == 1
    )
    return normalize_polygons(polygon_shapes)


def save_poly(filename, poly, crs):
    """saves the polygons to a file in the given crs"""
    gpd.GeoDataFrame(geometry=poly, crs=crs).to_file(filename)


def image_reprojector(input_tif, min_res=0, max_res=1e9):
    dataset = rasterio.open(input_tif)
    centroid = dataset.lnglat()
    utm_crs = get_utm_string_from_latlon(centroid[1], centroid[0])

    default_transform, width, height = rasterio.warp.calculate_default_transform(
        dataset.crs, utm_crs, dataset.width, dataset.height, *dataset.bounds
    )

    # get original resolution
    orig_res = default_transform.a

    target_res = None
    if orig_res < min_res:
        target_res = min_res
        print(
            f"Original resolution ({orig_res}) is smaller than minimum resolution ({min_res}). Reprojecting to minimum resolution."
        )
    if orig_res > max_res:
        target_res = max_res
        print(
            f"Original resolution ({orig_res}) is larger than maximum resolution ({max_res}). Reprojecting to maximum resolution."
        )

    if target_res is not None:
        default_transform, width, height = rasterio.warp.calculate_default_transform(
            dataset.crs,
            utm_crs,
            dataset.width,
            dataset.height,
            *dataset.bounds,
            resolution=target_res,
        )

    # An explicit nodata value takes precedence over an alpha band in GDAL.
    # Preserve alpha when present; otherwise preserve the source nodata value.
    has_alpha = ColorInterp.alpha in dataset.colorinterp
    vrt = WarpedVRT(
        dataset,
        crs=utm_crs,
        transform=default_transform,
        width=width,
        height=height,
        dtype="uint8",
        nodata=None if has_alpha else dataset.nodata,
    )

    return vrt


def reproject_polygons(polygons, src_crs, dst_src):
    """
    reprojects the polygons from the src_crs to the dst_crs
    """
    rep = rasterio.warp.transform_geom(src_crs, dst_src, polygons)
    if isinstance(rep, list):
        return shapely.from_geojson([json.dumps(x) for x in rep])
    else:
        return shapely.from_geojson(json.dumps(rep))


def filter_polygons_by_area(polygons, min_area):
    """
    filters the polygons by the minimum area
    """
    candidates = normalize_polygons(polygons)
    filtered = []
    for p in tqdm(candidates, desc="filtering polygons by area"):
        exterior = p.exterior

        # Filter holes (interior rings) by area
        filtered_holes = [
            hole for hole in p.interiors if Polygon(hole).area >= min_area
        ]

        # Create new polygon with filtered holes
        filtered_p = shapely.make_valid(Polygon(exterior, filtered_holes))
        for polygon_part in _polygon_parts(filtered_p):
            if polygon_part.area >= min_area:
                filtered.append(polygon_part)

    print(
        f"Filtered {len(candidates) - len(filtered)} polygons by minimum area of {min_area}m2."
    )
    return filtered
