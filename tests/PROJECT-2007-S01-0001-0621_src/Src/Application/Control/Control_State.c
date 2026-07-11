#include "Global.h"
#include "Control_State.h"

/* ***************************************************************** */
/**
 *    【函数名】:    SysStateProcessDefault
 *    【功能描述】:   系统状态默认处理
 *    【输入参数说明】:NONE
 *    【输出参数说明】:NONE
 *    【其他说明】:   清空所有前检状态标志
 *    【返回】:       NONE
 */
/* ***************************************************************** */
void SysStateProcessDefault(void)
{
    s_sysConData_t.airOilEndState_u16     = AIR_CON_END_STATE_INVALID;
    s_sysConData_t.conModeFlag_u16        = CON_MODE_FLAG_INVALID;
    s_RIUSendData_t.currState_u16         = RECEIVE_RIU_STATE_IDLE;
    s_RIUSendData_t.checkState_u16        = RECEIVE_RIU_REASON_NONE;
    s_RIUSendData_t.RCVcmd_t.all          = 0U;
    s_RIUSendData_t.RIUfltInfo1_t.all     = 0U;
    s_RIUSendData_t.RIUfltInfo2_t.all     = 0U;
    s_RIUSendData_t.ValveCtrl_t.bit.ST_ctrl_u16 = RECEIVE_ST_CMD_RECEIVE_POS;
    s_RIUSendData_t.ValveCtrl_t.bit.LT_ctrl_u16 = VALID;
    s_RIUSendData_t.press34PlaceholderActive_u16 = 1U;
    s_refuelCtx_t.presetReady_u16         = INVALID;
    PreTaskCheckContextReset();
    ControlFaultDebounceReset();
    s_controlFaultTripActive_u16                = INVALID;
    s_controlFaultClearCnt_u16                  = 0U;
    s_controlFaultRecoveryCooldownCnt_u16       = 0U;
}

/* ***************************************************************** */
/**
 *    【函数名】:    SysStateProcessSafety
 *    【功能描述】:   系统安全态处理
 *    【输入参数说明】:NONE
 *    【输出参数说明】:NONE
 *    【其他说明】:   强制进入 standby 模式并调默认处理
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void SysStateProcessSafety(void)
{
    s_sysConData_t.workModeLast_u16 = s_sysConData_t.workMode_u16;
    s_sysConData_t.workMode_u16     = WORK_MODE_STANDBY;
    s_sysConData_t.conFuncLast_u16  = s_sysConData_t.conFunc_u16;
    s_sysConData_t.conFunc_u16      = CON_FUNC_0_STANDBY;
    SysStateProcessDefault();
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlModeDebounceReset
 *
 * 【功能描述】控制模式去抖复位
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void ControlModeDebounceReset(void)
{
    s_controlModeDebounce_t.candidateMode_u16 = WORK_MODE_STANDBY;
    s_controlModeDebounce_t.stableCnt_u16 = 0U;
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlModeReentryLatchReset
 *
 * 【功能描述】控制模式重入锁存复位
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void ControlModeReentryLatchReset(void)
{
    s_controlModeReentryLatch_u16 = INVALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlModeReentryLatchSet
 *
 * 【功能描述】控制模式重入锁存设置
 *
 * 【输入参数说明】v_workMode_u16 ---- 工作模式值
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void ControlModeReentryLatchSet(Uint16 v_workMode_u16)
{
    if ((v_workMode_u16 < WORK_MODE_NUM) && (WORK_MODE_STANDBY != v_workMode_u16))
    {
        s_controlModeReentryLatch_u16 = VALID;
        /* 锁存建立后重新开始模式防抖，避免沿用旧命令的稳定计数。 */
        ControlModeDebounceReset();
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:WorkModeRIUDataCheck
 *
 * 【功能描述】工作模式 RIU 数据检查
 *
 * 【输入参数说明】v_objectData_u16 ---- 加油对象数据
 *             v_modeData_u16 ---- 加油模式数据
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】工作模式值
 */
/* ***************************************************************** */
Uint16 WorkModeRIUDataCheck(Uint16 v_objectData_u16, Uint16 v_modeData_u16)
{
    Uint16 l_newMode_u16 = WORK_MODE_STANDBY;

    /* 先按对象(直升机/固定翼)分大类,再在类内按收油方式定位工作模式 */
    switch (v_objectData_u16)
    {
        /* 直升机对象 */
        case RIU429_OBJECT_HELICOPTER:
            switch (v_modeData_u16)
            {
                /* 左吊舱 */
                case RIU429_MODE_LP:      l_newMode_u16 = WORK_MODE_LP_HELI; break;
                /* 右吊舱 */
                case RIU429_MODE_RP:      l_newMode_u16 = WORK_MODE_RP_HELI; break;
                /* 左右吊舱 */
                case RIU429_MODE_LRP:     l_newMode_u16 = WORK_MODE_LRP_HELI; break;
                /* 纯接收 */
                case RIU429_MODE_RECEIVE: l_newMode_u16 = WORK_MODE_RECEIVE; break;
                default:                  l_newMode_u16 = WORK_MODE_STANDBY; break;
            }
            break;

        /* 固定翼对象 */
        case RIU429_OBJECT_FIXEDWING:
            switch (v_modeData_u16)
            {
                /* 左吊舱 */
                case RIU429_MODE_LP:      l_newMode_u16 = WORK_MODE_LP_FIXEDWING; break;
                /* 右吊舱 */
                case RIU429_MODE_RP:      l_newMode_u16 = WORK_MODE_RP_FIXEDWING; break;
                /* 左右吊舱 */
                case RIU429_MODE_LRP:     l_newMode_u16 = WORK_MODE_LRP_FIXEDWING; break;
                /* 纯接收 */
                case RIU429_MODE_RECEIVE: l_newMode_u16 = WORK_MODE_RECEIVE; break;
                default:                  l_newMode_u16 = WORK_MODE_STANDBY; break;
            }
            break;

        /* 未知对象,统一回待机 */
        default:
            l_newMode_u16 = WORK_MODE_STANDBY;
            break;
    }

    return l_newMode_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:WorkModeUpdate
 *
 * 【功能描述】工作模式更新
 *
 * 【输入参数说明】v_newMode_u16 ---- 新工作模式值
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void WorkModeUpdate(Uint16 v_newMode_u16)
{
    if (v_newMode_u16 >= WORK_MODE_NUM)
    {
        return;
    }

    if (v_newMode_u16 != s_sysConData_t.workMode_u16)
    {
        if (CON_FUNC_0_STANDBY == s_sysConData_t.conFunc_u16)
        {
            /* 当前仅允许从待机功能态切入新的工作模式。 */
            s_sysConData_t.workModeLast_u16 = s_sysConData_t.workMode_u16;
            s_sysConData_t.workMode_u16 = v_newMode_u16;
            s_sysConData_t.workModeTime_u32 = sysTime();

            if (WORK_MODE_STANDBY != v_newMode_u16)
            {
                s_sysConData_t.conFuncLast_u16 = s_sysConData_t.conFunc_u16;
                s_sysConData_t.conFunc_u16 = CON_FUNC_1_PRE_TASK_CHECK;
                s_sysConData_t.airOilEndState_u16 = AIR_CON_END_STATE_INVALID;
                s_sysConData_t.conModeFlag_u16 = CON_MODE_FLAG_VALID;
            }
            else
            {
                s_sysConData_t.conFuncLast_u16 = s_sysConData_t.conFunc_u16;
            }
        }
        else if (WORK_MODE_STANDBY == v_newMode_u16)
        {
            /* 仅在任务结束态允许模式回到待机，避免处理中途被模式链回收。 */
            if (CON_FUNC_4_TASK_END == s_sysConData_t.conFunc_u16)
            {
                s_sysConData_t.conFuncLast_u16 = s_sysConData_t.conFunc_u16;
                s_sysConData_t.conFunc_u16 = CON_FUNC_0_STANDBY;
                s_sysConData_t.workModeLast_u16 = s_sysConData_t.workMode_u16;
                s_sysConData_t.workMode_u16 = v_newMode_u16;
                s_sysConData_t.workModeTime_u32 = sysTime();
            }
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:WorkModeDataObtain
 *
 * 【功能描述】工作模式数据获取
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void WorkModeDataObtain(void)
{
    union fuelCmd_Data l_oilCMD_RIU_un32;
    Uint16 l_newMode_RIU_u16 = WORK_MODE_STANDBY;
    Uint16 l_newMode_u16 = WORK_MODE_STANDBY;

    if (SYS_STATE_1WORK == s_sysConData_t.sysState_u16)
    {
        l_newMode_u16 = s_sysConData_t.workMode_u16;
        /* 模式数据只认当前统一选定的RIU源，避免待机入口和控制链看到不同模式指令。 */
        l_oilCMD_RIU_un32 = ControlRiuFuelCmdGet();
        l_newMode_RIU_u16 = WorkModeRIUDataCheck(
            l_oilCMD_RIU_un32.bit.fuelObject_u8,
            l_oilCMD_RIU_un32.bit.fuelMode_u8);
        if (VALID == s_controlModeReentryLatch_u16)
        {
            if (WORK_MODE_STANDBY == l_newMode_RIU_u16)
            {
                /* 只有命令真正释放回待机后，才允许下一次重新开始计边与防抖。 */
                ControlModeReentryLatchReset();
                ControlModeDebounceReset();
            }
            l_newMode_RIU_u16 = WORK_MODE_STANDBY;
        }
        /* 模式切换先经过去抖，再统一走WorkModeUpdate收口，避免多入口同时改mode/conFunc。 */
        if (l_newMode_RIU_u16 < WORK_MODE_NUM)
        {
            if (l_newMode_RIU_u16 != s_controlModeDebounce_t.candidateMode_u16)
            {
                s_controlModeDebounce_t.candidateMode_u16 = l_newMode_RIU_u16;
                s_controlModeDebounce_t.stableCnt_u16 = 1U;
            }
            else
            {
                if (s_controlModeDebounce_t.stableCnt_u16 < 0xFFFFU)
                {
                    s_controlModeDebounce_t.stableCnt_u16 = s_controlModeDebounce_t.stableCnt_u16 + 1U;
                }

                if (s_controlModeDebounce_t.stableCnt_u16 >= CONTROL_MODE_SWITCH_CONFIRM_CYCLES)
                {
                    l_newMode_u16 = l_newMode_RIU_u16;
                }
            }
        }
        /* 模式从 RECEIVE 切到 STANDBY 时清受油上下文,避免 faultActive 等状态跨轮残留 */
        if ((WORK_MODE_RECEIVE == s_sysConData_t.workMode_u16) &&
            (WORK_MODE_STANDBY == l_newMode_u16) &&
            (s_sysConData_t.workMode_u16 != WORK_MODE_STANDBY))
        {
            ReceiveModeContextReset();
        }
        WorkModeUpdate(l_newMode_u16);
    }
    else
    {
        ControlModeReentryLatchReset();
        ControlModeDebounceReset();
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:WorkStateProcess
 *
 * 【功能描述】工作状态处理
 *
 * 【输入参数说明】v_p_ConData_t ---- 控制数据指针
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void WorkStateProcess(ConData_t *v_p_ConData_t)
{
    ControlFaultEval_t l_faultEval_t;
    memset(&l_faultEval_t, 0, sizeof(l_faultEval_t));

    if (NULL == v_p_ConData_t)
    {
        return;
    }

    if (v_p_ConData_t->workMode_u16 < WORK_MODE_NUM)
    {
        /* 当前工作模式的主处理链先执行，再统一补控制故障评估与动作。 */
        switch (v_p_ConData_t->workMode_u16)
        {
            case WORK_MODE_STANDBY:
                if (CON_FUNC_0_STANDBY == v_p_ConData_t->conFunc_u16)
                {
                    SysStateProcessDefault();
                }
                break;

            case WORK_MODE_RECEIVE:
                WorkModeProcessReceive(v_p_ConData_t);
                break;

            default:
                WorkModeProcessRefuel(v_p_ConData_t);
                break;
        }
    }

    if ((WORK_MODE_LP_FIXEDWING == v_p_ConData_t->workMode_u16) ||
        (WORK_MODE_RP_FIXEDWING == v_p_ConData_t->workMode_u16) ||
        (WORK_MODE_LRP_FIXEDWING == v_p_ConData_t->workMode_u16) ||
        (WORK_MODE_LP_HELI == v_p_ConData_t->workMode_u16) ||
        (WORK_MODE_RP_HELI == v_p_ConData_t->workMode_u16) ||
        (WORK_MODE_LRP_HELI == v_p_ConData_t->workMode_u16))
    {
        if (s_controlFaultRecoveryCooldownCnt_u16 > 0U)
        {
            s_controlFaultRecoveryCooldownCnt_u16 = s_controlFaultRecoveryCooldownCnt_u16 - 1U;
        }

        ControlFaultEvaluate(&l_faultEval_t);
        s_controlFaultEval_t = l_faultEval_t;
        ControlFaultActionApply(&l_faultEval_t, v_p_ConData_t);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:MaintGroundInConditionCheck
 *
 * 【功能描述】维护态地面进入条件检查
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】维护指令和维护IO需持续满足，避免瞬时抖动误切维护态
 * 【返回】维护进入条件状态
 */
/* ***************************************************************** */
Uint16 MaintGroundInConditionCheck(void)
{
    Uint16 l_condition_u16 = MAINT_GROUND_IN_COND_INVALID;
    const RsMaintDataInfo_t *l_p_rxMaintData_t = NULL;
    Uint16 l_maintIoStatus_u16 = MAINT_IO_INVALID;
    static Uint16 s_l_holdStarted_u16 = INVALID;
    static Uint32 s_l_holdStartTime_u32 = 0UL;

    l_maintIoStatus_u16 = IoDataGet(IO_DINDEX_MAINTANCE);
    l_p_rxMaintData_t = CommMaintDataGet();

    if ((MAINT_IO_VALID == l_maintIoStatus_u16) &&
        (NULL != l_p_rxMaintData_t) &&
        (MAINT_CODE_MAINT_STATE == l_p_rxMaintData_t->MaintStateCode_u16))
    {
        /* 维护进入条件需持续保持一定时间，避免维护拨杆抖动误切状态。 */
        if (INVALID == s_l_holdStarted_u16)
        {
            s_l_holdStarted_u16 = VALID;
            s_l_holdStartTime_u32 = sysTime();
        }

        Uint32 l_holdTime_u32 = sysTime() - s_l_holdStartTime_u32;
        if (l_holdTime_u32 >= MAINT_FORCE_ENTER_MS)
        {
            /* 持续保持时间超过强制升级阈值，绕过工作模式限制 */
            l_condition_u16 = MAINT_GROUND_IN_COND_FORCE;
        }
        else if (l_holdTime_u32 >= CONTROL_MAINT_ENTER_CONFIRM_MS)
        {
            l_condition_u16 = MAINT_GROUND_IN_COND_VALID;
        }
    }
    else
    {
        s_l_holdStarted_u16 = INVALID;
        s_l_holdStartTime_u32 = 0UL;
    }

    return l_condition_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:StandbyFuncUpdate
 *
 * 【功能描述】待机功能更新
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void StandbyFuncUpdate(void)
{
    Uint16 l_condition_u16 = 0U;
    union fuelCmd_Data l_oilCmd_un32;

    if ((SYS_STATE_1WORK == s_sysConData_t.sysState_u16) &&
        (WORK_MODE_STANDBY == s_sysConData_t.workMode_u16))
    {
        switch (s_sysConData_t.conFunc_u16)
        {
            case CON_FUNC_0_STANDBY:
                /* 空中加油入口统一由WorkModeUpdate()在模式切换完成后推进到任务前检查，
                 * 待机态这里不再直接改conFunc，避免与模式防抖入口并存造成卡死。 */
                break;

            case CON_FUNC_1_PRE_TASK_CHECK:
            case CON_FUNC_2_FUEL_PRESET:
            case CON_FUNC_3_REFUEL_PROCESS:
                /* 若加油入口条件消失，则退回待机功能，避免悬空执行链。 */
                l_condition_u16 = COND_IN_INVALID;
                l_oilCmd_un32 = ControlRiuFuelCmdGet();
                if (((RIU429_OBJECT_HELICOPTER == l_oilCmd_un32.bit.fuelObject_u8) ||
                     (RIU429_OBJECT_FIXEDWING == l_oilCmd_un32.bit.fuelObject_u8)) &&
                    ((RIU429_MODE_LP == l_oilCmd_un32.bit.fuelMode_u8) ||
                     (RIU429_MODE_RP == l_oilCmd_un32.bit.fuelMode_u8) ||
                     (RIU429_MODE_LRP == l_oilCmd_un32.bit.fuelMode_u8) ||
                     (RIU429_MODE_RECEIVE == l_oilCmd_un32.bit.fuelMode_u8)))
                {
                    l_condition_u16 = COND_IN_VALID;
                }
                if (COND_IN_INVALID == l_condition_u16)
                {
                    s_sysConData_t.conFuncLast_u16 = s_sysConData_t.conFunc_u16;
                    s_sysConData_t.conFunc_u16 = CON_FUNC_0_STANDBY;
                }
                break;

            case CON_FUNC_4_TASK_END:
                /* 维护条件消失时退回待机功能,VALID/FORCE 保持任务结束 */
                l_condition_u16 = MaintGroundInConditionCheck();
                if (MAINT_GROUND_IN_COND_INVALID == l_condition_u16)
                {
                    ControlConFuncSwitch(&s_sysConData_t, CON_FUNC_0_STANDBY, sysTime());
                }
                break;

            default:
                break;
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:GroundMaintStateUpdate
 *
 * 【功能描述】地面维护状态更新
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void GroundMaintStateUpdate(void)
{
    const RsMaintDataInfo_t *l_p_rxMaintData_t = NULL;
    Uint16 l_condition_u16 = 0U;
    Uint16 l_okCount_u16 = 0U;
    Uint16 l_maintIoStatus_u16 = MAINT_IO_INVALID;

    if (SYS_STATE_3MAINTG == s_sysConData_t.sysState_u16)
    {
        switch (s_sysConData_t.maintFunc_u16)
        {
            case MAINT_FUNC_0_INVALID:
                /* 无维护功能时，优先检查是否进入维护控制，否则再看维护显示命令。 */
                l_condition_u16 = COND_IN_INVALID;
                l_okCount_u16 = 0U;

                /* 维护控制要求“硬线维护允许”和“422维护控制命令”同时成立。
                 * 这样单独误触发一个条件时，只会停留在普通维护显示路径。 */
                l_maintIoStatus_u16 = IoDataGet(IO_DINDEX_MAINTANCE);
                if (MAINT_IO_VALID == l_maintIoStatus_u16)
                {
                    l_okCount_u16++;
                }
                l_p_rxMaintData_t = CommMaintDataGet();
                if ((NULL != l_p_rxMaintData_t) && (MAINT_CODE_GROUND_CON == l_p_rxMaintData_t->MaintCMDCode_u16))
                {
                    l_okCount_u16++;
                }
                if (l_okCount_u16 >= 2U)
                {
                    l_condition_u16 = COND_IN_VALID;
                }
                if (COND_IN_VALID == l_condition_u16)
                {
                    s_sysConData_t.maintFunc_u16 = MAINT_FUNC_2_CON;
                }
                else
                {
                    /* 没有进入维护控制时，仍允许地面设备进入维护显示功能。 */
                    l_p_rxMaintData_t = CommMaintDataGet();
                    if ((NULL != l_p_rxMaintData_t) &&
                        (MAINT_CODE_MAINT_FUNC == l_p_rxMaintData_t->MaintCMDCode_u16))
                    {
                        s_sysConData_t.maintFunc_u16 = MAINT_FUNC_1_MAINT;
                    }
                }
                break;

            case MAINT_FUNC_1_MAINT:
            case MAINT_FUNC_2_CON:
                /* 地面端撤销维护命令后，维护子功能回到空闲，等待下一次命令选择。 */
                l_p_rxMaintData_t = CommMaintDataGet();
                if ((NULL != l_p_rxMaintData_t) &&
                    (MAINT_CODE_CMD_INVALID == l_p_rxMaintData_t->MaintCMDCode_u16))
                {
                    s_sysConData_t.maintFunc_u16 = MAINT_FUNC_0_INVALID;
                }
                break;

            default:
                break;
        }
    }
    else
    {
        s_sysConData_t.maintFunc_u16 = MAINT_FUNC_0_INVALID;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:PowerDownConditionCheck
 *
 * 【功能描述】掉电条件检查
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
Uint16 PowerDownConditionCheck(void)
{
    Uint16 l_condition_u16 = POWERDOWN_COND_INVALID;
    Uint16 l_powerDownFlag_u16 = PowerDownFlagGet();
    static Uint16 s_l_clrCount_u16 = 0U;
    Uint16 l_lowPowerState_u16 = 0U;
    Uint16 l_lowPowerCnt_u16 = 0U;
    Uint16 l_index_u16 = 0U;

    if (SYS_STATE_4POWERDOWN != s_sysConData_t.sysState_u16)
    {
        if (POWERDOWN_FLAG_VALID == l_powerDownFlag_u16)
        {
            l_condition_u16 = POWERDOWN_COND_ENTER;
        }
        else if (POWERDOWN_FLAG_PENDING == l_powerDownFlag_u16)
        {
            /* 掉电中断只先置 pending。这里再连续读电源状态，过滤掉瞬时毛刺。 */
            for(l_index_u16 = 0U; l_index_u16 < 10U; l_index_u16++)
            {
                l_lowPowerState_u16 = IoDataGet(IO_DINDEX_POWER_28V);
                if (CPLD_DATA_POWER_BIT_ERR == l_lowPowerState_u16)
                {
                    l_lowPowerCnt_u16++;
                }

                delayUs(33UL);
            }

            if(l_lowPowerCnt_u16 >= 8U)
            {
                /* 确认掉电后先落一笔关键数据，再让状态机进入掉电态。 */
                PowerDownFlagSetValid();
                FlashSingleStoreDataUpdate();
                l_condition_u16 = POWERDOWN_COND_ENTER;
            }
            else
            {
                PowerDownFlagClear();
            }
        }
    }
    else
    {
        /* 掉电态退出必须看到电源持续恢复一段时间，避免电源边沿抖动导致状态反复切换。 */
        l_lowPowerState_u16 = IoDataGet(IO_DINDEX_POWER_28V);
        if (CPLD_DATA_POWER_BIT_ERR == l_lowPowerState_u16)
        {
            s_l_clrCount_u16 = 0U;
        }
        else
        {
            s_l_clrCount_u16++;
            if (s_l_clrCount_u16 >= POWERDOWN_FLAG_CLR_COUNT_MAX)
            {
                PowerDownFlagClear();
                s_l_clrCount_u16 = 0U;
                l_condition_u16 = POWERDOWN_COND_OUT;
            }
        }
    }

    return l_condition_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:SysStateJudge
 * 【功能描述】系统状态机判定
 *            综合掉电条件、维护条件、工作模式判定本次目标状态
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】    是SysStateProcess的输入判定阶段
 * 【返回】        NONE
 */
/* ***************************************************************** */
void SysStateJudge(void)
{
    Uint16 l_targetState_u16 = s_sysConData_t.sysState_u16;
    Uint16 l_pdCondition_u16 = POWERDOWN_COND_INVALID;
    Uint16 l_maintCond_u16 = MaintGroundInConditionCheck();

    /* 这里只做“下一状态”的判定，不在分支内部顺手改上下文。
     * 顺序上始终先看掉电，再看维护入口，最后才按 BIT、超时和当前模式决定常规去向，
     * 这样能保证高优先级退出条件不会被后面的业务状态覆盖。 */
    switch (s_sysConData_t.sysState_u16)
    {
        case SYS_STATE_0INIT:
            /* 0INIT 优先响应掉电，其次是维护进入，最后等 PuBIT 确认或超时强制进安全态 */
            l_pdCondition_u16 = PowerDownConditionCheck();
            if (POWERDOWN_COND_ENTER == l_pdCondition_u16)
            {
                l_targetState_u16 = SYS_STATE_4POWERDOWN;
            }
            else if ((MAINT_GROUND_IN_COND_VALID == l_maintCond_u16) ||
                     (MAINT_GROUND_IN_COND_FORCE == l_maintCond_u16))
            {
                l_targetState_u16 = SYS_STATE_3MAINTG;
            }
            else if (VALID == ControlCriticalFaultExist())
            {
                l_targetState_u16 = SYS_STATE_2SAFETY;
            }
            else if ((sysTime() - s_initStateStartTime_u32) >= INIT_STATE_TIMEOUT_MS)
            {
                /* PuBIT 长时间不收敛(硬件故障),强制进入安全态 */
                l_targetState_u16 = SYS_STATE_2SAFETY;
            }
            else
            {
                l_targetState_u16 = SYS_STATE_1WORK;
            }
            break;

        case SYS_STATE_2SAFETY:
            /* 安全态只允许掉电或维护进入两条退出路径，其余保持安全态。 */
            l_pdCondition_u16 = PowerDownConditionCheck();
            if (POWERDOWN_COND_ENTER == l_pdCondition_u16)
            {
                l_targetState_u16 = SYS_STATE_4POWERDOWN;
            }
            else if ((MAINT_GROUND_IN_COND_VALID == l_maintCond_u16) ||
                     (MAINT_GROUND_IN_COND_FORCE == l_maintCond_u16))
            {
                l_targetState_u16 = SYS_STATE_3MAINTG;
            }
            break;

        case SYS_STATE_1WORK:
            /* 工作态优先响应掉电，其次是关键故障进入安全态，最后才允许待机下进入地面维护。 */
            l_pdCondition_u16 = PowerDownConditionCheck();
            if (POWERDOWN_COND_ENTER == l_pdCondition_u16)
            {
                l_targetState_u16 = SYS_STATE_4POWERDOWN;
            }
            else if (VALID == ControlCriticalFaultExist())
            {
                l_targetState_u16 = SYS_STATE_2SAFETY;
            }
            else
            {
                /* 维护条件 VALID 需要 STANDBY 模式配合;FORCE 可绕过工作模式限制,
                 * 用于加油中长时间保持维护意图时强制进入维护态 */
                if (((MAINT_GROUND_IN_COND_VALID == l_maintCond_u16) &&
                     (WORK_MODE_STANDBY == s_sysConData_t.workMode_u16)) ||
                    (MAINT_GROUND_IN_COND_FORCE == l_maintCond_u16))
                {
                    l_targetState_u16 = SYS_STATE_3MAINTG;
                }
            }
            break;

        case SYS_STATE_3MAINTG:
            /* 地面维护态同样优先响应掉电，维护条件消失后再按关键故障结果回工作/安全。 */
            l_pdCondition_u16 = PowerDownConditionCheck();
            if (POWERDOWN_COND_ENTER == l_pdCondition_u16)
            {
                l_targetState_u16 = SYS_STATE_4POWERDOWN;
            }
            else if (MAINT_GROUND_IN_COND_INVALID == l_maintCond_u16)
            {
                l_targetState_u16 = SYS_STATE_1WORK;
                if (VALID == ControlCriticalFaultExist())
                {
                    l_targetState_u16 = SYS_STATE_2SAFETY;
                }
            }
            break;

        case SYS_STATE_4POWERDOWN:
            /* 掉电态只在电源恢复确认后退出，并按掉电前最后状态回安全态或工作态;
             * 掉电前是 0INIT 时回到 0INIT 重新走 PuBIT,避免绕过 BIT,
             * 同时重置 0INIT 起始时间戳以重新计 10 秒超时窗口 */
            if (POWERDOWN_COND_OUT == PowerDownConditionCheck())
            {
                if (SYS_STATE_0INIT == s_sysConData_t.sysStateLast_u16)
                {
                    l_targetState_u16 = SYS_STATE_0INIT;
                }
                else
                {
                    if (SYS_STATE_2SAFETY == s_sysConData_t.sysStateLast_u16)
                    {
                        l_targetState_u16 = SYS_STATE_2SAFETY;
                    }
                    else
                    {
                        l_targetState_u16 = SYS_STATE_1WORK;
                    }
                }
            }
            break;

        default:
            break;
    }

    /* 真正提交状态变化时，再补做与目标状态绑定的上下文修正。
     * 把“判目标”和“落状态”分开，能避免同一拍里一边切状态一边用新状态继续参与判断。 */
    if (s_sysConData_t.sysState_u16 != l_targetState_u16)
    {
        if (SYS_STATE_1WORK == l_targetState_u16)
        {
            /* 任意状态回到工作态时，统一从待机工作模式重新进入。 */
            s_sysConData_t.workModeLast_u16 = s_sysConData_t.workMode_u16;
            s_sysConData_t.workMode_u16 = WORK_MODE_STANDBY;
        }
        else if (SYS_STATE_0INIT == l_targetState_u16)
        {
            /* 进入 0INIT 时重置超时起点,确保有完整的 10 秒窗口走 PuBIT */
            s_initStateStartTime_u32 = sysTime();
        }

        s_sysConData_t.sysStateLast_u16 = s_sysConData_t.sysState_u16;
        s_sysConData_t.sysState_u16 = l_targetState_u16;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:SysStateProcess
 * 【功能描述】系统状态机处理
 *            按当前目标状态执行对应分支：
 *            状态0：上电初始化；状态1：等待；状态2：热启动等待；状态3：维护
 *            状态4：掉电；状态5：BIT；状态6：待修
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】    由SysControl主流程按拍调用
 * 【返回】        NONE
 */
/* ***************************************************************** */
void SysStateProcess(void)
{
    const RsMaintDataInfo_t *l_p_maintData_t = NULL;
    Uint16 l_exeResult_u16 = MAINT_FUNC_EXE_RESULT_NONE;

    if (s_sysConData_t.sysState_u16 <= SYS_STATE_4POWERDOWN)
    {
        switch (s_sysConData_t.sysState_u16)
        {
            case SYS_STATE_0INIT:
                /* 初始化态当前不执行额外业务动作，仅等待状态机切到后续稳定态。 */
                break;

            case SYS_STATE_1WORK:
                WorkStateProcess(&s_sysConData_t);
                break;

            case SYS_STATE_2SAFETY:
                SysStateProcessSafety();
                break;

            case SYS_STATE_3MAINTG:
                switch (s_sysConData_t.maintFunc_u16)
                {
                    case MAINT_FUNC_0_INVALID:
                        SysStateProcessDefault();
                        break;

                    case MAINT_FUNC_1_MAINT:
                        l_p_maintData_t = CommMaintDataGet();
                        if ((NULL != l_p_maintData_t) && (MAINT_CMD_EXE_NEW == s_maintCMDExeState_u16))
                        {
                            /* 维护功能命令只在收到“新命令”状态时执行一次。 */
                            switch (l_p_maintData_t->MaintFuncCode_u16)
                            {
                                case GROUND_MAINT_FUNC_SOFT_CRC:
                                    l_exeResult_u16 = GroundMaintProcessSoftwCRC();
                                    break;
                                case GROUND_MAINT_FUNC_DATA_DOWNLOAD:
                                    l_exeResult_u16 = GroundMaintProcessDataDownLoad();
                                    break;
                                case GROUND_MAINT_FUNC_DATA_ERASE:
                                    l_exeResult_u16 = GroundMaintProcessDataErase();
                                    break;
                                case GROUND_MAINT_FUNC_HW_VERSION_ADJUST:
                                    l_exeResult_u16 = GroundMaintProcessHardVersionAdjust();
                                    break;
                                case GROUND_MAINT_FUNC_BIT_CLEAR:
                                    l_exeResult_u16 = GroundMaintProcessBitClear();
                                    break;
                                default:
                                    l_exeResult_u16 = MAINT_FUNC_EXE_RESULT_INVALID_PARA;
                                    break;
                            }

                            CommMaintExecStatusUpdate(l_p_maintData_t->MaintFuncCode_u16, l_exeResult_u16);
                            s_maintCMDExeCnt_u16++;
                            s_maintCMDExeState_u16 = MAINT_CMD_EXE_DONE;
                        }

                        /* 维护态也要继续执行默认状态处理，保证输出和基础状态刷新不断拍。 */
                        SysStateProcessDefault();
                        break;

                    default:
                        break;
                }
                break;

            case SYS_STATE_4POWERDOWN:
                SysStateProcessSafety();
                break;

            default:
                break;
        }
    }
}
