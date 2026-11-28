# ELRS UID lab

The lab of the course module `link-elrs`: binding phrase → UID → FHSS seed, CRC seed and Model Match,
ported from the ExpressLRS 4.1.0 source (file and line references are in the script's docstring).

```bash
python3 examples/elrs-uid/uid_lab.py     # Python 3.9+, standard library only
```

The output for the course's phrase `my-quad-2026` is saved in `uid_lab_output.txt`; a re-run must match it
byte for byte. Sections:

1. UID from the phrase (MD5 of `-DMY_BINDING_PHRASE="…"`, first 6 bytes) and a literal "4–6 numbers" UID;
2. what goes over the air: FHSS seed and CRC init (`OTA_VERSION_ID = 4`);
3. first hops in the `ISM2G4`/`CE_LBT`, `FCC915` and `EU868` domains, with a check that every block holds each channel once;
4. Model Match: UID5 in the SYNC packet for six TX/RX combinations;
5. link margin and range in free space (20 dB per decade) for four 2.4 GHz modes;
6. `Std` telemetry ratio → telemetry interval and packets per second.

The Russian module points to the same script, so its printed text is English there too.
