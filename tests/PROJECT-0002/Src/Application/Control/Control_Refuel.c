#include "Global.h"
#include "Control_State.h"

extern union fuelCmd_Data ControlRiuFuelCmdGet(void);

/* ***************************************************************** */
/**
 *    【函数名】:    RefuelStageStStateValidGet
 *    【功能描述】:   判断加油阶段三通阀反馈是否处于有效位置
 *    【输入参数说明】:stStateValue ---- 三通阀反馈状态值
 *    【输出参数说明】:NONE
 *    【其他说明】:   当前只接受“加油位/关闭位”两类稳定反馈
 *    【返回】:       VALID / INVALID
 */
/* ***************************************************************** */
static Uint16 RefuelStageStStateValidGet(Uint16 stStateValue)
{
    Uint16 l_valid_u16 = INVALID;

    if ((RECEIVE_ST_STATE_RECEIVE_POS == stStateValue) ||
        (RECEIVE_ST_STATE_CLOSED_POS == stStateValue))
    {
        l_valid_u16 = VALID;
    }

    return l_valid_u16;
}

/* ***************************************************************** */
/**
 *    【函数名】:    RefuelModeExitToTaskEnd
 *    【功能描述】:   受油模式退出到任务结束态
 *    【输入参数说明】:conDataPtr ---- 控制数据指针
 *    【输出参数说明】:NONE
 *    【其他说明】:   复用阶段切换公共收口函数
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void RefuelModeExitToTaskEnd(ConData_t *conDataPtr)
{
    ControlConFuncSwitch(conDataPtr, CON_FUNC_4_TASK_END, sysTime());
}

/* ***************************************************************** */
/**
 *    【函数名】:    RefuelModeLowPressureFaultApply
 *    【功能描述】:   受油低压故障置位
 *    【输入参数说明】:conDataPtr ---- 控制数据指针
 *                    fuelPumpValue ---- 加油泵状态
 *                    targetTankValue ---- 目标油箱
 *    【输出参数说明】:NONE
 *    【其他说明】:   根据目标油箱不同置对应泵的切断阀故障
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void RefuelModeLowPressureFaultApply(ConData_t *conDataPtr, union fuelPump_Data fuelPumpValue, Uint16 targetTankValue)
{
    /* 低压故障按当前目标供油路径上报，只点亮参与本轮任务的泵路故障位。
     * 这样 RIU 侧看到的是“本轮禁止自动加油的直接原因”，而不是全泵路泛化故障。 */
    if (REFUEL_TARGET_TANK0 == targetTankValue)
    {
        if (INVALID == fuelPumpValue.bit.FP0_left_state_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Lcutoff_fault_u16 = 1U;
        }
        if (INVALID == fuelPumpValue.bit.FP0_right_state_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Rcutoff_fault_u16 = 1U;
        }
    }
    else if (REFUEL_TARGET_TANK23 == targetTankValue)
    {
        if (INVALID == fuelPumpValue.bit.FP2_state_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump2_cutoff_fault_u16 = 1U;
        }
        if (INVALID == fuelPumpValue.bit.FP3_state_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump3_cutoff_fault_u16 = 1U;
        }
    }
    else if (REFUEL_TARGET_LRP_ALL == targetTankValue)
    {
        if (INVALID == fuelPumpValue.bit.FP0_left_state_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Lcutoff_fault_u16 = 1U;
        }
        if (INVALID == fuelPumpValue.bit.FP0_right_state_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Rcutoff_fault_u16 = 1U;
        }
        if (INVALID == fuelPumpValue.bit.FP2_state_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump2_cutoff_fault_u16 = 1U;
        }
        if (INVALID == fuelPumpValue.bit.FP3_state_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump3_cutoff_fault_u16 = 1U;
        }
    }

    /* 一旦预位/执行中确认目标路径低压，本轮加油不再尝试自动换路重试。
     * 状态统一收口到故障+任务结束，交由上层重新下发任务或人工处理。 */
    s_refuelCtx_t.presetReady_u16 = INVALID;
    s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_FAULT;
    s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_PRESET_FAIL;
    RefuelModeExitToTaskEnd(conDataPtr);
}

/* ***************************************************************** */
/**
 *    【函数名】:    PreTaskCheckContextReset
 *    【功能描述】:   前检上下文复位
 *    【输入参数说明】:NONE
 *    【输出参数说明】:NONE
 *    【其他说明】:   检查使能标志和超时
 *    【返回】:       VALID / INVALID
 */
/* ***************************************************************** */
void PreTaskCheckContextReset(void)
{
    s_preTaskCheckCtx_t.commandIssued_u16      = INVALID;
    s_preTaskCheckCtx_t.rcvChecked_u16        = INVALID;
    s_preTaskCheckCtx_t.valveChecked_u16      = INVALID;
    s_preTaskCheckCtx_t.measureChecked_u16    = INVALID;
    s_preTaskCheckCtx_t.rcvTimeoutFault_u16   = INVALID;
    s_preTaskCheckCtx_t.valveTimeoutFault_u16 = INVALID;
    s_preTaskCheckCtx_t.measureFault_u16      = INVALID;
}

/* ***************************************************************** */
/**
 *    【函数名】:    PreTaskCheckCommandBuild
 *    【功能描述】:   前检命令构建
 *    【输入参数说明】:NONE
 *    【输出参数说明】:NONE
 *    【其他说明】:   构建受油执行前的阀位关闭指令
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void PreTaskCheckCommandBuild(void)
{
    s_RIUSendData_t.RCVcmd_t.bit.RCV0_CloseCmd_u16 = VALID;
    s_RIUSendData_t.RCVcmd_t.bit.RCV1_CloseCmd_u16 = VALID;
    s_RIUSendData_t.RCVcmd_t.bit.RCV2_CloseCmd_u16 = VALID;
    s_RIUSendData_t.RCVcmd_t.bit.RCV3_CloseCmd_u16 = VALID;
    s_RIUSendData_t.RCVcmd_t.bit.RCV4_CloseCmd_u16 = VALID;
    s_RIUSendData_t.ValveCtrl_t.bit.ST_ctrl_u16    = RECEIVE_ST_CMD_RECEIVE_POS;
    s_RIUSendData_t.ValveCtrl_t.bit.LT_ctrl_u16    = VALID;
    s_RIUSendData_t.ValveCtrl_t.bit.LYJFY_ctrl_u16 = VALID;
    s_RIUSendData_t.ValveCtrl_t.bit.RYJFY_ctrl_u16 = VALID;
    s_preTaskCheckCtx_t.commandIssued_u16          = VALID;
}

/* ***************************************************************** */
/**
 *    【函数名】:    PreTaskCheckFaultStatusUpdate
 *    【功能描述】:   前检故障状态刷新
 *    【输入参数说明】:NONE
 *    【输出参数说明】:NONE
 *    【其他说明】:   前检阶段按当前未满足项实时刷新RIU故障位，条件恢复后自动清除
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void PreTaskCheckFaultStatusUpdate(void)
{
    union RCV_Data l_rcvData_un16;
    union valve1_Data l_valve1Data_un16;
    union valve2_Data l_valve2Data_un32;

    /* 入口先把本轮前检故障状态清零，后面只按当前拍真实反馈重新置位。 */
    s_preTaskCheckCtx_t.rcvTimeoutFault_u16 = INVALID;
    s_preTaskCheckCtx_t.valveTimeoutFault_u16 = INVALID;
    s_preTaskCheckCtx_t.measureFault_u16 = INVALID;

    /* 只清理前检会维护的故障位，避免误擦除后续阶段写入的泵路/接头阀故障。 */
    s_RIUSendData_t.RIUfltInfo1_t.bit.LYJFY_fault_u16 = 0U;
    s_RIUSendData_t.RIUfltInfo1_t.bit.RYJFY_fault_u16 = 0U;
    s_RIUSendData_t.RIUfltInfo1_t.bit.LT_fault_u16 = 0U;
    s_RIUSendData_t.RIUfltInfo1_t.bit.ST_fault_u16 = 0U;
    s_RIUSendData_t.RIUfltInfo1_t.bit.LDDTQ_fault_u16 = 0U;
    s_RIUSendData_t.RIUfltInfo1_t.bit.RDDTQ_fault_u16 = 0U;
    /* 清空上送给RIU的故障字2(RCV/油量计量) */
    s_RIUSendData_t.RIUfltInfo2_t.bit.RCV0_fault_u16 = 0U;
    s_RIUSendData_t.RIUfltInfo2_t.bit.RCV1_fault_u16 = 0U;
    s_RIUSendData_t.RIUfltInfo2_t.bit.RCV2_fault_u16 = 0U;
    s_RIUSendData_t.RIUfltInfo2_t.bit.RCV3_fault_u16 = 0U;
    s_RIUSendData_t.RIUfltInfo2_t.bit.RCV4_fault_u16 = 0U;
    s_RIUSendData_t.RIUfltInfo2_t.bit.oilMS_falut_u16 = 0U;

    /* 前检窗口内就把当前不满足项翻译成 RIU 可见故障，方便429侧观察退出原因。
     * 这些故障不是锁存故障，反馈恢复后下一拍会被上面的清零逻辑自动撤销。 */
    /* 读取冗余RCV状态字 */
    l_rcvData_un16.all = (Uint16)(RedunDataGet(REDUN_INDEX_RIU_RCV).dataU_u32 & 0xFFFFU);
    /* RCV0~4 任一未在关闭位，置对应故障位并标记RCV前检异常。 */
    if (INVALID == l_rcvData_un16.bit.RCV0_Close_u16)
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.RCV0_fault_u16 = 1U;
        s_preTaskCheckCtx_t.rcvTimeoutFault_u16 = VALID;
    }
    if (INVALID == l_rcvData_un16.bit.RCV1_Close_u16)
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.RCV1_fault_u16 = 1U;
        s_preTaskCheckCtx_t.rcvTimeoutFault_u16 = VALID;
    }
    if (INVALID == l_rcvData_un16.bit.RCV2_Close_u16)
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.RCV2_fault_u16 = 1U;
        s_preTaskCheckCtx_t.rcvTimeoutFault_u16 = VALID;
    }
    if (INVALID == l_rcvData_un16.bit.RCV3_Close_u16)
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.RCV3_fault_u16 = 1U;
        s_preTaskCheckCtx_t.rcvTimeoutFault_u16 = VALID;
    }
    if (INVALID == l_rcvData_un16.bit.RCV4_Close_u16)
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.RCV4_fault_u16 = 1U;
        s_preTaskCheckCtx_t.rcvTimeoutFault_u16 = VALID;
    }

    /* 读取冗余阀1/阀2状态 */
    l_valve1Data_un16.all = (Uint16)(RedunDataGet(REDUN_INDEX_RIU_VALVE1).dataU_u32 & 0xFFFFU);
    l_valve2Data_un32.all = RedunDataGet(REDUN_INDEX_RIU_VALVE2).dataU_u32 & 0x3FFFFUL;
    /* 阀1状态:LT/ST/LDDTQ/RDDTQ 异常置位 */
    if (RECEIVE_VALVE_STATE_CLOSED != l_valve1Data_un16.bit.LT_state_u16)
    {
        s_RIUSendData_t.RIUfltInfo1_t.bit.LT_fault_u16 = 1U;
        s_preTaskCheckCtx_t.valveTimeoutFault_u16 = VALID;
    }
    if (VALID != RefuelStageStStateValidGet(l_valve1Data_un16.bit.ST_state_u16))
    {
        s_RIUSendData_t.RIUfltInfo1_t.bit.ST_fault_u16 = 1U;
        s_preTaskCheckCtx_t.valveTimeoutFault_u16 = VALID;
    }
    if (RECEIVE_VALVE_STATE_OPEN != l_valve1Data_un16.bit.LDDTQ_state_u16)
    {
        s_RIUSendData_t.RIUfltInfo1_t.bit.LDDTQ_fault_u16 = 1U;
        s_preTaskCheckCtx_t.valveTimeoutFault_u16 = VALID;
    }
    if (RECEIVE_VALVE_STATE_OPEN != l_valve1Data_un16.bit.RDDTQ_state_u16)
    {
        s_RIUSendData_t.RIUfltInfo1_t.bit.RDDTQ_fault_u16 = 1U;
        s_preTaskCheckCtx_t.valveTimeoutFault_u16 = VALID;
    }
    /* 阀2状态:LYJFY/RYJFY(应急放油阀)异常置位 */
    if (RECEIVE_VALVE_STATE_CLOSED != l_valve2Data_un32.bit.LYJFY_state_u32)
    {
        s_RIUSendData_t.RIUfltInfo1_t.bit.LYJFY_fault_u16 = 1U;
        s_preTaskCheckCtx_t.valveTimeoutFault_u16 = VALID;
    }
    if (RECEIVE_VALVE_STATE_CLOSED != l_valve2Data_un32.bit.RYJFY_state_u32)
    {
        s_RIUSendData_t.RIUfltInfo1_t.bit.RYJFY_fault_u16 = 1U;
        s_preTaskCheckCtx_t.valveTimeoutFault_u16 = VALID;
    }

    /* 计量环节未完成检查则上报油量计量故障 */
    if (INVALID == s_preTaskCheckCtx_t.measureChecked_u16)
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.oilMS_falut_u16 = 1U;
        s_preTaskCheckCtx_t.measureFault_u16 = VALID;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RefuelStagePreCheck
 *
 * 【功能描述】加油阶段前检
 *
 * 【输入参数说明】v_p_ConData_t ---- 系统控制数据指针
 * 【输出参数说明】NONE
 * 【其他说明】检查进入加油前置条件(状态、阀门、测量)
 * 【返回】NONE
 */
/* ***************************************************************** */
static void RefuelStagePreCheck(ConData_t *v_p_ConData_t)
{
    Uint32 l_sysTime_u32 = 0UL;               /* 当前时间，用于判断前检是否超时。 */
    Uint16 l_rcvClosed_u16 = INVALID;         /* 活门全关结果，用于记录5路压力加油控制活门是否全部关闭。 */
    Uint16 l_valveClosed_u16 = INVALID;       /* 阀位检查结果，用于记录三通阀/通气阀/关键阀位是否满足要求。 */
    Uint16 l_measureOk_u16 = INVALID;         /* 测量正常结果，用于记录燃油测量系统是否保持正常。 */
    Uint16 l_stValveOk_u16 = INVALID;         /* 三通阀位置结果，用于记录三通阀是否处于允许集合。 */
    Uint16 l_ventValveOpen_u16 = INVALID;     /* 通气阀结果，用于记录左右电动通气阀是否都打开。 */
    union RCV_Data l_rcvData_un16;            /* 受油活门反馈，用于暂存RIU发送的5路压力加油控制活门状态。 */
    union valve1_Data l_valve1Data_un16;      /* 第一组阀位反馈，用于暂存第一组阀位反馈。 */
    union valve2_Data l_valve2Data_un32;      /* 第二组阀位反馈，用于暂存第二组阀位反馈。 */
    union faultInfo_Data l_faultInfo_un16;    /* 故障反馈，用于暂存故障反馈。 */
    union fuelCmd_Data l_taskCmd_un32;         /* 当前RIU任务模式，用于判断任务是否撤销。 */

    /* 空指针时本拍不做任何前检推进。 */
    if (NULL == v_p_ConData_t)
    {
        return;
    }

    l_taskCmd_un32 = ControlRiuFuelCmdGet();
    if (v_p_ConData_t->workMode_u16 !=
        WorkModeRIUDataCheck(l_taskCmd_un32.bit.fuelObject_u8, l_taskCmd_un32.bit.fuelMode_u8))
    {
        /* 加油模式指令撤销后，前检不再继续推进，统一切任务结束态收口。 */
        RefuelModeExitToTaskEnd(v_p_ConData_t);
        return;
    }

    /* 首次进入前检时先清掉上轮前检缓存，避免旧结果污染本轮判断。 */
    if (v_p_ConData_t->conFuncLast_u16 != v_p_ConData_t->conFunc_u16)
    {
        /* 首次进入前检时复位上下文并建立本轮超时基准。 */
        PreTaskCheckContextReset();
        s_refuelCtx_t.presetReady_u16 = INVALID;
        /* 以进入前检的时刻作为5秒超时基准。 */
        v_p_ConData_t->workModeTime_u32 = sysTime();
        /* 首拍动作只执行一次，避免每拍重置超时基准。 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    }

    /* 前检每拍都重申目标命令，确保执行链路在超时窗口内持续驱动到目标状态。 */
    PreTaskCheckCommandBuild();
    /* 读取当前拍时刻，供成功推进或超时退出共用。 */
    l_sysTime_u32 = sysTime();

    /* 任务前检查只服务当前加油链，因此直接在阶段函数内读取RCV、关键阀位和测量故障反馈。 */
    /* 读取RIU发送的压力加油控制活门状态。 */
    l_rcvData_un16.all = (Uint16)(RedunDataGet(REDUN_INDEX_RIU_RCV).dataU_u32 & 0xFFFFU);
    /* 只有5路RCV全部在关闭状态时，才认为该检查项通过。 */
    l_rcvClosed_u16 = l_rcvData_un16.bit.RCV0_Close_u16 &
                      l_rcvData_un16.bit.RCV1_Close_u16 &
                      l_rcvData_un16.bit.RCV2_Close_u16 &
                      l_rcvData_un16.bit.RCV3_Close_u16 &
                      l_rcvData_un16.bit.RCV4_Close_u16;

    /* 读取三通阀、通气阀、连通阀和应急放油切断阀的状态反馈。 */
    l_valve1Data_un16.all = (Uint16)(RedunDataGet(REDUN_INDEX_RIU_VALVE1).dataU_u32 & 0xFFFFU);
    l_valve2Data_un32.all = RedunDataGet(REDUN_INDEX_RIU_VALVE2).dataU_u32 & 0x3FFFFUL;
    l_stValveOk_u16 = RefuelStageStStateValidGet(l_valve1Data_un16.bit.ST_state_u16);
    l_ventValveOpen_u16 = (RECEIVE_VALVE_STATE_OPEN == l_valve1Data_un16.bit.LDDTQ_state_u16) &&
                          (RECEIVE_VALVE_STATE_OPEN == l_valve1Data_un16.bit.RDDTQ_state_u16);
    /* 三通阀处于允许位、通气阀打开且关键隔离阀都关到位时，阀位检查才算通过。 */
    l_valveClosed_u16 = (VALID == l_stValveOk_u16) &&
                        (VALID == l_ventValveOpen_u16) &&
                        (RECEIVE_VALVE_STATE_CLOSED == l_valve1Data_un16.bit.LT_state_u16) &&
                        (RECEIVE_VALVE_STATE_CLOSED == l_valve2Data_un32.bit.LYJFY_state_u32) &&
                        (RECEIVE_VALVE_STATE_CLOSED == l_valve2Data_un32.bit.RYJFY_state_u32);

    /* 读取测量系统故障位，前检阶段把故障、降级和传感器故障统一视为异常。 */
    l_faultInfo_un16.all = (Uint16)(RedunDataGet(REDUN_INDEX_RIU_FAULTINFO).dataU_u32 & 0xFFFFU);
    if (VALID == ControlMeasureFaultExists(l_faultInfo_un16))
    {
        l_measureOk_u16 = INVALID;
    }
    else
    {
        l_measureOk_u16 = VALID;
    }

    /* 把本拍检查结果回写到前检上下文，方便超时分支精确落故障。 */
    s_preTaskCheckCtx_t.rcvChecked_u16 = l_rcvClosed_u16;
    s_preTaskCheckCtx_t.valveChecked_u16 = l_valveClosed_u16;
    s_preTaskCheckCtx_t.measureChecked_u16 = l_measureOk_u16;
    PreTaskCheckFaultStatusUpdate();

    /* 三类检查全部通过时，才允许离开前检进入预位。 */
    if ((VALID == l_rcvClosed_u16) && (VALID == l_valveClosed_u16) && (VALID == l_measureOk_u16))
    {
        /* 所有前检项都通过后，才允许进入加油预位阶段。 */
        /* 前检通过后先把RIU状态恢复为空闲口径，再切阶段。 */
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_IDLE;
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_NONE;
        /* 前检完成后正式进入加油预位:复用阶段切换公共收口。 */
        ControlConFuncSwitch(v_p_ConData_t, CON_FUNC_2_FUEL_PRESET, l_sysTime_u32);
    }
    else
    {
        /* 未到5秒前也按当前故障口径持续上报，便于上位机在前检窗口内看到原因。 */
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_FAULT;
        if (VALID == s_preTaskCheckCtx_t.measureFault_u16)
        {
            s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_MEASURE;
        }
        else
        {
            s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_VALVE_TIMEOUT;
        }

        if ((l_sysTime_u32 - v_p_ConData_t->workModeTime_u32) > PRE_TASK_CHECK_TIMEOUT_MS)
        {
            /* 超时只负责退出，故障字已经在本拍按当前状态刷新过。 */
            ControlConFuncSwitch(v_p_ConData_t, CON_FUNC_4_TASK_END, l_sysTime_u32);
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RefuelStagePreset
 *
 * 【功能描述】燃油预位阶段处理
 *             下发预位阀位命令并等待到位确认，到位后推进到加油执行阶段
 * 【输入参数说明】v_p_ConData_t ---- 系统控制数据指针
 * 【输出参数说明】NONE
 * 【其他说明】       阀位到位超时触发前检故障
 * 【返回】           NONE
 */
/* ***************************************************************** */
static void RefuelStagePreset(ConData_t *v_p_ConData_t)
{
    Uint32 l_sysTime_u32 = 0UL;                     /* 当前时间，用于阀位开到位超时判断。 */
    RedunData_t l_redunData_t;                     /* 冗余池数据，用于暂存冗余池读取结果。 */
    union valve2_Data l_valveData2_un32;           /* 阀位反馈，用于暂存阀位反馈。 */
    union fuelPump_Data l_fuelPump_un8;            /* 泵低压反馈，用于暂存泵低压反馈。 */
    union fuelCmd_Data l_taskCmd_un32;              /* 当前RIU任务模式，用于判断任务是否撤销。 */
    float l_tank0Vol_f = 0.0F;                     /* 0号箱油量，用于决定单吊舱预位路径。 */
    Uint16 l_podValveOpen_u16 = INVALID;           /* 吊舱阀到位结果，用于记录吊舱切断阀是否已开到位。 */
    Uint16 l_otherValvesOk_u16 = INVALID;          /* 供油通路到位结果，用于记录目标供油通路的其余切断阀是否已开到位。 */
    const Uint16 VALVE_STATE_OPEN = 0x02U;         /* 开到位状态值，用于匹配阀位反馈中的开到位协议值。 */
    const Uint32 TIME_VALVE_OPEN_TIMEOUT = 5000UL; /* 开阀超时时间，用于限制预位开阀确认时间。 */

    /* 空指针时不推进预位。 */
    if (NULL == v_p_ConData_t)
    {
        return;
    }

    l_taskCmd_un32 = ControlRiuFuelCmdGet();
    if (v_p_ConData_t->workMode_u16 !=
        WorkModeRIUDataCheck(l_taskCmd_un32.bit.fuelObject_u8, l_taskCmd_un32.bit.fuelMode_u8))
    {
        /* 预位阶段若上位撤销加油模式，直接结束本轮加油流程。 */
        RefuelModeExitToTaskEnd(v_p_ConData_t);
        return;
    }

    /* 首次进入预位时先把上轮目标和发送标志清掉。 */
    if (v_p_ConData_t->conFuncLast_u16 != v_p_ConData_t->conFunc_u16)
    {
        /* 进入预位首拍时清空目标记录和命令发送标志。 */
        s_refuelCtx_t.targetTank_u16 = 0U;
        s_refuelCtx_t.commandSent_u16 = INVALID;
        s_refuelCtx_t.presetReady_u16 = INVALID;
        /* 首拍初始化只执行一次。 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    }

    if (INVALID == s_refuelCtx_t.commandSent_u16)
    {
        /* 预位阶段只在首拍建立一次开阀目标，后续拍等待反馈确认。 */
        if ((WORK_MODE_LRP_FIXEDWING == v_p_ConData_t->workMode_u16) ||
            (WORK_MODE_LRP_HELI == v_p_ConData_t->workMode_u16))
        {
            /* 双吊舱模式固定走四路同时预位，不再区分0号油箱是否可外供。 */
            s_refuelCtx_t.targetTank_u16 = REFUEL_TARGET_LRP_ALL;
            /* 打开左吊舱切断阀。 */
            s_RIUSendData_t.ValveCtrl_t.bit.LPQD_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            /* 打开右吊舱切断阀。 */
            s_RIUSendData_t.ValveCtrl_t.bit.RPQD_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            /* 打开0号左路泵切断阀。 */
            s_RIUSendData_t.ValveCtrl_t.bit.Pump0_Lcutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            /* 打开0号右路泵切断阀。 */
            s_RIUSendData_t.ValveCtrl_t.bit.Pump0_Rcutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            /* 打开2号泵切断阀。 */
            s_RIUSendData_t.ValveCtrl_t.bit.Pump2_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            /* 打开3号泵切断阀。 */
            s_RIUSendData_t.ValveCtrl_t.bit.Pump3_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
        }
        else
        {
            /* 单吊舱模式需要先看0号油箱是否还有可外供油量。 */
            l_tank0Vol_f = RedunDataGet(REDUN_INDEX_RIU_FQ_TANK0).dataF_f;

            /* 单吊舱模式只打开对应吊舱切断阀，再依据0号油箱剩余量决定目标供油箱组。 */
            if ((WORK_MODE_LP_FIXEDWING == v_p_ConData_t->workMode_u16) ||
                (WORK_MODE_LP_HELI == v_p_ConData_t->workMode_u16))
            {
                /* 左吊舱模式先打开左吊舱切断阀。 */
                s_RIUSendData_t.ValveCtrl_t.bit.LPQD_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            }
            else if ((WORK_MODE_RP_FIXEDWING == v_p_ConData_t->workMode_u16) ||
                     (WORK_MODE_RP_HELI == v_p_ConData_t->workMode_u16))
            {
                /* 右吊舱模式先打开右吊舱切断阀。 */
                s_RIUSendData_t.ValveCtrl_t.bit.RPQD_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            }

            if (l_tank0Vol_f > 0.0F)
            {
                /* 0号油箱有油时优先选择0号路径供油。 */
                s_refuelCtx_t.targetTank_u16 = REFUEL_TARGET_TANK0;
                /* 打开0号左路泵切断阀。 */
                s_RIUSendData_t.ValveCtrl_t.bit.Pump0_Lcutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
                /* 打开0号右路泵切断阀。 */
                s_RIUSendData_t.ValveCtrl_t.bit.Pump0_Rcutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            }
            else
            {
                /* 0号油箱不可外供时，直接切到2/3号路径预位。 */
                s_refuelCtx_t.targetTank_u16 = REFUEL_TARGET_TANK23;
                /* 打开2号泵切断阀。 */
                s_RIUSendData_t.ValveCtrl_t.bit.Pump2_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
                /* 打开3号泵切断阀。 */
                s_RIUSendData_t.ValveCtrl_t.bit.Pump3_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            }
        }
        /* 预位命令发出的这一拍作为5秒开到位超时起点。 */
        v_p_ConData_t->workModeTime_u32 = sysTime();
        /* 标记本轮预位命令已发送，后续拍只等待反馈。 */
        s_refuelCtx_t.commandSent_u16 = VALID;
    }

    /* 读取当前拍时间。 */
    l_sysTime_u32 = sysTime();
    /* 读取当前阀位反馈。 */
    l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_VALVE2);
    l_valveData2_un32.all = l_redunData_t.dataU_u32 & 0x3FFFFUL;

    if ((WORK_MODE_LP_FIXEDWING == v_p_ConData_t->workMode_u16) || (WORK_MODE_LP_HELI == v_p_ConData_t->workMode_u16))
    {
        /* 左吊舱模式只要求左吊舱切断阀到开位。 */
        if (l_valveData2_un32.bit.LPQD_state_u32 == VALVE_STATE_OPEN) { l_podValveOpen_u16 = VALID; }
    }
    else if ((WORK_MODE_RP_FIXEDWING == v_p_ConData_t->workMode_u16) || (WORK_MODE_RP_HELI == v_p_ConData_t->workMode_u16))
    {
        /* 右吊舱模式只要求右吊舱切断阀到开位。 */
        if (l_valveData2_un32.bit.RPQD_state_u32 == VALVE_STATE_OPEN) { l_podValveOpen_u16 = VALID; }
    }
    else if ((WORK_MODE_LRP_FIXEDWING == v_p_ConData_t->workMode_u16) || (WORK_MODE_LRP_HELI == v_p_ConData_t->workMode_u16))
    {
        if ((l_valveData2_un32.bit.LPQD_state_u32 == VALVE_STATE_OPEN) &&
            (l_valveData2_un32.bit.RPQD_state_u32 == VALVE_STATE_OPEN))
        {
            l_podValveOpen_u16 = VALID;
        }
    }

    if (REFUEL_TARGET_TANK0 == s_refuelCtx_t.targetTank_u16)
    {
        /* 0号油箱供油时，需要0号油箱左右两路切断阀同时开到位。 */
        if ((l_valveData2_un32.bit.Pump0_Lcutoff_state_u32 == VALVE_STATE_OPEN) &&
            (l_valveData2_un32.bit.Pump0_Rcutoff_state_u32 == VALVE_STATE_OPEN))
        {
            l_otherValvesOk_u16 = VALID;
        }
    }
    else if (REFUEL_TARGET_TANK23 == s_refuelCtx_t.targetTank_u16)
    {
        /* 2/3号油箱供油时，需要2号和3号泵切断阀同时开到位。 */
        if ((l_valveData2_un32.bit.Pump2_cutoff_state_u32 == VALVE_STATE_OPEN) &&
            (l_valveData2_un32.bit.Pump3_cutoff_state_u32 == VALVE_STATE_OPEN))
        {
            l_otherValvesOk_u16 = VALID;
        }
    }
    else if (REFUEL_TARGET_LRP_ALL == s_refuelCtx_t.targetTank_u16)
    {
        /* 双吊舱模式要求两侧吊舱阀和四路泵切断阀全部开到位。
         * 任一路没到位都不能提前进入执行态，否则后续低压/平衡判断会失去路径前提。 */
        if ((l_valveData2_un32.bit.Pump0_Lcutoff_state_u32 == VALVE_STATE_OPEN) &&
            (l_valveData2_un32.bit.Pump0_Rcutoff_state_u32 == VALVE_STATE_OPEN) &&
            (l_valveData2_un32.bit.Pump2_cutoff_state_u32 == VALVE_STATE_OPEN) &&
            (l_valveData2_un32.bit.Pump3_cutoff_state_u32 == VALVE_STATE_OPEN))
        {
            l_otherValvesOk_u16 = VALID;
        }
    }

    if ((VALID == l_podValveOpen_u16) && (VALID == l_otherValvesOk_u16))
    {
        /* 目标阀全部开到位后，立即检查对应路径泵低压是否正常。 */
        l_fuelPump_un8.all = (Uint8)(RedunDataGet(REDUN_INDEX_RIU_FUELPUMP).dataU_u32 & 0xFFU);

        /* 预位完成后立刻检查目标路径低压；低压则不允许自动空中加油，正常才进入执行态。 */
        if (REFUEL_TARGET_TANK0 == s_refuelCtx_t.targetTank_u16)
        {
            if ((INVALID == l_fuelPump_un8.bit.FP0_left_state_u16) ||
                (INVALID == l_fuelPump_un8.bit.FP0_right_state_u16))
            {
                /* 0号路径低压时，预位阶段直接按“禁止自动加油”故障收口。 */
                RefuelModeLowPressureFaultApply(v_p_ConData_t, l_fuelPump_un8, REFUEL_TARGET_TANK0);
                return;
            }
        }
        else if (REFUEL_TARGET_TANK23 == s_refuelCtx_t.targetTank_u16)
        {
            if ((INVALID == l_fuelPump_un8.bit.FP2_state_u16) ||
                (INVALID == l_fuelPump_un8.bit.FP3_state_u16))
            {
                /* 2/3路径低压时，同样在预位阶段直接禁止自动加油。 */
                RefuelModeLowPressureFaultApply(v_p_ConData_t, l_fuelPump_un8, REFUEL_TARGET_TANK23);
                return;
            }
        }
        else
        {
            if ((INVALID == l_fuelPump_un8.bit.FP0_left_state_u16) ||
                (INVALID == l_fuelPump_un8.bit.FP0_right_state_u16) ||
                (INVALID == l_fuelPump_un8.bit.FP2_state_u16) ||
                (INVALID == l_fuelPump_un8.bit.FP3_state_u16))
            {
                /* 双吊舱四路中任一路低压都视为不允许自动空中加油。 */
                RefuelModeLowPressureFaultApply(v_p_ConData_t, l_fuelPump_un8, REFUEL_TARGET_LRP_ALL);
                return;
            }
        }

        /* 预位成功且目标路径无低压后，才正式进入加油执行态。 */
        s_refuelCtx_t.presetReady_u16 = VALID;
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_ACTIVE;
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_NONE;
        ControlConFuncSwitch(v_p_ConData_t, CON_FUNC_3_REFUEL_PROCESS, l_sysTime_u32);
    }
    else if ((l_sysTime_u32 - v_p_ConData_t->workModeTime_u32) > TIME_VALVE_OPEN_TIMEOUT)
    {
        /* 超时未开到位时，按当前目标通路逐项置阀故障。 */
        if ((WORK_MODE_LP_FIXEDWING == v_p_ConData_t->workMode_u16) || (WORK_MODE_LP_HELI == v_p_ConData_t->workMode_u16))
        {
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.LPQD_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.LPQD_fault_u16 = 1U;
            }
        }
        else if ((WORK_MODE_RP_FIXEDWING == v_p_ConData_t->workMode_u16) || (WORK_MODE_RP_HELI == v_p_ConData_t->workMode_u16))
        {
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.RPQD_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.RPQD_fault_u16 = 1U;
            }
        }
        else if ((WORK_MODE_LRP_FIXEDWING == v_p_ConData_t->workMode_u16) || (WORK_MODE_LRP_HELI == v_p_ConData_t->workMode_u16))
        {
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.LPQD_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.LPQD_fault_u16 = 1U;
            }
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.RPQD_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.RPQD_fault_u16 = 1U;
            }
        }

        if (REFUEL_TARGET_TANK0 == s_refuelCtx_t.targetTank_u16)
        {
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.Pump0_Lcutoff_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Lcutoff_fault_u16 = 1U;
            }
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.Pump0_Rcutoff_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Rcutoff_fault_u16 = 1U;
            }
        }
        else if (REFUEL_TARGET_TANK23 == s_refuelCtx_t.targetTank_u16)
        {
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.Pump2_cutoff_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump2_cutoff_fault_u16 = 1U;
            }
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.Pump3_cutoff_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump3_cutoff_fault_u16 = 1U;
            }
        }
        else if (REFUEL_TARGET_LRP_ALL == s_refuelCtx_t.targetTank_u16)
        {
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.Pump0_Lcutoff_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Lcutoff_fault_u16 = 1U;
            }
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.Pump0_Rcutoff_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Rcutoff_fault_u16 = 1U;
            }
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.Pump2_cutoff_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump2_cutoff_fault_u16 = 1U;
            }
            if (VALVE_STATE_OPEN != l_valveData2_un32.bit.Pump3_cutoff_state_u32)
            {
                s_RIUSendData_t.RIUfltInfo1_t.bit.Pump3_cutoff_fault_u16 = 1U;
            }
        }

        /* 预位超时不进入加油执行态。这里保留已置位的具体阀故障，同时用统一原因码标识本轮失败类型。 */
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_FAULT;
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_VALVE_TIMEOUT;
        s_refuelCtx_t.presetReady_u16 = INVALID;
        ControlConFuncSwitch(v_p_ConData_t, CON_FUNC_4_TASK_END, l_sysTime_u32);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RefuelStageProcess
 *
 * 【功能描述】加油阶段执行
 *
 * 【输入参数说明】v_p_ConData_t ---- 系统控制数据指针
 * 【输出参数说明】NONE
 * 【其他说明】主循环监测泵/阀状态推进加油进度
 * 【返回】NONE
 */
/* ***************************************************************** */
static void RefuelStageProcess(ConData_t *v_p_ConData_t)
{
    RedunData_t l_redunData_t;           /* 冗余池数据，用于暂存冗余池读取结果。 */
    union fuelPump_Data l_fuelPump_un8;  /* 泵低压反馈，用于暂存各路泵低压状态。 */
    union fuelCmd_Data l_taskCmd_un32;    /* 当前RIU任务模式，用于判断任务是否撤销。 */
    float l_tank2Vol_f;                  /* 2号箱油量，用于记录当前2号油箱油量。 */
    float l_tank3Vol_f;                  /* 3号箱油量，用于记录当前3号油箱油量。 */
    float l_diff_f;                      /* 油量差值，用于记录2号与3号油量差值绝对值。 */
    float l_limitClose_f;                /* 平衡触发阈值，用于记录触发平衡控制的上阈值。 */
    float l_limitOpen_f;                 /* 平衡恢复阈值，用于记录平衡控制恢复时的下阈值。 */
    float l_limitAlarm_f;                /* 告警阈值，用于记录不平衡告警阈值。 */

    /* 加油执行态每拍只做三件事：确认任务仍有效、维护当前供油路径、在 2/3 号路径上做平衡控制。
     * 低压故障和任务撤销一旦成立，优先级都高于平衡调节，直接退出执行态。 */
    /* 空指针时不推进执行态。 */
    if (NULL == v_p_ConData_t)
    {
        return;
    }

    l_taskCmd_un32 = ControlRiuFuelCmdGet();
    if (v_p_ConData_t->workMode_u16 !=
        WorkModeRIUDataCheck(l_taskCmd_un32.bit.fuelObject_u8, l_taskCmd_un32.bit.fuelMode_u8))
    {
        /* 执行态检测到加油模式无效后，立即切任务结束态。 */
        RefuelModeExitToTaskEnd(v_p_ConData_t);
        return;
    }

    /* 直升机与固定翼使用不同的平衡与告警阈值。 */
    if ((WORK_MODE_LP_HELI == v_p_ConData_t->workMode_u16) ||
        (WORK_MODE_RP_HELI == v_p_ConData_t->workMode_u16) ||
        (WORK_MODE_LRP_HELI == v_p_ConData_t->workMode_u16))
    {
        /* 直升机模式按任务书采用 500/300kg 平衡控制、600kg 告警口径。 */
        l_limitClose_f = 500.0F;
        l_limitOpen_f = 300.0F;
        l_limitAlarm_f = 600.0F;
    }
    else
    {
        /* 固定翼模式按任务书采用 1000/600kg 平衡控制、1200kg 告警口径。 */
        l_limitClose_f = 1000.0F;
        l_limitOpen_f = 600.0F;
        l_limitAlarm_f = 1200.0F;
    }

    if (v_p_ConData_t->conFuncLast_u16 != v_p_ConData_t->conFunc_u16)
    {
        /* 执行态入口沿用预位阶段选定的供油路径；双吊舱统一视为全路径供油后进入23号路径平衡逻辑。 */
        if (REFUEL_TARGET_TANK23 == s_refuelCtx_t.targetTank_u16)
        {
            /* 单吊舱直接从2/3路径进入执行态。 */
            s_refuelCtx_t.supplySource_u16 = SUPPLY_SOURCE_TANK23;
        }
        else if (REFUEL_TARGET_LRP_ALL == s_refuelCtx_t.targetTank_u16)
        {
            /* 双吊舱执行态统一沿用23号路径平衡控制逻辑。 */
            s_refuelCtx_t.supplySource_u16 = SUPPLY_SOURCE_TANK23;
        }
        else
        {
            /* 单吊舱0号有油时先从0号路径开始供油。 */
            s_refuelCtx_t.supplySource_u16 = SUPPLY_SOURCE_TANK0;
        }
        /* 首拍进入执行态时先清掉平衡控制状态。 */
        s_refuelCtx_t.balancingValveClosed_u16 = BALANCING_VALVE_NONE;
        /* 执行态默认上报为加油活动中。 */
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_ACTIVE;
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_NONE;
        /* 入口沿消费后，避免每拍重置执行态上下文。 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    }

    /* 读取当前泵低压状态和2/3号油量。 */
    l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FUELPUMP);
    l_fuelPump_un8.all = (Uint8)(l_redunData_t.dataU_u32 & 0xFFU);
    l_tank2Vol_f = RedunDataGet(REDUN_INDEX_RIU_FQ_TANK2).dataF_f;
    l_tank3Vol_f = RedunDataGet(REDUN_INDEX_RIU_FQ_TANK3).dataF_f;
    /* 绝对值化后统一做平衡控制和告警判断。 */
    l_diff_f = l_tank2Vol_f - l_tank3Vol_f;

    if (l_diff_f < 0.0F)
    {
        l_diff_f = -l_diff_f;
    }

    /* 不平衡告警按机型阈值独立评估，不依赖当前是否已切到23号供油。 */
    if (l_diff_f > l_limitAlarm_f)
    {
        /* 超过告警阈值时，保持运行但向RIU上报不平衡。 */
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_IMBALANCE;
    }
    else if (RECEIVE_RIU_REASON_IMBALANCE == s_RIUSendData_t.checkState_u16)
    {
        /* 差值回落到安全范围后，清掉不平衡告警。 */
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_NONE;
    }

    if ((WORK_MODE_LRP_FIXEDWING == v_p_ConData_t->workMode_u16) ||
        (WORK_MODE_LRP_HELI == v_p_ConData_t->workMode_u16))
    {
        /* 双吊舱模式下任一路低压都直接中止自动空中加油。 */
        if ((INVALID == l_fuelPump_un8.bit.FP0_left_state_u16) ||
            (INVALID == l_fuelPump_un8.bit.FP0_right_state_u16) ||
            (INVALID == l_fuelPump_un8.bit.FP2_state_u16) ||
            (INVALID == l_fuelPump_un8.bit.FP3_state_u16))
        {
            RefuelModeLowPressureFaultApply(v_p_ConData_t, l_fuelPump_un8, REFUEL_TARGET_LRP_ALL);
            return;
        }
    }

    if (SUPPLY_SOURCE_TANK0 == s_refuelCtx_t.supplySource_u16)
    {
        /* 单吊舱模式先尽量走 0 号路径。
         * 只有 0 号泵路撑不住时才切到 2/3 号路径，避免过早进入 23 号平衡控制。 */
        if ((INVALID == l_fuelPump_un8.bit.FP0_left_state_u16) ||
            (INVALID == l_fuelPump_un8.bit.FP0_right_state_u16))
        {
            /* 0号路径低压后，先打开2/3号泵切断阀。 */
            s_RIUSendData_t.ValveCtrl_t.bit.Pump2_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            s_RIUSendData_t.ValveCtrl_t.bit.Pump3_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
            /* 再关闭0号左右两路，完成向2/3路径切路。 */
            s_RIUSendData_t.ValveCtrl_t.bit.Pump0_Lcutoff_ctrl_u16 = REFUEL_VALVE_CMD_CLOSE;
            s_RIUSendData_t.ValveCtrl_t.bit.Pump0_Rcutoff_ctrl_u16 = REFUEL_VALVE_CMD_CLOSE;
            /* 切路完成后，后续拍按2/3路径规则继续处理。 */
            s_refuelCtx_t.supplySource_u16 = SUPPLY_SOURCE_TANK23;
        }
    }

    if (SUPPLY_SOURCE_TANK23 == s_refuelCtx_t.supplySource_u16)
    {
        /* 2/3 号路径同时承担后备供油和平衡调节。
         * 所以切到这里后，先判断供油链是否还能继续，再决定是否通过关单侧阀做差量收敛。 */
        if ((INVALID == l_fuelPump_un8.bit.FP2_state_u16) ||
            (INVALID == l_fuelPump_un8.bit.FP3_state_u16))
        {
            RefuelModeLowPressureFaultApply(v_p_ConData_t, l_fuelPump_un8, REFUEL_TARGET_TANK23);
            return;
        }

        if ((l_diff_f > l_limitClose_f) && (BALANCING_VALVE_NONE == s_refuelCtx_t.balancingValveClosed_u16))
        {
            /* 差值首次越过上阈值时，只关闭油量较少一侧，避免两侧差值继续扩大。 */
            if (l_tank2Vol_f < l_tank3Vol_f)
            {
                /* 2号油量更少时先关2号路径，阻止继续向较少侧抽油。 */
                s_RIUSendData_t.ValveCtrl_t.bit.Pump2_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_CLOSE;
                s_refuelCtx_t.balancingValveClosed_u16 = BALANCING_VALVE_TANK2_CLOSED;
            }
            else
            {
                /* 3号油量更少时先关3号路径，阻止继续向较少侧抽油。 */
                s_RIUSendData_t.ValveCtrl_t.bit.Pump3_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_CLOSE;
                s_refuelCtx_t.balancingValveClosed_u16 = BALANCING_VALVE_TANK3_CLOSED;
            }
        }
        else if (l_diff_f < l_limitOpen_f)
        {
            /* 差值回落到恢复阈值以下后，再重新打开之前关闭的一侧。 */
            if (BALANCING_VALVE_TANK2_CLOSED == s_refuelCtx_t.balancingValveClosed_u16)
            {
                /* 差值恢复后重新打开2号路径，结束本轮平衡控制。 */
                s_RIUSendData_t.ValveCtrl_t.bit.Pump2_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
                s_refuelCtx_t.balancingValveClosed_u16 = BALANCING_VALVE_NONE;
            }
            else if (BALANCING_VALVE_TANK3_CLOSED == s_refuelCtx_t.balancingValveClosed_u16)
            {
                /* 差值恢复后重新打开3号路径，结束本轮平衡控制。 */
                s_RIUSendData_t.ValveCtrl_t.bit.Pump3_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_OPEN;
                s_refuelCtx_t.balancingValveClosed_u16 = BALANCING_VALVE_NONE;
            }
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RefuelStageTaskEnd
 *
 * 【功能描述】加油阶段结束
 *
 * 【输入参数说明】v_p_ConData_t ---- 系统控制数据指针
 * 【输出参数说明】NONE
 * 【其他说明】关闭阀门并退出加油阶段
 * 【返回】NONE
 */
/* ***************************************************************** */
static void RefuelStageTaskEnd(ConData_t *v_p_ConData_t)
{
    /* 空指针时不做收口。 */
    if (NULL == v_p_ConData_t)
    {
        return;
    }

    /* 任务结束首拍先把加油相关阀位全部打回关闭目标。 */
    if (v_p_ConData_t->conFuncLast_u16 != v_p_ConData_t->conFunc_u16)
    {
        /* 进入任务结束首拍时，先把加油相关阀命令恢复到默认关闭目标。 */
        s_RIUSendData_t.ValveCtrl_t.bit.Pump0_Lcutoff_ctrl_u16 = REFUEL_VALVE_CMD_CLOSE;
        s_RIUSendData_t.ValveCtrl_t.bit.Pump0_Rcutoff_ctrl_u16 = REFUEL_VALVE_CMD_CLOSE;
        s_RIUSendData_t.ValveCtrl_t.bit.Pump2_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_CLOSE;
        s_RIUSendData_t.ValveCtrl_t.bit.Pump3_cutoff_ctrl_u16 = REFUEL_VALVE_CMD_CLOSE;
        s_RIUSendData_t.ValveCtrl_t.bit.LPQD_ctrl_u16 = REFUEL_VALVE_CMD_CLOSE;
        s_RIUSendData_t.ValveCtrl_t.bit.RPQD_ctrl_u16 = REFUEL_VALVE_CMD_CLOSE;
        s_refuelCtx_t.presetReady_u16 = INVALID;
        /* 任务结束首拍动作只执行一次。 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    }

    if (VALID == s_controlFaultTripActive_u16)
    {
        /* 故障触发后只允许在连续清故障确认满足时重新回到任务前检查。 */
        if (INVALID == ControlFaultRawExists())
        {
            /* 原始故障消失后，累加连续清故障拍数。 */
            if (s_controlFaultClearCnt_u16 < 0xFFFFU)
            {
                s_controlFaultClearCnt_u16++;
            }

            if (s_controlFaultClearCnt_u16 >= CONTROL_FAULT_CLEAR_CYCLES)
            {
                /* 连续清故障确认满足后，先把RIU状态和故障位恢复为空闲口径。 */
                s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_IDLE;
                s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_NONE;
                s_RIUSendData_t.RIUfltInfo1_t.all = 0U;
                s_RIUSendData_t.RIUfltInfo2_t.all = 0U;

                /* 复位故障去抖与恢复冷却计数，为重新前检做准备。 */
                ControlFaultDebounceReset();
                s_controlFaultTripActive_u16 = INVALID;
                s_controlFaultClearCnt_u16 = 0U;
                s_controlFaultRecoveryCooldownCnt_u16 = CONTROL_FAULT_RECOVERY_COOLDOWN_CYCLES;

                /* 故障恢复后重新回到前检，而不是直接回执行态。 */
                ControlConFuncSwitch(v_p_ConData_t, CON_FUNC_1_PRE_TASK_CHECK, sysTime());
                return;
            }
        }
        else
        {
            /* 原始故障仍存在时，清故障确认计数必须重新开始。 */
            s_controlFaultClearCnt_u16 = 0U;
        }
        /* 故障保持期间不允许继续向正常收口推进。 */
        return;
    }

    /* 当前不存在故障保持时，直接按正常结束回到待机。 */
    s_controlFaultTripActive_u16 = INVALID;
    s_controlFaultClearCnt_u16 = 0U;
    ControlModeReentryLatchSet(v_p_ConData_t->workMode_u16);
    v_p_ConData_t->workModeLast_u16 = v_p_ConData_t->workMode_u16;
    v_p_ConData_t->workMode_u16 = WORK_MODE_STANDBY;
    v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    v_p_ConData_t->conFunc_u16 = CON_FUNC_0_STANDBY;
}

/* ***************************************************************** */
/**
 * 【函数名】:WorkModeProcessRefuel
 * 【功能描述】加油模式处理入口
 *            根据当前控制功能分发到加油各阶段（前检、预设、执行、结束）
 * 【输入参数说明】v_p_ConData_t ---- 系统控制数据指针
 * 【输出参数说明】NONE
 * 【其他说明】    与WorkModeProcessReceive共同组成主受控模式业务入口
 * 【返回】        NONE
 */
/* ***************************************************************** */
void WorkModeProcessRefuel(ConData_t *v_p_ConData_t)
{
    /* 入参保护 */
    if (NULL == v_p_ConData_t)
    {
        return;
    }

    /* 按 conFunc 分发到对应受油阶段处理函数 */
    switch (v_p_ConData_t->conFunc_u16)
    {
        /* 待机:执行默认状态机 */
        case CON_FUNC_0_STANDBY:
            SysStateProcessDefault();
            break;

        /* 任务前检查 */
        case CON_FUNC_1_PRE_TASK_CHECK:
            RefuelStagePreCheck(v_p_ConData_t);
            break;

        /* 油量预置 */
        case CON_FUNC_2_FUEL_PRESET:
            RefuelStagePreset(v_p_ConData_t);
            break;

        /* 实际受油过程 */
        case CON_FUNC_3_REFUEL_PROCESS:
            RefuelStageProcess(v_p_ConData_t);
            break;

        /* 任务结束收尾 */
        case CON_FUNC_4_TASK_END:
            RefuelStageTaskEnd(v_p_ConData_t);
            break;

        /* 非法 conFunc 兜底:记录上一个值后强制回待机 */
        default:
            /* conFunc 出现非法值(内存扰动或维护注入异常),统一回待机收口 */
            ControlConFuncSwitch(&s_sysConData_t, CON_FUNC_0_STANDBY, sysTime());
            break;
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
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
