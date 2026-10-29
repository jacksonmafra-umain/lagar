"""Kommun centroids for the app's offline location suggestion.

Reads SCB's simplified kommun boundaries ("Digitala gränser", ArcView shape zip, SWEREF 99 TM, CC0) and writes,
for every kommun in the app's bundled ``sweden.json``, the area centroid as WGS 84 latitude/longitude and the
distance in km from the centroid to the farthest boundary vertex (``radiusKm``). The app picks the kommun whose
centroid is nearest and uses the radii to tell a position outside Sweden from one inside it.

Source: https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/digitala-granser/
File:   https://www.scb.se/contentassets/3443fea3fa6640f7a57ea15d9a372d33/shape_svenska_260225.zip
Licence: CC0 (attribution optional; "Source: Statistics Sweden").
"""

import argparse
import io
import json
import math
import struct
import sys
import zipfile
from pathlib import Path

SOURCE_URL = "https://www.scb.se/contentassets/3443fea3fa6640f7a57ea15d9a372d33/shape_svenska_260225.zip"
DEFAULT_GEO = "app/shared/src/commonMain/composeResources/files/geo/sweden.json"
KOMMUN_ARCHIVE = "Kommun_Sweref99TM.zip"
CODE_FIELD = "KnKod"
DECIMALS = 3
EARTH_RADIUS_KM = 6371.0088

# GRS 80 ellipsoid and the SWEREF 99 TM projection parameters.
_A = 6378137.0
_F = 1 / 298.257222101
_LON0 = 15.0
_K0 = 0.9996
_FALSE_EASTING = 500000.0
_FALSE_NORTHING = 0.0


def read_dbf(data, encoding="cp1252"):
    """Records of a dBase III table as dicts of stripped strings."""
    count, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields = []
    pos = 32
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\x00")[0].decode("ascii")
        fields.append((name, data[pos + 16]))
        pos += 32
    records = []
    for i in range(count):
        start = header_len + i * record_len
        if data[start] == 0x2A:  # deleted
            continue
        offset = start + 1
        record = {}
        for name, length in fields:
            record[name] = data[offset:offset + length].decode(encoding).strip()
            offset += length
        records.append(record)
    return records


def read_polygons(data):
    """Polygon shapes of a .shp file; each shape is a list of rings of (x, y) points."""
    shapes = []
    pos = 100
    while pos < len(data):
        _, content_words = struct.unpack(">II", data[pos:pos + 8])
        content = data[pos + 8:pos + 8 + content_words * 2]
        pos += 8 + content_words * 2
        shape_type = struct.unpack("<i", content[:4])[0]
        if shape_type == 0:
            shapes.append([])
            continue
        if shape_type != 5:
            raise ValueError(f"unsupported shape type {shape_type}")
        num_parts, num_points = struct.unpack("<ii", content[36:44])
        parts = list(struct.unpack(f"<{num_parts}i", content[44:44 + 4 * num_parts]))
        base = 44 + 4 * num_parts
        points = [struct.unpack("<dd", content[base + 16 * i:base + 16 * i + 16]) for i in range(num_points)]
        bounds = parts + [num_points]
        shapes.append([points[bounds[i]:bounds[i + 1]] for i in range(num_parts)])
    return shapes


def centroid(rings):
    """Area centroid of a polygon given as rings; holes wind the other way, so signed areas cancel them."""
    area = cx = cy = 0.0
    for ring in rings:
        for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
            cross = x0 * y1 - x1 * y0
            area += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
    if area == 0:
        raise ValueError("degenerate polygon")
    return cx / (3 * area), cy / (3 * area)


def sweref99tm_to_wgs84(easting, northing):
    """Inverse Gauss conformal projection (Lantmäteriet's formulas) from SWEREF 99 TM to (lat, lon) degrees."""
    e2 = _F * (2 - _F)
    n = _F / (2 - _F)
    a_roof = _A / (1 + n) * (1 + n ** 2 / 4 + n ** 4 / 64)
    d1 = n / 2 - 2 * n ** 2 / 3 + 37 * n ** 3 / 96 - n ** 4 / 360
    d2 = n ** 2 / 48 + n ** 3 / 15 - 437 * n ** 4 / 1440
    d3 = 17 * n ** 3 / 480 - 37 * n ** 4 / 840
    d4 = 4397 * n ** 4 / 161280
    a_star = e2 + e2 ** 2 + e2 ** 3 + e2 ** 4
    b_star = -(7 * e2 ** 2 + 17 * e2 ** 3 + 30 * e2 ** 4) / 6
    c_star = (224 * e2 ** 3 + 889 * e2 ** 4) / 120
    d_star = -(4279 * e2 ** 4) / 1260

    xi = (northing - _FALSE_NORTHING) / (_K0 * a_roof)
    eta = (easting - _FALSE_EASTING) / (_K0 * a_roof)
    xi_p = xi
    eta_p = eta
    for k, d in enumerate((d1, d2, d3, d4), start=1):
        xi_p -= d * math.sin(2 * k * xi) * math.cosh(2 * k * eta)
        eta_p -= d * math.cos(2 * k * xi) * math.sinh(2 * k * eta)
    phi_star = math.asin(math.sin(xi_p) / math.cosh(eta_p))
    d_lambda = math.atan(math.sinh(eta_p) / math.cos(xi_p))
    s2 = math.sin(phi_star) ** 2
    phi = phi_star + math.sin(phi_star) * math.cos(phi_star) * (
        a_star + b_star * s2 + c_star * s2 ** 2 + d_star * s2 ** 3
    )
    return math.degrees(phi), _LON0 + math.degrees(d_lambda)


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def kommun_centroids(shp, dbf):
    """``{code: (lat, lon, radius_km)}`` for every kommun in the shapefile."""
    result = {}
    for record, rings in zip(read_dbf(dbf), read_polygons(shp)):
        code = record[CODE_FIELD]
        lat, lon = sweref99tm_to_wgs84(*centroid(rings))
        radius = max(
            haversine_km(lat, lon, *sweref99tm_to_wgs84(x, y)) for ring in rings for x, y in ring
        )
        result[code] = (round(lat, DECIMALS), round(lon, DECIMALS), math.ceil(radius))
    return result


def read_source(path):
    """The kommun .shp and .dbf bytes from SCB's outer zip (which nests one zip per level)."""
    with zipfile.ZipFile(path) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read(KOMMUN_ARCHIVE)))
    names = inner.namelist()
    shp = next(n for n in names if n.lower().endswith(".shp"))
    dbf = next(n for n in names if n.lower().endswith(".dbf"))
    return inner.read(shp), inner.read(dbf)


def render(geo, centroids):
    """``sweden.json`` text, one entry per line, with each kommun's centroid; fails on a missing or extra code."""
    codes = {k["code"] for k in geo["kommuner"]}
    if codes != set(centroids):
        missing = sorted(codes - set(centroids))
        extra = sorted(set(centroids) - codes)
        raise ValueError(f"kommun codes differ: missing {missing}, extra {extra}")

    def line(entry):
        return "  " + json.dumps(entry, ensure_ascii=False, separators=(", ", ": "))

    kommuner = []
    for k in geo["kommuner"]:
        lat, lon, radius = centroids[k["code"]]
        kommuner.append({
            "code": k["code"], "name": k["name"], "regionCode": k["regionCode"],
            "lat": lat, "lon": lon, "radiusKm": radius,
        })
    regions = ",\n".join(line(r) for r in geo["regions"])
    return '{"regions":[\n' + regions + '\n],"kommuner":[\n' + ",\n".join(line(k) for k in kommuner) + "\n]}\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Add kommun centroids to the app's sweden.json.")
    parser.add_argument("source", help=f"SCB boundaries zip, downloaded from {SOURCE_URL}")
    parser.add_argument("--geo", default=DEFAULT_GEO, help="sweden.json to update in place")
    args = parser.parse_args(argv)
    geo_path = Path(args.geo)
    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    centroids = kommun_centroids(*read_source(args.source))
    geo_path.write_text(render(geo, centroids), encoding="utf-8")
    print(f"wrote {len(centroids)} centroids to {geo_path}", file=sys.stderr)
    return 0
