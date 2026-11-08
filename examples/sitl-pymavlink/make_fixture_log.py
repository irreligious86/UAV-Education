#!/usr/bin/env python3
"""Write small synthetic ArduPilot DataFlash (.bin) logs for testing check_lab_log.py.

Real SITL logs are better; these fixtures only exercise the grader's logic in CI. The format is the
real one (0xA3 0x95 <id> <payload>, FMT self-description first), so pymavlink's DFReader parses them.

Usage: python3 make_fixture_log.py <out_dir>
Writes failsafe_pass.bin, failsafe_fail.bin, hover_pass.bin, hover_fail.bin, mission_pass.bin, motorfail_pass.bin
"""
import struct, sys, pathlib

HEAD = b"\xa3\x95"
FMT_ID = 128
# (id, name, format, columns)
FORMATS = {
    "MODE": (1, "QMBB", "TimeUS,Mode,ModeNum,Rsn"),
    "ERR":  (2, "QBB", "TimeUS,Subsys,ECode"),
    "VIBE": (3, "QBfffII", "TimeUS,IMU,VibeX,VibeY,VibeZ,Clip,Clip2"),
    "CTUN": (4, "QffffffffffffH", "TimeUS,ThI,ABst,ThO,ThH,DAlt,Alt,BAlt,DSAlt,SAlt,TAlt,DCRt,CRt,N"),
    "ATT":  (5, "QccccCCCC", "TimeUS,DesRoll,Roll,DesPitch,Pitch,DesYaw,Yaw,ErrRP,ErrYaw"),
    "BAT":  (6, "QBfffffcf", "TimeUS,Inst,Volt,VoltR,Curr,CurrTot,EnrgTot,Temp,Res"),
    "GPS":  (7, "QBBIHBcLLeffffB", "TimeUS,I,Status,GMS,GWk,NSats,HDop,Lat,Lng,Alt,Spd,GCrs,VZ,Yaw,U"),
    "CMD":  (8, "QHHHffffLLfB", "TimeUS,CTot,CNum,CId,Prm1,Prm2,Prm3,Prm4,Lat,Lng,Alt,Frame"),
    "MSG":  (9, "QZ", "TimeUS,Message"),
    "RCOU": (10, "QHHHHHHHH", "TimeUS,C1,C2,C3,C4,C5,C6,C7,C8"),
}
STRUCT = {"a": "64s", "b": "b", "B": "B", "h": "h", "H": "H", "i": "i", "I": "I", "f": "f", "n": "4s", "N": "16s",
          "Z": "64s", "c": "h", "C": "H", "e": "i", "E": "I", "L": "i", "d": "d", "M": "b", "q": "q", "Q": "Q"}
MULT = {"c": 100, "C": 100, "e": 100, "E": 100, "L": 1e7}


def pack_fmt(mid, name, fmt, cols):
    length = 3 + struct.calcsize("<" + "".join(STRUCT[c] for c in fmt))
    return HEAD + bytes([FMT_ID]) + struct.pack("<BB4s16s64s", mid, length, name.encode(), fmt.encode(), cols.encode())


def pack(name, **vals):
    mid, fmt, cols = FORMATS[name]
    out = []
    for c, col in zip(fmt, cols.split(",")):
        v = vals.get(col, 0)
        if c in ("n", "N", "Z", "a"):
            v = str(v).encode()
        elif c in MULT:
            v = int(round(v * MULT[c]))
        out.append(v)
    return HEAD + bytes([mid]) + struct.pack("<" + "".join(STRUCT[c] for c in fmt), *out)


class Log:
    def __init__(self):
        self.b = bytearray(pack_fmt(FMT_ID, "FMT", "BBnNZ", "Type,Length,Name,Format,Columns"))
        for name, (mid, fmt, cols) in FORMATS.items():
            self.b += pack_fmt(mid, name, fmt, cols)
    def add(self, name, t, **vals):
        self.b += pack(name, TimeUS=int(t * 1e6), **vals)
    def write(self, path):
        pathlib.Path(path).write_bytes(bytes(self.b))


def failsafe(ok):
    L = Log()
    L.add("MODE", 1.0, Mode=5, ModeNum=5, Rsn=1)           # LOITER
    L.add("ERR", 10.0, Subsys=5, ECode=1)                  # radio failsafe
    if ok:
        L.add("MODE", 11.5, Mode=6, ModeNum=6, Rsn=4)      # RTL after 1.5 s
    L.add("ERR", 20.0, Subsys=5, ECode=0)
    return L


def hover(ok):
    L = Log()
    for i in range(200):
        t = 1 + i * 0.1
        L.add("VIBE", t, IMU=0, VibeX=5, VibeY=5, VibeZ=(8 if ok else 45), Clip=(0 if ok else 3))
        L.add("CTUN", t, ThO=(0.38 if ok else 0.72), ThH=0.38, DAlt=5, Alt=5, BAlt=5)
        L.add("ATT", t, DesRoll=2.0, Roll=(2.5 if ok else 20), DesPitch=0, Pitch=0.5)
        L.add("BAT", t, Inst=0, Volt=(24.0 - (1.0 if ok else 5.0) * i / 200), Curr=20, CurrTot=100)
    return L


def mission():
    L = Log()
    L.add("MODE", 1, Mode=3, ModeNum=3, Rsn=1)
    for i, cid in enumerate([22, 16, 16, 16, 20]):
        L.add("CMD", 2 + i * 5, CTot=5, CNum=i + 1, CId=cid, Lat=50.0, Lng=30.0, Alt=50)
        if cid == 16:
            L.add("MSG", 3 + i * 5, Message=f"Reached command #{i + 1}")
    for i in range(30):
        L.add("GPS", 1 + i, I=0, Status=3, NSats=14, HDop=0.9, Lat=50.0, Lng=30.0, Alt=100)
    L.add("MODE", 28, Mode=6, ModeNum=6, Rsn=4)
    return L


def motorfail():
    L = Log()
    for i in range(300):
        t = 1 + i * 0.1
        failed = t > 15
        L.add("RCOU", t, C1=1500, C2=(2000 if failed else 1500), C3=1500, C4=1500, C5=1500, C6=1500, C7=1500, C8=1500)
        L.add("CTUN", t, ThO=0.5, Alt=20 - (1.5 if failed else 0))
        L.add("ATT", t, DesRoll=0, Roll=(4 if failed else 1))
    return L


if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures"); out.mkdir(parents=True, exist_ok=True)
    failsafe(True).write(out / "failsafe_pass.bin"); failsafe(False).write(out / "failsafe_fail.bin")
    hover(True).write(out / "hover_pass.bin"); hover(False).write(out / "hover_fail.bin")
    mission().write(out / "mission_pass.bin"); motorfail().write(out / "motorfail_pass.bin")
    print("fixtures written to", out)
