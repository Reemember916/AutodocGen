"""Maintenance RS422 protocol helpers for the PROJECT-2007 project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


FRAME_LEN = 16

HOST_HEADER = bytes((0xEB, 0x90))
DSP_HEADER = bytes((0x55, 0xAA))

CMD_COMM_INFO = 0x11
CMD_MAINT_FUNC = 0x99
CMD_GROUND_CONTROL = 0x66
CMD_RIU_SIM_INJECT = 0x67
CMD_STATE_COND_INJECT = 0x68

MAINT_STATE_INVALID = 0x00
MAINT_STATE_GROUND = 0x22

GROUND_MAINT_FUNC_INVALID = 0x00
GROUND_MAINT_FUNC_SOFT_CRC = 0x01
GROUND_MAINT_FUNC_DATA_DOWNLOAD = 0x02
GROUND_MAINT_FUNC_DATA_ERASE = 0x03
GROUND_MAINT_FUNC_PID_PARA_ADJUST = 0x04

CMD_UPDATE_INVALID = 0x00
CMD_UPDATE_VALID = 0x34

RIU_SIM_DISABLE = 0x00
RIU_SIM_ENABLE = 0x01
RIU_SIM_FUEL_CMD = 0x10
RIU_SIM_FUEL_PRESET = 0x11
RIU_SIM_TANK_0_3 = 0x12
RIU_SIM_TANK_4_EXT = 0x13
RIU_SIM_IO_FAULT = 0x14

RIU_OBJECT_HELICOPTER = 0
RIU_OBJECT_FIXEDWING = 1

RIU_MODE_OFF = 0
RIU_MODE_LP = 1
RIU_MODE_RP = 2
RIU_MODE_LRP = 3
RIU_MODE_RECEIVE = 4
RIU_MODE_MANUAL = 7

RIU_WHEEL_UNKNOWN = 0
RIU_WHEEL_GROUND = 1
RIU_WHEEL_AIR = 2

STATE_COND_DISABLE = 0x00
STATE_COND_ENABLE = 0x01
STATE_COND_IO = 0x10
STATE_COND_BIT = 0x20

GROUND_CONTROL_JYB_1 = 0
GROUND_CONTROL_JYB_2 = 1
GROUND_CONTROL_PQF = 2
GROUND_CONTROL_SOV = 3
GROUND_CONTROL_KZZZ = 4


class FrameError(ValueError):
    """Raised when a frame is malformed or fails validation."""


@dataclass(frozen=True)
class ParsedFrame:
    """Decoded DSP-to-host frame."""

    frame_id: int
    valid_checksum: bool
    raw: bytes
    fields: dict[str, int | str | bool]

    @property
    def hex(self) -> str:
        return bytes_to_hex(self.raw)


def clamp_byte(value: int) -> int:
    return int(value) & 0xFF


def bytes_to_hex(data: Iterable[int]) -> str:
    return " ".join(f"{clamp_byte(item):02X}" for item in data)


def parse_hex_bytes(text: str) -> bytes:
    cleaned = text.replace(",", " ").replace("0x", " ").replace("0X", " ")
    parts = [part for part in cleaned.split() if part]
    if not parts:
        raise FrameError("no bytes entered")
    try:
        values = [int(part, 16) for part in parts]
    except ValueError as exc:
        raise FrameError("hex input contains invalid bytes") from exc
    if any(value < 0 or value > 0xFF for value in values):
        raise FrameError("hex byte out of range")
    return bytes(values)


def checksum(data: bytes | bytearray) -> int:
    if len(data) != FRAME_LEN - 1:
        raise FrameError("checksum requires first 15 frame bytes")
    return ((~sum(data)) + 1) & 0xFF


def apply_checksum(frame: bytearray) -> bytes:
    if len(frame) != FRAME_LEN:
        raise FrameError("frame must be 16 bytes")
    frame[FRAME_LEN - 1] = checksum(frame[: FRAME_LEN - 1])
    return bytes(frame)


def validate_frame(frame: bytes | bytearray, header: bytes | None = None) -> bool:
    if len(frame) != FRAME_LEN:
        return False
    if header is not None and bytes(frame[:2]) != header:
        return False
    return checksum(bytes(frame[: FRAME_LEN - 1])) == frame[FRAME_LEN - 1]


def make_host_frame(
    command: int,
    frame_count: int = 0,
    maint_state: int = MAINT_STATE_GROUND,
    payload: dict[str, int] | None = None,
) -> bytes:
    payload = payload or {}
    frame = bytearray(FRAME_LEN)
    frame[0:2] = HOST_HEADER
    frame[2] = clamp_byte(frame_count)
    frame[3] = clamp_byte(command)
    frame[13] = clamp_byte(maint_state)

    if command == CMD_COMM_INFO:
        a429_info = clamp_byte(payload.get("a429_info", 0)) & 0x0F
        flowb_info = clamp_byte(payload.get("flowb_info", 0)) & 0x0F
        read_addr = int(payload.get("read_addr", 0)) & 0xFFFFFF
        frame[4] = a429_info | (flowb_info << 4)
        frame[5] = clamp_byte(payload.get("a429_label", 0))
        frame[6] = read_addr & 0xFF
        frame[7] = (read_addr >> 8) & 0xFF
        frame[8] = (read_addr >> 16) & 0xFF
        frame[9] = clamp_byte(payload.get("redundancy_info", 0))
        frame[10] = clamp_byte(payload.get("software_info", 0))
        frame[11] = clamp_byte(payload.get("analog_info", 0))
        frame[12] = clamp_byte(payload.get("pump_info", 0))
    elif command == CMD_MAINT_FUNC:
        func = clamp_byte(payload.get("function", GROUND_MAINT_FUNC_INVALID))
        frame[4] = func
        if func == GROUND_MAINT_FUNC_DATA_DOWNLOAD:
            start_addr = int(payload.get("download_start", 0)) & 0xFFFFFFFF
            length = int(payload.get("download_length", 0)) & 0xFFFFFFFF
            frame[5] = start_addr & 0xFF
            frame[6] = (start_addr >> 8) & 0xFF
            frame[7] = (start_addr >> 16) & 0xFF
            frame[8] = (start_addr >> 24) & 0xFF
            frame[9] = length & 0xFF
            frame[10] = (length >> 8) & 0xFF
            frame[11] = (length >> 16) & 0xFF
            frame[12] = (length >> 24) & 0xFF
    elif command == CMD_GROUND_CONTROL:
        data = int(payload.get("data", 0)) & 0xFFFF
        frame[4] = clamp_byte(payload.get("update_flag", CMD_UPDATE_VALID))
        frame[5] = clamp_byte(payload.get("command_id", GROUND_CONTROL_JYB_1))
        frame[6] = data & 0xFF
        frame[7] = (data >> 8) & 0xFF
    else:
        raise FrameError(f"unsupported host command 0x{command:02X}")

    return apply_checksum(frame)


def make_manual_host_frame(values: bytes | bytearray | Iterable[int]) -> bytes:
    frame = bytearray(values)
    if len(frame) != FRAME_LEN:
        raise FrameError("manual frame must be 16 bytes")
    frame[0:2] = HOST_HEADER
    return apply_checksum(frame)


def make_riu_sim_frame(subcmd: int, payload: Iterable[int] = (), frame_count: int = 0) -> bytes:
    data = [clamp_byte(item) for item in payload]
    if len(data) > 8:
        raise FrameError("RIU simulation payload must be at most 8 bytes")
    frame = bytearray(FRAME_LEN)
    frame[0:2] = HOST_HEADER
    frame[2] = clamp_byte(frame_count)
    frame[3] = CMD_RIU_SIM_INJECT
    frame[4] = clamp_byte(subcmd)
    frame[5 : 5 + len(data)] = bytes(data)
    frame[13] = MAINT_STATE_GROUND
    return apply_checksum(frame)


def make_state_cond_frame(subcmd: int, payload: Iterable[int] = (), frame_count: int = 0) -> bytes:
    data = [clamp_byte(item) for item in payload]
    if len(data) > 8:
        raise FrameError("state condition payload must be at most 8 bytes")
    frame = bytearray(FRAME_LEN)
    frame[0:2] = HOST_HEADER
    frame[2] = clamp_byte(frame_count)
    frame[3] = CMD_STATE_COND_INJECT
    frame[4] = clamp_byte(subcmd)
    frame[5 : 5 + len(data)] = bytes(data)
    frame[13] = MAINT_STATE_GROUND
    return apply_checksum(frame)


def le16(value: int) -> tuple[int, int]:
    value = int(value) & 0xFFFF
    return value & 0xFF, (value >> 8) & 0xFF


def parse_dsp_frame(frame: bytes | bytearray) -> ParsedFrame:
    raw = bytes(frame)
    if len(raw) != FRAME_LEN:
        raise FrameError("DSP frame must be 16 bytes")
    if raw[:2] != DSP_HEADER:
        raise FrameError("DSP frame header must be 55 AA")

    valid = validate_frame(raw, DSP_HEADER)
    frame_id = raw[2]
    fields: dict[str, int | str | bool] = {
        "frame_id": frame_id,
        "checksum": raw[15],
        "valid_checksum": valid,
    }

    if frame_id == 0:
        sys_time = raw[4] | (raw[5] << 8) | (raw[6] << 16) | (raw[7] << 24)
        fields.update(
            {
                "frame_name": "ID0 basic status",
                "tx_count": raw[3],
                "system_time": sys_time,
                "sys_state": raw[8] & 0x0F,
                "sys_state_last": (raw[8] >> 4) & 0x0F,
                "work_mode": raw[9] & 0x0F,
                "work_mode_last": (raw[9] >> 4) & 0x0F,
                "runtime_role": raw[10] & 0x0F,
                "static_role": (raw[10] >> 4) & 0x0F,
                "control_output_valid": bool(raw[11] & 0x01),
                "local_chv_permit": bool(raw[11] & 0x02),
                "channel_2": bool(raw[11] & 0x08),
                "oil_mode": (raw[11] >> 4) & 0x0F,
                "con_func": raw[12] & 0x0F,
                "con_func_last": (raw[12] >> 4) & 0x0F,
                "chv_input": raw[13],
                "air_oil_end_state": raw[14],
            }
        )
    elif frame_id == 1:
        fields.update(
            {
                "frame_name": "ID1 master arbitration",
                "local_preferred_master": raw[4],
                "peer_preferred_master": raw[5],
                "arbitrated_master": raw[6],
                "channel_type_code": raw[7],
            }
        )
    elif frame_id == 2:
        chv_input = raw[8] | (raw[9] << 8)
        condition_mask = raw[14]
        fields.update(
            {
                "frame_name": "ID2 output authorization",
                "tx_count": raw[3],
                "runtime_role": raw[4] & 0x0F,
                "static_role": (raw[4] >> 4) & 0x0F,
                "my_channel_id": raw[5] & 0x0F,
                "channel_type_code": (raw[5] >> 4) & 0x0F,
                "local_chv_permit_value": raw[6],
                "control_output_state": raw[7],
                "control_output_valid": raw[7] == 1,
                "chv_input": chv_input,
                "my_chv": bool(chv_input & 0x01),
                "other_chv": bool(chv_input & 0x02),
                "wdv_normal": bool(chv_input & 0x04),
                "cpuv_normal": bool(chv_input & 0x08),
                "latch_en": bool(chv_input & 0x10),
                "peer_alive": raw[10],
                "peer_control_seen": raw[11],
                "sys_state": raw[12] & 0x0F,
                "work_mode": (raw[12] >> 4) & 0x0F,
                "con_func": raw[13] & 0x0F,
                "maint_func": (raw[13] >> 4) & 0x0F,
                "condition_mask": condition_mask,
                "condition_role_master": bool(condition_mask & 0x01),
                "condition_local_chv_permit": bool(condition_mask & 0x02),
                "condition_my_chv": bool(condition_mask & 0x04),
                "condition_output_valid": bool(condition_mask & 0x08),
                "diagnostic_peer_alive": bool(condition_mask & 0x10),
                "diagnostic_peer_control_seen": bool(condition_mask & 0x20),
            }
        )
    elif frame_id == 3:
        control_fault_mask = raw[7]
        ifbit_signature = raw[9] | (raw[10] << 8) | (raw[11] << 16) | (raw[12] << 24)
        mbit_signature_low16 = raw[13] | (raw[14] << 8)
        fields.update(
            {
                "frame_name": "ID3 BIT fault summary",
                "tx_count": raw[3],
                "pubit_key_fault": bool(raw[4]),
                "ifbit_level": raw[5],
                "mbit_level": raw[6],
                "control_fault_mask": control_fault_mask,
                "control_comm_fault": bool(control_fault_mask & 0x01),
                "control_measure_fault": bool(control_fault_mask & 0x02),
                "control_imbalance_fault": bool(control_fault_mask & 0x04),
                "control_has_fault": bool(control_fault_mask & 0x08),
                "control_fault_reason": raw[8],
                "ifbit_signature": ifbit_signature,
                "mbit_signature_low16": mbit_signature_low16,
            }
        )
    elif frame_id == 4:
        source_word = raw[4]
        valid_mask = raw[14]
        fields.update(
            {
                "frame_name": "ID4 redundancy source",
                "tx_count": raw[3],
                "source_word": source_word,
                "riu_source": source_word & 0x03,
                "ccdl_source": (source_word >> 2) & 0x03,
                "kzzz_source": (source_word >> 4) & 0x03,
                "riu_state": raw[5],
                "kzzz_left_state": raw[6],
                "kzzz_right_state": raw[7],
                "ccdl_state": raw[8],
                "riu_heartbeat": raw[9],
                "kzzz_left_snapshot": raw[10],
                "kzzz_right_snapshot": raw[11],
                "ccdl_peer_sys_state": raw[12],
                "ccdl_peer_ch_type": raw[13] & 0x0F,
                "ccdl_peer_preferred_master": (raw[13] >> 4) & 0x0F,
                "source_valid_mask": valid_mask,
                "riu_valid": bool(valid_mask & 0x01),
                "kzzz_left_valid": bool(valid_mask & 0x02),
                "kzzz_right_valid": bool(valid_mask & 0x04),
                "ccdl_valid": bool(valid_mask & 0x08),
                "riu_source_invalid": bool(valid_mask & 0x10),
                "ccdl_source_invalid": bool(valid_mask & 0x20),
                "kzzz_source_invalid": bool(valid_mask & 0x40),
            }
        )
    elif frame_id == 5:
        status_mask = raw[14]
        total_fuel_deciliter = raw[10] | (raw[11] << 8)
        fault_info = raw[12] | (raw[13] << 8)
        fields.update(
            {
                "frame_name": "ID5 RIU simulation status",
                "tx_count": raw[3],
                "riu_sim_active": bool(raw[4]),
                "riu_sim_target": raw[5],
                "riu_sim_last_subcmd": raw[6],
                "riu_sim_timeout_100ms": raw[7],
                "riu_sim_object": raw[8] & 0x0F,
                "riu_sim_mode": (raw[8] >> 4) & 0x0F,
                "riu_sim_wheel_load": raw[9],
                "riu_sim_total_fuel_deciliter": total_fuel_deciliter,
                "riu_sim_fault_info": fault_info,
                "riu_sim_status_mask": status_mask,
                "riu_sim_condition_active": bool(status_mask & 0x01),
                "riu_sim_condition_timeout": bool(status_mask & 0x02),
                "riu_sim_condition_target_valid": bool(status_mask & 0x04),
            }
        )
    elif frame_id == 6:
        status_mask = raw[14]
        fields.update(
            {
                "frame_name": "ID6 state condition injection",
                "tx_count": raw[3],
                "state_cond_active": bool(raw[4]),
                "state_cond_last_subcmd": raw[5],
                "state_cond_timeout_100ms": raw[6],
                "state_cond_io_mask": raw[7],
                "state_cond_maint_io": raw[8] & 0x0F,
                "state_cond_power28v_io": (raw[8] >> 4) & 0x0F,
                "state_cond_bit_mask": raw[9],
                "state_cond_pubit_key_fault": bool(raw[10]),
                "state_cond_ifbit_level": raw[11],
                "state_cond_mbit_level": raw[12],
                "state_cond_status_mask": status_mask,
                "state_cond_condition_active": bool(status_mask & 0x01),
                "state_cond_condition_timeout": bool(status_mask & 0x02),
                "state_cond_condition_io": bool(status_mask & 0x04),
                "state_cond_condition_bit": bool(status_mask & 0x08),
            }
        )
    else:
        fields["frame_name"] = "unknown"

    return ParsedFrame(frame_id=frame_id, valid_checksum=valid, raw=raw, fields=fields)


def extract_dsp_frames(buffer: bytearray) -> list[ParsedFrame]:
    frames: list[ParsedFrame] = []
    while True:
        start = buffer.find(DSP_HEADER)
        if start < 0:
            if len(buffer) > 1:
                del buffer[:-1]
            break
        if start > 0:
            del buffer[:start]
        if len(buffer) < FRAME_LEN:
            break
        raw = bytes(buffer[:FRAME_LEN])
        del buffer[:FRAME_LEN]
        frames.append(parse_dsp_frame(raw))
    return frames


def make_simulated_dsp_frame(frame_id: int = 0) -> bytes:
    frame = bytearray(FRAME_LEN)
    frame[0:2] = DSP_HEADER
    frame[2] = clamp_byte(frame_id)

    if frame_id == 0:
        frame[3] = 1
        frame[4:8] = (123456).to_bytes(4, "little")
        frame[8] = 0x21
        frame[9] = 0x43
        frame[10] = 0x11
        frame[11] = 0x13
        frame[12] = 0x54
        frame[13] = 0xA5
        frame[14] = 0x02
    elif frame_id == 1:
        frame[4] = 1
        frame[5] = 2
        frame[6] = 1
        frame[7] = 0x10
    elif frame_id == 2:
        frame[3] = 3
        frame[4] = 0x11
        frame[5] = 0x21
        frame[6] = 1
        frame[7] = 1
        frame[8] = 0x0D
        frame[9] = 0x00
        frame[10] = 1
        frame[11] = 0
        frame[12] = 0x01
        frame[13] = 0x00
        frame[14] = 0x1F
    elif frame_id == 3:
        frame[3] = 4
        frame[4] = 1
        frame[5] = 1
        frame[6] = 0
        frame[7] = 0x09
        frame[8] = 2
        frame[9:13] = (0x00028080).to_bytes(4, "little")
        frame[13:15] = (0x0041).to_bytes(2, "little")
    elif frame_id == 4:
        frame[3] = 5
        frame[4] = 0x24
        frame[5] = 1
        frame[6] = 2
        frame[7] = 0
        frame[8] = 1
        frame[9] = 0x5A
        frame[10] = 0x11
        frame[11] = 0x00
        frame[12] = 1
        frame[13] = 0x21
        frame[14] = 0x0B
    elif frame_id == 5:
        frame[3] = 6
        frame[4] = 1
        frame[5] = 0
        frame[6] = RIU_SIM_FUEL_CMD
        frame[7] = 48
        frame[8] = (RIU_MODE_RECEIVE << 4) | RIU_OBJECT_FIXEDWING
        frame[9] = RIU_WHEEL_AIR
        frame[10:12] = (1234).to_bytes(2, "little")
        frame[12:14] = (0x0002).to_bytes(2, "little")
        frame[14] = 0x07
    elif frame_id == 6:
        frame[3] = 7
        frame[4] = 1
        frame[5] = STATE_COND_BIT
        frame[6] = 48
        frame[7] = 0x01
        frame[8] = 0x00
        frame[9] = 0x06
        frame[10] = 0
        frame[11] = 1
        frame[12] = 0
        frame[14] = 0x0F

    return apply_checksum(frame)
