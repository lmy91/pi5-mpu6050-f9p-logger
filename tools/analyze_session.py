#!/usr/bin/env python3
"""Analyze one MPU6050/F9P recording session and write a Chinese quality report.

The analyzer is dependency-free and streams large CSV/UBX files. It checks
acquisition integrity first, then sensor and GNSS observation quality.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import random
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable


GPS_WEEK_S = 604_800.0
EARTH_RADIUS_M = 6_378_137.0


@dataclass
class Finding:
    level: str
    code: str
    message: str


class SampleStats:
    """Online moments plus a bounded deterministic percentile reservoir."""

    def __init__(self, sample_limit: int = 100_000, seed: int = 1):
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.minimum = math.inf
        self.maximum = -math.inf
        self.samples: list[float] = []
        self.sample_limit = sample_limit
        self.random = random.Random(seed)

    def add(self, value: float) -> bool:
        if not math.isfinite(value):
            return False
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)
        if len(self.samples) < self.sample_limit:
            self.samples.append(value)
        else:
            index = self.random.randrange(self.n)
            if index < self.sample_limit:
                self.samples[index] = value
        return True

    @property
    def std(self) -> float:
        return math.sqrt(self.m2 / (self.n - 1)) if self.n > 1 else 0.0

    def percentile(self, q: float) -> float | None:
        if not self.samples:
            return None
        ordered = sorted(self.samples)
        position = (len(ordered) - 1) * q
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = position - lower
        return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction

    def summary(self) -> dict[str, float | int | None]:
        return {
            "count": self.n,
            "min": None if self.n == 0 else self.minimum,
            "mean": None if self.n == 0 else self.mean,
            "std": None if self.n == 0 else self.std,
            "p50": self.percentile(0.50),
            "p95": self.percentile(0.95),
            "p99": self.percentile(0.99),
            "max": None if self.n == 0 else self.maximum,
        }


class Unwrapper:
    def __init__(self, bits: int = 32):
        self.modulus = 1 << bits
        self.offset = 0
        self.last_raw: int | None = None

    def add(self, raw: int) -> tuple[int, bool]:
        backwards = False
        if self.last_raw is not None and raw < self.last_raw:
            if self.last_raw - raw > self.modulus // 2:
                self.offset += self.modulus
            else:
                backwards = True
        self.last_raw = raw
        return raw + self.offset, backwards


def number(row: dict[str, str], name: str, integer: bool = False) -> float | int:
    value = row.get(name)
    if value is None or value == "":
        raise ValueError(f"missing {name}")
    parsed = int(value) if integer else float(value)
    if not integer and not math.isfinite(parsed):
        raise ValueError(f"non-finite {name}")
    return parsed


def ratio(part: int, total: int) -> float:
    return part / total if total else 0.0


def pct(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def fmt(value: float | int | None, digits: int = 3) -> str:
    if value is None or not math.isfinite(float(value)):
        return "--"
    return f"{float(value):.{digits}f}"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def latest_session(data_dir: pathlib.Path) -> pathlib.Path:
    candidates = [p for p in data_dir.iterdir() if p.is_dir() and
                  ((p / "imu.csv").is_file() or (p / "gnss.csv").is_file())]
    if not candidates:
        raise FileNotFoundError(f"{data_dir} 中没有采集会话")
    return max(candidates, key=lambda p: (p.stat().st_mtime, p.name))


def resolve_session(value: str | None, project_root: pathlib.Path) -> pathlib.Path:
    if value:
        path = pathlib.Path(value).expanduser().resolve()
        if path.is_file():
            path = path.parent
        if not path.is_dir():
            raise FileNotFoundError(f"采集目录不存在：{path}")
        return path
    return latest_session(project_root / "data" / "decoded")


def csv_rows(path: pathlib.Path, required: Iterable[str]):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        missing = sorted(set(required) - set(fields))
        if missing:
            raise ValueError(f"缺少字段：{', '.join(missing)}")
        for row in reader:
            malformed = None in row or any(value is None for value in row.values())
            yield row, malformed


def analyze_imu(path: pathlib.Path, findings: list[Finding]) -> dict[str, object]:
    required = ["sample", "gps_week", "gps_tow_us", "time_valid", "timer_us",
                "ax_raw", "ay_raw", "az_raw", "gx_raw", "gy_raw", "gz_raw",
                "ax_m_s2", "ay_m_s2", "az_m_s2", "temp_deg_c",
                "gx_deg_h", "gy_deg_h", "gz_deg_h"]
    rows = malformed = invalid_numeric = timed_valid = 0
    clipped_acc = clipped_gyro = sample_discontinuities = 0
    clipped_acc_axes = [0, 0, 0]
    current_clip_run = longest_clip_run = 0
    timer_backwards = timer_duplicates = gap_count = estimated_missing = 0
    first_timer = last_timer = previous_timer = previous_sample = None
    first_gps = last_gps = previous_gps = previous_timed_timer = None
    sync_step, dt_stats = SampleStats(), SampleStats()
    accel_norm, gyro_norm, temperature = SampleStats(), SampleStats(), SampleStats()
    accel_axes = [SampleStats(seed=10 + i) for i in range(3)]
    gyro_axes = [SampleStats(seed=20 + i) for i in range(3)]
    timer_unwrapper, sample_unwrapper = Unwrapper(), Unwrapper()
    try:
        for row, bad_shape in csv_rows(path, required):
            rows += 1
            malformed += int(bad_shape)
            if bad_shape:
                continue
            try:
                sample_raw = int(number(row, "sample", True))
                timer_raw = int(number(row, "timer_us", True))
                week = int(number(row, "gps_week", True))
                tow_us = int(number(row, "gps_tow_us", True))
                valid = int(number(row, "time_valid", True))
                accel_raw = [int(number(row, name, True)) for name in
                             ("ax_raw", "ay_raw", "az_raw")]
                gyro_raw = [int(number(row, name, True)) for name in
                            ("gx_raw", "gy_raw", "gz_raw")]
                accel = [float(number(row, name)) for name in
                         ("ax_m_s2", "ay_m_s2", "az_m_s2")]
                gyro = [float(number(row, name)) / 3600.0 for name in
                        ("gx_deg_h", "gy_deg_h", "gz_deg_h")]
                temp = float(number(row, "temp_deg_c"))
            except (ValueError, TypeError):
                invalid_numeric += 1
                continue
            sample, _ = sample_unwrapper.add(sample_raw)
            timer, backwards = timer_unwrapper.add(timer_raw)
            timer_backwards += int(backwards)
            if previous_sample is not None and sample != previous_sample + 1:
                sample_discontinuities += 1
                if sample > previous_sample + 1:
                    estimated_missing += sample - previous_sample - 1
            previous_sample = sample
            if previous_timer is not None:
                delta = (timer - previous_timer) / 1e6
                if delta == 0:
                    timer_duplicates += 1
                elif delta > 0:
                    dt_stats.add(delta)
                    gap_count += int(delta > 0.015)
            previous_timer = timer
            first_timer = timer if first_timer is None else first_timer
            last_timer = timer
            if valid == 1 and 0 <= tow_us < int(GPS_WEEK_S * 1e6):
                timed_valid += 1
                gps = week * GPS_WEEK_S + tow_us / 1e6
                first_gps = gps if first_gps is None else first_gps
                last_gps = gps
                if previous_gps is not None and previous_timed_timer is not None:
                    gps_step = gps - previous_gps
                    timer_step = (timer - previous_timed_timer) / 1e6
                    if 0 < gps_step < 1.0 and timer_step > 0:
                        sync_step.add(abs(gps_step - timer_step))
                previous_gps, previous_timed_timer = gps, timer
            accel_clipped = any(abs(v) >= 32760 for v in accel_raw)
            clipped_acc += int(accel_clipped)
            clipped_gyro += int(any(abs(v) >= 32760 for v in gyro_raw))
            for index, value in enumerate(accel_raw):
                clipped_acc_axes[index] += int(abs(value) >= 32760)
            current_clip_run = current_clip_run + 1 if accel_clipped else 0
            longest_clip_run = max(longest_clip_run, current_clip_run)
            for stats, value in zip(accel_axes, accel):
                stats.add(value)
            for stats, value in zip(gyro_axes, gyro):
                stats.add(value)
            accel_norm.add(math.sqrt(sum(v * v for v in accel)))
            gyro_norm.add(math.sqrt(sum(v * v for v in gyro)))
            temperature.add(temp)
    except (OSError, ValueError, csv.Error) as error:
        findings.append(Finding("ERROR", "IMU_FILE", f"IMU文件无法解析：{error}"))
        return {"rows": rows, "error": str(error)}

    duration = ((last_timer - first_timer) / 1e6
                if first_timer is not None and last_timer is not None else 0.0)
    valid_rows = max(0, rows - malformed - invalid_numeric)
    rate_hz = (valid_rows - 1) / duration if duration > 0 and valid_rows > 1 else 0.0
    if rows < 2:
        findings.append(Finding("ERROR", "IMU_EMPTY", "IMU有效数据不足2行"))
    if malformed or invalid_numeric:
        findings.append(Finding("ERROR", "IMU_PARSE",
                                f"IMU存在{malformed}行列数异常、{invalid_numeric}行数值异常"))
    if rate_hz and not 98.0 <= rate_hz <= 102.0:
        level = "ERROR" if not 90.0 <= rate_hz <= 110.0 else "WARN"
        findings.append(Finding(level, "IMU_RATE", f"IMU平均频率{rate_hz:.3f} Hz，偏离100 Hz"))
    if gap_count or sample_discontinuities or timer_backwards or timer_duplicates:
        findings.append(Finding("WARN", "IMU_TIMING",
                                f"IMU间隔超15 ms {gap_count}次，序号不连续{sample_discontinuities}次，"
                                f"时间倒退/重复{timer_backwards}/{timer_duplicates}次，估算缺样{estimated_missing}"))
    if clipped_acc or clipped_gyro:
        findings.append(Finding("ERROR", "IMU_CLIP",
                                f"IMU达到ADC量程边缘：加速度{clipped_acc}行、陀螺{clipped_gyro}行"))
    time_valid_ratio = ratio(timed_valid, valid_rows)
    if valid_rows and time_valid_ratio < 0.99:
        level = "ERROR" if time_valid_ratio < 0.50 else "WARN"
        findings.append(Finding(level, "IMU_GNSS_TIME",
                                f"带有效GNSS时间的IMU仅占{pct(time_valid_ratio)}"))
    p99_dt = dt_stats.percentile(0.99)
    if p99_dt is not None and p99_dt > 0.012:
        findings.append(Finding("WARN", "IMU_JITTER", f"IMU间隔P99为{p99_dt*1000:.3f} ms"))
    sync_p99 = sync_step.percentile(0.99)
    if sync_p99 is not None and sync_p99 > 0.0002:
        findings.append(Finding("WARN", "IMU_TIME_SYNC",
                                f"相邻IMU的GNSS时间与MCU时间步长误差P99为{sync_p99*1e6:.1f} us"))
    return {
        "rows": rows, "valid_rows": valid_rows, "duration_s": duration,
        "rate_hz": rate_hz, "malformed_rows": malformed,
        "invalid_numeric_rows": invalid_numeric,
        "time_valid_ratio": time_valid_ratio, "gap_count": gap_count,
        "estimated_missing": estimated_missing,
        "sample_discontinuities": sample_discontinuities,
        "timer_backwards": timer_backwards, "timer_duplicates": timer_duplicates,
        "clipped_accel_rows": clipped_acc, "clipped_accel_axes_xyz": clipped_acc_axes,
        "longest_accel_clip_run": longest_clip_run,
        "clipped_gyro_rows": clipped_gyro,
        "dt_s": dt_stats.summary(), "gps_timer_step_error_s": sync_step.summary(),
        "accel_norm_m_s2": accel_norm.summary(), "gyro_norm_deg_s": gyro_norm.summary(),
        "temperature_deg_c": temperature.summary(),
        "accel_axes_m_s2": [s.summary() for s in accel_axes],
        "gyro_axes_deg_s": [s.summary() for s in gyro_axes],
        "gps_start_s": first_gps, "gps_end_s": last_gps,
    }


def analyze_gnss(path: pathlib.Path, findings: list[Finding]) -> dict[str, object]:
    required = ["gps_week", "gps_tow_ms", "time_valid", "rx_timer_us", "fix", "num_sv",
                "carr_soln", "gnss_fix_ok", "diff_soln", "lat_deg", "lon_deg",
                "hmsl_m", "h_acc_m", "v_acc_m", "vel_n_m_s", "vel_e_m_s",
                "vel_d_m_s", "ground_speed_m_s", "s_acc_m_s", "pdop"]
    rows = malformed = invalid_numeric = time_valid = fix_ok = diff = 0
    invalid_rx_timestamps = 0
    rtk_float = rtk_fixed = invalid_coord = position_steps = 0
    gaps = backwards = duplicates = large_jumps = fix_transitions = 0
    first_time = last_time = previous_time = None
    previous_position = previous_fix_state = None
    distance_m = 0.0
    dt_stats, step_stats, implied_speed = SampleStats(), SampleStats(), SampleStats()
    satellites, pdop, hacc, vacc, sacc, ground = (SampleStats(seed=30 + i) for i in range(6))
    heights = SampleStats(seed=40)
    fix_counter: Counter[int] = Counter()
    try:
        for row, bad_shape in csv_rows(path, required):
            rows += 1
            malformed += int(bad_shape)
            if bad_shape:
                continue
            try:
                week = int(number(row, "gps_week", True))
                tow_ms = int(number(row, "gps_tow_ms", True))
                valid = int(number(row, "time_valid", True))
                rx_timer_us = int(number(row, "rx_timer_us", True))
                fix = int(number(row, "fix", True))
                num_sv = int(number(row, "num_sv", True))
                carr = int(number(row, "carr_soln", True))
                good = int(number(row, "gnss_fix_ok", True))
                differential = int(number(row, "diff_soln", True))
                lat = float(number(row, "lat_deg")); lon = float(number(row, "lon_deg"))
                height = float(number(row, "hmsl_m"))
                values = [float(number(row, name)) for name in
                          ("h_acc_m", "v_acc_m", "s_acc_m_s", "pdop", "ground_speed_m_s")]
            except (ValueError, TypeError):
                invalid_numeric += 1
                continue
            # A local microsecond timestamp in the upper half of uint64 would
            # require over 292,000 years of uptime. Values there indicate the
            # historical low-word reconstruction underflow in STM32 firmware.
            invalid_rx_timestamps += int(rx_timer_us >= (1 << 63))
            time_valid += int(valid == 1)
            # iTOW remains useful for relative continuity when the firmware has
            # not accepted an absolute GPS week from TIM-TP.
            stamp = week * GPS_WEEK_S + tow_ms / 1000.0
            continuity_stamp = stamp if week > 0 else tow_ms / 1000.0
            if previous_time is not None:
                delta = continuity_stamp - previous_time
                if delta < -GPS_WEEK_S / 2:
                    delta += GPS_WEEK_S
                if delta < 0:
                    backwards += 1
                elif delta == 0:
                    duplicates += 1
                else:
                    dt_stats.add(delta)
                    gaps += int(delta > 1.5)
            previous_time = continuity_stamp
            if valid == 1 and week > 0:
                first_time = stamp if first_time is None else first_time
                last_time = stamp
            fix_ok += int(good == 1 and fix >= 3)
            diff += int(differential == 1)
            rtk_float += int(carr == 1); rtk_fixed += int(carr == 2)
            fix_counter[fix] += 1
            state = (fix, carr, good)
            if previous_fix_state is not None and state != previous_fix_state:
                fix_transitions += 1
            previous_fix_state = state
            satellites.add(num_sv); hacc.add(values[0]); vacc.add(values[1])
            sacc.add(values[2]); pdop.add(values[3]); ground.add(values[4]); heights.add(height)
            coordinate_good = good == 1 and fix >= 3 and -90 <= lat <= 90 and -180 <= lon <= 180
            invalid_coord += int(not (-90 <= lat <= 90 and -180 <= lon <= 180))
            if coordinate_good:
                position = (lat, lon, continuity_stamp)
                if previous_position is not None:
                    step = haversine_m(previous_position[0], previous_position[1], lat, lon)
                    delta = stamp - previous_position[2]
                    step_stats.add(step); distance_m += step; position_steps += 1
                    if delta > 0:
                        speed = step / delta
                        implied_speed.add(speed)
                        large_jumps += int(speed > max(100.0, values[4] + 50.0))
                previous_position = position
    except (OSError, ValueError, csv.Error) as error:
        findings.append(Finding("ERROR", "GNSS_FILE", f"GNSS文件无法解析：{error}"))
        return {"rows": rows, "error": str(error)}

    valid_rows = max(0, rows - malformed - invalid_numeric)
    duration = dt_stats.mean * dt_stats.n if dt_stats.n else 0.0
    rate_hz = dt_stats.n / duration if duration > 0 else 0.0
    if rows < 2:
        findings.append(Finding("ERROR", "GNSS_EMPTY", "GNSS有效数据不足2行"))
    if malformed or invalid_numeric:
        findings.append(Finding("ERROR", "GNSS_PARSE",
                                f"GNSS存在{malformed}行列数异常、{invalid_numeric}行数值异常"))
    if invalid_rx_timestamps:
        findings.append(Finding(
            "ERROR", "GNSS_RX_TIMESTAMP",
            f"GNSS存在{invalid_rx_timestamps}/{valid_rows}行本地接收时间戳下溢；"
            "这些行可从低32位恢复，但不得直接用于IMU/GNSS配时"))
    if rate_hz and not 0.95 <= rate_hz <= 1.05:
        level = "ERROR" if not 0.80 <= rate_hz <= 1.20 else "WARN"
        findings.append(Finding(level, "GNSS_RATE", f"GNSS平均频率{rate_hz:.3f} Hz，偏离1 Hz"))
    if gaps or backwards or duplicates:
        findings.append(Finding("WARN", "GNSS_TIMING",
                                f"GNSS间隔超1.5 s {gaps}次，时间倒退/重复{backwards}/{duplicates}次"))
    time_ratio = ratio(time_valid, valid_rows); fix_ratio = ratio(fix_ok, valid_rows)
    if valid_rows and time_ratio < 0.99:
        findings.append(Finding("WARN" if time_ratio >= 0.5 else "ERROR", "GNSS_TIME",
                                f"GNSS有效时间占比{pct(time_ratio)}"))
    if valid_rows and fix_ratio < 0.90:
        findings.append(Finding("WARN" if fix_ratio > 0 else "ERROR", "GNSS_FIX",
                                f"3D及以上有效定位占比{pct(fix_ratio)}"))
    if satellites.percentile(0.50) is not None and satellites.percentile(0.50) < 10:
        findings.append(Finding("WARN", "GNSS_SAT", f"卫星数中位数仅{satellites.percentile(0.50):.0f}"))
    if pdop.percentile(0.95) is not None and pdop.percentile(0.95) > 4.0:
        findings.append(Finding("WARN", "GNSS_PDOP", f"PDOP P95为{pdop.percentile(0.95):.2f}"))
    if hacc.percentile(0.95) is not None and hacc.percentile(0.95) > 5.0:
        findings.append(Finding("WARN", "GNSS_HACC", f"水平精度估计P95为{hacc.percentile(0.95):.2f} m"))
    if large_jumps:
        findings.append(Finding("WARN", "GNSS_JUMP", f"检测到{large_jumps}次疑似位置跳变（>100 m/s）"))
    if invalid_coord:
        findings.append(Finding("ERROR", "GNSS_COORD", f"存在{invalid_coord}行非法经纬度"))
    return {
        "rows": rows, "valid_rows": valid_rows, "duration_s": duration,
        "rate_hz": rate_hz, "malformed_rows": malformed,
        "invalid_numeric_rows": invalid_numeric, "time_valid_ratio": time_ratio,
        "invalid_rx_timestamp_rows": invalid_rx_timestamps,
        "fix_ok_ratio": fix_ratio, "differential_ratio": ratio(diff, valid_rows),
        "rtk_float_ratio": ratio(rtk_float, valid_rows),
        "rtk_fixed_ratio": ratio(rtk_fixed, valid_rows),
        "fix_counts": dict(sorted(fix_counter.items())), "fix_transitions": fix_transitions,
        "gap_count": gaps, "time_backwards": backwards, "time_duplicates": duplicates,
        "distance_m": distance_m, "position_steps": position_steps,
        "large_jump_count": large_jumps, "dt_s": dt_stats.summary(),
        "position_step_m": step_stats.summary(), "implied_speed_m_s": implied_speed.summary(),
        "ground_speed_m_s": ground.summary(), "satellites": satellites.summary(),
        "pdop": pdop.summary(), "h_acc_m": hacc.summary(), "v_acc_m": vacc.summary(),
        "s_acc_m_s": sacc.summary(), "height_m": heights.summary(),
        "gps_start_s": first_time, "gps_end_s": last_time,
    }


def analyze_rawx(path: pathlib.Path, findings: list[Finding]) -> dict[str, object]:
    required = ["gps_week", "rcv_tow_s", "rx_timer_us", "epoch_total_meas", "gnss_id", "sv_id",
                "sig_id", "pseudorange_m", "carrier_phase_cycles", "doppler_hz",
                "locktime_ms", "cno_dbhz", "pr_valid", "cp_valid"]
    rows = malformed = invalid_numeric = pr_valid = cp_valid = 0
    invalid_rx_timestamps = 0
    epochs = incomplete_epochs = gaps = backwards = duplicates = lock_resets = 0
    first_time = last_time = previous_epoch_time = None
    current_key = None
    current_count = current_expected = 0
    incomplete_indices: list[int] = []
    cno, measurements_per_epoch, epoch_dt = SampleStats(), SampleStats(), SampleStats()
    constellations: Counter[int] = Counter(); signals: Counter[str] = Counter()
    constellation_cp: Counter[int] = Counter()
    last_lock: dict[tuple[int, int, int, int], int] = {}

    def finish_epoch() -> None:
        nonlocal epochs, incomplete_epochs
        if current_key is None:
            return
        epochs += 1; measurements_per_epoch.add(current_count)
        if current_expected > 0 and current_count != current_expected:
            incomplete_epochs += 1
            incomplete_indices.append(epochs)

    try:
        for row, bad_shape in csv_rows(path, required):
            rows += 1; malformed += int(bad_shape)
            if bad_shape:
                continue
            try:
                week = int(number(row, "gps_week", True)); tow = float(number(row, "rcv_tow_s"))
                rx_timer_us = int(number(row, "rx_timer_us", True))
                expected = int(number(row, "epoch_total_meas", True))
                gnss_id = int(number(row, "gnss_id", True)); sv_id = int(number(row, "sv_id", True))
                sig_id = int(number(row, "sig_id", True)); freq_id = int(row.get("freq_id") or 0)
                lock = int(number(row, "locktime_ms", True)); cn0 = float(number(row, "cno_dbhz"))
                pseudorange = float(number(row, "pseudorange_m"))
                float(number(row, "carrier_phase_cycles")); float(number(row, "doppler_hz"))
                prv = int(number(row, "pr_valid", True)); cpv = int(number(row, "cp_valid", True))
            except (ValueError, TypeError):
                invalid_numeric += 1
                continue
            if not 1e6 < pseudorange < 1e8:
                invalid_numeric += 1
                continue
            invalid_rx_timestamps += int(rx_timer_us >= (1 << 63))
            stamp = week * GPS_WEEK_S + tow; key = (week, round(tow, 4))
            if key != current_key:
                finish_epoch()
                if previous_epoch_time is not None:
                    delta = stamp - previous_epoch_time
                    if delta < 0: backwards += 1
                    elif delta == 0: duplicates += 1
                    else:
                        epoch_dt.add(delta); gaps += int(delta > 1.5)
                previous_epoch_time = stamp
                first_time = stamp if first_time is None else first_time; last_time = stamp
                current_key, current_count, current_expected = key, 0, expected
            current_count += 1; current_expected = max(current_expected, expected)
            pr_valid += int(prv == 1); cp_valid += int(cpv == 1)
            cno.add(cn0); constellations[gnss_id] += 1
            constellation_cp[gnss_id] += int(cpv == 1)
            signals[row.get("signal") or f"GNSS{gnss_id}_SIG{sig_id}"] += 1
            obs_key = (gnss_id, sv_id, sig_id, freq_id); previous_lock = last_lock.get(obs_key)
            if cpv == 1 and previous_lock is not None and lock + 1000 < previous_lock:
                lock_resets += 1
            last_lock[obs_key] = lock
        finish_epoch()
    except (OSError, ValueError, csv.Error) as error:
        findings.append(Finding("ERROR", "RAWX_FILE", f"RAWX文件无法解析：{error}"))
        return {"rows": rows, "error": str(error)}

    valid_rows = max(0, rows - malformed - invalid_numeric)
    duration = last_time - first_time if first_time is not None and last_time is not None else 0.0
    rate_hz = (epochs - 1) / duration if duration > 0 and epochs > 1 else 0.0
    if rows == 0 or epochs == 0:
        findings.append(Finding("ERROR", "RAWX_EMPTY", "RAWX没有有效观测值"))
    if malformed or invalid_numeric:
        findings.append(Finding("ERROR", "RAWX_PARSE",
                                f"RAWX存在{malformed}行列数异常、{invalid_numeric}行数值/伪距异常"))
    if invalid_rx_timestamps:
        findings.append(Finding(
            "ERROR", "RAWX_RX_TIMESTAMP",
            f"RAWX存在{invalid_rx_timestamps}/{valid_rows}行本地接收时间戳下溢；"
            "这些行可从低32位恢复，但不得直接用于IMU/GNSS配时"))
    boundary_incomplete = sum(index in (1, epochs) for index in incomplete_indices)
    interior_incomplete = incomplete_epochs - boundary_incomplete
    if interior_incomplete:
        level = "ERROR" if ratio(interior_incomplete, epochs) > 0.01 else "WARN"
        findings.append(Finding(level, "RAWX_INCOMPLETE",
                                f"RAWX内部不完整历元{interior_incomplete}/{epochs}（{pct(ratio(interior_incomplete, epochs))}）"))
    if rate_hz and not 0.90 <= rate_hz <= 1.10:
        findings.append(Finding("WARN", "RAWX_RATE", f"RAWX历元平均频率{rate_hz:.3f} Hz"))
    if gaps or backwards or duplicates:
        findings.append(Finding("WARN", "RAWX_TIMING",
                                f"RAWX历元间隔超1.5 s {gaps}次，时间倒退/重复{backwards}/{duplicates}次"))
    cp_ratio = ratio(cp_valid, valid_rows)
    if valid_rows and cp_ratio < 0.80:
        findings.append(Finding("WARN", "RAWX_CARRIER", f"有效载波相位观测仅占{pct(cp_ratio)}"))
    return {
        "rows": rows, "valid_rows": valid_rows, "epochs": epochs,
        "duration_s": duration, "rate_hz": rate_hz,
        "malformed_rows": malformed, "invalid_numeric_rows": invalid_numeric,
        "invalid_rx_timestamp_rows": invalid_rx_timestamps,
        "incomplete_epochs": incomplete_epochs,
        "boundary_incomplete_epochs": boundary_incomplete,
        "interior_incomplete_epochs": interior_incomplete, "gap_count": gaps,
        "time_backwards": backwards, "time_duplicates": duplicates,
        "pr_valid_ratio": ratio(pr_valid, valid_rows), "cp_valid_ratio": cp_ratio,
        "lock_reset_count": lock_resets, "cno_dbhz": cno.summary(),
        "measurements_per_epoch": measurements_per_epoch.summary(),
        "epoch_dt_s": epoch_dt.summary(), "constellation_measurements": dict(constellations),
        "signal_measurements": dict(signals),
        "constellation_cp_valid_ratio": {
            str(key): ratio(constellation_cp[key], count)
            for key, count in sorted(constellations.items())},
        "gps_start_s": first_time,
        "gps_end_s": last_time,
    }


def analyze_ubx(path: pathlib.Path, findings: list[Finding]) -> dict[str, object]:
    total_bytes = path.stat().st_size
    frames = bad_checksum = discarded = 0
    message_types: Counter[str] = Counter(); buffer = bytearray()

    def consume(final: bool = False) -> None:
        nonlocal frames, bad_checksum, discarded, buffer
        while True:
            sync = buffer.find(b"\xb5\x62")
            if sync < 0:
                keep = 1 if not final and buffer.endswith(b"\xb5") else 0
                discarded += len(buffer) - keep
                buffer = buffer[-keep:] if keep else bytearray()
                return
            if sync:
                discarded += sync; del buffer[:sync]
            if len(buffer) < 6: return
            length = buffer[4] | (buffer[5] << 8); frame_length = 8 + length
            if len(buffer) < frame_length:
                if final:
                    discarded += len(buffer); buffer.clear()
                return
            frame = buffer[:frame_length]; ck_a = ck_b = 0
            for value in frame[2:-2]:
                ck_a = (ck_a + value) & 0xFF; ck_b = (ck_b + ck_a) & 0xFF
            if ck_a == frame[-2] and ck_b == frame[-1]:
                frames += 1; message_types[f"{frame[2]:02X}-{frame[3]:02X}"] += 1
                del buffer[:frame_length]
            else:
                bad_checksum += 1; discarded += 1; del buffer[0]

    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                buffer.extend(chunk); consume()
        consume(final=True)
    except OSError as error:
        findings.append(Finding("ERROR", "UBX_FILE", f"UBX文件无法读取：{error}"))
        return {"bytes": total_bytes, "error": str(error)}
    if total_bytes == 0 or frames == 0:
        findings.append(Finding("ERROR", "UBX_EMPTY", "f9p.ubx为空或没有完整UBX帧"))
    if bad_checksum:
        level = "ERROR" if ratio(bad_checksum, frames + bad_checksum) > 0.001 else "WARN"
        findings.append(Finding(level, "UBX_CRC", f"UBX校验失败{bad_checksum}帧，成功{frames}帧"))
    if total_bytes and ratio(discarded, total_bytes) > 0.001:
        findings.append(Finding("WARN", "UBX_GARBAGE", f"UBX流中有{discarded}字节不属于有效帧"))
    if frames and message_types.get("02-15", 0) == 0:
        findings.append(Finding("WARN", "UBX_NO_RAWX", "UBX流中没有RXM-RAWX消息(02-15)"))
    if frames and message_types.get("02-13", 0) == 0:
        findings.append(Finding("WARN", "UBX_NO_SFRBX", "UBX流中没有RXM-SFRBX导航电文(02-13)"))
    return {"bytes": total_bytes, "frames": frames,
            "bad_checksum_frames": bad_checksum, "discarded_bytes": discarded,
            "message_types": dict(message_types.most_common())}


def add_cross_checks(results: dict[str, object], findings: list[Finding]) -> None:
    spans = []
    for name in ("imu", "gnss", "rawx"):
        item = results.get(name)
        if isinstance(item, dict) and isinstance(item.get("gps_start_s"), (int, float)):
            spans.append((name, float(item["gps_start_s"]), float(item["gps_end_s"])))
    if len(spans) < 2: return
    overlap_start = max(item[1] for item in spans); overlap_end = min(item[2] for item in spans)
    union_start = min(item[1] for item in spans); union_end = max(item[2] for item in spans)
    coverage = max(0.0, overlap_end - overlap_start) / max(1e-9, union_end - union_start)
    results["time_coverage"] = {"overlap_ratio": coverage,
                                "start_spread_s": max(x[1] for x in spans) - min(x[1] for x in spans),
                                "end_spread_s": max(x[2] for x in spans) - min(x[2] for x in spans)}
    if coverage < 0.95:
        findings.append(Finding("WARN", "TIME_COVERAGE",
                                f"IMU/GNSS/RAWX共同时间覆盖仅{pct(coverage)}，检查是否同时启停"))


def add_motion_mode_checks(results: dict[str, object], findings: list[Finding], mode: str) -> None:
    imu = results.get("imu"); gnss = results.get("gnss")
    if not isinstance(imu, dict) or not isinstance(gnss, dict):
        return
    speed = gnss.get("ground_speed_m_s")
    speed_p95 = speed.get("p95") if isinstance(speed, dict) else None
    selected = mode
    if mode == "auto":
        selected = "static" if isinstance(speed_p95, (int, float)) and speed_p95 < 0.30 else "dynamic"
    results["motion_mode"] = selected
    if selected != "static":
        return
    axes = imu.get("gyro_axes_deg_s")
    means = [abs(float(item.get("mean") or 0.0)) for item in axes] if isinstance(axes, list) else []
    max_bias = max(means, default=0.0)
    if max_bias > 3.0:
        level = "ERROR" if max_bias > 20.0 else "WARN"
        findings.append(Finding(level, "IMU_STATIC_GYRO_BIAS",
                                f"静态数据最大轴平均角速度为{max_bias:.3f} °/s，零偏偏大，应标定并反馈补偿"))
    accel_norm = imu.get("accel_norm_m_s2")
    accel_mean = accel_norm.get("mean") if isinstance(accel_norm, dict) else None
    accel_std = accel_norm.get("std") if isinstance(accel_norm, dict) else None
    if isinstance(accel_mean, (int, float)) and abs(accel_mean - 9.80665) > 0.5:
        findings.append(Finding("WARN", "IMU_STATIC_ACCEL_SCALE",
                                f"静态加速度模长均值{accel_mean:.3f} m/s²，偏离标准重力较多"))
    if isinstance(accel_std, (int, float)) and accel_std > 0.20:
        findings.append(Finding("WARN", "IMU_STATIC_MOTION",
                                f"标记为静态但加速度模长标准差为{accel_std:.3f} m/s²"))
    if isinstance(speed_p95, (int, float)) and speed_p95 > 0.50:
        findings.append(Finding("WARN", "GNSS_STATIC_MOTION",
                                f"标记为静态但GNSS地速P95为{speed_p95:.3f} m/s"))


def verdict(findings: list[Finding]) -> tuple[str, int]:
    if any(item.level == "ERROR" for item in findings):
        return "异常：存在会影响后续解算的数据完整性问题", 2
    if any(item.level == "WARN" for item in findings):
        return "基本可用：采集完成，但存在需要核查的警告", 1
    return "正常：未发现明显的采集完整性或质量异常", 0


def nested_fmt(container: dict[str, object], key: str, subkey: str, digits: int = 3) -> str:
    value = container.get(key)
    return fmt(value.get(subkey), digits) if isinstance(value, dict) else "--"


def fmt_ms(container: dict[str, object], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, dict) or value.get("p99") is None: return "--"
    return f"{float(value['p99']) * 1000:.3f} ms"


def build_report(session: pathlib.Path, results: dict[str, object], findings: list[Finding]) -> str:
    result_text, _ = verdict(findings)
    imu = results.get("imu", {}); gnss = results.get("gnss", {})
    rawx = results.get("rawx", {}); ubx = results.get("ubx", {})
    assert isinstance(imu, dict) and isinstance(gnss, dict)
    assert isinstance(rawx, dict) and isinstance(ubx, dict)
    mode_text = {"static": "静态", "dynamic": "动态"}.get(str(results.get("motion_mode")), "自动")
    lines = ["# GNSS/IMU采集质量报告", "", f"- 会话：`{session.name}`",
             f"- 目录：`{session}`", f"- 分析模式：{mode_text}",
             f"- 总结：**{result_text}**", "", "## 结论与问题", ""]
    if findings:
        icon = {"ERROR": "❌", "WARN": "⚠️", "INFO": "ℹ️"}
        lines.extend(f"- {icon.get(x.level, '•')} **{x.level} {x.code}**：{x.message}" for x in findings)
    else:
        lines.append("- ✅ 所有自动检查通过。")
    lines += ["", "## 采集完整性", "",
              "| 数据 | 数量 | 时长 | 平均频率 | 时间间隔P99 | 主要异常 |",
              "|---|---:|---:|---:|---:|---|",
              f"| IMU | {imu.get('valid_rows', 0)}行 | {fmt(imu.get('duration_s'), 1)} s | {fmt(imu.get('rate_hz'))} Hz | {fmt_ms(imu, 'dt_s')} | 缺样估计 {imu.get('estimated_missing', 0)}，饱和 {int(imu.get('clipped_accel_rows', 0) or 0)+int(imu.get('clipped_gyro_rows', 0) or 0)} |",
              f"| GNSS | {gnss.get('valid_rows', 0)}行 | {fmt(gnss.get('duration_s'), 1)} s | {fmt(gnss.get('rate_hz'))} Hz | {fmt_ms(gnss, 'dt_s')} | 间断 {gnss.get('gap_count', 0)}，跳点 {gnss.get('large_jump_count', 0)} |",
              f"| RAWX | {rawx.get('epochs', 0)}历元/{rawx.get('valid_rows', 0)}观测 | {fmt(rawx.get('duration_s'), 1)} s | {fmt(rawx.get('rate_hz'))} Hz | {fmt_ms(rawx, 'epoch_dt_s')} | 不完整历元 {rawx.get('incomplete_epochs', 0)}（边界 {rawx.get('boundary_incomplete_epochs', 0)}） |",
              f"| UBX | {ubx.get('frames', 0)}帧/{ubx.get('bytes', 0)} B | -- | -- | -- | CRC错 {ubx.get('bad_checksum_frames', 0)}，杂字节 {ubx.get('discarded_bytes', 0)} |",
              "", "## IMU", "",
              f"- GNSS时间有效率：{pct(float(imu.get('time_valid_ratio', 0) or 0))}",
              f"- 加速度模长：均值 {nested_fmt(imu, 'accel_norm_m_s2', 'mean')} m/s²，P99 {nested_fmt(imu, 'accel_norm_m_s2', 'p99')} m/s²，最大 {nested_fmt(imu, 'accel_norm_m_s2', 'max')} m/s²",
              f"- 加速度饱和：{imu.get('clipped_accel_rows', 0)}行；X/Y/Z轴计数 `{imu.get('clipped_accel_axes_xyz', [])}`；最长连续 {imu.get('longest_accel_clip_run', 0)}个样本",
              f"- 角速度模长：均值 {nested_fmt(imu, 'gyro_norm_deg_s', 'mean')} °/s，P99 {nested_fmt(imu, 'gyro_norm_deg_s', 'p99')} °/s，最大 {nested_fmt(imu, 'gyro_norm_deg_s', 'max')} °/s",
              f"- 温度：{nested_fmt(imu, 'temperature_deg_c', 'min')}～{nested_fmt(imu, 'temperature_deg_c', 'max')} °C",
              f"- GNSS时间与MCU时间相邻步长误差P99：{fmt(1e6 * float((imu.get('gps_timer_step_error_s') or {}).get('p99') or 0), 3)} µs",
              "", "## GNSS定位", "",
              f"- 有效定位率：{pct(float(gnss.get('fix_ok_ratio', 0) or 0))}；差分率：{pct(float(gnss.get('differential_ratio', 0) or 0))}",
              f"- RTK浮点/固定率：{pct(float(gnss.get('rtk_float_ratio', 0) or 0))} / {pct(float(gnss.get('rtk_fixed_ratio', 0) or 0))}",
              f"- 卫星数：中位数 {nested_fmt(gnss, 'satellites', 'p50', 1)}，P95 {nested_fmt(gnss, 'satellites', 'p95', 1)}",
              f"- PDOP：中位数 {nested_fmt(gnss, 'pdop', 'p50')}，P95 {nested_fmt(gnss, 'pdop', 'p95')}",
              f"- hAcc：中位数 {nested_fmt(gnss, 'h_acc_m', 'p50')} m，P95 {nested_fmt(gnss, 'h_acc_m', 'p95')} m",
              f"- 地速：最大 {nested_fmt(gnss, 'ground_speed_m_s', 'max')} m/s；轨迹逐点累计长度 {fmt(gnss.get('distance_m'), 1)} m",
              "", "## 原始观测", "",
              f"- 每历元观测数：中位数 {nested_fmt(rawx, 'measurements_per_epoch', 'p50', 1)}，P95 {nested_fmt(rawx, 'measurements_per_epoch', 'p95', 1)}",
              f"- 伪距/载波相位有效率：{pct(float(rawx.get('pr_valid_ratio', 0) or 0))} / {pct(float(rawx.get('cp_valid_ratio', 0) or 0))}",
              f"- C/N0：中位数 {nested_fmt(rawx, 'cno_dbhz', 'p50')} dB-Hz，P95 {nested_fmt(rawx, 'cno_dbhz', 'p95')} dB-Hz",
              f"- 载波锁定时间复位计数（仅提示潜在周跳）：{rawx.get('lock_reset_count', 0)}",
              f"- 各系统载波有效率（0/2/3/5/6=GPS/Galileo/北斗/QZSS/GLONASS）：`{json.dumps(rawx.get('constellation_cp_valid_ratio', {}), ensure_ascii=False)}`",
              f"- UBX消息类型计数：`{json.dumps(ubx.get('message_types', {}), ensure_ascii=False)}`",
              "", "## 判读说明", "",
              "自动检查用于发现丢样、时间断裂、CSV损坏、传感器饱和、GNSS失锁、RAWX缺历元和UBX校验错误。",
              "动态轨迹累计长度包含GNSS噪声，不能直接当作测程；潜在周跳计数也不能替代后处理软件的周跳探测。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="检查一次树莓派GNSS/IMU采集是否完整、连续且质量合理")
    parser.add_argument("session", nargs="?", help="采集会话目录；省略时分析data/decoded中最新目录")
    parser.add_argument("--report", help="Markdown报告路径；默认写入会话目录quality_report.md")
    parser.add_argument("--json", dest="json_path", help="另存机器可读JSON报告")
    parser.add_argument("--no-save", action="store_true", help="只在终端显示，不写Markdown")
    parser.add_argument("--mode", choices=("auto", "static", "dynamic"), default="auto",
                        help="运动模式；auto按GNSS地速判断，默认auto")
    args = parser.parse_args(); project_root = pathlib.Path(__file__).resolve().parents[1]
    try:
        session = resolve_session(args.session, project_root)
    except (OSError, FileNotFoundError) as error:
        print(f"错误：{error}", file=sys.stderr); return 2
    findings: list[Finding] = []; results: dict[str, object] = {"session": str(session)}
    analyzers = (("imu", "imu.csv", analyze_imu), ("gnss", "gnss.csv", analyze_gnss),
                 ("rawx", "rawx.csv", analyze_rawx), ("ubx", "f9p.ubx", analyze_ubx))
    for key, filename, analyzer in analyzers:
        path = session / filename
        if not path.is_file():
            findings.append(Finding("ERROR" if key in ("imu", "gnss") else "WARN",
                                    f"{key.upper()}_MISSING", f"缺少{filename}"))
            results[key] = {}; continue
        print(f"正在分析 {filename} ({path.stat().st_size / 1024 / 1024:.1f} MiB)…")
        results[key] = analyzer(path, findings)
    add_cross_checks(results, findings)
    add_motion_mode_checks(results, findings, args.mode)
    result_text, exit_code = verdict(findings); report = build_report(session, results, findings)
    print("\n" + result_text)
    if findings:
        for item in findings: print(f"[{item.level}] {item.code}: {item.message}")
    else: print("[OK] 所有自动检查通过")
    if not args.no_save:
        report_path = pathlib.Path(args.report).expanduser() if args.report else session / "quality_report.md"
        report_path.write_text(report, encoding="utf-8", newline="\n"); print(f"报告：{report_path}")
    if args.json_path:
        payload = {"verdict": result_text, "exit_code": exit_code,
                   "findings": [asdict(item) for item in findings], "results": results}
        pathlib.Path(args.json_path).expanduser().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        print(f"JSON：{args.json_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
