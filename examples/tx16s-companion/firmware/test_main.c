/* Host test driver: reads hex bytes from stdin, prints one JSON line per decoded frame. */
#include <stdio.h>
#include "crsf_telemetry.h"

int main(void) {
    crsf_parser_t p; crsf_telemetry_t t; crsf_init(&p, &t);
    unsigned v;
    while (scanf("%2x", &v) == 1) {
        uint8_t type = crsf_feed(&p, &t, (uint8_t)v);
        if (type == CRSF_FRAME_BATTERY) printf("{\"type\":8,\"v\":%.1f,\"a\":%.1f,\"mah\":%u,\"pct\":%u}\n", t.voltage_v, t.current_a, t.capacity_mah, t.remaining_pct);
        else if (type == CRSF_FRAME_LINK_STATS) printf("{\"type\":20,\"rssi1\":%d,\"rssi2\":%d,\"lq\":%u,\"snr\":%d,\"dlq\":%u}\n", t.up_rssi1_dbm, t.up_rssi2_dbm, t.up_lq, t.up_snr, t.down_lq);
        else if (type == CRSF_FRAME_ATTITUDE) printf("{\"type\":30,\"pitch\":%.2f,\"roll\":%.2f,\"yaw\":%.2f}\n", t.pitch_deg, t.roll_deg, t.yaw_deg);
        else if (type == CRSF_FRAME_GPS) printf("{\"type\":2,\"lat\":%.7f,\"lon\":%.7f,\"alt\":%d,\"sats\":%u}\n", t.lat_deg, t.lon_deg, t.alt_m, t.sats);
        else if (type) printf("{\"type\":%u}\n", type);
    }
    printf("{\"ok\":%u,\"crc\":%u,\"len\":%u,\"unknown\":%u}\n", t.frames_ok, t.crc_errors, t.length_errors, t.unknown_types);
    return 0;
}
