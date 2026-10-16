"""Run actual pure C scheduler/capture arithmetic with a native C compiler.

This is a logic simulation, not electrical or live IMU acceptance.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


class FirmwareSyncTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc') or shutil.which('gcc'), 'native C compiler required')
    def test_real_scheduler_wrap_capture_delay_and_sequence(self):
        root = Path(__file__).resolve().parents[1]
        source = (root/'Src/main.c').read_text()
        capture = re.search(r'static uint64_t timer_capture_time\(.*?\n\}', source, re.S).group()
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include "local_sync_schedule.h"
#define TIM_UIF 1u
CAPTURE_FUNCTION
int main(void) {
    local_sync_schedule_t s = {.due_us=50000};
    uint64_t last_rising=0;
    for (unsigned i=0; i<400000; ++i) {
        uint64_t edge=s.due_us;
        assert(local_sync_advance(&s, edge+20)==0);
        if (s.high) {
            if (last_rising) assert(edge-last_rising==50000);
            last_rising=edge;
        }
        assert(s.due_us>edge && s.due_us-edge<65536);
        assert((uint16_t)s.due_us==(s.due_us & 65535));
    }
    assert(s.sequence==200000);
    local_sync_schedule_t late={.due_us=65000};
    assert(local_sync_advance(&late,69500)==LOCAL_SYNC_LATE);
    assert(late.due_us==65000); /* cannot rearm a passed comparison */
    local_sync_schedule_t stalled={.due_us=50000};
    assert(local_sync_advance(&stalled,50000+65536)==LOCAL_SYNC_LATE);
    local_sync_schedule_t sequence={.due_us=50000,.sequence=UINT32_MAX};
    assert(local_sync_advance(&sequence,50000)==LOCAL_SYNC_SEQUENCE_END);
    /* The real CH1/CH2 capture arithmetic on both sides of overflow. */
    assert(timer_capture_time(65530,1,9)==9*65536ull+65530);
    assert(timer_capture_time(5,1,9)==10*65536ull+5);
    assert(timer_capture_time(5,0,10)==10*65536ull+5);
    /* Independent channels keep the same extended epoch at simultaneous IRQ. */
    assert(timer_capture_time(65530,1,9)<timer_capture_time(5,1,9));
    return 0;
}
'''.replace('CAPTURE_FUNCTION', capture)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp); (path/'test.c').write_text(harness)
            exe=path/'test'
            subprocess.run([shutil.which('cc') or shutil.which('gcc'), '-std=c99', '-Wall',
                            '-Wextra', '-Werror', '-I', str(root/'Src'), str(path/'test.c'),
                            '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__': unittest.main()
