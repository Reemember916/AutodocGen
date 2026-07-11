#include "Global.h"
#include "Control_State.h"

static Uint16 RoleConfirmUpdate(RoleConfirmContext_t *vp_ctx_t,
                                Uint16 v_condition_u16,
                                Uint32 v_holdTimeMs_u32);

static RoleConfirmContext_t s_masterLossConfirmCtx_t = {INVALID, 0UL};     /* 主控本地健康失效确认窗口 */
static RoleConfirmContext_t s_peerTakeoverConfirmCtx_t = {INVALID, 0UL};   /* 备通道接管确认窗口 */
static RoleConfirmContext_t s_peerFaultConfirmCtx_t = {INVALID, 0UL};      /* 对端关键故障确认窗口 */

/* ***************************************************************** */
/**
 * 【函数名】:ControlRiuFuelCmdGet
 * 【功能描述】读取当前有效RIU来源的燃油控制命令
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       本地429无有效源时回退到余度池中的命令镜像
 * 【返回】          RIU燃油控制命令字
 */
/* ***************************************************************** */
union fuelCmd_Data ControlRiuFuelCmdGet(void)
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
        /* 有活动429源时直接取实时命令，避免余度池旧镜像覆盖主链路。 */
        l_cmd_t = Comm429RIURxDataGet(l_commID_u16).fuelCmd_t;
    }
    else
    {
        /* 兜底:429通讯无效时,从冗余区取一字节命令。 */
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_REFUEL_CMD);
        l_cmd_t.all = (Uint8)(l_redunData_t.dataU_u32 & 0xFFU);
    }

    return l_cmd_t;
}



/* ***************************************************************** */
/**
 * 【函数名】:ControlMeasureFaultExists
 *
 * 【功能描述】判断当前故障字是否满足测量系统故障组合条件
 *             统一把总测量故障、降级和各翼箱传感器故障视为测量异常
 * 【输入参数说明】v_faultInfo_un16：故障字快照
 * 【输出参数说明】无
 * 【其他说明】       与加油/受油阶段内的测量故障口径保持一致(跨文件共享实现)
 * 【返回】          VALID-异常 / INVALID-正常
 */
/* ***************************************************************** */
Uint16 ControlMeasureFaultExists(union faultInfo_Data v_faultInfo_un16)
{
    Uint16 l_fault_u16 = INVALID;

    /* 综合判定:总测量故障 / 降级 / 5个油箱传感器任一异常即视为测量故障(供控制层使用) */
    if ((0U != v_faultInfo_un16.bit.oilMS_falut_u16) ||
        (0U != v_faultInfo_un16.bit.oilMS_downGrade_u16) ||
        (0U != v_faultInfo_un16.bit.tank1_sensor_fault_u16) ||
        (0U != v_faultInfo_un16.bit.tank2_sensor_fault_u16) ||
        (0U != v_faultInfo_un16.bit.tank3_sensor_fault_u16) ||
        (0U != v_faultInfo_un16.bit.tank4_sensor_fault_u16))
    {
        /* 任一测量链路异常都会影响目标量/当前量判断，控制层统一按测量异常处理。 */
        l_fault_u16 = VALID;
    }

    return l_fault_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlConFuncSwitch
 *
 * 【功能描述】控制功能阶段切换公共收口
 *             统一完成 conFuncLast/conFunc/workModeTime 三连赋值
 * 【输入参数说明】vp_ConData_t：系统控制数据指针
 * 【输入参数说明】v_conFunc_u16：目标控制功能阶段
 * 【输入参数说明】v_time_u32：阶段切换时间戳(由调用方传入,保持原 sysTime 或局部捕获时间口径)
 * 【输出参数说明】无
 * 【其他说明】       各阶段切换点复用,避免跨文件重复拼接三连语句
 * 【返回】          无
 */
/* ***************************************************************** */
void ControlConFuncSwitch(ConData_t *vp_ConData_t, Uint16 v_conFunc_u16, Uint32 v_time_u32)
{
    /* 空指针保护:避免野指针破坏控制上下文 */
    if (NULL != vp_ConData_t)
    {
        /* 记录阶段切换前的旧阶段,供下拍识别"首拍进入" */
        vp_ConData_t->conFuncLast_u16 = vp_ConData_t->conFunc_u16;
        /* 切换到目标控制功能阶段 */
        vp_ConData_t->conFunc_u16 = v_conFunc_u16;
        /* 更新阶段基准时间戳 */
        vp_ConData_t->workModeTime_u32 = v_time_u32;
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
            /* 直升机受油允许的不平衡量更小，后续故障判据直接使用600kg。 */
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
        /* 调用方没有提供计数器时，不尝试确认故障。 */
        return INVALID;
    }

    /* 去抖只做“连续确认”，不保留锁存。
     * 原始故障一旦消失，计数立即清零，后面必须重新积满确认拍数才重新成立。 */
    if (VALID == v_raw_u16)
    {
        if (*v_p_count_u16 < 0xFFFFU)
        {
            (*v_p_count_u16)++;
        }
    }
    else
    {
        /* 原始故障一消失就重新计数，避免断续抖动累计成确认故障。 */
        *v_p_count_u16 = 0U;
    }

    if (*v_p_count_u16 >= CONTROL_FAULT_CONFIRM_CYCLES)
    {
        return VALID;
    }

    return INVALID;
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
    /* 阶段重入或恢复后清空去抖上下文，下一轮故障必须重新连续确认。 */
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
        /* 没有可信RIU命令源时，继续执行控制动作比退出更危险。 */
        return VALID;
    }

    l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FAULTINFO);
    l_faultInfo_un16.all = (Uint16)(l_redunData_t.dataU_u32 & 0xFFFFU);
    if (VALID == ControlMeasureFaultExists(l_faultInfo_un16))
    {
        /* 测量异常会污染受油/加油目标判断，按控制原始故障处理。 */
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
        /* 不平衡只看当前机型阈值，不把阀位状态混进快速恢复判据。 */
        return VALID;
    }

    return INVALID;
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

    /* 评估结果每拍重新生成，不沿用上一拍结论。
     * 去抖状态保存在 s_controlFaultDebounce_t 中，输出结构只表达“本拍已确认”的故障结果。 */
    v_p_faultEval_t->commFault_u16 = INVALID;
    v_p_faultEval_t->measureFault_u16 = INVALID;
    v_p_faultEval_t->imbalanceFault_u16 = INVALID;
    v_p_faultEval_t->hasFault_u16 = INVALID;
    v_p_faultEval_t->reason_u16 = RECEIVE_RIU_REASON_NONE;

    /* 这里先分别得到三类“原始故障”，再统一走去抖和原因码归并。
     * 拆开做的原因是：控制层真正关心的是状态机是否该退出当前任务，
     * 而不是底层某一类瞬时异常刚冒出来的那个瞬间。 */
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
        /* 不平衡故障只看 2/3 号油量差和当前机型阈值，避免把平衡阀当前开闭状态混入故障判据。 */
        l_imbalanceFaultRaw_u16 = VALID;
    }

    /* 三类故障分别去抖，避免瞬态抖动直接推动状态机进入TASK_END。 */
    v_p_faultEval_t->commFault_u16 =
        ControlFaultDebounceUpdate(l_commFaultRaw_u16, &s_controlFaultDebounce_t.commCnt_u16);
    v_p_faultEval_t->measureFault_u16 =
        ControlFaultDebounceUpdate(l_measureFaultRaw_u16, &s_controlFaultDebounce_t.measureCnt_u16);
    v_p_faultEval_t->imbalanceFault_u16 =
        ControlFaultDebounceUpdate(l_imbalanceFaultRaw_u16, &s_controlFaultDebounce_t.imbalanceCnt_u16);

    /* 原因码是给上层流程和外部接口看的，所以这里按控制语义做收口。
     * 通信故障和测量故障都会让控制事实源变得不可信，因此统一归到测量类原因；
     * 只有前两类都没有成立时，才把不平衡作为主导原因抛出去。 */
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
        /* 故障动作需要同时改故障字和控制阶段，缺任一上下文都不执行。 */
        return;
    }

    if ((VALID == v_p_faultEval_t->commFault_u16) || (VALID == v_p_faultEval_t->imbalanceFault_u16))
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.EMS_fault_u16 = 1U;
    }
    else
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.EMS_fault_u16 = 0U;
    }

    if (VALID == v_p_faultEval_t->measureFault_u16)
    {
        /* 测量类故障单独点亮0232，方便上位机区分通信/测量/不平衡原因。 */
        s_RIUSendData_t.RIUfltInfo2_t.bit.oilMS_falut_u16 = 1U;
    }
    else if (!((CON_FUNC_1_PRE_TASK_CHECK == v_p_ConData_t->conFunc_u16) &&
               (VALID == s_preTaskCheckCtx_t.measureFault_u16)))
    {
        /* 前检窗口使用原始测量异常做临时上报，避免被控制故障去抖结果提前清掉。 */
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
            ControlConFuncSwitch(v_p_ConData_t, CON_FUNC_4_TASK_END, sysTime());
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
    /* 返回本拍缓存快照，不在这里重新计算故障，避免调用顺序影响结果。 */
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
    Uint16 l_rData_u16 = ERR_STORE_FLAG_OFF;
    /* 收集本轮BIT结果、控制故障评估和余度状态快照 */
    ControlFaultEval_t l_faultEval_t = ControlFaultEvalGet();
    const ConData_t *lc_p_conData_t = ConDataGet();
    /* 通信链路上层来源:RIU心跳/左右吊舱/KZZZ/CCDL */
    RedunData_t l_riuState_t = RedunDataGet(REDUN_INDEX_RIU_HEART);
    RedunData_t l_kzzzLeftState_t = RedunDataGet(REDUN_INDEX_KZZZ_L_CURR_TIME_REQ);
    RedunData_t l_kzzzRightState_t = RedunDataGet(REDUN_INDEX_KZZZ_R_CURR_TIME_REQ);
    RedunData_t l_ccdlState_t = RedunDataGet(REDUN_INDEX_CCDL_SYSST);
    /* 当前拍的IFBIT/MBIT位图(用于签名比较) */
    Uint32 l_ifbit_u32 = IFBITResultGet(IFBIT_DINDEX_RESULTS_BIT32_1);
    Uint32 l_mbit_u32 = MBITResultGet(MBIT_DINDEX_RESULTS_BIT32_1);

    /* 故障存储采用“签名跳变”口径：只在关键状态发生变化时触发。
     * 这样既能记录故障出现/消失的边沿，也避免稳定故障每拍重复写存储。 */
    /* 13个签名任一变化+ConData指针有效即触发故障存储 */
    /* 签名池覆盖:BIT结果(IFBIT+MBIT)、控制故障原因/检查状态/故障标志 */
    /* 通信链(RIU/KZZZ_L/KZZZ_R/CCDL)的余度状态，以及通信来源配置 */
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
        /* 任何关键签名跳变即产生一次故障存储请求 */
        l_rData_u16 = ERR_STORE_FLAG_ON;
    }

    /* 缓存本轮签名为下一拍边沿检测做准备 */
    l_s_ifbit_u32 = l_ifbit_u32;
    l_s_mbit_u32 = l_mbit_u32;
    l_s_reason_u16 = l_faultEval_t.reason_u16;
    l_s_checkState_u16 = s_RIUSendData_t.checkState_u16;
    l_s_hasFault_u16 = l_faultEval_t.hasFault_u16;
    l_s_commFault_u16 = l_faultEval_t.commFault_u16;
    l_s_measureFault_u16 = l_faultEval_t.measureFault_u16;
    l_s_imbalanceFault_u16 = l_faultEval_t.imbalanceFault_u16;
    /* 通信来源从ConData结构体获取，不能直接用局部变量——ConData可能为NULL */
    if (NULL != lc_p_conData_t)
    {
        l_s_commSource_u16 = lc_p_conData_t->commDataSourse_un16.all;
    }
    l_s_riuState_u16 = l_riuState_t.dataState_u16;
    l_s_kzzzLeftState_u16 = l_kzzzLeftState_t.dataState_u16;
    l_s_kzzzRightState_u16 = l_kzzzRightState_t.dataState_u16;
    l_s_ccdlState_u16 = l_ccdlState_t.dataState_u16;

    return l_rData_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:CHVControlOut
 *
 * 【功能描述】输出本通道CHV控制信号
 *             同步刷新CPLD输出寄存器和板级GPIO
 * 【输入参数说明】v_control_u16：CHV有效/无效控制值
 * 【输出参数说明】无
 * 【其他说明】       两个物理输出必须保持一致，避免上位状态和硬件回绕口径分裂
 * 【返回】	   无
 */
/* ***************************************************************** */
static void CHVControlOut(Uint16 v_control_u16)
{
    if (CHV_VALID == v_control_u16)
    {
        /* CHV有效时，同时拉高CPLD输出寄存器和板级GPIO，保持内外口径一致。 */
        HardXintUint16Write(CPLD_ADDR_W_CPUV_OUT, CPUV_IN_NOMAL);
        GPIOSetNum(GPIO_OUT_DSP_CHV);
    }
    else
    {
        /* CHV无效时，两个物理输出都必须同步撤销。 */
        HardXintUint16Write(CPLD_ADDR_W_CPUV_OUT, CPUV_IN_ERR);
        GPIOClearNum(GPIO_OUT_DSP_CHV);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlCriticalFaultExist
 *
 * 【功能描述】判断本通道是否存在任务书定义的关键等级故障
 *             仅用于安全态迁移、控制权切除和通道失效判定
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】普通 BIT 故障仍按原流程上报和存储，但不在这里泛化为关键故障
 * 【返回】VALID-存在关键故障 / INVALID-无关键故障
 */
/* ***************************************************************** */
Uint16 ControlCriticalFaultExist(void)
{
    Uint16 l_fault_u16 = INVALID; /* 本拍关键故障综合结果 */

    /* 上电关键项按任务书清单收敛:CPU、CPLD、主备识别、片上AD和5V。 */
    if (PUBIT_TEST_OK != (PuBITDataGet() & PUBIT_KEY_FAULT_CODE))
    {
        l_fault_u16 = VALID;
    }

    /* 周期BIT只取任务书列出的运行期关键项，不再用综合FLEVEL一刀切。 */
    if ((IFBIT_TEST_ERR == IFBITInfoGet(IFBIT_INDEX_AD)) ||
        (IFBIT_TEST_ERR == IFBITInfoGet(IFBIT_INDEX_P5V)) ||
        ((IFBIT_TEST_ERR == IFBITInfoGet(IFBIT_INDEX_CPLD_HEART)) &&
         (IFBIT_TEST_ERR == IFBITInfoGet(IFBIT_INDEX_COMM_CCDL_CPLD))))
    {
        l_fault_u16 = VALID;
    }

    /* 400C里的CPUV/CHV是当前控制输出链路的回绕量，不能反过来当成本端关键故障源。
     * 否则软件主动撤销CHV后，会把自己的低电平回绕误判成新故障，导致恢复路径被锁住。 */

    return l_fault_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlPeerCriticalFaultExist
 *
 * 【功能描述】判断对端是否通过现有CCDL基础状态表现出关键失效
 *             供备通道升主判据使用，最终仍由peerCtrlSeen防止双主
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】当前CCDL基础帧没有独立关键故障字，先复用对端安全态和本地健康位
 * 【返回】VALID-对端关键失效确认 / INVALID-未确认
 */
/* ***************************************************************** */
Uint16 ControlPeerCriticalFaultExist(void)
{
    PeerBaseStatus_t l_peerBase_t;             /* 对端基础帧快照 */
    Uint16 l_ccdlID_u16 = COMM_CCDL_SCI;       /* 当前选中的CCDL链路 */
    Uint16 l_ccdlValid_u16 = INVALID;          /* CCDL链路有效标志 */
    Uint16 l_peerFaultRaw_u16 = INVALID;       /* 对端关键失效原始判据 */
    Uint32 l_currTime_u32 = 0UL;               /* 当前系统时间 */

    memset(&l_peerBase_t, 0, sizeof(l_peerBase_t));
    (void)ControlCCDLActiveSourceSelect(&l_ccdlID_u16, &l_ccdlValid_u16);
    if (VALID != l_ccdlValid_u16)
    {
        (void)RoleConfirmUpdate(&s_peerFaultConfirmCtx_t, INVALID, CONTROL_CRITICAL_CONFIRM_MS);
        return INVALID;
    }

    l_peerBase_t = CommCCDLPeerBaseGet(l_ccdlID_u16);
    l_currTime_u32 = sysTime();
    if ((VALID != l_peerBase_t.valid_u16) ||
        ((l_currTime_u32 - l_peerBase_t.lastRxTime_u32) > ROLE_PEER_LOSS_TIMEOUT_MS))
    {
        (void)RoleConfirmUpdate(&s_peerFaultConfirmCtx_t, INVALID, CONTROL_CRITICAL_CONFIRM_MS);
        return INVALID;
    }

    /* 对端进入安全态，或基础帧声明“本地控制健康”无效，均视为对端已失去控制资格。 */
    if ((SYS_STATE_2SAFETY == l_peerBase_t.sysState_u16) ||
        (0U == (l_peerBase_t.ctrlInfo_u16 & (0x01U << COMM_CCDL_CTRLINFO_LOCAL_HEALTH_BIT))))
    {
        /* 对端已声明“不健康”时，不必等到基础帧完全失联才允许备份接管。 */
        l_peerFaultRaw_u16 = VALID;
    }

    return RoleConfirmUpdate(&s_peerFaultConfirmCtx_t,
                             l_peerFaultRaw_u16,
                             CONTROL_CRITICAL_CONFIRM_MS);
}

/* ***************************************************************** */
/**
 *    【函数名】:CHVConDataObtain
 *    【功能描述】采集并判定通道有效控制输入
 *    【输入参数说明】NONE
 *    【输出参数说明】NONE
 *    【其他说明】       只按任务书关键故障撤销CHV资格，普通BIT故障继续走上报/存储链路
 *    【返回】	   无
 */
/* ***************************************************************** */
void CHVConDataObtain(void)
{
    /* 先读取CPLD回绕输入，供当前拍的CHV仲裁使用。 */
    s_sysConData_t.CHVIn_un16.all = HardXintUint16Read(CPLD_ADDR_W_CPUV_IN);

    /* 关键故障才切除本通道有效资格；429、二/三次电源等普通故障不在这里直接切权。 */
    if (VALID == ControlCriticalFaultExist())
    {
        s_sysConData_t.ConOutData_t.localChvPermit_u16 = CHV_INVALID;
    }
    /* 健康恢复后也只在锁存允许释放时恢复有效，避免故障后立刻抖动恢复。 */
    else if (LATCH_EN_VALID != s_sysConData_t.CHVIn_un16.bit.LATCH_EN_u16)
    {
        s_sysConData_t.ConOutData_t.localChvPermit_u16 = CHV_VALID;
    }
}

/* ***************************************************************** */
/**
 *    【函数名】:ConOutStateUpdate
 *    【功能描述】刷新控制输出状态
 *    【输入参数说明】NONE
 *    【输出参数说明】NONE
 *    【其他说明】       该状态按拍全量计算，不依赖上一拍结果
 *    【返回】	   无
 */
/* ***************************************************************** */
void ConOutStateUpdate(void)
{
    /* 先给出保守默认值，然后只在当前拍明确满足输出条件时再放开输出。 */
    s_sysConData_t.ConOutData_t.conOutState_u16 = CON_OUT_STATE_INVALID;

    /* 当前工程只有"本端是主 + 本端资格有效 + 本端CHV回绕有效"才允许真正打开控制输出。 */
    if ((ROLE_MASTER == s_sysConData_t.runtimeRole_u16) &&
        (CHV_VALID == s_sysConData_t.ConOutData_t.localChvPermit_u16) &&
        (CHV_VALID == s_sysConData_t.CHVIn_un16.bit.myCHV_u16))
    {
        s_sysConData_t.ConOutData_t.conOutState_u16 = CON_OUT_STATE_VALID;
    }
}


/* ***************************************************************** */
/**
 *    【函数名】:SysControlOut
 *    【功能描述】执行控制输出
 *    【输入参数说明】NONE
 *    【输出参数说明】NONE
 *    【其他说明】       统一完成CHV输出和KZZZ发送有效控制
 *                       寄存器0x4170低有效：0x0000=KZZZ发送有效，0xFFFF=发送无效
 *    【返回】	   无
 */
/* ***************************************************************** */
void SysControlOut(void)
{
    /* CHV物理输出始终先执行，确保对外"本通道有效"状态先于KZZZ发送收敛。 */
    CHVControlOut(s_sysConData_t.ConOutData_t.localChvPermit_u16);

    if (CON_OUT_STATE_VALID == s_sysConData_t.ConOutData_t.conOutState_u16)
    {
        /* 控制输出有效时，写0x0000使能KZZZ发送（低有效），避免主备同时出话。 */
        HardXintUint16Write(CPLD_ADDR_W_KZZZ_SEND_VALID, CPLD_DATA_KZZZ_SEND_VALID);
    }
    else
    {
        /* 输出无效时，写0xFFFF禁止KZZZ发送。 */
        HardXintUint16Write(CPLD_ADDR_W_KZZZ_SEND_VALID, CPLD_DATA_KZZZ_SEND_INVALID);
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
        if (SYS_CH_ID_1 == s_sysConData_t.myChID_u16)
        {
            l_nextMasterChId_u16 = SYS_CH_ID_2;
        }
        else
        {
            l_nextMasterChId_u16 = SYS_CH_ID_1;
        }
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
    if ((l_now_u32 - vp_ctx_t->startTime_u32) >= v_holdTimeMs_u32)
    {
        return VALID;
    }

    return INVALID;
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
    Uint16 l_targetRole_u16 = ROLE_BACKUP;

    if (ROLE_MASTER == v_role_u16)
    {
        l_targetRole_u16 = ROLE_MASTER;
    }

    /* 仅在角色实际切换时刷新运行时上下文,避免无谓抖动 */
    if (s_sysConData_t.runtimeRole_u16 != l_targetRole_u16)
    {
        /* 写入新角色并记录进入时间 */
        s_sysConData_t.runtimeRole_u16 = l_targetRole_u16;
        s_sysConData_t.roleEnterTime_u32 = sysTime();
        /* 清空主控失效与备通道接管两个确认窗口。 */
        s_masterLossConfirmCtx_t.active_u16 = INVALID;
        s_masterLossConfirmCtx_t.startTime_u32 = 0UL;
        s_peerTakeoverConfirmCtx_t.active_u16 = INVALID;
        s_peerTakeoverConfirmCtx_t.startTime_u32 = 0UL;
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
    Uint16 l_otherChvSample_u16 = CHV_INVALID;
    Uint16 l_fallbackMasterChId_u16 = SYS_CH_ID_1;
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

    /* 这里判的是启动期静态主备身份，后面运行期只在这个结果上做角色确认和接管。
     * 也就是说，本函数要解决的是“先天谁是主、谁是备”，不是运行中每拍的控制权漂移。 */
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
                if (SYS_CH_ID_1 == s_sysConData_t.myChID_u16)
                {
                    s_sysConData_t.arbMasterChId_u16 = SYS_CH_ID_2;
                }
                else
                {
                    s_sysConData_t.arbMasterChId_u16 = SYS_CH_ID_1;
                }
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
                /* 对端尚未形成稳定主备时，先尝试按冷启动轮值协商。
                 * 两端都给出有效且一致的“下一主通道”时，直接按轮值落位，
                 * 这样可以让冷启动结果可复现，而不是每次都落到随机仲裁。 */
                l_peerNextMasterChId_u16 = l_peerBase_t.preferredMasterChId_u16;
                s_sysConData_t.peerPreferredMasterChId_u16 = l_peerNextMasterChId_u16;
                if ((SYS_CH_ID_1 == l_localNextMasterChId_u16) || (SYS_CH_ID_2 == l_localNextMasterChId_u16))
                {
                    l_localPreferredValid_u16 = VALID;
                }
                else
                {
                    l_localPreferredValid_u16 = INVALID;
                }

                if ((SYS_CH_ID_1 == l_peerNextMasterChId_u16) || (SYS_CH_ID_2 == l_peerNextMasterChId_u16))
                {
                    l_peerPreferredValid_u16 = VALID;
                }
                else
                {
                    l_peerPreferredValid_u16 = INVALID;
                }

                if ((VALID == l_localPreferredValid_u16) &&
                    (VALID == l_peerPreferredValid_u16) &&
                    (l_localNextMasterChId_u16 == l_peerNextMasterChId_u16))
                {
                    if (s_sysConData_t.myChID_u16 == l_localNextMasterChId_u16)
                    {
                        l_chType_u16 = CH_TYPE_CON;
                    }
                    else
                    {
                        l_chType_u16 = CH_TYPE_BF;
                    }
                    s_sysConData_t.localPreferredMasterChId_u16 = l_localNextMasterChId_u16;
                    s_sysConData_t.ChTypeCode_u16 = TYPEJUDGE_CODE_NONE;
                    s_sysConData_t.arbMasterChId_u16 = l_localNextMasterChId_u16;
                }
                else
                {
                    /* 轮值值无效、不一致，或者对端没给出可信建议时，再退回随机数仲裁。
                     * 这里重点不是绝对公平，而是让双方基于同一批基础帧数据尽快收敛成互补结果。 */
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
                        if (SYS_CH_ID_1 == s_sysConData_t.myChID_u16)
                        {
                            s_sysConData_t.arbMasterChId_u16 = SYS_CH_ID_2;
                        }
                        else
                        {
                            s_sysConData_t.arbMasterChId_u16 = SYS_CH_ID_1;
                        }
                    }
                    else
                    {
                        /* 平局时不强推结论，继续等待下一轮基础帧。
                         * 多等一拍比双方在相等条件下各自选边更安全。 */
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
        if (0U != GPIOReadBitNum(GPIO_IN_DSP_CHV))
        {
            l_otherChvSample_u16 = CHV_VALID;
        }
        if (CHV_INVALID == l_otherChvSample_u16)
        {
            l_fallbackMasterChId_u16 = s_sysConData_t.myChID_u16;
        }

        /* 走到这里说明正常协商窗口内没有收敛。
         * 兜底策略故意偏保守，先避免双主，再尽量把控制权留给更可能存活的一侧。
         *
         * 轮值值缺失/不一致/超时时：
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

    /* 判型完成后固化静态主备身份，ChType运行周期内不变；控制权归属单独初始化。
     * 后续 RuntimeRoleUpdate 可以把运行控制权降备/升主，但不会再改这个启动判型结果。 */

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
    s_peerTakeoverConfirmCtx_t.active_u16 = INVALID;
    s_peerTakeoverConfirmCtx_t.startTime_u32 = 0UL;

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
    Uint16 l_localHealthy_u16 = INVALID;
    Uint16 l_peerLossConfirmed_u16 = INVALID;
    Uint16 l_masterLossConfirmed_u16 = INVALID;
    Uint16 l_ccdlID_u16 = COMM_CCDL_SCI;
    Uint16 l_ccdlValid_u16 = INVALID;
    Uint16 l_peerLossSample_u16 = INVALID;
    Uint16 l_peerCriticalFault_u16 = INVALID;
    Uint16 l_localFaultSample_u16 = INVALID;
    PeerBaseStatus_t l_peerBase_t;
    Uint32 l_currTime_u32 = 0UL;
    memset(&l_peerBase_t, 0, sizeof(l_peerBase_t));

    /* 本地健康使用“允许输出 + 本端CHV反馈”双条件，避免单靠软件许可或单靠硬件反馈误判可控。 */
    if ((CHV_VALID == s_sysConData_t.ConOutData_t.localChvPermit_u16) &&
        (CHV_VALID == s_sysConData_t.CHVIn_un16.bit.myCHV_u16))
    {
        l_localHealthy_u16 = VALID;
    }

    /* 运行期主备切换流程：
     * 1. 判定本通道本地健康（localChvPermit + myCHV 同时有效），失效则启动主控丢失确认窗口；
     * 2. 通过 CCDL 基础帧获取对端状态，判定对端是否仍在线或已经关键失效；
     * 3. RoleConfirmUpdate 以固定时间窗口（ROLE_PEER_LOSS_TIMEOUT_MS/CONTROL_OWNER_HOLD_MS）做去抖确认；
     * 4. 本地健康、未见对端控制权且对端失联/关键失效确认后，本端升主（ROLE_MASTER）；
     * 5. 本地健康失效确认后，本端降备（ROLE_BACKUP），等待对端接管；
     * 6. 切换通过 RuntimeRoleSet 落地，并复位确认窗口上下文。
     */

    s_sysConData_t.peerAlive_u16 = INVALID;
    s_sysConData_t.peerCtrlSeen_u16 = INVALID;
    (void)ControlCCDLActiveSourceSelect(&l_ccdlID_u16, &l_ccdlValid_u16);
    if (VALID == l_ccdlValid_u16)
    {
        /* 只从当前活动CCDL源读取对端基础帧，避免SCI/CPLD两份旧快照互相干扰。 */
        l_peerBase_t = CommCCDLPeerBaseGet(l_ccdlID_u16);
        l_currTime_u32 = sysTime();
        if ((VALID == l_peerBase_t.valid_u16) &&
            ((l_currTime_u32 - l_peerBase_t.lastRxTime_u32) <= ROLE_PEER_LOSS_TIMEOUT_MS))
        {
            s_sysConData_t.peerAlive_u16 = VALID;
            if (0U != (l_peerBase_t.ctrlInfo_u16 & (0x01U << COMM_CCDL_CTRLINFO_OWNER_BIT)))
            {
                /* peerCtrlSeen是防双主的硬约束，只要对端仍声明控制权，本端备份不抢主。 */
                s_sysConData_t.peerCtrlSeen_u16 = VALID;
            }
        }
    }
    /* 运行期升主不再单独依赖 otherCHV。
     * 单板调试或CPLD异常时，400C/otherCHV可能假有效；
     * 因此以CCDL基础帧持续失联作为对端失效主判据，peerCtrlSeen仍优先用于防双主。 */
    if (VALID != s_sysConData_t.peerAlive_u16)
    {
        l_peerLossSample_u16 = VALID;
    }
    l_peerCriticalFault_u16 = ControlPeerCriticalFaultExist();
    /* 对端失联和对端关键故障共用一个确认窗口，避免单拍抖动触发升主。 */
    l_peerLossConfirmed_u16 =
        RoleConfirmUpdate(&s_peerTakeoverConfirmCtx_t,
                          ((VALID == l_peerLossSample_u16) || (VALID == l_peerCriticalFault_u16)) ? VALID : INVALID,
                          CONTROL_OWNER_HOLD_MS);

    switch (s_sysConData_t.runtimeRole_u16)
    {
        case ROLE_MASTER:
            if (VALID != l_localHealthy_u16)
            {
                l_localFaultSample_u16 = VALID;
            }
            l_masterLossConfirmed_u16 =
                RoleConfirmUpdate(&s_masterLossConfirmCtx_t, l_localFaultSample_u16, CONTROL_OWNER_HOLD_MS);
            if (VALID == l_masterLossConfirmed_u16)
            {
                /* 主控本地健康持续失效时主动降备，给对端接管留出确定窗口。 */
                RuntimeRoleSet(ROLE_BACKUP);
            }
            else if ((VALID == s_sysConData_t.peerAlive_u16) &&
                     (VALID == s_sysConData_t.peerCtrlSeen_u16) &&
                     (SYS_CH_ID_1 != s_sysConData_t.myChID_u16))
            {
                /* 若对端已经明确宣称控制权，非1通道主控退让，避免双主同时输出。 */
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
            else if (VALID == l_peerLossConfirmed_u16)
            {
                /* 备份只有在本地健康、未见对端控制权且对端失联/关键失效确认后升主。 */
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

    /* RIU源选择:按429物理通道IFBIT健康优先级逐级回退 */
    /* 本通道(RIU_1) -> SCI镜像(RIU_2) -> CPLD镜像(RIU_3) */
    /*
     * 这里更新的是“上报给上层看的来源枚举”，真正取数仍由各通信接口按同样优先级返回。
     * 因此来源状态要尽量反映当前可用路径，而不是记住上一次可用路径。
     */
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

    /* CCDL源选择:SCI直连为主，CPLD回绕为备 */
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

    /* KZZZ来源汇总:本地429优先(左或右任一路)、CCDL对端镜像次之 */
    if (RX429_STATE_OK == Comm429KZZZRxStateGet(COMM429_KZZZ_1).rxState_u16)
    {
        l_kzzzLeftOk_u16 = VALID;
    }
    if (RX429_STATE_OK == Comm429KZZZRxStateGet(COMM429_KZZZ_2).rxState_u16)
    {
        l_kzzzRightOk_u16 = VALID;
    }
    if ((VALID == l_ccdlValid_u16) &&
        ((VALID == Comm429KZZZCcdlExtValidGet(l_ccdlID_u16, COMM429_KZZZ_1)) ||
         (VALID == Comm429KZZZCcdlExtValidGet(l_ccdlID_u16, COMM429_KZZZ_2))))
    {
        /* 任一侧吊舱镜像完整且新鲜，就认为KZZZ可从CCDL侧回退取数。 */
        l_kzzzPeerOk_u16 = VALID;
    }

    /* 本地429健康优先取COMM_SOURCE_1，CCDL对端镜像回退取COMM_SOURCE_3 */
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
