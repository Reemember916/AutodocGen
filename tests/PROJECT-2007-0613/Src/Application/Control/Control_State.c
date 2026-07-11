#include "Global.h"
#include "Control_State.h"
extern Uint32 s_initStateStartTime_u32;  /* 0INIT 状态起始时间戳(定义于 Control_Main.c) */
extern void ReceiveModeContextReset(void);  /* 受油模式上下文复位(定义于 Control_Receive.c) */

static RoleConfirmContext_t s_masterLossConfirmCtx_t = {INVALID, 0UL};     /* 主控本地健康失效确认窗口 */

extern void WorkModeProcessRefuel(ConData_t *v_p_ConData_t);


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

/**
 * 【函数名】:ControlRiuFuelCmdGet
 *
 * 【功能描述】控制 RIU 加油命令获取
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】加油命令数据
 */
/* ***************************************************************** */
static union fuelCmd_Data ControlRiuFuelCmdGet(void)
{
    /* 先清空命令字,再按当前活动通讯源选择有效路径 */
    union fuelCmd_Data l_cmd_t;
    RedunData_t l_redunData_t;
    Uint16 l_commID_u16 = COMM429_RIU_1;
    Uint16 l_valid_u16 = INVALID;
    memset(&l_cmd_t, 0, sizeof(l_cmd_t));

    /* 选主:ARINC429 通道有效时取该通道的 fuelCmd 联合体 */
    ControlRIUActiveSourceSelect(&l_commID_u16, &l_valid_u16);
    if (VALID == l_valid_u16)
    {
        l_cmd_t = Comm429RIURxDataGet(l_commID_u16).fuelCmd_t;
    }
    else
    /* 兜底:429通讯无效时,从冗余区取一字节命令 */
    {
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_REFUEL_CMD);
        l_cmd_t.all = (Uint8)(l_redunData_t.dataU_u32 & 0xFFU);
    }

    return l_cmd_t;
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
 * 【函数名】:PreTaskCheckTimeoutFaultApply
 *
 * 【功能描述】任务前检查超时故障应用
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】关闭阀门并触发任务退出流程
 * 【返回】NONE
 */
/* ***************************************************************** */
static void PreTaskCheckTimeoutFaultApply(void)
{
    union RCV_Data l_rcvData_un16;
    union valve1_Data l_valve1Data_un16;
    union valve2_Data l_valve2Data_un32;

    /* 入口先把本轮超时故障位全部清零:RCV、阀、计量三类 */
    s_preTaskCheckCtx_t.rcvTimeoutFault_u16 = INVALID;
    s_preTaskCheckCtx_t.valveTimeoutFault_u16 = INVALID;
    s_preTaskCheckCtx_t.measureFault_u16 = INVALID;

    /* 清空上送给RIU的故障字1(加油/放油/接头阀) */
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

    /* 读取冗余RCV状态字 */
    l_rcvData_un16.all = (Uint16)(RedunDataGet(REDUN_INDEX_RIU_RCV).dataU_u32 & 0xFFFFU);
    /* RCV0~4 任一未在关闭位,置对应故障位并标 RCV 超时故障 */
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
    l_measureOk_u16 = (VALID == RefuelMeasureFaultExists(l_faultInfo_un16)) ? INVALID : VALID;

    /* 把本拍检查结果回写到前检上下文，方便超时分支精确落故障。 */
    s_preTaskCheckCtx_t.rcvChecked_u16 = l_rcvClosed_u16;
    s_preTaskCheckCtx_t.valveChecked_u16 = l_valveClosed_u16;
    s_preTaskCheckCtx_t.measureChecked_u16 = l_measureOk_u16;

    /* 三类检查全部通过时，才允许离开前检进入预位。 */
    if ((VALID == l_rcvClosed_u16) && (VALID == l_valveClosed_u16) && (VALID == l_measureOk_u16))
    {
        /* 所有前检项都通过后，才允许进入加油预位阶段。 */
        /* 前检通过后先把RIU状态恢复为空闲口径，再切阶段。 */
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_IDLE;
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_NONE;
        /* 记录阶段切换前的旧阶段，供下拍识别“首拍进入”。 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
        /* 前检完成后正式进入加油预位。 */
        v_p_ConData_t->conFunc_u16 = CON_FUNC_2_FUEL_PRESET;
        /* 把阶段基准时间切到当前时刻，供预位阶段继续使用。 */
        v_p_ConData_t->workModeTime_u32 = l_sysTime_u32;
    }
    /* 前检超时后，不再继续等待反馈，而是按当前未满足项落故障退出。 */
    else if ((l_sysTime_u32 - v_p_ConData_t->workModeTime_u32) > PRE_TASK_CHECK_TIMEOUT_MS)
    {
        /* 超时后按当前未到位项落故障，再统一切入任务结束。 */
        PreTaskCheckTimeoutFaultApply();
        /* 前检失败统一向RIU报告故障态。 */
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_FAULT;
        /* 测量系统故障优先上报测量原因，其余前检失败统一按阀超时上报。 */
        if (VALID == s_preTaskCheckCtx_t.measureFault_u16)
        {
            s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_MEASURE;
        }
        else
        {
            s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_VALVE_TIMEOUT;
        }
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
        v_p_ConData_t->conFunc_u16 = CON_FUNC_4_TASK_END;
        v_p_ConData_t->workModeTime_u32 = l_sysTime_u32;
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
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
        v_p_ConData_t->conFunc_u16 = CON_FUNC_3_REFUEL_PROCESS;
        v_p_ConData_t->workModeTime_u32 = l_sysTime_u32;
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

        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_FAULT;
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_VALVE_TIMEOUT;
        s_refuelCtx_t.presetReady_u16 = INVALID;
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
        v_p_ConData_t->conFunc_u16 = CON_FUNC_4_TASK_END;
        v_p_ConData_t->workModeTime_u32 = l_sysTime_u32;
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
        /* 单吊舱模式在0号路径低压时切到2/3路径，之后才允许进入23号油箱平衡控制。 */
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
        /* 只有23号路径供油时才做平衡控制；该路径低压则直接中止自动空中加油。 */
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
                v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
                v_p_ConData_t->conFunc_u16 = CON_FUNC_1_PRE_TASK_CHECK;
                v_p_ConData_t->workModeTime_u32 = sysTime();
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
            s_sysConData_t.conFuncLast_u16 = s_sysConData_t.conFunc_u16;
            s_sysConData_t.conFunc_u16 = CON_FUNC_0_STANDBY;
            s_sysConData_t.workModeTime_u32 = sysTime();
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
                    s_sysConData_t.conFuncLast_u16 = s_sysConData_t.conFunc_u16;
                    s_sysConData_t.conFunc_u16 = CON_FUNC_0_STANDBY;
                    s_sysConData_t.workModeTime_u32 = sysTime();
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
            else if (PUBIT_TEST_OK != (PuBITDataGet() & PUBIT_KEY_FAULT_CODE))
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
            /* 工作态优先响应掉电，其次是BIT进入安全态，最后才允许待机下进入地面维护。 */
            l_pdCondition_u16 = PowerDownConditionCheck();
            if (POWERDOWN_COND_ENTER == l_pdCondition_u16)
            {
                l_targetState_u16 = SYS_STATE_4POWERDOWN;
            }
            else if ((IFBITResultGet(IFBIT_DINDEX_FLEVEL) >= IFBIT_FLEVEL_1) ||
                     (MBITResultGet(MBIT_DINDEX_FLEVEL) >= MBIT_FLEVEL_1))
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
            /* 地面维护态同样优先响应掉电，维护条件消失后再按BIT等级回工作/安全。 */
            l_pdCondition_u16 = PowerDownConditionCheck();
            if (POWERDOWN_COND_ENTER == l_pdCondition_u16)
            {
                l_targetState_u16 = SYS_STATE_4POWERDOWN;
            }
            else if (MAINT_GROUND_IN_COND_INVALID == l_maintCond_u16)
            {
                l_targetState_u16 =
                    ((IFBITResultGet(IFBIT_DINDEX_FLEVEL) >= IFBIT_FLEVEL_1) ||
                     (MBITResultGet(MBIT_DINDEX_FLEVEL) >= MBIT_FLEVEL_1))
                        ? SYS_STATE_2SAFETY
                        : SYS_STATE_1WORK;
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
                    l_targetState_u16 = (SYS_STATE_2SAFETY == s_sysConData_t.sysStateLast_u16) ? SYS_STATE_2SAFETY : SYS_STATE_1WORK;
                }
            }
            break;

        default:
            break;
    }

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
                                    GroundMaintProcessSoftwCRC();
                                    l_exeResult_u16 = MAINT_FUNC_EXE_RESULT_OK;
                                    break;
                                case GROUND_MAINT_FUNC_DATA_DOWNLOAD:
                                    GroundMaintProcessDataDownLoad();
                                    l_exeResult_u16 = MAINT_FUNC_EXE_RESULT_OK;
                                    break;
                                case GROUND_MAINT_FUNC_DATA_ERASE:
                                    GroundMaintProcessDataErase();
                                    l_exeResult_u16 = MAINT_FUNC_EXE_RESULT_OK;
                                    break;
                                default:
                                    l_exeResult_u16 = MAINT_FUNC_EXE_RESULT_INVALID_PARA;
                                    break;
                            }

                            CommMaintExecStatusUpdate(l_p_maintData_t->MaintFuncCode_u16, l_exeResult_u16);
                            s_maintCMDExeCnt_u16++;
                            s_maintCMDExeState_u16 = MAINT_CMD_EXE_DONE;
                        }
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

/* ***************************************************************** */
/**
 * 【函数名】:ChTypeRoundRobinCommitColdStartup
 *
 * 【功能描述】冷启动后通道类型轮询提交
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void ChTypeRoundRobinCommitColdStartup(void)
{
    Uint16 l_nextMasterChId_u16 = 0U;

    /* 当前为主控:轮询切换,把主控权交给对端通道 */
    if (ROLE_MASTER == s_sysConData_t.runtimeRole_u16)
    {
        l_nextMasterChId_u16 = (SYS_CH_ID_1 == s_sysConData_t.myChID_u16) ? SYS_CH_ID_2 : SYS_CH_ID_1;
    }
    /* 当前为备控:下一轮主控沿用本通道(轮询基点) */
    else if (ROLE_BACKUP == s_sysConData_t.runtimeRole_u16)
    {
        l_nextMasterChId_u16 = s_sysConData_t.myChID_u16;
    }

    /* 仅当计算结果落在合法通道ID时,才把下一任主控ID写入SPE持久化区 */
    if ((SYS_CH_ID_1 == l_nextMasterChId_u16) || (SYS_CH_ID_2 == l_nextMasterChId_u16))
    {
        (void)SpeDataWrite(SPE_DATA_DINDEX_CH_TYPE_CODE, l_nextMasterChId_u16);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RoleConfirmUpdate
 *
 * 【功能描述】主备角色确认更新
 *
 * 【输入参数说明】vp_ctx_t ---- 角色上下文指针
 *             v_condition_u16 ---- 当前条件
 *             v_holdTimeMs_u32 ---- 保持时间ms
 * 【输出参数说明】NONE
 * 【其他说明】主备双机根据心跳条件确认主备角色
 * 【返回】VALID / INVALID
 */
/* ***************************************************************** */
static Uint16 RoleConfirmUpdate(RoleConfirmContext_t *vp_ctx_t,
                                Uint16 v_condition_u16,
                                Uint32 v_holdTimeMs_u32)
{
    /* 取当前系统时间作为窗口判断基准 */
    Uint32 l_now_u32 = sysTime();

    /* 入参指针为空直接返回无效 */
    if (NULL == vp_ctx_t)
    {
        return INVALID;
    }

    /* 触发条件不成立,关闭确认窗口 */
    if (VALID != v_condition_u16)
    {
        vp_ctx_t->active_u16 = INVALID;
        vp_ctx_t->startTime_u32 = 0UL;
        return INVALID;
    }

    /* 首次检测到条件成立,开启新的确认窗口并记起始时间 */
    if (VALID != vp_ctx_t->active_u16)
    {
        vp_ctx_t->active_u16 = VALID;
        vp_ctx_t->startTime_u32 = l_now_u32;
        return INVALID;
    }

    /* 条件已持续达到保持时间才输出确认结果 */
    return ((l_now_u32 - vp_ctx_t->startTime_u32) >= v_holdTimeMs_u32) ? VALID : INVALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:RuntimeRoleSet
 *
 * 【功能描述】运行时角色设置
 *
 * 【输入参数说明】v_role_u16 ---- 角色值
 * 【输出参数说明】NONE
 * 【其他说明】更新s_RuntimeRole_u16并触发对应回调
 * 【返回】NONE
 */
/* ***************************************************************** */
static void RuntimeRoleSet(Uint16 v_role_u16)
{
    /* 归一化目标角色:非 MASTER 一律视为 BACKUP */
    Uint16 l_targetRole_u16 = (ROLE_MASTER == v_role_u16) ? ROLE_MASTER : ROLE_BACKUP;

    /* 仅在角色实际切换时刷新运行时上下文,避免无谓抖动 */
    if (s_sysConData_t.runtimeRole_u16 != l_targetRole_u16)
    {
        /* 写入新角色并记录进入时间 */
        s_sysConData_t.runtimeRole_u16 = l_targetRole_u16;
        s_sysConData_t.roleEnterTime_u32 = sysTime();
        /* 清空主控失效与对端CHV失效两个确认窗口 */
        s_masterLossConfirmCtx_t.active_u16 = INVALID;
        s_masterLossConfirmCtx_t.startTime_u32 = 0UL;
        s_otherChvConfirmCtx_t.active_u16 = INVALID;
        s_otherChvConfirmCtx_t.startTime_u32 = 0UL;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ChTypeJudge
 *
 * 【功能描述】主备类型判定
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void ChTypeJudge(void)
{
    Uint16 l_chType_u16 = CH_TYPE_INIT;
    Uint16 l_errorCnt_u16 = 0U;
    Uint16 l_localNextMasterChId_u16 = 0U;
    Uint16 l_peerNextMasterChId_u16 = 0U;
    Uint16 l_localPreferredValid_u16 = INVALID;
    Uint16 l_peerPreferredValid_u16 = INVALID;
    Uint16 l_puBitCpld_u16 = 0U;
    Uint16 l_puBitTx_u16 = 0U;
    Uint16 l_ccdlID_u16 = COMM_CCDL_SCI;
    Uint16 l_localRandData_u16 = 0U;
    Uint16 l_peerRandData_u16 = 0U;
    PeerBaseStatus_t l_peerBase_t;
    SpeData_t l_nvmData_t = {0};
    Uint32 l_startTime_u32 = 0UL;
    /* 启动期主备判型流程：
     * 1. 读取 NVM 中上次冷启动默认主控通道号（l_localNextMasterChId），作为本端协商建议；
     * 2. 通过 CCDL 基础帧获取对端协商建议（l_peerNextMasterChId），并校验对端数据有效性；
     * 3. 优先服从对端稳定角色：若对端已声明主控/备份，本端补位对端缺失角色；
     * 4. 对端未声明时按冷启动轮值协商：比较两端 NVM 默认主控值，一致则本端按建议落位；
     * 5. 轮值异常或FLASH轮值无效时按基础帧随机数仲裁，随机数相等则重试；
     * 6. 随机数持续相等/无新帧超时后，保守回退到硬件CHV/通道1优先（TYPEJUDGE_CODE_ERR）；
     * 7. 最终将判型结果写入 ChType_u16/ChTypeCode_u16，并更新 PuBIT 主备识别项供维护追溯。
     */
    Uint32 l_currTime_u32 = 0UL;
    memset(&l_peerBase_t, 0, sizeof(l_peerBase_t));

    l_puBitCpld_u16 = PUBITInfoGet(PUBIT_INDEX_CCDL_CPLD);
    l_puBitTx_u16 = PUBITInfoGet(PUBIT_INDEX_CCDL_TX);

    if (PUBIT_TEST_OK == l_puBitCpld_u16)
    {
        /* 启动判型优先走CPLD-CCDL直链；只有直链不可用时才回退到SCI发送+接收闭环。 */
        CommCCDLDataSend();
    }

    SpeDataGet(SPE_DATA_DINDEX_CH_TYPE_CODE, &l_nvmData_t);
    if ((SPE_DATA_STATE_OK == l_nvmData_t.dataState_u16) &&
        ((SYS_CH_ID_1 == l_nvmData_t.dataU_u16) || (SYS_CH_ID_2 == l_nvmData_t.dataU_u16)))
    {
        l_localNextMasterChId_u16 = l_nvmData_t.dataU_u16;
    }
    /* 进入启动判型前先快照本端轮值值，并清空对端轮值/仲裁主通道结果。 */
    s_sysConData_t.localPreferredMasterChId_u16 = l_localNextMasterChId_u16;
    s_sysConData_t.peerPreferredMasterChId_u16 = 0U;
    s_sysConData_t.arbMasterChId_u16 = 0U;
    CycleDogFeed();
    l_startTime_u32 = sysTime();

    /* 按CCDL基础帧周期轮询对端状态，在有限重试次数内完成启动主备收敛。 */
    while ((CH_TYPE_INIT == l_chType_u16) && (l_errorCnt_u16 < TYPEJUDGE_CNT_MAX))
    {
        l_currTime_u32 = sysTime();
        if ((l_currTime_u32 - l_startTime_u32) >= COMM_CCDL_PRIOD_MS)
        {
            l_startTime_u32 = sysTime();
            CycleDogFeed();

            if (PUBIT_TEST_OK == l_puBitCpld_u16)
            {
                /* 优先走CPLD直链读取对端基础帧，减少启动判型时延。 */
                CommCCDLDataBuffRead(COMM_CCDL_CPLD);
                CommCCDLFrameProcess(COMM_CCDL_CPLD);
                l_peerBase_t = CommCCDLPeerBaseGet(COMM_CCDL_CPLD);
                l_ccdlID_u16 = COMM_CCDL_CPLD;
            }
            else if (PUBIT_TEST_OK == l_puBitTx_u16)
            {
                Uint32 l_sciStartTime_u32 = ReadCpuTimer1Counter();
                /* 直链不可用时退回SCI发送+本端回读闭环，在PUBIT窗口内尽量完成一帧交互。 */
                CommCCDLSCIDataStartSend();

                while ((RS422_COMM_TX_FLAG_ON == CommCCDL422TxFlagGet()) &&
                       (CpuTimer1DeltaGet(l_sciStartTime_u32, ReadCpuTimer1Counter()) < PUBIT_CCDL_TIME))
                {
                    CommCCDLSCIDataSend();
                    delayUs(666UL);
                    CycleDogFeed();
                    CommCCDLDataBuffRead(COMM_CCDL_SCI);
                    CommCCDLFrameProcess(COMM_CCDL_SCI);
                    l_peerBase_t = CommCCDLPeerBaseGet(COMM_CCDL_SCI);
                    l_ccdlID_u16 = COMM_CCDL_SCI;
                }
            }

            if (VALID != CommCCDLPeerBaseAdvancedGet(l_ccdlID_u16))
            {
                /* 帧计数不前进说明本周期没看到对端新基础帧，继续发本端基础帧并累计重试。 */
                l_errorCnt_u16++;
                CommCCDLDataSend();
                continue;
            }
            if (CH_TYPE_CON == l_peerBase_t.chType_u16)
            {
                /* 对端已稳定宣称主控，则本端直接收敛为备份。 */
                l_chType_u16 = CH_TYPE_BF;
                s_sysConData_t.ChTypeCode_u16 = TYPEJUDGE_CODE_OC;
                s_sysConData_t.arbMasterChId_u16 = (SYS_CH_ID_1 == s_sysConData_t.myChID_u16) ? SYS_CH_ID_2 : SYS_CH_ID_1;
            }
            else if (CH_TYPE_BF == l_peerBase_t.chType_u16)
            {
                /* 对端已稳定宣称备份，则本端直接收敛为主控。 */
                l_chType_u16 = CH_TYPE_CON;
                s_sysConData_t.ChTypeCode_u16 = TYPEJUDGE_CODE_OM;
                s_sysConData_t.arbMasterChId_u16 = s_sysConData_t.myChID_u16;
            }
            else if (CH_TYPE_INIT == l_peerBase_t.chType_u16)
            {
                /* 对端尚未形成稳定主备时，优先按冷启动轮值协商；轮值异常时用随机数仲裁。 */
                l_peerNextMasterChId_u16 = l_peerBase_t.preferredMasterChId_u16;
                s_sysConData_t.peerPreferredMasterChId_u16 = l_peerNextMasterChId_u16;
                l_localPreferredValid_u16 =
                    ((SYS_CH_ID_1 == l_localNextMasterChId_u16) || (SYS_CH_ID_2 == l_localNextMasterChId_u16)) ? VALID : INVALID;
                l_peerPreferredValid_u16 =
                    ((SYS_CH_ID_1 == l_peerNextMasterChId_u16) || (SYS_CH_ID_2 == l_peerNextMasterChId_u16)) ? VALID : INVALID;

                if ((VALID == l_localPreferredValid_u16) &&
                    (VALID == l_peerPreferredValid_u16) &&
                    (l_localNextMasterChId_u16 == l_peerNextMasterChId_u16))
                {
                    l_chType_u16 = (s_sysConData_t.myChID_u16 == l_localNextMasterChId_u16) ? CH_TYPE_CON : CH_TYPE_BF;
                    s_sysConData_t.localPreferredMasterChId_u16 = l_localNextMasterChId_u16;
                    s_sysConData_t.ChTypeCode_u16 = TYPEJUDGE_CODE_NONE;
                    s_sysConData_t.arbMasterChId_u16 = l_localNextMasterChId_u16;
                }
                else
                {
                    l_localRandData_u16 = CommCCDLTxRandDataGet(l_ccdlID_u16);
                    l_peerRandData_u16 = l_peerBase_t.randData_u16 & 0xFFU;

                    if (l_localRandData_u16 > l_peerRandData_u16)
                    {
                        l_chType_u16 = CH_TYPE_CON;
                        s_sysConData_t.ChTypeCode_u16 = TYPEJUDGE_CODE_RAND;
                        s_sysConData_t.arbMasterChId_u16 = s_sysConData_t.myChID_u16;
                    }
                    else if (l_localRandData_u16 < l_peerRandData_u16)
                    {
                        l_chType_u16 = CH_TYPE_BF;
                        s_sysConData_t.ChTypeCode_u16 = TYPEJUDGE_CODE_RAND;
                        s_sysConData_t.arbMasterChId_u16 =
                            (SYS_CH_ID_1 == s_sysConData_t.myChID_u16) ? SYS_CH_ID_2 : SYS_CH_ID_1;
                    }
                    else
                    {
                        l_errorCnt_u16++;
                        CommCCDLDataSend();
                        continue;
                    }
                }
            }

            /* 无论本周期是否收敛，都继续发送本端基础帧，帮助对端完成同样判型。 */
            CommCCDLDataSend();
        }
    }

    if (CH_TYPE_INIT == l_chType_u16)
    {
        Uint16 l_otherChvSample_u16 = (0U != GPIOReadBitNum(GPIO_IN_DSP_CHV)) ? CHV_VALID : CHV_INVALID;
        Uint16 l_fallbackMasterChId_u16 =
            (CHV_INVALID == l_otherChvSample_u16) ? s_sysConData_t.myChID_u16 : SYS_CH_ID_1;

        /* 轮值值缺失/不一致/超时时：
         * 若硬件已确认对端CHV失效，则当前存活通道直接落主；
         * 否则继续使用CH1优先，避免通信缺失场景的双主。 */
        if (s_sysConData_t.myChID_u16 == l_fallbackMasterChId_u16)
        {
            l_chType_u16 = CH_TYPE_CON;
        }
        else
        {
            l_chType_u16 = CH_TYPE_BF;
        }
        s_sysConData_t.ChTypeCode_u16 = TYPEJUDGE_CODE_ERR;
        s_sysConData_t.arbMasterChId_u16 = l_fallbackMasterChId_u16;
    }

    /* 判型完成后固化静态主备身份，ChType运行周期内不变；控制权归属单独初始化。 */

    s_sysConData_t.ChType_u16 = l_chType_u16;

    if(CH_TYPE_CON == l_chType_u16)
    {
        s_sysConData_t.runtimeRole_u16 = ROLE_MASTER;
    }
    else
    {
        s_sysConData_t.runtimeRole_u16 = ROLE_BACKUP;
    }

    s_sysConData_t.roleEnterTime_u32 = sysTime();
    s_masterLossConfirmCtx_t.active_u16 = INVALID;
    s_masterLossConfirmCtx_t.startTime_u32 = 0UL;
    s_otherChvConfirmCtx_t.active_u16 = INVALID;
    s_otherChvConfirmCtx_t.startTime_u32 = 0UL;

    if (COLD_POW_STARTUP_MODE == StartUpModeGet())
    {
        PuBITForceResultUpdate(PUBIT_INDEX_ROLE_IDENTIFY, PUBIT_TEST_OK);
    }
}
/* ***************************************************************** */
/**
 * 【函数名】:RuntimeRoleUpdate
 *
 * 【功能描述】运行时角色状态更新
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void RuntimeRoleUpdate(void)
{
    Uint16 l_localHealthy_u16 =
        ((CHV_VALID == s_sysConData_t.ConOutData_t.localChvPermit_u16) &&
         (CHV_VALID == s_sysConData_t.CHVIn_un16.bit.myCHV_u16)) ? VALID : INVALID;
    Uint16 l_otherChvInvalidConfirmed_u16 = INVALID;
    Uint16 l_masterLossConfirmed_u16 = INVALID;
    Uint16 l_ccdlID_u16 = COMM_CCDL_SCI;
    Uint16 l_ccdlValid_u16 = INVALID;
    PeerBaseStatus_t l_peerBase_t;
    Uint32 l_currTime_u32 = 0UL;
    memset(&l_peerBase_t, 0, sizeof(l_peerBase_t));

    /* 运行期主备切换流程：
     * 1. 判定本通道本地健康（localChvPermit + myCHV 同时有效），失效则启动主控丢失确认窗口；
     * 2. 通过 CCDL 基础帧获取对端状态，判定对端 CHV 是否失效，启动对端失效确认窗口；
     * 3. RoleConfirmUpdate 以固定时间窗口（ROLE_PEER_LOSS_TIMEOUT_MS/CONTROL_OWNER_HOLD_MS）做去抖确认；
     * 4. 本地健康恢复且对端 CHV 持续失效确认后，本端升主（ROLE_MASTER）；
     * 5. 本地健康失效确认后，本端降备（ROLE_BACKUP），等待对端接管；
     * 6. 切换通过 RuntimeRoleSet 落地，并复位确认窗口上下文。
     */

    s_sysConData_t.peerAlive_u16 = INVALID;
    s_sysConData_t.peerCtrlSeen_u16 = INVALID;
    (void)ControlCCDLActiveSourceSelect(&l_ccdlID_u16, &l_ccdlValid_u16);
    if (VALID == l_ccdlValid_u16)
    {
        l_peerBase_t = CommCCDLPeerBaseGet(l_ccdlID_u16);
        l_currTime_u32 = sysTime();
        if ((VALID == l_peerBase_t.valid_u16) &&
            ((l_currTime_u32 - l_peerBase_t.lastRxTime_u32) <= ROLE_PEER_LOSS_TIMEOUT_MS))
        {
            s_sysConData_t.peerAlive_u16 = VALID;
            if (0U != (l_peerBase_t.ctrlInfo_u16 & (0x01U << COMM_CCDL_CTRLINFO_OWNER_BIT)))
            {
                s_sysConData_t.peerCtrlSeen_u16 = VALID;
            }
        }
    }
    l_otherChvInvalidConfirmed_u16 =
        RoleConfirmUpdate(&s_otherChvConfirmCtx_t,
                          (CHV_INVALID == s_sysConData_t.CHVIn_un16.bit.otherCHV_u16) ? VALID : INVALID,
                          CONTROL_OWNER_HOLD_MS);

    switch (s_sysConData_t.runtimeRole_u16)
    {
        case ROLE_MASTER:
            l_masterLossConfirmed_u16 =
                RoleConfirmUpdate(&s_masterLossConfirmCtx_t,
                                  (VALID == l_localHealthy_u16) ? INVALID : VALID,
                                  CONTROL_OWNER_HOLD_MS);
            if (VALID == l_masterLossConfirmed_u16)
            {
                RuntimeRoleSet(ROLE_BACKUP);
            }
            else if ((VALID == s_sysConData_t.peerAlive_u16) &&
                     (VALID == s_sysConData_t.peerCtrlSeen_u16) &&
                     (SYS_CH_ID_1 != s_sysConData_t.myChID_u16))
            {
                RuntimeRoleSet(ROLE_BACKUP);
            }
            break;

        case ROLE_BACKUP:
            if (VALID != l_localHealthy_u16)
            {
                RuntimeRoleSet(ROLE_BACKUP);
            }
            else if (VALID == s_sysConData_t.peerCtrlSeen_u16)
            {
                RuntimeRoleSet(ROLE_BACKUP);
            }
            else if (VALID == l_otherChvInvalidConfirmed_u16)
            {
                RuntimeRoleSet(ROLE_MASTER);
            }
            break;

        default:
            RuntimeRoleSet(ROLE_BACKUP);
            break;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommDataSourceUpdate
 *
 * 【功能描述】通信数据源切换
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void CommDataSourceUpdate(void)
{
    Uint16 l_ccdlID_u16 = COMM_CCDL_SCI;
    Uint16 l_ccdlValid_u16 = INVALID;
    Uint16 l_kzzzLeftOk_u16 = INVALID;
    Uint16 l_kzzzRightOk_u16 = INVALID;
    Uint16 l_kzzzPeerOk_u16 = INVALID;

    if (IFBIT_TEST_OK == IFBITInfoGet(IFBIT_INDEX_COMM_429RIU_1))
    {
        s_sysConData_t.commDataSourse_un16.bit.RIU = COMM_SOURCE_1;
    }
    else if (IFBIT_TEST_OK == IFBITInfoGet(IFBIT_INDEX_COMM_429RIU_2))
    {
        s_sysConData_t.commDataSourse_un16.bit.RIU = COMM_SOURCE_2;
    }
    else if (IFBIT_TEST_OK == IFBITInfoGet(IFBIT_INDEX_COMM_429RIU_3))
    {
        s_sysConData_t.commDataSourse_un16.bit.RIU = COMM_SOURCE_3;
    }
    else
    {
        s_sysConData_t.commDataSourse_un16.bit.RIU = COMM_SOURCE_INVALID;
    }

    (void)ControlCCDLActiveSourceSelect(&l_ccdlID_u16, &l_ccdlValid_u16);
    if ((VALID == l_ccdlValid_u16) && (COMM_CCDL_SCI == l_ccdlID_u16))
    {
        s_sysConData_t.commDataSourse_un16.bit.CCDL = COMM_SOURCE_1;
    }
    else if ((VALID == l_ccdlValid_u16) && (COMM_CCDL_CPLD == l_ccdlID_u16))
    {
        s_sysConData_t.commDataSourse_un16.bit.CCDL = COMM_SOURCE_2;
    }
    else
    {
        s_sysConData_t.commDataSourse_un16.bit.CCDL = COMM_SOURCE_INVALID;
    }

    /* 左右吊舱是独立业务通道，因此这里只汇总“当前KZZZ是否主要来自本地还是对端镜像”。 */
    l_kzzzLeftOk_u16 = (RX429_STATE_OK == Comm429KZZZRxStateGet(COMM429_KZZZ_1).rxState_u16) ? VALID : INVALID;
    l_kzzzRightOk_u16 = (RX429_STATE_OK == Comm429KZZZRxStateGet(COMM429_KZZZ_2).rxState_u16) ? VALID : INVALID;
    if ((VALID == l_ccdlValid_u16) &&
        ((VALID == Comm429KZZZCcdlExtValidGet(l_ccdlID_u16, COMM429_KZZZ_1)) ||
         (VALID == Comm429KZZZCcdlExtValidGet(l_ccdlID_u16, COMM429_KZZZ_2))))
    {
        l_kzzzPeerOk_u16 = VALID;
    }

    if ((VALID == l_kzzzLeftOk_u16) || (VALID == l_kzzzRightOk_u16))
    {
        s_sysConData_t.commDataSourse_un16.bit.KZZZ = COMM_SOURCE_1;
    }
    else if (VALID == l_kzzzPeerOk_u16)
    {
        s_sysConData_t.commDataSourse_un16.bit.KZZZ = COMM_SOURCE_3;
    }
    else
    {
        s_sysConData_t.commDataSourse_un16.bit.KZZZ = COMM_SOURCE_INVALID;
    }
}


/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
