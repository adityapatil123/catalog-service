import h3


def polygon_to_h3_indices(polygon, resolution=9):
    return h3.polyfill(polygon, resolution)
