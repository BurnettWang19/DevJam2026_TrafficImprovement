from pyproj import Transformer


def build_transformer(source_epsg: int, target_epsg: int) -> Transformer:
    return Transformer.from_crs(f"EPSG:{source_epsg}", f"EPSG:{target_epsg}", always_xy=True)
