#include "Global.h"

/* ***************************************************************** */
/**
 * 【函数名】:ControlMeasureFaultExists
 *
 * 【功能描述】判断当前故障字是否满足测量系统故障组合条件
 *             统一把总测量故障、降级和各翼箱传感器故障视为测量异常
 * 【输入参数说明】v_faultInfo_un16：故障字快照
 * 【输出参数说明】无
 * 【其他说明】       与加油/受油阶段内的测量故障口径保持一致
 * 【返回】          VALID-异常 / INVALID-正常
 */
/* ***************************************************************** */
static Uint16 ControlMeasureFaultExists(union faultInfo_Data v_faultInfo_un16)
{
    /* 综合判定:4个信号转换盒 + 5个油量传感器任一异常即视为测量故障(供控制层使用)。
     * 注: docx 0o264 故障字只含 1-4 号信号转换盒 + 0-4 号油量传感器, 不含 oilMS。
     *      oilMS 测量故障由控制器内部逻辑(RIUfltInfo2_t)维护, 不参与本次协议故障判定。 */
    if ((0U != v_faultInfo_un16.bit.STB1_fault_u16) ||
        (0U != v_faultInfo_un16.bit.STB2_fault_u16) ||
        (0U != v_faultInfo_un16.bit.STB3_fault_u16) ||
        (0U != v_faultInfo_un16.bit.STB4_fault_u16) ||
        (0U != v_faultInfo_un16.bit.tank0_sensor_fault_u16) ||
        (0U != v_faultInfo_un16.bit.tank1_sensor_fault_u16) ||
        (0U != v_faultInfo_un16.bit.tank2_sensor_fault_u16) ||
        (0U != v_faultInfo_un16.bit.tank3_sensor_fault_u16) ||
        (0U != v_faultInfo_un16.bit.tank4_sensor_fault_u16))
    {
        return VALID;
    }
    else
    {
        return INVALID;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlRefuelImbalanceThresholdGet
 *
 * 【功能描述】获取当前加油工作模式对应的不平衡告警阈值
 *             固定翼按1200kg，直升机按600kg，与4.2.7任务书收敛
 * 【输入参数说明】v_workMode_u16：当前工作模式
 * 【输出参数说明】无
 * 【其他说明】       非直升机模式默认按固定翼阈值处理
 * 【返回】          阈值（kg）
 */
/* ***************************************************************** */
static float ControlRefuelImbalanceThresholdGet(Uint16 v_workMode_u16)
{
    /* 直升机600kg,其他模式默认按固定翼1200kg处理 */
    switch (v_workMode_u16)
    {
        case WORK_MODE_LP_HELI:
        case WORK_MODE_RP_HELI:
        case WORK_MODE_LRP_HELI:
            return 600.0F;

        default:
            /* 默认固定翼阈值1200kg */
            return 1200.0F;
    }
}


/* ***************************************************************** */
/**
 * 【函数名】:ControlFaultDebounceUpdate
 *
 * 【功能描述】控制故障去抖更新
 *             对单类原始故障进行计数确认，达到确认拍数后输出有效故障
 * 【输入参数说明】v_raw_u16:原始故障值
 *               v_p_count_u16:对应故障去抖计数指针
 * 【输出参数说明】无
 * 【其他说明】       原始故障清除时计数同步清零
 * 【返回】	   去抖确认后的故障结果
 */
/* ***************************************************************** */
static Uint16 ControlFaultDebounceUpdate(Uint16 v_raw_u16, Uint16 *v_p_count_u16)
{
    if (NULL == v_p_count_u16)
    {
        return INVALID;
    }

    if (VALID == v_raw_u16)
    {
        if (*v_p_count_u16 < 0xFFFFU)
        {
            (*v_p_count_u16)++;
        }
    }
    else
    {
        *v_p_count_u16 = 0U;
    }

    if (*v_p_count_u16 >= CONTROL_FAULT_CONFIRM_CYCLES)
    {
        return VALID;
    }
    else
    {
        return INVALID;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlFaultDebounceReset
 *
 * 【功能描述】复位控制故障去抖计数
 *             将通信故障、测量故障和不平衡故障的确认计数全部清零
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       进入默认态、故障恢复等路径会调用该函数
 * 【返回】	   无
 */
/* ***************************************************************** */
void ControlFaultDebounceReset(void)
{
    s_controlFaultDebounce_t.commCnt_u16 = 0U;
    s_controlFaultDebounce_t.measureCnt_u16 = 0U;
    s_controlFaultDebounce_t.imbalanceCnt_u16 = 0U;
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlFaultRawExists
 *
 * 【功能描述】检查当前是否存在原始控制故障
 *             综合RIU通信有效性、测量系统故障和油量不平衡结果进行快速判定
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       用于TASK_END恢复判据，返回的是未经去抖的原始结果
 * 【返回】	   原始故障是否存在
 */
/* ***************************************************************** */
Uint16 ControlFaultRawExists(void)
{
    RedunData_t l_redunData_t;             /* 冗余池数据，用于暂存余度池读取结果。 */
    union faultInfo_Data l_faultInfo_un16; /* 故障反馈，用于暂存故障位快照。 */
    float l_imbalanceDiff_f;               /* 不平衡差值，用于记录2号与3号油量差值绝对值。 */
    Uint16 l_valid_u16 = INVALID;          /* RIU有效标志，用于标记当前是否存在有效RIU来源。 */
    float l_limitAlarm_f = 1200.0F;        /* 当前机型不平衡告警阈值。 */
    const ConData_t *lc_p_conData_t = ConDataGet();

    /* 控制链没有有效RIU源时，直接视为原始故障成立。 */
    (void)ControlRIUActiveSourceSelect(NULL, &l_valid_u16);
    if (VALID != l_valid_u16)
    {
        return VALID;
    }

    l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FAULTINFO);
    l_faultInfo_un16.all = (Uint16)(l_redunData_t.dataU_u32 & 0xFFFFU);
    if (VALID == ControlMeasureFaultExists(l_faultInfo_un16))
    {
        return VALID;
    }

    l_imbalanceDiff_f = RedunDataGet(REDUN_INDEX_RIU_FQ_TANK2).dataF_f - RedunDataGet(REDUN_INDEX_RIU_FQ_TANK3).dataF_f;
    if (l_imbalanceDiff_f < 0.0F)
    {
        l_imbalanceDiff_f = -l_imbalanceDiff_f;
    }

    if (NULL != lc_p_conData_t)
    {
        l_limitAlarm_f = ControlRefuelImbalanceThresholdGet(lc_p_conData_t->workMode_u16);
    }

    if (l_imbalanceDiff_f > l_limitAlarm_f)
    {
        return VALID;
    }
    else
    {
        return INVALID;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlFaultEvaluate
 *
 * 【功能描述】评估控制故障结果
 *             对通信、测量和油量不平衡三类原始故障进行去抖并生成综合故障结论
 * 【输入参数说明】v_p_faultEval_t:故障评估结果指针
 * 【输出参数说明】v_p_faultEval_t:输出本拍综合故障结果
 * 【其他说明】       当前通信故障与测量故障共用RECEIVE_RIU_REASON_MEASURE原因码
 * 【返回】	   无
 */
/* ***************************************************************** */
void ControlFaultEvaluate(ControlFaultEval_t *v_p_faultEval_t)
{
    RedunData_t l_redunData_t;                     /* 冗余池数据，用于暂存余度池读取结果。 */
    union faultInfo_Data l_faultInfo_un16;         /* 故障反馈，用于暂存故障位快照。 */
    float l_imbalanceDiff_f;                       /* 不平衡差值，用于记录2号与3号油量差值绝对值。 */
    Uint16 l_commFaultRaw_u16 = INVALID;           /* 原始通信故障，用于记录去抖前的通信故障结果。 */
    Uint16 l_measureFaultRaw_u16 = INVALID;        /* 原始测量故障，用于记录去抖前的测量故障结果。 */
    Uint16 l_imbalanceFaultRaw_u16 = INVALID;      /* 原始不平衡故障，用于记录去抖前的不平衡故障结果。 */
    Uint16 l_valid_u16 = INVALID;                  /* RIU有效标志，用于标记当前是否存在有效RIU来源。 */
    float l_limitAlarm_f = 1200.0F;                /* 当前机型不平衡告警阈值。 */
    const ConData_t *lc_p_conData_t = ConDataGet();

    if (NULL == v_p_faultEval_t)
    {
        return;
    }

    v_p_faultEval_t->commFault_u16 = INVALID;
    v_p_faultEval_t->measureFault_u16 = INVALID;
    v_p_faultEval_t->imbalanceFault_u16 = INVALID;
    v_p_faultEval_t->hasFault_u16 = INVALID;
    v_p_faultEval_t->reason_u16 = RECEIVE_RIU_REASON_NONE;

    /* 控制链无有效RIU源时，通信故障原始量直接成立。 */
    (void)ControlRIUActiveSourceSelect(NULL, &l_valid_u16);
    if (VALID != l_valid_u16)
    {
        l_commFaultRaw_u16 = VALID;
    }

    l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FAULTINFO);
    l_faultInfo_un16.all = (Uint16)(l_redunData_t.dataU_u32 & 0xFFFFU);
    if (VALID == ControlMeasureFaultExists(l_faultInfo_un16))
    {
        l_measureFaultRaw_u16 = VALID;
    }

    l_imbalanceDiff_f = RedunDataGet(REDUN_INDEX_RIU_FQ_TANK2).dataF_f - RedunDataGet(REDUN_INDEX_RIU_FQ_TANK3).dataF_f;
    if (l_imbalanceDiff_f < 0.0F)
    {
        l_imbalanceDiff_f = -l_imbalanceDiff_f;
    }
    if (NULL != lc_p_conData_t)
    {
        l_limitAlarm_f = ControlRefuelImbalanceThresholdGet(lc_p_conData_t->workMode_u16);
    }
    if (l_imbalanceDiff_f > l_limitAlarm_f)
    {
        l_imbalanceFaultRaw_u16 = VALID;
    }

    /* 三类故障分别去抖，避免瞬态抖动直接推动状态机进入TASK_END。 */
    v_p_faultEval_t->commFault_u16 =
        ControlFaultDebounceUpdate(l_commFaultRaw_u16, &s_controlFaultDebounce_t.commCnt_u16);
    v_p_faultEval_t->measureFault_u16 =
        ControlFaultDebounceUpdate(l_measureFaultRaw_u16, &s_controlFaultDebounce_t.measureCnt_u16);
    v_p_faultEval_t->imbalanceFault_u16 =
        ControlFaultDebounceUpdate(l_imbalanceFaultRaw_u16, &s_controlFaultDebounce_t.imbalanceCnt_u16);

    if ((VALID == v_p_faultEval_t->commFault_u16) || (VALID == v_p_faultEval_t->measureFault_u16))
    {
        /* 原因归并优先级：通信故障与测量故障共用“测量类原因码”，优先于不平衡故障。 */
        v_p_faultEval_t->hasFault_u16 = VALID;
        v_p_faultEval_t->reason_u16 = RECEIVE_RIU_REASON_MEASURE;
    }
    else if (VALID == v_p_faultEval_t->imbalanceFault_u16)
    {
        v_p_faultEval_t->hasFault_u16 = VALID;
        v_p_faultEval_t->reason_u16 = RECEIVE_RIU_REASON_IMBALANCE;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlFaultActionApply
 *
 * 【功能描述】应用控制故障动作
 *             根据综合故障结果刷新RIU故障发送状态，并在需要时推动控制功能进入TASK_END
 * 【输入参数说明】v_p_faultEval_t:故障评估结果
 *               v_p_ConData_t:系统控制数据指针
 * 【输出参数说明】无
 * 【其他说明】       仅在未处于恢复冷却期且当前不在待机/TASK_END时触发跳转
 * 【返回】	   无
 */
/* ***************************************************************** */
void ControlFaultActionApply(const ControlFaultEval_t *v_p_faultEval_t, ConData_t *v_p_ConData_t)
{
    if ((NULL == v_p_faultEval_t) || (NULL == v_p_ConData_t))
    {
        return;
    }

    if (VALID == v_p_faultEval_t->measureFault_u16)
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.oilMS_falut_u16 = 1U;
    }
    else
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.oilMS_falut_u16 = 0U;
    }

    if (VALID == v_p_faultEval_t->hasFault_u16)
    {
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_FAULT;
        s_RIUSendData_t.checkState_u16 = v_p_faultEval_t->reason_u16;

        /* 故障动作只在允许触发的功能态内生效，避免待机态被重复改写。 */
        if ((0U == s_controlFaultRecoveryCooldownCnt_u16) &&
            (CON_FUNC_4_TASK_END != v_p_ConData_t->conFunc_u16) &&
            (CON_FUNC_0_STANDBY != v_p_ConData_t->conFunc_u16))
        {
            s_controlFaultTripActive_u16 = VALID;
            s_controlFaultClearCnt_u16 = 0U;
            v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
            v_p_ConData_t->conFunc_u16 = CON_FUNC_4_TASK_END;
            v_p_ConData_t->workModeTime_u32 = sysTime();
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlFaultEvalGet
 *
 * 【功能描述】获取本拍控制故障评估结果
 *             对外提供控制模块缓存的故障评估快照
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       返回值按值拷贝，不暴露内部缓存指针
 * 【返回】	   控制故障评估结果
 */
/* ***************************************************************** */
ControlFaultEval_t ControlFaultEvalGet(void)
{
    return s_controlFaultEval_t;
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlErrStoreFlagGet
 *
 * 【功能描述】获取系统级故障存储触发标志
 *             对BIT结果、控制故障结果、通信来源和关键余度状态做签名比较
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       任一关键状态变化都会触发一次故障存储
 * 【返回】	   故障存储触发标志
 */
/* ***************************************************************** */
Uint16 ControlErrStoreFlagGet(void)
{
    Uint16 l_rData_u16 = ERR_STORE_FLAG_OFF;
    /* 收集本次的BIT、控制故障评估、控制上下文快照 */
    ControlFaultEval_t l_faultEval_t = ControlFaultEvalGet();
    const ConData_t *lc_p_conData_t = ConDataGet();
    RedunData_t l_riuState_t = RedunDataGet(REDUN_INDEX_RIU_HEART);
    RedunData_t l_kzzzLeftState_t = RedunDataGet(REDUN_INDEX_KZZZ_L_CURR_TIME_REQ);
    RedunData_t l_kzzzRightState_t = RedunDataGet(REDUN_INDEX_KZZZ_R_CURR_TIME_REQ);
    /* 收集通信源 / RIU心跳 / 左右吊舱 / CCDL 关键余度状态 */
    RedunData_t l_ccdlState_t = RedunDataGet(REDUN_INDEX_CCDL_SYSST);
    Uint32 l_ifbit_u32 = IFBITResultGet(IFBIT_DINDEX_RESULTS_BIT32_1);
    Uint32 l_mbit_u32 = MBITResultGet(MBIT_DINDEX_RESULTS_BIT32_1);
    static Uint32 l_s_ifbit_u32 = 0UL;
    static Uint32 l_s_mbit_u32 = 0UL;
    static Uint16 l_s_reason_u16 = RECEIVE_RIU_REASON_NONE;
    static Uint16 l_s_checkState_u16 = RECEIVE_RIU_REASON_NONE;
    static Uint16 l_s_hasFault_u16 = INVALID;
    static Uint16 l_s_commFault_u16 = INVALID;
    static Uint16 l_s_measureFault_u16 = INVALID;
    static Uint16 l_s_imbalanceFault_u16 = INVALID;
    static Uint16 l_s_commSource_u16 = 0U;
    static Uint16 l_s_riuState_u16 = REDUN_DATA_STATE_ERR;
    static Uint16 l_s_kzzzLeftState_u16 = REDUN_DATA_STATE_ERR;
    static Uint16 l_s_kzzzRightState_u16 = REDUN_DATA_STATE_ERR;
    static Uint16 l_s_ccdlState_u16 = REDUN_DATA_STATE_ERR;

    /* 同时检查指针有效性和13个关键签名的当前值与上次缓存是否一致 */
    if ((NULL != lc_p_conData_t) &&
        ((l_s_ifbit_u32 != l_ifbit_u32) ||
         (l_s_mbit_u32 != l_mbit_u32) ||
         (l_s_reason_u16 != l_faultEval_t.reason_u16) ||
         (l_s_checkState_u16 != s_RIUSendData_t.checkState_u16) ||
         (l_s_hasFault_u16 != l_faultEval_t.hasFault_u16) ||
         (l_s_commFault_u16 != l_faultEval_t.commFault_u16) ||
         (l_s_measureFault_u16 != l_faultEval_t.measureFault_u16) ||
         (l_s_imbalanceFault_u16 != l_faultEval_t.imbalanceFault_u16) ||
         (l_s_commSource_u16 != lc_p_conData_t->commDataSourse_un16.all) ||
         (l_s_riuState_u16 != l_riuState_t.dataState_u16) ||
         (l_s_kzzzLeftState_u16 != l_kzzzLeftState_t.dataState_u16) ||
         (l_s_kzzzRightState_u16 != l_kzzzRightState_t.dataState_u16) ||
         (l_s_ccdlState_u16 != l_ccdlState_t.dataState_u16)))
    {
        /* 关键签名任一变化即触发一次故障存储 */
        l_rData_u16 = ERR_STORE_FLAG_ON;
    }

    l_s_ifbit_u32 = l_ifbit_u32;
    l_s_mbit_u32 = l_mbit_u32;
    l_s_reason_u16 = l_faultEval_t.reason_u16;
    l_s_checkState_u16 = s_RIUSendData_t.checkState_u16;
    l_s_hasFault_u16 = l_faultEval_t.hasFault_u16;
    l_s_commFault_u16 = l_faultEval_t.commFault_u16;
    l_s_measureFault_u16 = l_faultEval_t.measureFault_u16;
    l_s_imbalanceFault_u16 = l_faultEval_t.imbalanceFault_u16;
    /* commSource来自上层ConData,需要再次防NULL再缓存 */
    if (NULL != lc_p_conData_t)
    {
        l_s_commSource_u16 = lc_p_conData_t->commDataSourse_un16.all;
    }
    l_s_riuState_u16 = l_riuState_t.dataState_u16;
    l_s_kzzzLeftState_u16 = l_kzzzLeftState_t.dataState_u16;
    l_s_kzzzRightState_u16 = l_kzzzRightState_t.dataState_u16;
    l_s_ccdlState_u16 = l_ccdlState_t.dataState_u16;

    /* 返回本次签名比较得到的故障存储触发标志 */
    return l_rData_u16;
}
