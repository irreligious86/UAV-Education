# Vision pipeline lab (module per-vision-pipeline)

End-to-end on-board vision chain on a synthetic flight, then a replay into ArduCopter SITL.
Needs `../perception/camgeo.py` (or `CAMGEO_DIR=<dir with camgeo.py>`).

```bash
pip install opencv-python numpy pymavlink        # ultralytics only for --detector yolo
python3 gen_video.py data                        # flight.mp4, telemetry.csv, truth.csv (40 s, 1200 frames)
python3 pipeline.py data --undistort point       # per-stage latency table, writes data/targets.csv
python3 score.py data                            # precision/recall per slice, ground error, ID switches
python3 pipeline.py data --undistort frame       # the failing configuration discussed in the module
python3 pipeline.py data --undistort point --att-offset-ms 100
# SITL (ArduCopter 4.6.3, instance 4 -> tcp 5800), see the header of sitl_follow.py
python3 sitl_follow.py tcp:127.0.0.1:5800 data/targets.csv
# optional YOLO path
python3 make_dataset.py data yolo/ds
yolo detect train data=yolo/ds/data.yaml model=yolo11n.pt epochs=8 imgsz=320 project=yolo/runs name=target
YOLO_WEIGHTS=yolo/runs/target/weights/best.pt python3 pipeline.py data --detector yolo --undistort point
```

`sample-output/` holds the runs quoted in the module (2-core x86, Python 3.13, OpenCV 5.0).
