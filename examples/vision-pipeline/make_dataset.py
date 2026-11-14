#!/usr/bin/env python3
"""Auto-label the synthetic video from truth.csv into a YOLO dataset (every 5th frame, 80/20 split).
python3 make_dataset.py data yolo/ds"""
import csv, math, os, sys
import cv2
sys.path.insert(0, os.environ.get("CAMGEO_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "perception")))   # examples/perception/camgeo.py
import camgeo as cg

src, dst = sys.argv[1], sys.argv[2]
K = cg.K_matrix(400, 400, 320, 240); R = cg.R_bc_for_mount(90)
truth = list(csv.DictReader(open(f"{src}/truth.csv")))
cap = cv2.VideoCapture(f"{src}/flight.mp4")
for sub in ("images/train", "images/val", "labels/train", "labels/val"):
    os.makedirs(f"{dst}/{sub}", exist_ok=True)
n = 0
for r in truth:
    i = int(r["frame"]); ok, f = cap.read()
    if i % 5 or not ok: continue
    split = "val" if (i // 5) % 5 == 0 else "train"
    cv2.imwrite(f"{dst}/images/{split}/f{i:04d}.jpg", f)
    lines = []
    if r["visible"] == "1":
        dn, de = float(r["tgt_n"]) - float(r["veh_n"]), float(r["tgt_e"]) - float(r["veh_e"])
        u, v = cg.ground_to_pixel(dn, de, K, float(r["roll"]), float(r["pitch"]), float(r["yaw"]), float(r["agl"]), R_bc=R, k1=-0.10, k2=0.02)
        rpx = 0.40 * 400 / float(r["agl"]) + 2
        lines.append(f"0 {u / 640:.5f} {v / 480:.5f} {2 * rpx / 640:.5f} {2 * rpx / 480:.5f}")
    open(f"{dst}/labels/{split}/f{i:04d}.txt", "w").write("\n".join(lines))
    n += 1
open(f"{dst}/data.yaml", "w").write(f"path: {dst}\ntrain: images/train\nval: images/val\nnames:\n  0: target\n")
print(f"{n} frames labelled -> {dst}")
