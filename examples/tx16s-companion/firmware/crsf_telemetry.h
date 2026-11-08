/* CRSF telemetry parser for a radio-side companion (ESP32 in a TX16S bay, project #12 starter).
 * Portable C99, no allocation, byte-at-a-time: call crsf_feed() from the UART ISR/task with every byte.
 * Frame: [sync][len][type][payload...][crc8]; len = type + payload + crc (2..62); CRC8 poly 0xD5 over
 * type+payload; multi-byte fields big-endian (TBS CRSF spec). */
#ifndef CRSF_TELEMETRY_H
#define CRSF_TELEMETRY_H
#include <stdint.h>
#include <stdbool.h>

#define CRSF_FRAME_GPS        0x02
#define CRSF_FRAME_BATTERY    0x08
#define CRSF_FRAME_LINK_STATS 0x14
#define CRSF_FRAME_ATTITUDE   0x1E
#define CRSF_MAX_FRAME        64

typedef struct {
    /* battery 0x08 */
    float voltage_v, current_a; uint32_t capacity_mah; uint8_t remaining_pct;
    /* link statistics 0x14 */
    int16_t up_rssi1_dbm, up_rssi2_dbm; uint8_t up_lq; int8_t up_snr; uint8_t rf_profile, up_power_idx;
    int16_t down_rssi_dbm; uint8_t down_lq; int8_t down_snr;
    /* attitude 0x1E, degrees */
    float pitch_deg, roll_deg, yaw_deg;
    /* GPS 0x02 */
    double lat_deg, lon_deg; float groundspeed_kmh, heading_deg; int16_t alt_m; uint8_t sats;
    /* bookkeeping */
    uint32_t frames_ok, crc_errors, length_errors, unknown_types;
    uint8_t last_type;
} crsf_telemetry_t;

typedef struct {
    uint8_t buf[CRSF_MAX_FRAME];
    uint8_t pos, expected;     /* bytes collected, total frame length including sync and len */
} crsf_parser_t;

uint8_t crsf_crc8(const uint8_t *data, uint8_t len);
void crsf_init(crsf_parser_t *p, crsf_telemetry_t *t);
/* Returns the frame type when a valid frame completed with this byte, 0 otherwise. */
uint8_t crsf_feed(crsf_parser_t *p, crsf_telemetry_t *t, uint8_t byte);

#endif
