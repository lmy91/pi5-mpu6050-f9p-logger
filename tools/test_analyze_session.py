import csv
import pathlib
import struct
import tempfile
import unittest

import analyze_session


def ubx_frame(message_class: int, message_id: int, payload: bytes) -> bytes:
    body = bytes((message_class, message_id)) + struct.pack("<H", len(payload)) + payload
    ck_a = ck_b = 0
    for value in body:
        ck_a = (ck_a + value) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return b"\xb5\x62" + body + bytes((ck_a, ck_b))


class AnalyzeSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.session = pathlib.Path(self.temp.name) / "20260913120000"
        self.session.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write_csv(self, name, fields, rows):
        with (self.session / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)

    def test_ubx_parser_detects_raw_and_navigation_messages(self):
        path = self.session / "f9p.ubx"
        path.write_bytes(ubx_frame(2, 0x15, b"raw") + ubx_frame(2, 0x13, b"nav"))
        findings = []
        result = analyze_session.analyze_ubx(path, findings)
        self.assertEqual(result["frames"], 2)
        self.assertEqual(result["bad_checksum_frames"], 0)
        self.assertEqual(result["message_types"], {"02-15": 1, "02-13": 1})
        self.assertFalse(findings)

    def test_imu_rate_and_gap_detection(self):
        fields = ["sample", "gps_week", "gps_tow_us", "time_valid", "timer_us",
                  "ax_raw", "ay_raw", "az_raw", "gx_raw", "gy_raw", "gz_raw",
                  "ax_m_s2", "ay_m_s2", "az_m_s2", "temp_deg_c",
                  "gx_deg_h", "gy_deg_h", "gz_deg_h"]
        rows = []
        for index, timer in enumerate((0, 10_000, 20_000, 50_000)):
            values = [index, 2435, 100_000_000 + timer, 1, timer,
                      0, 0, 16384, 0, 0, 0, 0, 0, 9.80665, 25, 0, 0, 0]
            rows.append(dict(zip(fields, values)))
        self.write_csv("imu.csv", fields, rows)
        findings = []
        result = analyze_session.analyze_imu(self.session / "imu.csv", findings)
        self.assertEqual(result["gap_count"], 1)
        self.assertTrue(any(item.code == "IMU_TIMING" for item in findings))


if __name__ == "__main__":
    unittest.main()
