#include "Global.h"

ConData_t s_sysConData_t;                                     /* 系统控制数据 */
Uint16 s_maintCMDExeState_u16 = 0U;                          /* 维护指令执行状态 */
Uint16 s_maintCMDExeCnt_u16 = 0U;                            /* 维护指令执行计数 */
RIU429SendData_t s_RIUSendData_t;                            /* RIU429发送数据 */
ControlModeDebounce_t s_controlModeDebounce_t = {WORK_MODE_STANDBY, 0U}; /* 控制模式切换去抖数据 */
Uint16 s_controlModeReentryLatch_u16 = INVALID;             /* 任务正常结束后的模式重入锁存 */
RefuelModeContext_t s_refuelCtx_t;                           /* 加油模式过程数据 */
ReceiveModeContext_t s_receiveCtx_t;                         /* 受油模式过程数据 */
PreTaskCheckContext_t s_preTaskCheckCtx_t;                   /* 任务前检查过程数据 */
ControlFaultDebounce_t s_controlFaultDebounce_t;             /* 控制故障去抖数据 */
ControlFaultEval_t s_controlFaultEval_t;                     /* 控制故障评估结果 */
Uint16 s_controlFaultTripActive_u16 = INVALID;               /* 控制故障触发标志 */
Uint16 s_controlFaultClearCnt_u16 = 0U;                      /* 控制故障解除确认计数 */
Uint16 s_controlFaultRecoveryCooldownCnt_u16 = 0U;           /* 控制故障恢复冷却计数 */
Uint32 s_initStateStartTime_u32 = 0UL;                       /* 0INIT 状态起始时间戳,用于超时保护 */

/* ***************************************************************** */
/**
 * 【函数名】:AirOilModeUpdate
 *
 * 【功能描述】按当前工作模式刷新高低压加油语义
 *             固定翼加油模式统一视为高压，直升机加油模式统一视为低压
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       待机/受油/维护态保持当前安全默认值，不额外引入新的模式源
 * 【返回】	   无
 */
/* ***************************************************************** */
static void AirOilModeUpdate(void)
{
    switch (s_sysConData_t.workMode_u16)
    {
        /* 固定翼加油模式 → 高压语义(LP/RP/LRP均归此类) */
        case WORK_MODE_LP_FIXEDWING:
        case WORK_MODE_RP_FIXEDWING:
        case WORK_MODE_LRP_FIXEDWING:
            s_sysConData_t.OilMode_u16 = AIR_OIL_MODE_H;
            break;

        /* 直升机加油模式 → 低压语义 */
        case WORK_MODE_LP_HELI:
        case WORK_MODE_RP_HELI:
        case WORK_MODE_LRP_HELI:
            s_sysConData_t.OilMode_u16 = AIR_OIL_MODE_L;
            break;

        /* 非加油模式:保持当前OilMode不变,不做切换 */
        default:
            break;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RIU429SendDataGet
 *
 * 【功能描述】获取RIU 429发送上下文
 *             供通信发送链路读取当前控制模块组织好的RIU发送数据
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       返回内部静态数据指针，只允许外部只读访问
 * 【返回】	   RIU429SendData_t常量指针
 */
/* ***************************************************************** */
const RIU429SendData_t* RIU429SendDataGet(void)
{
    return &s_RIUSendData_t;
}

/* ***************************************************************** */
/**
 * 【函数名】:ConDataGet
 *
 * 【功能描述】获取系统控制事实源数据
 *             供外部模块读取控制状态、输出状态和运行期关键量
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       返回内部静态数据指针，只允许外部只读访问
 * 【返回】	   ConData_t常量指针
 */
/* ***************************************************************** */
const ConData_t* ConDataGet(void)
{
    return &s_sysConData_t;
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlRIUActiveSourceSelect
 *
 * 【功能描述】选择当前有效的RIU数据源
 *             先按commDataSourse配置选择优先路，若优先路异常则回退到其余可用通道
 * 【输入参数说明】vp_commID_u16:返回选中的RIU通道号
 *               vp_valid_u16:返回是否找到有效通道
 * 【输出参数说明】vp_commID_u16:输出选中的RIU通道号
 *               vp_valid_u16:输出有效标志
 * 【其他说明】       该函数只负责选路，不缓存RIU快照数据
 * 【返回】	   最终选中的RIU通道号
 */
/* ***************************************************************** */
Uint16 ControlRIUActiveSourceSelect(Uint16 *vp_commID_u16, Uint16 *vp_valid_u16)
{
    Uint16 l_preferredID_u16 = COMM429_RIU_1; /* 优先通道，用于记录当前优先RIU通道。 */
    Uint16 l_tryID_u16 = 0U;                  /* 候选通道，用于遍历候选RIU通道。 */
    A429Info_t l_rxState_t;                   /* 接收状态，用于暂存RIU接收状态。 */
    Uint16 l_found_u16 = INVALID;             /* 找到标志，用于标记是否已找到有效RIU通道。 */
    Uint16 l_selectedID_u16 = COMM429_RIU_1;  /* 最终通道，用于记录最终选中的RIU通道。 */
    memset(&l_rxState_t, 0, sizeof(l_rxState_t));

    /* 先按当前通信来源记录选择优先RIU通道，再决定是否需要回退。 */
    if (COMM_SOURCE_2 == s_sysConData_t.commDataSourse_un16.bit.RIU)
    {
        l_preferredID_u16 = COMM429_RIU_2;
    }
    else if (COMM_SOURCE_3 == s_sysConData_t.commDataSourse_un16.bit.RIU)
    {
        l_preferredID_u16 = COMM429_RIU_3;
    }

    l_rxState_t = Comm429RIURxStateGet(l_preferredID_u16);
    if (RX429_STATE_OK == l_rxState_t.rxState_u16)
    {
        l_selectedID_u16 = l_preferredID_u16;
        l_found_u16 = VALID;
    }

    /* 优先路异常时，按剩余通道顺序寻找第一路可用RIU数据。 */
    if (INVALID == l_found_u16)
    {
        for (l_tryID_u16 = 0U; l_tryID_u16 < COMM429_RIU_NUM; l_tryID_u16++)
        {
            if (l_tryID_u16 == l_preferredID_u16)
            {
                continue;
            }

            l_rxState_t = Comm429RIURxStateGet(l_tryID_u16);
            if (RX429_STATE_OK == l_rxState_t.rxState_u16)
            {
                l_selectedID_u16 = l_tryID_u16;
                l_found_u16 = VALID;
                break;
            }
        }
    }

    if (NULL != vp_commID_u16)
    {
        if (VALID == l_found_u16)
        {
            *vp_commID_u16 = l_selectedID_u16;
        }
        else
        {
            *vp_commID_u16 = l_preferredID_u16;
        }
    }
    if (NULL != vp_valid_u16)
    {
        *vp_valid_u16 = l_found_u16;
    }

    if (VALID == l_found_u16)
    {
        return l_selectedID_u16;
    }

    return l_preferredID_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:MaintCMDExeStateClear
 *
 * 【功能描述】更新维护指令执行状态
 *             仅接收“执行完成”或“收到新指令”两种合法状态码
 * 【输入参数说明】v_exeState_u16:新的维护指令执行状态
 * 【输出参数说明】无
 * 【其他说明】       非法状态码直接忽略
 * 【返回】	   无
 */
/* ***************************************************************** */
void MaintCMDExeStateClear(Uint16 v_exeState_u16)
{
    if ((MAINT_CMD_EXE_DONE == v_exeState_u16) || (MAINT_CMD_EXE_NEW == v_exeState_u16))
    {
        s_maintCMDExeState_u16 = v_exeState_u16;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RandomDataGenerate
 *
 * 【功能描述】生成启动期主备随机仲裁字段
 *             从ADC结果寄存器提取中间8位，随CCDL基础帧上报给对端
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       仅在启动期轮值冲突或轮值无效时参与主备判定
 * 【返回】	   8位随机数据
 */
/* ***************************************************************** */
Uint16 RandomDataGenerate(void)
{
    Uint16 l_randomData_u16 = HardXintUint16Read(ADC_RESULTS_REG_BASE); /* 原始随机值，用于暂存ADC原始值并提取随机字段。 */
    return (Uint16)((l_randomData_u16 >> 4U) & 0xFFU);
}

/* ***************************************************************** */
/**
 * 【函数名】:SysWorkTimeUpdate
 *
 * 【功能描述】更新系统工作时间
 *             根据上电后累计运行时间，刷新本次工作时间和累计工作时间
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       基准累计时间仅在首次调用时从NVM快照中建立
 * 【返回】	   无
 */
/* ***************************************************************** */
static void SysWorkTimeUpdate(void)
{
    Uint32 l_tickTime_u32 = 0UL;         /* 当前节拍时间，用于记录当前系统节拍时间。 */
    static Uint16 s_l_baseTime_u16 = 0U; /* 累计时间基值，用于缓存上电时恢复的累计工作时间基值。 */
    static Uint16 s_l_initFlag_u16 = 0U; /* 初始化标志，用于标记累计时间基值是否已初始化。 */

    /* 基准累计时间只在首次调用时建立，后续只叠加本次上电工作时间。 */
    if (0U == s_l_initFlag_u16)
    {
        s_l_initFlag_u16 = 1U;
        s_l_baseTime_u16 = s_sysConData_t.sysWorkTimeSum_u16;
    }

    l_tickTime_u32 = sysTime();
    s_sysConData_t.sysWorkTime_u16 = (Uint16)(l_tickTime_u32 / 60000UL);
    s_sysConData_t.sysWorkTimeSum_u16 = s_l_baseTime_u16 + s_sysConData_t.sysWorkTime_u16;

    if (s_sysConData_t.sysWorkTimeSum_u16 > TMIE_WORK_SUM_MAX)
    {
        s_sysConData_t.sysWorkTimeSum_u16 = 0U;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:SysWorkTimeGet
 *
 * 【功能描述】获取系统累计工作时间
 *             返回当前控制模块维护的累计工作时间，单位为分钟
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       无
 * 【返回】	   系统累计工作时间
 */
/* ***************************************************************** */
Uint16 SysWorkTimeGet(void)
{
    return s_sysConData_t.sysWorkTimeSum_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:SysConDataUpdate
 *
 * 【功能描述】更新系统控制运行数据
 *             刷新工作时间、数据来源、模式数据、维护指令覆盖项和输出相关中间量
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       维护控制指令有效时，会覆盖当前KZZZ控制输出指令1
 * 【返回】	   无
 */
/* ***************************************************************** */
static void SysConDataUpdate(void)
{

    /* 更新系统工作时间 */
    SysWorkTimeUpdate();
    /* 更新通信数据来源 */
    CommDataSourceUpdate();
    /* 获取当前工作模式数据 */
    WorkModeDataObtain();
    /* 更新加油模式 */
    AirOilModeUpdate();
    /* 更新备用功能状态 */
    StandbyFuncUpdate();
    /* 更新地面维护状态 */
    GroundMaintStateUpdate();

    /* 获取CHV控制数据 */
    CHVConDataObtain();
    /* 更新运行角色 */
    RuntimeRoleUpdate();
    /* 更新控制输出状态 */
    ConOutStateUpdate();
}

/* ***************************************************************** */
/**
 * 【函数名】:SysControl
 *
 * 【功能描述】系统控制主流程
 *             每拍按“状态判断-数据更新-状态处理-输出执行”的顺序完成控制闭环
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       入口处会先清空本拍故障评估结果，再由后续流程重新生成
 * 【返回】	   无
 */
/* ***************************************************************** */
void SysControl(void)
{
    /* 故障评估结果按拍清空，确保本拍结论完全由后续流程重新生成。 */
    s_controlFaultEval_t.commFault_u16 = INVALID;
    s_controlFaultEval_t.measureFault_u16 = INVALID;
    s_controlFaultEval_t.imbalanceFault_u16 = INVALID;
    s_controlFaultEval_t.hasFault_u16 = INVALID;
    s_controlFaultEval_t.reason_u16 = RECEIVE_RIU_REASON_NONE;

    /* 主流程顺序固定为：先判状态，再刷新事实源，然后执行状态处理，最后统一下发输出。 */
    SysStateJudge();
    SysConDataUpdate();
    SysStateProcess();
    SysControlOut();
}

/* ***************************************************************** */
/**
 * 【函数名】:SysControlPowerDown
 *
 * 【功能描述】掉电态最小控制处理
 *             仅保留掉电恢复判定、安全默认收口和输出关闭，不再执行完整控制闭环
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       掉电态退出后的完整控制逻辑由后续正常调度重新接管
 * 【返回】     无

 *
 */
/* ***************************************************************** */
void SysControlPowerDown(void)
{
    SysStateJudge();

    if (SYS_STATE_4POWERDOWN == s_sysConData_t.sysState_u16)
    {
        SysStateProcess();
    }

    /* 掉电态及恢复边界统一强制关闭发送授权，确保控制链保持安全收口。 */
    s_sysConData_t.ConOutData_t.localChvPermit_u16 = CHV_INVALID;
    s_sysConData_t.CHVIn_un16.bit.myCHV_u16 = CHV_INVALID;
    s_sysConData_t.ConOutData_t.conOutState_u16 = CON_OUT_STATE_INVALID;
    SysControlOut();
}

/* ***************************************************************** */
/**
 * 【函数名】:SysConInit
 *
 * 【功能描述】系统控制模块初始化
 *             完成控制状态、输出状态、维护状态、工作时间和通道基础信息的上电初始化
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       初始化只建立控制模块自身事实源，不负责余度池和通信模块初始化
 * 【返回】	   无
 */
/* ***************************************************************** */
void SysConInit(void)
{
    SpeData_t l_nvmData_t;         /* NVM数据，用于暂存NVM读取出的累计工作时间数据。 */
    Uint16 l_IDData_u16 = 0U;      /* 通道编码，用于暂存维护IO给出的通道ID编码。 */
    Uint32 l_sysTime_u32 = 0UL;    /* 初始化时间，用于记录初始化时的系统时间。 */

    /* 先清零维护执行与故障恢复上下文，避免继承上次运行状态。 */
    s_maintCMDExeState_u16 = MAINT_CMD_EXE_DONE;
    s_maintCMDExeCnt_u16 = 0U;
    s_RIUSendData_t.dataCount_u16 = 0U;
    s_controlFaultTripActive_u16 = INVALID;
    s_controlFaultClearCnt_u16 = 0U;
    s_controlFaultRecoveryCooldownCnt_u16 = 0U;
    s_preTaskCheckCtx_t.commandIssued_u16 = INVALID;
    s_preTaskCheckCtx_t.rcvChecked_u16 = INVALID;
    s_preTaskCheckCtx_t.valveChecked_u16 = INVALID;
    s_preTaskCheckCtx_t.measureChecked_u16 = INVALID;
    s_preTaskCheckCtx_t.rcvTimeoutFault_u16 = INVALID;
    s_preTaskCheckCtx_t.valveTimeoutFault_u16 = INVALID;
    s_preTaskCheckCtx_t.measureFault_u16 = INVALID;
    ControlModeReentryLatchReset();
    s_initStateStartTime_u32 = sysTime();
    ControlModeDebounceReset();

    /* 先整体清零，再只设置非零或有明确语义的默认值。 */
    memset(&s_sysConData_t, 0, sizeof(s_sysConData_t));

    /* 这里建立控制模块核心事实源的初始状态，默认按待机、自动、初始通道处理。 */
    s_sysConData_t.sysState_u16 = SYS_STATE_0INIT;
    s_sysConData_t.sysStateLast_u16 = SYS_STATE_0INIT;
    s_sysConData_t.workMode_u16 = WORK_MODE_STANDBY;
    s_sysConData_t.workModeLast_u16 = WORK_MODE_STANDBY;
    s_sysConData_t.OilMode_u16 = AIR_OIL_MODE_L;
    s_sysConData_t.ChType_u16 = CH_TYPE_INIT;
    s_sysConData_t.ChTypeCode_u16 = TYPEJUDGE_CODE_NONE;
    s_sysConData_t.airOilEndState_u16 = AIR_CON_END_STATE_INVALID;
    s_sysConData_t.conMode_u16 = CON_MODE_AUTO;
    s_sysConData_t.conModeFlag_u16 = CON_MODE_FLAG_INVALID;
    s_sysConData_t.maintFunc_u16 = MAINT_FUNC_0_INVALID;
    s_sysConData_t.conFunc_u16 = CON_FUNC_0_STANDBY;
    s_sysConData_t.conFuncLast_u16 = CON_FUNC_0_STANDBY;
    s_sysConData_t.runtimeRole_u16 = ROLE_BACKUP;
    s_sysConData_t.peerAlive_u16 = INVALID;
    s_sysConData_t.peerCtrlSeen_u16 = INVALID;

    /* 预位/执行阶段相关私有上下文在上电时一并复位，避免继承上次任务残留。 */
    s_refuelCtx_t.targetTank_u16 = 0U;
    s_refuelCtx_t.commandSent_u16 = INVALID;
    s_refuelCtx_t.presetReady_u16 = INVALID;
    s_refuelCtx_t.supplySource_u16 = SUPPLY_SOURCE_TANK0;
    s_refuelCtx_t.balancingValveClosed_u16 = BALANCING_VALVE_NONE;

    s_sysConData_t.commDataSourse_un16.all = COMM_SOURCE_1;

    /* 通道ID来自维护IO编码。若编码异常，则统一回落到通道1。 */
    l_IDData_u16 = HardXintUint16Read(CPLD_ADDR_R_HKA_DATA1);
    l_IDData_u16 = ((l_IDData_u16 >> 12U) & 0x3U )+ 1U;
    if (SYS_CH_ID_2 == l_IDData_u16)
    {
        s_sysConData_t.myChID_u16 = SYS_CH_ID_2;
    }
    else
    {
        s_sysConData_t.myChID_u16 = SYS_CH_ID_1;
    }

    l_sysTime_u32 = sysTime();
    s_sysConData_t.sysWorkTime_u16 = (Uint16)(l_sysTime_u32 / 60000UL);

    /* 累计工作时间优先从NVM恢复。若读取失败，则按首次上电处理。 */
    SpeDataGet(SPE_DATA_DINDEX_SYS_TIME_SUM, &l_nvmData_t);
    if (SPE_DATA_STATE_OK == l_nvmData_t.dataState_u16)
    {
        s_sysConData_t.sysWorkTimeSum_u16 = l_nvmData_t.dataU_u16;
    }
    s_sysConData_t.Comm429_Aperi_Flag_u32 = COMM_APERI_TX_FLAG_INVALID;

    s_sysConData_t.ConOutData_t.conOutState_u16 = CON_OUT_STATE_INVALID;

    /* 上电初值保持保守无效状态，以避免在自检和主备仲裁前对外宣告本通道可控。 */
    s_sysConData_t.ConOutData_t.localChvPermit_u16 = CHV_INVALID;
    s_sysConData_t.CHVIn_un16.bit.myCHV_u16 = CHV_INVALID;
    s_sysConData_t.CHVIn_un16.bit.otherCHV_u16 = CHV_INVALID;
    s_sysConData_t.CHVIn_un16.bit.WDV_u16 = WDV_IN_NOMAL;
    s_sysConData_t.CHVIn_un16.bit.CPUV_u16 = CPUV_IN_NOMAL;
    s_sysConData_t.CHVIn_un16.bit.LATCH_EN_u16 = LATCH_EN_VALID;

    /* 初始化末尾统一下发一次输出，以保证硬件侧看到的是明确的保守初始状态。 */
    SysControlOut();
}
