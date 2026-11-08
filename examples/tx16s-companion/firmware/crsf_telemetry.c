#include "crsf_telemetry.h"
#include <string.h>

static bool is_sync(uint8_t b) { return b == 0xC8 || b == 0x00 || b == 0xEA || b == 0xEE; }
static int16_t  be16s(const uint8_t *p) { return (int16_t)((p[0] << 8) | p[1]); }
static uint16_t be16u(const uint8_t *p) { return (uint16_t)((p[0] << 8) | p[1]); }
static uint32_t be24u(const uint8_t *p) { return ((uint32_t)p[0] << 16) | ((uint32_t)p[1] << 8) | p[2]; }
static int32_t  be32s(const uint8_t *p) { return (int32_t)(((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]); }

uint8_t crsf_crc8(const uint8_t *data, uint8_t len) {
    uint8_t crc = 0;
    for (uint8_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++) crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0xD5) : (uint8_t)(crc << 1);
    }
    return crc;
}

void crsf_init(crsf_parser_t *p, crsf_telemetry_t *t) {
    memset(p, 0, sizeof(*p));
    if (t) memset(t, 0, sizeof(*t));
}

static void decode(crsf_telemetry_t *t, uint8_t type, const uint8_t *pl, uint8_t n) {
    const float RAD2DEG = 57.29577951f;
    switch (type) {
    case CRSF_FRAME_BATTERY:
        if (n < 8) return;
        t->voltage_v = be16s(pl) / 10.0f; t->current_a = be16s(pl + 2) / 10.0f;
        t->capacity_mah = be24u(pl + 4); t->remaining_pct = pl[7];
        break;
    case CRSF_FRAME_LINK_STATS:
        if (n < 10) return;
        t->up_rssi1_dbm = -(int16_t)pl[0]; t->up_rssi2_dbm = -(int16_t)pl[1]; t->up_lq = pl[2]; t->up_snr = (int8_t)pl[3];
        t->rf_profile = pl[5]; t->up_power_idx = pl[6];
        t->down_rssi_dbm = -(int16_t)pl[7]; t->down_lq = pl[8]; t->down_snr = (int8_t)pl[9];
        break;
    case CRSF_FRAME_ATTITUDE:
        if (n < 6) return;
        t->pitch_deg = be16s(pl) * 1e-4f * RAD2DEG; t->roll_deg = be16s(pl + 2) * 1e-4f * RAD2DEG; t->yaw_deg = be16s(pl + 4) * 1e-4f * RAD2DEG;
        break;
    case CRSF_FRAME_GPS:
        if (n < 15) return;
        t->lat_deg = be32s(pl) / 1e7; t->lon_deg = be32s(pl + 4) / 1e7;
        t->groundspeed_kmh = be16u(pl + 8) / 10.0f; t->heading_deg = be16u(pl + 10) / 100.0f;
        t->alt_m = (int16_t)(be16u(pl + 12) - 1000); t->sats = pl[14];
        break;
    default:
        t->unknown_types++;
        return;
    }
}

uint8_t crsf_feed(crsf_parser_t *p, crsf_telemetry_t *t, uint8_t byte) {
    if (p->pos == 0) {                       /* hunting for a sync byte */
        if (is_sync(byte)) p->buf[p->pos++] = byte;
        return 0;
    }
    if (p->pos == 1) {                       /* length byte */
        if (byte < 2 || byte > 62) {         /* invalid: maybe this byte is itself a sync */
            t->length_errors++;
            p->pos = 0;
            if (is_sync(byte)) p->buf[p->pos++] = byte;
            return 0;
        }
        p->buf[p->pos++] = byte;
        p->expected = (uint8_t)(byte + 2);
        return 0;
    }
    p->buf[p->pos++] = byte;
    if (p->pos < p->expected) return 0;
    /* frame complete: buf = sync, len, type, payload..., crc */
    uint8_t len = p->buf[1];
    uint8_t crc = crsf_crc8(&p->buf[2], (uint8_t)(len - 1));
    uint8_t type = p->buf[2];
    p->pos = 0;
    if (crc != p->buf[len + 1]) { t->crc_errors++; return 0; }
    t->frames_ok++; t->last_type = type;
    decode(t, type, &p->buf[3], (uint8_t)(len - 2));
    return type;
}
