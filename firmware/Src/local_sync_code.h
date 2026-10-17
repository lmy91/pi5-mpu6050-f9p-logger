#ifndef LOCAL_SYNC_CODE_H
#define LOCAL_SYNC_CODE_H
#include <stdint.h>
#define LOCAL_SYNC_WORD_PULSES 81u
#define LOCAL_SYNC_CODE_NOT_READY 8u

/* Main-loop only. Network byte order: boot32, base-sequence32, CRC16-CCITT. */
static inline void local_sync_code_word(uint32_t boot, uint32_t base, uint8_t bytes[10])
{
    for (unsigned i=0u; i<4u; ++i) {
        bytes[i]=(uint8_t)(boot >> (24u-8u*i));
        bytes[i+4u]=(uint8_t)(base >> (24u-8u*i));
    }
    uint16_t crc=0xffffu;
    for (unsigned i=0u; i<8u; ++i) {
        crc ^= (uint16_t)((uint16_t)bytes[i] << 8);
        for (unsigned k=0u; k<8u; ++k)
            crc=(uint16_t)((crc & 0x8000u) ? ((uint32_t)crc<<1)^0x1021u : (uint32_t)crc<<1);
    }
    bytes[8]=(uint8_t)(crc>>8); bytes[9]=(uint8_t)crc;
}

/* ISR: fixed byte lookup, no CRC, division, UART or software GPIO edge. */
static inline uint32_t local_sync_code_width(const volatile uint8_t *bytes, uint8_t position)
{
    if (!position) return 15000u;
    uint8_t bit=(uint8_t)(position-1u);
    return (bytes[bit>>3] & (1u << (7u-(bit & 7u)))) ? 10000u : 5000u;
}
#endif
