#ifndef LOCAL_SYNC_SCHEDULE_H
#define LOCAL_SYNC_SCHEDULE_H
#include <stdint.h>

#define LOCAL_SYNC_HIGH_US 5000u
#define LOCAL_SYNC_PERIOD_US 50000u
#define LOCAL_SYNC_GUARD_US 500u
#define LOCAL_SYNC_LATE 1u
#define LOCAL_SYNC_QUEUE_LOSS 2u
#define LOCAL_SYNC_SEQUENCE_END 4u
#define LOCAL_SYNC_COLD_BOOT 256u

typedef struct {
    uint64_t due_us;
    uint32_t sequence;
    uint32_t faults;
    uint8_t high;
} local_sync_schedule_t;

/* Called AFTER the hardware toggle. No GPIO software edge, division or I/O.
 * A late ISR cannot safely rearm a CCR already passed by the counter. Stop
 * this channel rather than silently producing a 65536-us-late pulse. */
static inline uint32_t local_sync_advance(volatile local_sync_schedule_t *s, uint64_t now)
{
    s->high ^= 1u;
    if (s->high && ++s->sequence == 0u) s->faults |= LOCAL_SYNC_SEQUENCE_END;
    uint32_t interval = s->high ? LOCAL_SYNC_HIGH_US :
                               LOCAL_SYNC_PERIOD_US - LOCAL_SYNC_HIGH_US;
    if (now < s->due_us || now - s->due_us >= interval - LOCAL_SYNC_GUARD_US)
        s->faults |= LOCAL_SYNC_LATE;
    if (!s->faults) s->due_us += interval;
    return s->faults;
}
#endif
