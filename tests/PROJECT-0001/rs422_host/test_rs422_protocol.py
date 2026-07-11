import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rs422_protocol as proto


class Rs422ProtocolTest(unittest.TestCase):
    def test_checksum_validates_host_frame(self) -> None:
        frame = proto.make_host_frame(proto.CMD_COMM_INFO, frame_count=0x12)
        self.assertEqual(len(frame), proto.FRAME_LEN)
        self.assertEqual(frame[:2], proto.HOST_HEADER)
        self.assertTrue(proto.validate_frame(frame, proto.HOST_HEADER))

    def test_comm_info_payload_layout(self) -> None:
        frame = proto.make_host_frame(
            proto.CMD_COMM_INFO,
            frame_count=1,
            payload={
                "a429_info": 3,
                "flowb_info": 1,
                "a429_label": 0xAB,
                "read_addr": 0x123456,
                "redundancy_info": 7,
                "software_info": 8,
                "analog_info": 9,
                "pump_info": 10,
            },
        )
        self.assertEqual(frame[3], proto.CMD_COMM_INFO)
        self.assertEqual(frame[4], 0x13)
        self.assertEqual(frame[5], 0xAB)
        self.assertEqual(frame[6:9], bytes((0x56, 0x34, 0x12)))
        self.assertEqual(frame[9:13], bytes((7, 8, 9, 10)))

    def test_download_payload_layout(self) -> None:
        frame = proto.make_host_frame(
            proto.CMD_MAINT_FUNC,
            frame_count=2,
            payload={
                "function": proto.GROUND_MAINT_FUNC_DATA_DOWNLOAD,
                "download_start": 0x11223344,
                "download_length": 0x55667788,
            },
        )
        self.assertEqual(frame[3], proto.CMD_MAINT_FUNC)
        self.assertEqual(frame[4], proto.GROUND_MAINT_FUNC_DATA_DOWNLOAD)
        self.assertEqual(frame[5:9], bytes((0x44, 0x33, 0x22, 0x11)))
        self.assertEqual(frame[9:13], bytes((0x88, 0x77, 0x66, 0x55)))

    def test_riu_sim_frame_layout(self) -> None:
        frame = proto.make_riu_sim_frame(
            proto.RIU_SIM_FUEL_CMD,
            payload=(proto.RIU_OBJECT_FIXEDWING, proto.RIU_MODE_RECEIVE, proto.RIU_WHEEL_AIR, 0, 0x34, 0x12),
            frame_count=3,
        )
        self.assertEqual(frame[:2], proto.HOST_HEADER)
        self.assertEqual(frame[2], 3)
        self.assertEqual(frame[3], proto.CMD_RIU_SIM_INJECT)
        self.assertEqual(frame[4], proto.RIU_SIM_FUEL_CMD)
        self.assertEqual(frame[5:11], bytes((1, 4, 2, 0, 0x34, 0x12)))
        self.assertEqual(frame[13], proto.MAINT_STATE_GROUND)
        self.assertTrue(proto.validate_frame(frame, proto.HOST_HEADER))

    def test_state_cond_frame_layout(self) -> None:
        frame = proto.make_state_cond_frame(
            proto.STATE_COND_BIT,
            payload=(0x06, 0, 1, 0),
            frame_count=4,
        )
        self.assertEqual(frame[:2], proto.HOST_HEADER)
        self.assertEqual(frame[2], 4)
        self.assertEqual(frame[3], proto.CMD_STATE_COND_INJECT)
        self.assertEqual(frame[4], proto.STATE_COND_BIT)
        self.assertEqual(frame[5:9], bytes((0x06, 0, 1, 0)))
        self.assertEqual(frame[13], proto.MAINT_STATE_GROUND)
        self.assertTrue(proto.validate_frame(frame, proto.HOST_HEADER))

    def test_parse_id0(self) -> None:
        frame = proto.make_simulated_dsp_frame(0)
        parsed = proto.parse_dsp_frame(frame)
        self.assertTrue(parsed.valid_checksum)
        self.assertEqual(parsed.frame_id, 0)
        self.assertEqual(parsed.fields["frame_name"], "ID0 basic status")
        self.assertEqual(parsed.fields["system_time"], 123456)

    def test_parse_id2_output_authorization(self) -> None:
        frame = proto.make_simulated_dsp_frame(2)
        parsed = proto.parse_dsp_frame(frame)
        self.assertTrue(parsed.valid_checksum)
        self.assertEqual(parsed.frame_id, 2)
        self.assertEqual(parsed.fields["frame_name"], "ID2 output authorization")
        self.assertEqual(parsed.fields["runtime_role"], 1)
        self.assertEqual(parsed.fields["static_role"], 1)
        self.assertEqual(parsed.fields["my_channel_id"], 1)
        self.assertTrue(parsed.fields["condition_role_master"])
        self.assertTrue(parsed.fields["condition_local_chv_permit"])
        self.assertTrue(parsed.fields["condition_my_chv"])
        self.assertTrue(parsed.fields["condition_output_valid"])

    def test_parse_id3_bit_fault_summary(self) -> None:
        frame = proto.make_simulated_dsp_frame(3)
        parsed = proto.parse_dsp_frame(frame)
        self.assertTrue(parsed.valid_checksum)
        self.assertEqual(parsed.frame_id, 3)
        self.assertEqual(parsed.fields["frame_name"], "ID3 BIT fault summary")
        self.assertTrue(parsed.fields["pubit_key_fault"])
        self.assertEqual(parsed.fields["ifbit_level"], 1)
        self.assertEqual(parsed.fields["mbit_level"], 0)
        self.assertTrue(parsed.fields["control_comm_fault"])
        self.assertFalse(parsed.fields["control_measure_fault"])
        self.assertFalse(parsed.fields["control_imbalance_fault"])
        self.assertTrue(parsed.fields["control_has_fault"])
        self.assertEqual(parsed.fields["control_fault_reason"], 2)
        self.assertEqual(parsed.fields["ifbit_signature"], 0x00028080)
        self.assertEqual(parsed.fields["mbit_signature_low16"], 0x0041)

    def test_parse_id4_redundancy_source(self) -> None:
        frame = proto.make_simulated_dsp_frame(4)
        parsed = proto.parse_dsp_frame(frame)
        self.assertTrue(parsed.valid_checksum)
        self.assertEqual(parsed.frame_id, 4)
        self.assertEqual(parsed.fields["frame_name"], "ID4 redundancy source")
        self.assertEqual(parsed.fields["riu_source"], 0)
        self.assertEqual(parsed.fields["ccdl_source"], 1)
        self.assertEqual(parsed.fields["kzzz_source"], 2)
        self.assertEqual(parsed.fields["riu_state"], 1)
        self.assertEqual(parsed.fields["kzzz_left_state"], 2)
        self.assertEqual(parsed.fields["kzzz_right_state"], 0)
        self.assertEqual(parsed.fields["ccdl_state"], 1)
        self.assertTrue(parsed.fields["riu_valid"])
        self.assertTrue(parsed.fields["kzzz_left_valid"])
        self.assertFalse(parsed.fields["kzzz_right_valid"])
        self.assertTrue(parsed.fields["ccdl_valid"])
        self.assertFalse(parsed.fields["riu_source_invalid"])
        self.assertFalse(parsed.fields["ccdl_source_invalid"])
        self.assertFalse(parsed.fields["kzzz_source_invalid"])

    def test_parse_id5_riu_sim_status(self) -> None:
        frame = proto.make_simulated_dsp_frame(5)
        parsed = proto.parse_dsp_frame(frame)
        self.assertTrue(parsed.valid_checksum)
        self.assertEqual(parsed.frame_id, 5)
        self.assertEqual(parsed.fields["frame_name"], "ID5 RIU simulation status")
        self.assertTrue(parsed.fields["riu_sim_active"])
        self.assertEqual(parsed.fields["riu_sim_last_subcmd"], proto.RIU_SIM_FUEL_CMD)
        self.assertEqual(parsed.fields["riu_sim_mode"], proto.RIU_MODE_RECEIVE)
        self.assertEqual(parsed.fields["riu_sim_wheel_load"], proto.RIU_WHEEL_AIR)
        self.assertEqual(parsed.fields["riu_sim_total_fuel_deciliter"], 1234)
        self.assertEqual(parsed.fields["riu_sim_fault_info"], 0x0002)

    def test_parse_id6_state_condition(self) -> None:
        frame = proto.make_simulated_dsp_frame(6)
        parsed = proto.parse_dsp_frame(frame)
        self.assertTrue(parsed.valid_checksum)
        self.assertEqual(parsed.frame_id, 6)
        self.assertEqual(parsed.fields["frame_name"], "ID6 state condition injection")
        self.assertTrue(parsed.fields["state_cond_active"])
        self.assertEqual(parsed.fields["state_cond_last_subcmd"], proto.STATE_COND_BIT)
        self.assertEqual(parsed.fields["state_cond_io_mask"], 1)
        self.assertEqual(parsed.fields["state_cond_bit_mask"], 6)
        self.assertEqual(parsed.fields["state_cond_ifbit_level"], 1)
        self.assertEqual(parsed.fields["state_cond_mbit_level"], 0)

    def test_extract_frames_keeps_partial_tail(self) -> None:
        first = proto.make_simulated_dsp_frame(0)
        second = proto.make_simulated_dsp_frame(1)
        buffer = bytearray(b"\x00" + first + second[:5])
        frames = proto.extract_dsp_frames(buffer)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].frame_id, 0)
        self.assertEqual(buffer, bytearray(second[:5]))


if __name__ == "__main__":
    unittest.main()
