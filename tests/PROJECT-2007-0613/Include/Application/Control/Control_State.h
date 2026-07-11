/**********************************************************************************
 *
 *             ***     **      **   **     ******
 *             ***     **     **    **   ***   ***
 *            ****     **     **   **   **      **
 *           ** **     **    **    **  **       **
 *          *** **     **   **     **  **
 *          **  **     **   **    **  **
 *         **   **     **  **     **  **
 *        ***   **     ** **      **  **
 *        ********     ** **     **   **      **
 *       **     **     ****      **   **     **
 *      **      **     ***       **   ***   **
 *      **      **     ***      **     ******
 *
 **********************************************************************************
 *
 * 文件名称:    Control_State.h
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V0.0.1.3
 *
 **********************************************************************************
 *
 * 功能说明:    Control_State.c 的私有定义头文件
 *
 *    集中存放 Control_State.c 内部使用的状态机条件注入、任务前检查、加油模式
 *    故障处理等函数式宏及内部函数原型。仅供 Control_State.c 自身引用，
 *    宏内部引用的 static 变量定义于 Control_State.c，其他文件 include 本头
 *    文件将因符号未定义而编译失败，从而保证私有性。
 *
 *********************************************************************************/

#ifndef CONTROL_STATE_H_

#define CONTROL_STATE_H_

#include "Global.h"
#include "Control_Priv.h"


/* 任务前检查上下文复位 */
#define PreTaskCheckContextReset() \
    do { \
        s_preTaskCheckCtx_t.commandIssued_u16 = INVALID; \
        s_preTaskCheckCtx_t.rcvChecked_u16 = INVALID; \
        s_preTaskCheckCtx_t.valveChecked_u16 = INVALID; \
        s_preTaskCheckCtx_t.measureChecked_u16 = INVALID; \
        s_preTaskCheckCtx_t.rcvTimeoutFault_u16 = INVALID; \
        s_preTaskCheckCtx_t.valveTimeoutFault_u16 = INVALID; \
        s_preTaskCheckCtx_t.measureFault_u16 = INVALID; \
    } while(0)

/* 加油测量故障存在性判定: 4个信号转换盒 + 5个油量传感器任一异常即视为测量故障。
 * 注: docx 0o264 故障字不含 oilMS, 见 Control_Fault.c 注释。 */
#define RefuelMeasureFaultExists(faultInfoValue) \
    (((0U != (faultInfoValue).bit.STB1_fault_u16) || \
      (0U != (faultInfoValue).bit.STB2_fault_u16) || \
      (0U != (faultInfoValue).bit.STB3_fault_u16) || \
      (0U != (faultInfoValue).bit.STB4_fault_u16) || \
      (0U != (faultInfoValue).bit.tank0_sensor_fault_u16) || \
      (0U != (faultInfoValue).bit.tank1_sensor_fault_u16) || \
      (0U != (faultInfoValue).bit.tank2_sensor_fault_u16) || \
      (0U != (faultInfoValue).bit.tank3_sensor_fault_u16) || \
      (0U != (faultInfoValue).bit.tank4_sensor_fault_u16)) ? VALID : INVALID)

/* 加油阶段三通阀状态有效性判定 */
#define RefuelStageStStateValidGet(stStateValue) \
    (((RECEIVE_ST_STATE_RECEIVE_POS == (stStateValue)) || \
      (RECEIVE_ST_STATE_CLOSED_POS == (stStateValue))) ? VALID : INVALID)

/* 加油模式退出转任务结束 */
#define RefuelModeExitToTaskEnd(conDataPtr) \
    do { \
        if(NULL != (conDataPtr)) { \
            (conDataPtr)->conFuncLast_u16 = (conDataPtr)->conFunc_u16; \
            (conDataPtr)->conFunc_u16 = CON_FUNC_4_TASK_END; \
            (conDataPtr)->workModeTime_u32 = sysTime(); \
        } \
    } while(0)

/* 加油模式低压故障应用：按目标油箱分组置位泵切断故障并退出加油 */
#define RefuelModeLowPressureFaultApply(conDataPtr, fuelPumpValue, targetTankValue) \
    do { \
        if(REFUEL_TARGET_TANK0 == (targetTankValue)) { \
            if(INVALID == (fuelPumpValue).bit.FP0_left_state_u16) { \
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Lcutoff_fault_u16 = 1U; \
            } \
            if(INVALID == (fuelPumpValue).bit.FP0_right_state_u16) { \
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Rcutoff_fault_u16 = 1U; \
            } \
        } else if(REFUEL_TARGET_TANK23 == (targetTankValue)) { \
            if(INVALID == (fuelPumpValue).bit.FP2_state_u16) { \
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump2_cutoff_fault_u16 = 1U; \
            } \
            if(INVALID == (fuelPumpValue).bit.FP3_state_u16) { \
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump3_cutoff_fault_u16 = 1U; \
            } \
        } else if(REFUEL_TARGET_LRP_ALL == (targetTankValue)) { \
            if(INVALID == (fuelPumpValue).bit.FP0_left_state_u16) { \
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Lcutoff_fault_u16 = 1U; \
            } \
            if(INVALID == (fuelPumpValue).bit.FP0_right_state_u16) { \
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Rcutoff_fault_u16 = 1U; \
            } \
            if(INVALID == (fuelPumpValue).bit.FP2_state_u16) { \
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump2_cutoff_fault_u16 = 1U; \
            } \
            if(INVALID == (fuelPumpValue).bit.FP3_state_u16) { \
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump3_cutoff_fault_u16 = 1U; \
            } \
        } \
        s_refuelCtx_t.presetReady_u16 = INVALID; \
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_FAULT; \
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_PRESET_FAIL; \
        RefuelModeExitToTaskEnd(conDataPtr); \
    } while(0)

/* 任务前检查命令构建：关闭全部受油活门并打开通气/加油阀 */
#define PreTaskCheckCommandBuild() \
    do { \
        s_RIUSendData_t.RCVcmd_t.bit.RCV0_CloseCmd_u16 = VALID; \
        s_RIUSendData_t.RCVcmd_t.bit.RCV1_CloseCmd_u16 = VALID; \
        s_RIUSendData_t.RCVcmd_t.bit.RCV2_CloseCmd_u16 = VALID; \
        s_RIUSendData_t.RCVcmd_t.bit.RCV3_CloseCmd_u16 = VALID; \
        s_RIUSendData_t.RCVcmd_t.bit.RCV4_CloseCmd_u16 = VALID; \
        s_RIUSendData_t.ValveCtrl_t.bit.ST_ctrl_u16 = RECEIVE_ST_CMD_RECEIVE_POS; \
        s_RIUSendData_t.ValveCtrl_t.bit.LT_ctrl_u16 = VALID; \
        s_RIUSendData_t.ValveCtrl_t.bit.LYJFY_ctrl_u16 = VALID; \
        s_RIUSendData_t.ValveCtrl_t.bit.RYJFY_ctrl_u16 = VALID; \
        s_preTaskCheckCtx_t.commandIssued_u16 = VALID; \
    } while(0)

/* 状态机处理默认动作：复位输出与上下文 */
#define SysStateProcessDefault() \
    do { \
        s_sysConData_t.airOilEndState_u16 = AIR_CON_END_STATE_INVALID; \
        s_sysConData_t.conModeFlag_u16 = CON_MODE_FLAG_INVALID; \
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_IDLE; \
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_NONE; \
        s_RIUSendData_t.RCVcmd_t.all = 0U; \
        s_RIUSendData_t.RIUfltInfo1_t.all = 0U; \
        s_RIUSendData_t.RIUfltInfo2_t.all = 0U; \
        s_RIUSendData_t.ValveCtrl_t.bit.ST_ctrl_u16 = RECEIVE_ST_CMD_RECEIVE_POS; \
        s_RIUSendData_t.ValveCtrl_t.bit.LT_ctrl_u16 = VALID; \
        s_RIUSendData_t.press34PlaceholderActive_u16 = 1U; \
        s_refuelCtx_t.presetReady_u16 = INVALID; \
        PreTaskCheckContextReset(); \
        ControlFaultDebounceReset(); \
        s_controlFaultTripActive_u16 = INVALID; \
        s_controlFaultClearCnt_u16 = 0U; \
        s_controlFaultRecoveryCooldownCnt_u16 = 0U; \
    } while(0)

/* 状态机处理安全态动作：回退待机并执行默认复位 */
#define SysStateProcessSafety() \
    do { \
        s_sysConData_t.workModeLast_u16 = s_sysConData_t.workMode_u16; \
        s_sysConData_t.workMode_u16 = WORK_MODE_STANDBY; \
        s_sysConData_t.conFuncLast_u16 = s_sysConData_t.conFunc_u16; \
        s_sysConData_t.conFunc_u16 = CON_FUNC_0_STANDBY; \
        SysStateProcessDefault(); \
    } while(0)

/* ******************************************************************************** */
/* Control_State.c 内部函数原型 */

static union fuelCmd_Data ControlRiuFuelCmdGet(void);
static Uint16 RoleConfirmUpdate(RoleConfirmContext_t *vp_ctx_t, Uint16 v_condition_u16, Uint32 v_holdTimeMs_u32);
static void RuntimeRoleSet(Uint16 v_role_u16);

#endif /* end of include guard: CONTROL_STATE_H_ */

/* ===================================================================================== */
/* END OF FILE */
/* ===================================================================================== */
