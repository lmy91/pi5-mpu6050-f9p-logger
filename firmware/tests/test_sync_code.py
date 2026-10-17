"""Execute C codeword/schedule, compare every width with independent Python CRC."""
import binascii
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class CodedSyncTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc') or shutil.which('gcc'),'native C compiler required')
    def test_c_width_stream_matches_crc_protocol_and_keeps_20hz_rises(self):
        source=r'''
#include <stdio.h>
#include <assert.h>
#include "local_sync_schedule.h"
#include "local_sync_code.h"
int main(void) {
    uint8_t bytes[10];
    local_sync_schedule_t s={.due_us=50000};
    unsigned position=0;uint64_t previous=0;
    for (unsigned seq=1;seq<=8100;++seq) {
        if (!position) local_sync_code_word(17u,seq,bytes);
        unsigned width=local_sync_code_width(bytes,(uint8_t)position);
        s.high_us=(uint16_t)width;
        uint64_t rise=s.due_us;
        assert(local_sync_advance(&s,rise+20)==0);
        assert(s.high && s.due_us-rise==width);
        if (previous) assert(rise-previous==50000);
        previous=rise;
        assert(local_sync_advance(&s,s.due_us+20)==0);
        assert(!s.high && s.due_us-rise==50000);
        printf("%u\n",width);
        if (++position==81) position=0;
    }
    return 0;
}
'''
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'code.c').write_text(source)
            exe=path/'test-code'
            subprocess.run([shutil.which('cc') or shutil.which('gcc'),'-std=c99','-Wall','-Wextra','-Werror',
                '-I',str(root/'Src'),str(path/'code.c'),'-o',str(exe)],check=True)
            widths=[int(x) for x in subprocess.check_output([str(exe)],text=True).splitlines()]
        expected=[]
        for seq in range(1,8101):
            position=(seq-1)%81
            if position==0:expected.append(15000);continue
            data=(17).to_bytes(4,'big')+(seq-position).to_bytes(4,'big')
            data+=binascii.crc_hqx(data,0xffff).to_bytes(2,'big')
            expected.append(10000 if data[(position-1)//8] & (1<<(7-(position-1)%8)) else 5000)
        self.assertEqual(widths,expected)


if __name__=='__main__':unittest.main()
