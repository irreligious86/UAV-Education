#!/usr/bin/env python3
"""link-elrs lab: binding phrase -> UID -> FHSS seed, CRC seed, Model Match (ExpressLRS 4.1.0).

Everything here is a port of the 4.1.0 source, nothing is invented:
  UID          src/python/build_flags.py:71-74, src/lib/CONFIG/config.cpp:14-41 (MD5 of -DMY_BINDING_PHRASE="...")
  literal UID  src/python/binary_configurator.py:35-44 ("4-6 numbers" are used as the UID itself)
  seeds        src/lib/OTA/OTA.cpp:28-45, OTA_VERSION_ID = 4 (src/include/targets.h:8)
  FHSS         src/lib/FHSS/FHSS.cpp:19-52 (domains), :91-101, :140-176; src/lib/FHSS/random.cpp
  Model Match  src/src/tx_main.cpp:407-415, src/src/rx_main.cpp:1010-1090, MODELMATCH_MASK = 0x3f (lib/OTA/OTA.h:27)
  margin       free-space 20 dB/decade (module rf-link-budget); sensitivities src/src/common.cpp:93-103
  Std ratios   src/src/common.cpp:9-15, 31-51, 81-91 (TLMinterval column)
Course module: link-elrs.
Run: python3 examples/elrs-uid/uid_lab.py   (Python 3.9+, standard library only)
"""
import hashlib

OTA_VERSION_ID = 4
MODELMATCH_MASK = 0x3F
FHSS_SEQUENCE_LEN = 256


def uid_from_phrase(phrase: str) -> list[int]:
    """build_flags.py: hashlib.md5('-DMY_BINDING_PHRASE="<phrase>"'.encode()).digest()[0:6]"""
    # binary_configurator.py:35-44: literal UID only if every comma-separated item is digits (no spaces)
    items = phrase.split(",")
    nums = [int(x) if x.isdigit() else -1 for x in items]
    if 4 <= len(nums) <= 6 and all(0 <= n < 256 for n in nums):
        return [0] * (6 - len(nums)) + nums
    define = f'-DMY_BINDING_PHRASE="{phrase}"'
    return list(hashlib.md5(define.encode()).digest()[0:6])


def uid_seed(uid):           # OtaGetUidSeed()
    return (uid[2] << 24) + (uid[3] << 16) + (uid[4] << 8) + (uid[5] ^ OTA_VERSION_ID)


def crc_init(uid):           # OtaUpdateCrcInitFromUid()
    return (((uid[4] << 8) | uid[5]) ^ (OTA_VERSION_ID << 8)) & 0xFFFF


class Rng:                   # random.cpp: LCG, uint32 arithmetic
    def __init__(self, seed): self.seed = seed & 0xFFFFFFFF
    def rng(self):
        self.seed = ((214013 * self.seed + 2531011) & 0xFFFFFFFF) % 2147483648
        return self.seed >> 16
    def n(self, mx): return self.rng() % mx


DOMAINS = {  # name: (start Hz, stop Hz, channel count)   FHSS.cpp:19-52
    "ISM2G4 / CE_LBT": (2400400000, 2479400000, 80),
    "FCC915": (903500000, 926900000, 40),
    "EU868": (863275000, 869575000, 13),
}


def fhss_sequence(seed, count):
    sync = count // 2
    n = (FHSS_SEQUENCE_LEN // count) * count
    seq = []
    for i in range(n):
        if i % count == 0: seq.append(sync)
        elif i % count == sync: seq.append(0)
        else: seq.append(i % count)
    r = Rng(seed)
    for i in range(n):
        if i % count != 0:
            off = (i // count) * count
            k = r.n(count - 1) + 1
            seq[i], seq[off + k] = seq[off + k], seq[i]
    return seq, sync


def freq_mhz(domain, ch):
    a, b, c = DOMAINS[domain]
    return (a + ch * (b - a) / (c - 1)) / 1e6


def tx_uid5(uid, model_match_on, model_id):      # tx_main.cpp:407-415
    v = uid[5]
    if model_match_on:
        v ^= (~model_id) & MODELMATCH_MASK
    return v & 0xFF


def rx_check(uid, rx_model_id, sync_uid4, sync_uid5):  # rx_main.cpp:1013-1076
    if sync_uid4 != uid[4]:
        return "SYNC packet dropped: UID4 does not match"
    if (sync_uid5 & ~MODELMATCH_MASK & 0xFF) != (uid[5] & ~MODELMATCH_MASK & 0xFF):
        return "SYNC packet dropped: high 2 bits of UID5 do not match"
    xor = (~rx_model_id) & MODELMATCH_MASK      # rx_model_id = 0xFF -> Model Match off -> xor 0
    return "link, channels flow" if sync_uid5 == (uid[5] ^ xor) else "link up, no channels (Model Mismatch)"


print("== 1. UID from the phrase (MD5 of the string -DMY_BINDING_PHRASE=\"...\", first 6 bytes) ==")
for p in ["my-quad-2026", "My-quad-2026", "my-quad-2026 ", "12,34,56,78"]:
    define = f'-DMY_BINDING_PHRASE="{p}"'
    md5 = hashlib.md5(define.encode()).hexdigest()
    u = uid_from_phrase(p)
    print(f"{p!r:18} md5={md5}  UID={','.join(map(str, u))}")
print("(build_flags.py prints a line of the same form: 'UID bytes: a,b,c,d,e,f')")

u = uid_from_phrase("my-quad-2026")
print("\n== 2. What goes over the air from the UID (phrase my-quad-2026) ==")
print(f"FHSS seed = UID[2..5] with UID[5]^4 = 0x{uid_seed(u):08X}")
print(f"CRC init  = (UID[4]<<8 | UID[5]) ^ 0x0400 = 0x{crc_init(u):04X}")
print("UID[0], UID[1] never go over the air: OtaUidIsBound() looks only at UID[2..5]")

print("\n== 3. First 12 hops (one phrase, different domains) ==")
for d, (_, _, c) in DOMAINS.items():
    seq, sync = fhss_sequence(uid_seed(u), c)
    hops = seq[:12]
    print(f"{d:16} channels {c:2}, sync channel {sync:2}, length {len(seq)}: {hops}")
    print(f"{'':16} MHz: {[round(freq_mhz(d, ch), 2) for ch in hops[:6]]}")
    blk = [sorted(seq[i:i + c]) == list(range(c)) for i in range(0, len(seq), c)]
    print(f"{'':16} check: every block of {c} has each channel exactly once: {all(blk)}; "
          f"sync at the start of every block: {all(seq[i] == sync for i in range(0, len(seq), c))}")
u2 = uid_from_phrase("My-quad-2026")
seq2, _ = fhss_sequence(uid_seed(u2), 80)
seq1, _ = fhss_sequence(uid_seed(u), 80)
same = sum(a == b for a, b in zip(seq1, seq2))
print(f"Phrase differs by one letter: {same} of {len(seq1)} positions match "
      f"({len(seq1)//80} of them are the sync channel at the start of a block)")

print("\n== 4. Model Match: UID5 in the SYNC packet ==")
print(f"UID5 = {u[5]} = 0b{u[5]:08b}; mask 0x3F = low 6 bits, model ID 0…63")
cases = [("Off", None, 0xFF), ("On", 1, 1), ("On", 2, 1), ("On", 0, 0xFF), ("Off", None, 1), ("On", 65, 1)]
for mm, tx_id, rx_id in cases:
    v = tx_uid5(u, mm == "On", tx_id or 0)
    rxs = "Off (0xFF)" if rx_id == 0xFF else str(rx_id)
    print(f"TX Model Match {mm:3} ID {str(tx_id):4} -> UID5 in SYNC = {v:3};  RX stores ID {rxs:10} -> {rx_check(u, rx_id, u[4], v)}")
print("ID 65 & 0x3F = 1: numbers 1 and 65 are indistinguishable (EdgeTX only offers 0…63 anyway)")

print("\n== 5. Link margin and range (free space, 20 dB per decade) ==")
print(f"6 dB -> x{10**(6/20):.3f}, 3 dB -> x{10**(-3/20):.3f} (minus), 10 dB -> x{10**(10/20):.2f}")
d0, rssi, m_req = 1.0, -80, 12
for mode, s in [("2.4 GHz 250Hz", -108), ("2.4 GHz 150Hz", -112), ("2.4 GHz 50Hz", -115), ("2.4 GHz F1000", -104)]:
    m = rssi - s
    d = d0 * 10 ** ((m - m_req) / 20)
    print(f"{mode:14} S={s} dBm: margin at {d0:.0f} km = {m} dB, {m_req} dB of margin remains out to {d:.1f} km; "
          f"with a -6 dB reality correction: {d / 10**(6/20):.1f} km")

print("\n== 6. Std: telemetry interval = ratio * 1000 / rate ==")
for name, rate, ratio in [("25Hz", 25, 8), ("50Hz", 50, 16), ("100Hz", 100, 32), ("150Hz", 150, 32), ("200Hz", 200, 64),
                          ("250Hz", 250, 64), ("333Hz Full", 333.33, 128), ("500Hz", 500, 128), ("F1000", 1000, 128)]:
    print(f"{name:10} 1:{ratio:<3} -> every {ratio * 1000 / rate:5.0f} ms, {rate / ratio:.1f} packets/s")
