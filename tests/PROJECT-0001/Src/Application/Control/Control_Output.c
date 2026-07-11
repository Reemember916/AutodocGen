#include "Global.h"
#include "Control_Output.h"

static KZZZTxCache_t s_kzzzTxCache_t =
{
    0U,
    0xFFFFU,
    0xFFFFU,
    0xFFFFU,
    0xFFFFU,
    0xFFFFU,
    0xFFFFU,
    0xFFFFU,
    0xFFFFU
};

/* ***************************************************************** */
/**
 * 【函数名】:ControlKZZZTxCacheReset
 *
 * 【功能描述】复位KZZZ发送缓存
 *             当控制输出失效或RIU源不可用时，清空事件去重缓存并重置周期分频
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       使用0xFFFF作为“未发送过”的哨兵值，便于下一次恢复后重新发送事件量
 * 【返回】	   无
 */
/* ***************************************************************** */
static void ControlKZZZTxCacheReset(void)
{
    /* 周期量分频回到0，保证恢复后重新从完整200ms周期起步。 */
    s_kzzzTxCache_t.periodicDiv_u16 = 0U;
    /* 事件缓存统一刷成非法值，确保恢复后的首个有效值一定能触发发送。 */
    s_kzzzTxCache_t.lastMbitCmd_u16 = 0xFFFFU;
    s_kzzzTxCache_t.lastPzValid_u16 = 0xFFFFU;
    s_kzzzTxCache_t.lastLpPreFuel_u16 = 0xFFFFU;
    s_kzzzTxCache_t.lastRpPreFuel_u16 = 0xFFFFU;
    s_kzzzTxCache_t.lastLifeLeft_u16 = 0xFFFFU;
    s_kzzzTxCache_t.lastLifeRight_u16 = 0xFFFFU;
    s_kzzzTxCache_t.lastOilResetLeft_u16 = 0xFFFFU;
    s_kzzzTxCache_t.lastOilResetRight_u16 = 0xFFFFU;
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlRIURawBitGet
 *
 * 【功能描述】从RIU原始429字中提取单bit离散量
 *             统一按arinc429Data的数据域位序读取，避免各发送路径自行位操作
 * 【输入参数说明】vp_orig_t:RIU原始字指针
 *               v_shift_u16:数据域右移位数
 * 【输出参数说明】无
 * 【其他说明】       空指针按全0原始字处理，调用侧无需额外判空
 * 【返回】	   提取出的1bit值
 */
/* ***************************************************************** */
static Uint16 ControlRIURawBitGet(const Orig429Data_t *vp_orig_t, Uint16 v_shift_u16)
{
    union arinc429Data l_rdata_un; /* 临时429字，用于统一完成数据域解析。 */

    /* 默认原始字为0，空指针时所有事件位都按无效处理。 */
    l_rdata_un.msgData = 0UL;
    if(NULL != vp_orig_t)
    {
        /* 原始字存在时，再把完整32bit报文装入统一结构。 */
        l_rdata_un.msgData = vp_orig_t->OrigData_u32;
    }

    /* 只读取data域，不消费label/ssm/parity位。 */
    return (Uint16)((l_rdata_un.bit.data >> v_shift_u16) & 0x1UL);
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlRIURawBitsGet
 *
 * 【功能描述】从RIU原始429字中提取连续多bit离散量
 *             与ControlRIURawBitGet配套，供维护BIT等2bit事件字复用
 * 【输入参数说明】vp_orig_t:RIU原始字指针
 *               v_shift_u16:右移位数
 *               v_mask_u16:提取掩码
 * 【输出参数说明】无
 * 【其他说明】       空指针同样按全0原始字处理
 * 【返回】	   提取后的多bit值
 */
/* ***************************************************************** */
static Uint16 ControlRIURawBitsGet(const Orig429Data_t *vp_orig_t, Uint16 v_shift_u16, Uint16 v_mask_u16)
{
    union arinc429Data l_rdata_un; /* 临时429字，用于统一完成数据域解析。 */

    /* 默认原始字为0，保持空指针输入下的确定性返回。 */
    l_rdata_un.msgData = 0UL;
    if(NULL != vp_orig_t)
    {
        /* 原始字有效时再装入完整报文。 */
        l_rdata_un.msgData = vp_orig_t->OrigData_u32;
    }

    /* 掩码由调用者给定，这里只负责通用提取。 */
    return (Uint16)((l_rdata_un.bit.data >> v_shift_u16) & (Uint32)v_mask_u16);
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlKZZZCurrTimeRequestCheck
 *
 * 【功能描述】汇总左右吊舱当前时间请求
 *             只有对应侧KZZZ链路健康且请求位有效时，才把该侧请求纳入结果位图
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       返回值是左右两侧请求位图，而不是单路布尔值
 * 【返回】	   左右吊舱当前时间请求位图
 */
/* ***************************************************************** */
static Uint16 ControlKZZZCurrTimeRequestCheck(void)
{
    Uint16 l_currTimeAsk_u16 = 0U; /* 当前时间请求位图，用于区分左右吊舱的时间请求结果。 */

    /* 左侧只有在链路健康且请求位=1时才应答，避免对失效侧回发时间。 */
    if ((RX429_STATE_OK == Comm429KZZZRxStateGet(COMM429_KZZZ_1).rxState_u16) &&
        (KZZZ_TIME_REQUEST_VALID == Comm429KzzzRxDataGet(COMM429_KZZZ_1).currTimeAsk_u16))
    {
        l_currTimeAsk_u16 |= KZZZ_TIME_REQUEST_SIDE_LEFT;
    }

    /* 右侧同理独立判定，避免一侧异常影响另一侧应答。 */
    if ((RX429_STATE_OK == Comm429KZZZRxStateGet(COMM429_KZZZ_2).rxState_u16) &&
        (KZZZ_TIME_REQUEST_VALID == Comm429KzzzRxDataGet(COMM429_KZZZ_2).currTimeAsk_u16))
    {
        l_currTimeAsk_u16 |= KZZZ_TIME_REQUEST_SIDE_RIGHT;
    }

    return l_currTimeAsk_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:CHVControlOut
 *
 * 【功能描述】更新通道有效信号输出
 *             根据控制模块判定的CHV结果，同时刷新CPLD输出寄存器和GPIO输出脚
 * 【输入参数说明】v_control_u16:通道有效控制值
 * 【输出参数说明】无
 * 【其他说明】       仅负责物理输出，不参与上层判据
 * 【返回】	   无
 */
/* ***************************************************************** */
static void CHVControlOut(Uint16 v_control_u16)
{
    if (CHV_VALID == v_control_u16)
    {
        /* CHV有效时，同时拉高CPLD输出寄存器和板级GPIO，保持内外口径一致。 */
        HARD_XINT_UINT16(CPLD_ADDR_W_CPUV_OUT) = CPUV_IN_NOMAL;
        GPIOSetNum(GPIO_OUT_DSP_CHV);
    }
    else
    {
        /* CHV无效时，两个物理输出都必须同步撤销。 */
        HARD_XINT_UINT16(CPLD_ADDR_W_CPUV_OUT) = CPUV_IN_ERR;
        GPIOClearNum(GPIO_OUT_DSP_CHV);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CHVConDataObtain
 *
 * 【功能描述】采集并判定通道有效控制输入
 *             综合PuBIT/IFBIT/MBIT健康状态和CPLD输入，刷新CHV控制结果
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       当前实现保留LATCH_EN锁存语义，恢复路径依赖外部输入释放
 * 【返回】	   无
 */
/* ***************************************************************** */
void CHVConDataObtain(void)
{
    Uint16 l_puBitStatus_u16 = 0U;             /* 上电自检状态，用于记录PuBIT健康状态。 */
    Uint16 l_ifBitLevel_u16 = 0U;              /* 接口故障等级，用于记录IFBIT故障等级。 */
    Uint16 l_mBitLevel_u16 = 0U;               /* 维护故障等级，用于记录MBIT故障等级。 */
   // Uint16 l_otherChvSample_u16 = CHV_INVALID; /* 对端通道采样，用于采样对端CHV输入。 */

    l_puBitStatus_u16 = PuBITDataGet();
    l_ifBitLevel_u16 = IFBITResultGet(IFBIT_DINDEX_FLEVEL);
    l_mBitLevel_u16 = MBITResultGet(MBIT_DINDEX_FLEVEL);

    /* 先读取CPLD回绕输入，供当前拍的CHV仲裁使用。 */
    s_sysConData_t.CHVIn_un16.all = HARD_XINT_UINT16(CPLD_ADDR_W_CPUV_IN);

    /* 任一BIT等级异常时，系统必须立即撤销本通道有效输出资格。 */
    if ((PUBIT_TEST_OK != (l_puBitStatus_u16 & PUBIT_KEY_FAULT_CODE)) ||
        (l_ifBitLevel_u16 >= IFBIT_FLEVEL_1) ||
        (l_mBitLevel_u16 >= MBIT_FLEVEL_1))
    {
        s_sysConData_t.ConOutData_t.localChvPermit_u16 = CHV_INVALID;
    }
    /* 健康恢复后也只在锁存允许释放时恢复有效，以避免故障后立刻抖动恢复。 */
    else if (LATCH_EN_VALID != s_sysConData_t.CHVIn_un16.bit.LATCH_EN_u16)
    {
        s_sysConData_t.ConOutData_t.localChvPermit_u16 = CHV_VALID;
    }

    /* 运行期主备授权不再直接信任CPLD中的myCHV/otherCHV位。本端改用资格位代理，对端改走GPIO采样。 */
//    s_sysConData_t.CHVIn_un16.bit.myCHV_u16 = s_sysConData_t.ConOutData_t.localChvPermit_u16;
//    l_otherChvSample_u16 = (0U != GPIOReadBitNum(GPIO_IN_DSP_CHV)) ? CHV_VALID : CHV_INVALID;
//    s_sysConData_t.CHVIn_un16.bit.otherCHV_u16 = l_otherChvSample_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:ConOutStateUpdate
 *
 * 【功能描述】刷新控制输出状态
 *             仅依据当前控制权归属和本端CHV资格，给出本拍控制输出是否允许发送
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       该状态按拍全量计算，不依赖上一拍结果
 * 【返回】	   无
 */
/* ***************************************************************** */
void ConOutStateUpdate(void)
{
    /* 先给出保守默认值，然后只在当前拍明确满足输出条件时再放开输出。 */
    s_sysConData_t.ConOutData_t.conOutState_u16 = CON_OUT_STATE_INVALID;

    /* 当前工程只有“本端是主 + 本端资格有效 + 本端CHV回绕有效”才允许真正打开控制输出。 */
    if ((ROLE_MASTER == s_sysConData_t.runtimeRole_u16) &&
        (CHV_VALID == s_sysConData_t.ConOutData_t.localChvPermit_u16) &&
        (CHV_VALID == s_sysConData_t.CHVIn_un16.bit.myCHV_u16))
    {
        s_sysConData_t.ConOutData_t.conOutState_u16 = CON_OUT_STATE_VALID;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:SysControlOut
 *
 * 【功能描述】执行控制输出
 *             统一完成CHV输出和发送使能控制
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       当控制输出无效时，仅关闭发送使能
 * 【返回】	   无
 */
/* ***************************************************************** */
void SysControlOut(void)
{
    /* CHV物理输出始终先执行，确保对外“本通道有效”状态先于业务发送使能收敛。 */
    CHVControlOut(s_sysConData_t.ConOutData_t.localChvPermit_u16);

    if (CON_OUT_STATE_VALID == s_sysConData_t.ConOutData_t.conOutState_u16)
    {
        /* 只有控制输出有效时才允许对外发送业务报文。 */
        HARD_XINT_UINT16(CPLD_ADDR_W_COMM_SEND_EN) = CPLD_DATA_COMM_SEND_EN_VALID;
    }
    else
    {
        /* 输出无效时立即关闭统一发送使能，避免主备同时出话。 */
        HARD_XINT_UINT16(CPLD_ADDR_W_COMM_SEND_EN) = CPLD_DATA_COMM_SEND_EN_INVALID;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:Comm429KZZZPeriodInfoTx
 *
 * 【功能描述】发送系统周期性429状态信息
 *             汇总当前控制状态、余度数据和寿命信息，完成KZZZ周期发送
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       当前时间下发必须同时满足KZZZ请求有效且RIU源有效
 * 【返回】	   无
 */
/* ***************************************************************** */
void Comm429KZZZPeriodInfoTx(void)
{
    RIU429InfoData_t l_RIU429RxData_t;      /* RIU接收数据，用于暂存当前选定RIU源的接收数据。 */
    RIU429OrigData_t l_RIU429OrigData_t;    /* RIU原始429字，用于转发事件量原始命令位。 */
    Uint16 l_currTimeAsk_u16;               /* 时间请求位图，用于记录KZZZ当前时间请求标志。 */
    Uint16 l_commID_u16 = COMM429_RIU_1;    /* RIU通道号，用于记录当前选定的RIU通道。 */
    Uint16 l_riuValid_u16 = INVALID;        /* RIU有效标志，用于标记当前是否找到有效RIU来源。 */
    Uint16 l_mbitCmd_u16;
    Uint16 l_pzValid_u16;
    Uint16 l_lifeLeft_u16;
    Uint16 l_lifeRight_u16;
    Uint16 l_oilResetLeft_u16;
    Uint16 l_oilResetRight_u16;
    Uint16 l_lpPreFuel_u16;
    Uint16 l_rpPreFuel_u16;
    Uint16 l_lowFuel_u16;
    Uint16 l_air_u16;
    Uint16 l_fuelReset_u16;

    /* 控制输出资格失效时，直接清缓存并停止KZZZ发送，避免事件量在恢复后丢沿。 */
    if (CON_OUT_STATE_VALID != s_sysConData_t.ConOutData_t.conOutState_u16)
    {
        ControlKZZZTxCacheReset();
        return;
    }

    /* 周期发送只读取当前统一选定的RIU数据源，以避免发送链与控制链的输入口径分裂。 */
    ControlRIUActiveSourceSelect(&l_commID_u16, &l_riuValid_u16);
    if (VALID == l_riuValid_u16)
    {
        l_RIU429RxData_t = Comm429RIURxDataGet(l_commID_u16);
        l_RIU429OrigData_t = Comm429RIUOrigDataGet(l_commID_u16);
    }
    else
    {
        ControlKZZZTxCacheReset();
        return;
    }
    l_currTimeAsk_u16 = ControlKZZZCurrTimeRequestCheck();

    /* 当前时间请求按吊舱分别应答，避免一侧请求却双侧广播。 */
    if (0U != (l_currTimeAsk_u16 & KZZZ_TIME_REQUEST_SIDE_LEFT))
    {
        Comm429KZZZCurrTimeTx(COMM429_KZZZ_1, l_RIU429RxData_t);
    }
    if (0U != (l_currTimeAsk_u16 & KZZZ_TIME_REQUEST_SIDE_RIGHT))
    {
        Comm429KZZZCurrTimeTx(COMM429_KZZZ_2, l_RIU429RxData_t);
    }

    /* 维护BIT执行命令属于事件量：仅在命令变化且非0时向吊舱转发。 */
    l_mbitCmd_u16 = ControlRIURawBitsGet(&l_RIU429OrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_MBIT_EXEC], 0U, 0x3U);
    if (s_kzzzTxCache_t.lastMbitCmd_u16 != l_mbitCmd_u16)
    {
        s_kzzzTxCache_t.lastMbitCmd_u16 = l_mbitCmd_u16;
        if (0U != l_mbitCmd_u16)
        {
            Comm429KZZZSendDual(KZZZ_LABEL_T_MBIT_RUN, (Uint32)(l_mbitCmd_u16 & 0x3U));
        }
    }

    /* 配置信息请求同样只在有效沿出现时发送，避免每拍重复刷相同事件。 */
    l_pzValid_u16 = ControlRIURawBitGet(&l_RIU429OrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_SOFTV_REQ], 0U);
    if (s_kzzzTxCache_t.lastPzValid_u16 != l_pzValid_u16)
    {
        s_kzzzTxCache_t.lastPzValid_u16 = l_pzValid_u16;
        if (KZZZ_TIME_REQUEST_VALID == l_pzValid_u16)
        {
            Comm429KZZZSendDual(KZZZ_LABEL_T_PZXX, (Uint32)(l_pzValid_u16 & 0x1U));
        }
    }

    /* 预选油量按100kg量化后做变化检测，既保持ICD分辨率，也避免浮点细抖动重复发事件。 */
    l_lpPreFuel_u16 = (Uint16)(l_RIU429RxData_t.lpPFV_f / OIL_RATIO);
    if (s_kzzzTxCache_t.lastLpPreFuel_u16 != l_lpPreFuel_u16)
    {
        s_kzzzTxCache_t.lastLpPreFuel_u16 = l_lpPreFuel_u16;
        Comm429KZZZSendPreFuel(COMM429_KZZZ_1, l_RIU429RxData_t.lpPFV_f);
    }

    l_rpPreFuel_u16 = (Uint16)(l_RIU429RxData_t.rpPFV_f / OIL_RATIO);
    if (s_kzzzTxCache_t.lastRpPreFuel_u16 != l_rpPreFuel_u16)
    {
        s_kzzzTxCache_t.lastRpPreFuel_u16 = l_rpPreFuel_u16;
        Comm429KZZZSendPreFuel(COMM429_KZZZ_2, l_RIU429RxData_t.rpPFV_f);
    }

    /* 左右寿命信息请求分别按各自触发沿转发，避免双侧相互串扰。 */
    l_lifeLeft_u16 = ControlRIURawBitGet(&l_RIU429OrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_LIFE_INFO], 0U);
    if (s_kzzzTxCache_t.lastLifeLeft_u16 != l_lifeLeft_u16)
    {
        s_kzzzTxCache_t.lastLifeLeft_u16 = l_lifeLeft_u16;
        if (KZZZ_TIME_REQUEST_VALID == l_lifeLeft_u16)
        {
            Comm429KZZZSendLifeInfo(COMM429_KZZZ_1, l_lifeLeft_u16);
        }
    }

    l_lifeRight_u16 = ControlRIURawBitGet(&l_RIU429OrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_LIFE_INFO], 1U);
    if (s_kzzzTxCache_t.lastLifeRight_u16 != l_lifeRight_u16)
    {
        s_kzzzTxCache_t.lastLifeRight_u16 = l_lifeRight_u16;
        if (KZZZ_TIME_REQUEST_VALID == l_lifeRight_u16)
        {
            Comm429KZZZSendLifeInfo(COMM429_KZZZ_2, l_lifeRight_u16);
        }
    }

    /* 油量清零请求与寿命请求同理，都按吊舱侧独立做边沿发送。 */
    l_oilResetLeft_u16 = ControlRIURawBitGet(&l_RIU429OrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_OIL_RESET], 0U);
    if (s_kzzzTxCache_t.lastOilResetLeft_u16 != l_oilResetLeft_u16)
    {
        s_kzzzTxCache_t.lastOilResetLeft_u16 = l_oilResetLeft_u16;
        if (KZZZ_TIME_REQUEST_VALID == l_oilResetLeft_u16)
        {
            Comm429KZZZSendOilReset(COMM429_KZZZ_1, l_oilResetLeft_u16);
        }
    }

    l_oilResetRight_u16 = ControlRIURawBitGet(&l_RIU429OrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_OIL_RESET], 1U);
    if (s_kzzzTxCache_t.lastOilResetRight_u16 != l_oilResetRight_u16)
    {
        s_kzzzTxCache_t.lastOilResetRight_u16 = l_oilResetRight_u16;
        if (KZZZ_TIME_REQUEST_VALID == l_oilResetRight_u16)
        {
            Comm429KZZZSendOilReset(COMM429_KZZZ_2, l_oilResetRight_u16);
        }
    }

    /* 周期量统一按50ms调度累计4拍后发送一次，以保持200ms总线节拍。 */
    s_kzzzTxCache_t.periodicDiv_u16 = (Uint16)((s_kzzzTxCache_t.periodicDiv_u16 + 1U) % KZZZ_PERIODIC_SEND_DIV);
    if (0U == s_kzzzTxCache_t.periodicDiv_u16)
    {
        /* 燃油密度是标准周期量，每到200ms整拍即广播左右吊舱。 */
        Comm429KZZZSendFuelDensity(l_RIU429RxData_t.oilMD_f);

        /* 0267 的三个离散量都来自当前统一选定RIU源，避免控制链和发送链口径分裂。 */
        l_lowFuel_u16 = l_RIU429RxData_t.fuelLow_u16;
        /* 0267空地位只消费RIU兼容聚合量wheelLoad_u16：
         * 004三路轮载的保守归并规则已在RIU接收链内处理，此处不再重复解释原始位。 */
        l_air_u16 = (RIU_DK_AIR == l_RIU429RxData_t.wheelLoad_u16) ? 1U : 0U;
        l_fuelReset_u16 = l_RIU429RxData_t.fuelReset_u16;
        /* 最后统一打包控制指令字，保证三类离散量始终在同一拍一起发送。 */
        Comm429KZZZSendCtrlCmd(l_lowFuel_u16, l_air_u16, l_fuelReset_u16);
    }
}
