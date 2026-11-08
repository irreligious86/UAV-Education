# Route inspection (project #6 starter)

Fly along a line object, shoot by distance, and put every finding on a map at the right coordinates.

```bash
python -m pytest -q tests                                     # 5 tests
python plan.py line.csv --offset 15 --alt 30 --trigger 5      # -> mission.waypoints (QGC WPL 110)
python geotag.py cam.csv photos.csv findings.csv              # -> report.geojson
```

| File | Role |
|---|---|
| `plan.py` | parallel offset of the object's polyline (mitred corners), mission with `DO_SET_CAM_TRIGG_DIST` on the inspected stretch only, RTL |
| `geotag.py` | camera-clock offset from the first pairs, nearest-time matching photo ↔ `CAM`, missed triggers and extra photos reported, findings → GeoJSON |

Why time and not order: one missed trigger shifts every later photo by one position (see the test). Use
`CAM` records (shutter feedback, `CAM1_FEEDBAK_PIN`) when you have them; `TRIG` is only the command time.
Milestones (course page "Проекты → 6"): read `CAM` straight from the DataFlash log with pymavlink, EXIF
from the photos (exifread/Pillow), write geotags back, Leaflet report, accuracy check on control points.
