import io
import json
import struct
import unittest
import zipfile

from lagar import centroids


def shp(shapes):
    """A minimal polygon .shp file; each shape is a list of rings of (x, y) points."""
    records = b""
    for number, rings in enumerate(shapes, start=1):
        points = [p for ring in rings for p in ring]
        parts, offset = [], 0
        for ring in rings:
            parts.append(offset)
            offset += len(ring)
        content = struct.pack("<i4d", 5, 0, 0, 0, 0)
        content += struct.pack("<ii", len(rings), len(points))
        content += struct.pack(f"<{len(parts)}i", *parts)
        content += b"".join(struct.pack("<dd", *p) for p in points)
        records += struct.pack(">II", number, len(content) // 2) + content
    header = struct.pack(">i", 9994) + b"\x00" * 20 + struct.pack(">i", (100 + len(records)) // 2)
    header += struct.pack("<ii4d4d", 1000, 5, 0, 0, 0, 0, 0, 0, 0, 0)
    return header + records


def dbf(rows):
    """A minimal dBase III table with KnKod (4) and KnNamn (15) character fields."""
    fields = [("KnKod", 4), ("KnNamn", 15)]
    record_len = 1 + sum(length for _, length in fields)
    header_len = 32 + 32 * len(fields) + 1
    out = struct.pack("<B3BIHH", 3, 26, 1, 1, len(rows), header_len, record_len) + b"\x00" * 20
    for name, length in fields:
        out += name.encode("ascii").ljust(11, b"\x00") + b"C" + b"\x00" * 4 + bytes([length]) + b"\x00" * 15
    out += b"\x0d"
    for code, name in rows:
        out += b" " + code.encode("cp1252").ljust(4) + name.encode("cp1252").ljust(15)
    return out + b"\x1a"


# A 10 km square around a point near Stockholm, clockwise as shapefiles store outer rings.
SQUARE = [(670000, 6575000), (670000, 6585000), (680000, 6585000), (680000, 6575000)]
HOLE = [(671000, 6576000), (673000, 6576000), (673000, 6578000), (671000, 6578000)]


class ProjectionTest(unittest.TestCase):
    def test_central_meridian_maps_to_15_degrees(self):
        _, lon = centroids.sweref99tm_to_wgs84(500000, 6500000)
        self.assertAlmostEqual(lon, 15.0, places=9)

    def test_stockholm_reference_point(self):
        lat, lon = centroids.sweref99tm_to_wgs84(674032.357, 6580821.991)
        self.assertAlmostEqual(lat, 59.3302, places=3)
        self.assertAlmostEqual(lon, 18.0592, places=3)


class CentroidTest(unittest.TestCase):
    def test_square_centroid_is_its_centre(self):
        self.assertEqual(centroids.centroid([SQUARE]), (675000, 6580000))

    def test_hole_shifts_the_centroid_away(self):
        x, y = centroids.centroid([SQUARE, HOLE])
        self.assertGreater(x, 675000)
        self.assertGreater(y, 6580000)

    def test_haversine_one_degree_of_latitude(self):
        self.assertAlmostEqual(centroids.haversine_km(59, 18, 60, 18), 111.2, places=1)


class ShapefileTest(unittest.TestCase):
    def test_reads_records_and_polygons(self):
        rows = centroids.read_dbf(dbf([("0180", "Stockholm"), ("0117", "Österåker")]))
        self.assertEqual(rows, [{"KnKod": "0180", "KnNamn": "Stockholm"}, {"KnKod": "0117", "KnNamn": "Österåker"}])
        shapes = centroids.read_polygons(shp([[SQUARE], [SQUARE, HOLE]]))
        self.assertEqual([len(s) for s in shapes], [1, 2])
        self.assertEqual(shapes[1][1], [tuple(map(float, p)) for p in HOLE])

    def test_kommun_centroids_round_and_bound(self):
        result = centroids.kommun_centroids(shp([[SQUARE]]), dbf([("0180", "Stockholm")]))
        lat, lon, radius = result["0180"]
        self.assertEqual(round(lat, 3), lat)
        self.assertAlmostEqual(lat, 59.32, places=1)
        self.assertAlmostEqual(lon, 18.04, places=1)
        self.assertEqual(radius, 8)  # half the 14.1 km diagonal, rounded up

    def test_read_source_unwraps_the_nested_zip(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            z.writestr("Kommun_Sweref99TM.shp", b"shp")
            z.writestr("Kommun_Sweref99TM.dbf", b"dbf")
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as z:
            z.writestr(centroids.KOMMUN_ARCHIVE, inner.getvalue())
        outer.seek(0)
        self.assertEqual(centroids.read_source(outer), (b"shp", b"dbf"))


class RenderTest(unittest.TestCase):
    GEO = {
        "regions": [{"code": "01", "name": "Stockholms län"}],
        "kommuner": [{"code": "0180", "name": "Stockholm", "regionCode": "01"}],
    }

    def test_adds_coordinates_one_entry_per_line(self):
        text = centroids.render(self.GEO, {"0180": (59.323, 18.0, 15)})
        self.assertIn(
            '  {"code": "0180", "name": "Stockholm", "regionCode": "01", "lat": 59.323, "lon": 18.0, "radiusKm": 15}\n',
            text,
        )
        self.assertIn('  {"code": "01", "name": "Stockholms län"}\n', text)
        self.assertEqual(json.loads(text)["kommuner"][0]["radiusKm"], 15)

    def test_rejects_mismatched_codes(self):
        with self.assertRaises(ValueError):
            centroids.render(self.GEO, {"0181": (59.0, 18.0, 1)})


if __name__ == "__main__":
    unittest.main()
