"""Print the distinct OADJ (Dijkstra) records and the FENCE/OA parameters of a dataflash log.
usage: python3 oadj.py <log.BIN>"""
import sys
from pymavlink import DFReader

log = DFReader.DFReader_binary(sys.argv[1])
seen = set()
while (m := log.recv_match(type=["OADJ", "PARM"])) is not None:
    if m.get_type() == "PARM":
        if m.Name in ("OA_TYPE", "OA_MARGIN_MAX", "FENCE_ENABLE", "FENCE_TYPE", "GUID_OPTIONS", "WP_SPD"):
            print(f"PARM {m.Name} = {m.Value:g}")
        continue
    k = (m.State, m.CurrPoint, m.TotPoints, round(m.OALat, 6), round(m.OALng, 6))
    if k not in seen:
        seen.add(k)
        print(f"OADJ State {m.State} point {m.CurrPoint}/{m.TotPoints} OA {m.OALat:.6f} {m.OALng:.6f}")
