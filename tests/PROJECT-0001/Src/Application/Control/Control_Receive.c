#include "Global.h"

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveModeRiuCmdGet
 *
 * 【功能描述】获取当前统一选定的RIU加受油模式指令
 *             优先使用控制链选中的有效RIU源，若无有效源则回退到余度池镜像
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       仅用于受油链内部检查模式是否仍保持有效
 * 【返回】          RIU加受油模式指令
 */
/* ***************************************************************** */
static union fuelCmd_Data ReceiveModeRiuCmdGet(void)
{
    union fuelCmd_Data l_cmd_t;
    RedunData_t l_redunData_t;
    Uint16 l_commID_u16 = COMM429_RIU_1;
    Uint16 l_valid_u16 = INVALID;
    /* 清零返回结构,避免栈上脏数据被读走 */
    memset(&l_cmd_t, 0, sizeof(l_cmd_t));

    /* 由控制链统一挑选当前有效RIU源(遍历RIU 1/2/3) */
    ControlRIUActiveSourceSelect(&l_commID_u16, &l_valid_u16);
    /* 选中源有效时直接从429接收缓存取最新fuelCmd */
    if (VALID == l_valid_u16)
    {
        l_cmd_t = Comm429RIURxDataGet(l_commID_u16).fuelCmd_t;
    }
    else
    {
        /* 选中源无效时回退余度池里镜像保存的fuelCmd */
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_REFUEL_CMD);
        l_cmd_t.all = (Uint8)(l_redunData_t.dataU_u32 & 0xFFU);
    }

    return l_cmd_t;
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveModeTaskValidCheck
 *
 * 【功能描述】检查受油链的模式指令是否仍保持有效
 *             一旦RIU撤销受油模式，受油链应统一切入任务结束态收口
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       仅返回条件，不直接修改状态机
 * 【返回】          VALID-仍为受油 / INVALID-已无效
 */
/* ***************************************************************** */
static Uint16 ReceiveModeTaskValidCheck(void)
{
    union fuelCmd_Data l_cmd_t = ReceiveModeRiuCmdGet();

    if (WORK_MODE_RECEIVE == WorkModeRIUDataCheck(l_cmd_t.bit.fuelObject_u8,
                                                  l_cmd_t.bit.fuelMode_u8))
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
 * 【函数名】:ReceiveModeMeasureFaultExists
 *
 * 【功能描述】判断受油链是否存在任务书定义的测量系统组合故障
 *             统一把故障、降级和各翼箱油量传感器故障都视为测量异常
 * 【输入参数说明】v_faultInfo_un16：故障字快照
 * 【输出参数说明】无
 * 【其他说明】       与加油前检和外层Control_Fault口径保持一致
 * 【返回】          VALID-异常 / INVALID-正常
 */
/* ***************************************************************** */
static Uint16 ReceiveModeMeasureFaultExists(union faultInfo_Data v_faultInfo_un16)
{
    /* 综合判定:4个信号转换盒 + 5个油箱传感器任一异常即视为测量故障。
     * 注: docx 0o264 故障字不含 oilMS, 见 Control_Fault.c 注释。 */
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
 * 【函数名】:ReceiveModeExitToTaskEnd
 *
 * 【功能描述】把受油链统一切入任务结束态
 *             供模式无效等非故障退出条件复用，避免多个阶段各自拼接跳转代码
 * 【输入参数说明】v_p_ConData_t：系统控制数据指针
 * 【输出参数说明】无
 * 【其他说明】       不主动修改故障锁存，仅做conFunc收口
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveModeExitToTaskEnd(ConData_t *v_p_ConData_t)
{
    /* 仅对非空指针做收口,避免野指针破坏控制上下文 */
    if (NULL != v_p_ConData_t)
    {
        /* 记录上一拍conFunc,便于上层追溯退出前所在阶段 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
        /* 统一切入任务结束态,所有受油链复用同一收口 */
        v_p_ConData_t->conFunc_u16 = CON_FUNC_4_TASK_END;
        /* 打时间戳:任务结束态的计时起点 */
        v_p_ConData_t->workModeTime_u32 = sysTime();
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveModeContextReset
 *
 * 【功能描述】受油模式上下文复位
 *             清除预设总量、每箱目标量、关活门掩码和完成/故障状态
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       在进入受油模式首拍和正常结束后调用
 * 【返回】          无
 */
/* ***************************************************************** */
void ReceiveModeContextReset(void)
{
    Uint16 l_tankIndex_u16; /* 油箱索引，用于逐箱清零目标量和关活门计时。 */

    /* 清除本轮预设总量。 */
    s_receiveCtx_t.presetTotalKg_f = 0.0F;
    /* 清除进入受油时的初始总油量快照。 */
    s_receiveCtx_t.initialTotalKg_f = 0.0F;
    /* 复位“预设已准备好”标志。 */
    s_receiveCtx_t.presetReady_u16 = INVALID;
    /* 清除当前关活门目标掩码。 */
    s_receiveCtx_t.rcvCloseMask_u16 = 0U;
    /* 清除故障锁存标志。 */
    s_receiveCtx_t.faultActive_u16 = INVALID;
    /* 缺省按“非全关RCV故障”复位，具体故障动作由触发点重新填写。 */
    s_receiveCtx_t.faultCloseAllRcv_u16 = INVALID;
    /* 清除“已发完成”标志。 */
    s_receiveCtx_t.completionIssued_u16 = INVALID;
    /* 清除“完成延时已到”标志。 */
    s_receiveCtx_t.completionSettled_u16 = INVALID;
    /* 清除完成延时起点。 */
    s_receiveCtx_t.completionTimestamp_u32 = 0UL;

    for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
    {
        /* 清除每箱目标油量。 */
        s_receiveCtx_t.perTankTargetKg_f[l_tankIndex_u16] = 0.0F;
        /* 清除每箱关活门命令时间。 */
        s_receiveCtx_t.rcvCloseCmdTime_u32[l_tankIndex_u16] = 0UL;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveModeRcvCloseFaultSet
 *
 * 【功能描述】设置指定油箱的RCV关闭故障位
 *             仅负责0232中的5路RCV关闭故障位，不修改其它故障字
 * 【输入参数说明】v_tankIndex_u16：油箱索引
 *                  v_fault_u16：故障标志
 * 【输出参数说明】无
 * 【其他说明】       超范围索引直接忽略
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveModeRcvCloseFaultSet(Uint16 v_tankIndex_u16, Uint16 v_fault_u16)
{
    /* 按油箱索引选位设置RCV0~RCV4活门关闭故障,超范围索引忽略 */
    switch (v_tankIndex_u16)
    {
        case 0U: s_RIUSendData_t.RIUfltInfo2_t.bit.RCV0_fault_u16 = v_fault_u16; break;
        case 1U: s_RIUSendData_t.RIUfltInfo2_t.bit.RCV1_fault_u16 = v_fault_u16; break;
        case 2U: s_RIUSendData_t.RIUfltInfo2_t.bit.RCV2_fault_u16 = v_fault_u16; break;
        case 3U: s_RIUSendData_t.RIUfltInfo2_t.bit.RCV3_fault_u16 = v_fault_u16; break;
        case 4U: s_RIUSendData_t.RIUfltInfo2_t.bit.RCV4_fault_u16 = v_fault_u16; break;
        /* 索引越界:不修改任何故障位 */
        default: break;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveModeSetRcvClose
 *
 * 【功能描述】设置单路受油活门关闭命令
 *             同步维护关闭掩码和命令下发时间，用于后续关闭确认超时检查
 *             受油链当前把“关闭活门”和“断电关闭活门”作为同一收口动作一起下发给RIU
 * 【输入参数说明】v_tankIndex_u16：油箱索引
 *                  v_closeCmd_u16：关闭命令
 * 【输出参数说明】无
 * 【其他说明】       仅维护受油模式自己的关活门过程量
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveModeSetRcvClose(Uint16 v_tankIndex_u16, Uint16 v_closeCmd_u16)
{
    /* 只允许对受油模式实际存在的5个油箱下发命令。 */
    if (v_tankIndex_u16 < RECEIVE_TANK_COUNT)
    {
        if (VALID == v_closeCmd_u16)
        {
            /* 只有首拍发出关闭命令时才建立超时基准，避免反复刷新10秒窗口。 */
            if (0U == (s_receiveCtx_t.rcvCloseMask_u16 & (1U << v_tankIndex_u16)))
            {
                /* 首次发出该箱关闭命令时立刻记时，后续10s关闭确认统一以此时刻为基准。 */
                s_receiveCtx_t.rcvCloseCmdTime_u32[v_tankIndex_u16] = sysTime();
            }
            /* 把该箱加入“等待关闭确认”的掩码。 */
            s_receiveCtx_t.rcvCloseMask_u16 |= (1U << v_tankIndex_u16);
        }
        else
        {
            /* 取消关闭目标时同时清除掩码和计时，避免旧的超时窗口污染后续判定。 */
            s_receiveCtx_t.rcvCloseMask_u16 &= ~(1U << v_tankIndex_u16);
            s_receiveCtx_t.rcvCloseCmdTime_u32[v_tankIndex_u16] = 0UL;
        }

        switch (v_tankIndex_u16)
        {
            case 0U:
                /* 0号箱同时下发关闭命令和断电关闭命令。 */
                s_RIUSendData_t.RCVcmd_t.bit.RCV0_CloseCmd_u16 = v_closeCmd_u16;
                s_RIUSendData_t.RCVcmd_t.bit.RCV0_OffCloseCmd_u16 = v_closeCmd_u16;
                break;
            case 1U:
                /* 1号箱同时下发关闭命令和断电关闭命令。 */
                s_RIUSendData_t.RCVcmd_t.bit.RCV1_CloseCmd_u16 = v_closeCmd_u16;
                s_RIUSendData_t.RCVcmd_t.bit.RCV1_OffCloseCmd_u16 = v_closeCmd_u16;
                break;
            case 2U:
                /* 2号箱同时下发关闭命令和断电关闭命令。 */
                s_RIUSendData_t.RCVcmd_t.bit.RCV2_CloseCmd_u16 = v_closeCmd_u16;
                s_RIUSendData_t.RCVcmd_t.bit.RCV2_OffCloseCmd_u16 = v_closeCmd_u16;
                break;
            case 3U:
                /* 3号箱同时下发关闭命令和断电关闭命令。 */
                s_RIUSendData_t.RCVcmd_t.bit.RCV3_CloseCmd_u16 = v_closeCmd_u16;
                s_RIUSendData_t.RCVcmd_t.bit.RCV3_OffCloseCmd_u16 = v_closeCmd_u16;
                break;
            case 4U:
                /* 4号箱同时下发关闭命令和断电关闭命令。 */
                s_RIUSendData_t.RCVcmd_t.bit.RCV4_CloseCmd_u16 = v_closeCmd_u16;
                s_RIUSendData_t.RCVcmd_t.bit.RCV4_OffCloseCmd_u16 = v_closeCmd_u16;
                break;
            /* 超范围索引已在前面挡住，这里仅保持默认分支完整。 */
            default: break;
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveModeLoadTankVolume
 *
 * 【功能描述】读取受油各箱当前油量
 *             从余度池中读取指定油箱的实时油量
 * 【输入参数说明】v_tankIndex_u16：油箱索引
 * 【输出参数说明】无
 * 【其他说明】       超出油箱范围时返回0
 * 【返回】          当前油量
 */
/* ***************************************************************** */
static float ReceiveModeLoadTankVolume(Uint16 v_tankIndex_u16)
{
    if (v_tankIndex_u16 < RECEIVE_TANK_COUNT)
    {
        return RedunDataGet(REDUN_INDEX_RIU_FQ_TANK0 + v_tankIndex_u16).dataF_f;
    }
    else
    {
        return 0.0F;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveModeBuildTargets
 *
 * 【功能描述】构建受油预设分配目标
 *             根据总预设量、当前油量和高液位传感器状态计算各油箱目标油量
 * 【输入参数说明】v_currVol_f：当前各箱油量
 *                  v_presetTotal_f：总预设油量
 *                  v_hlSensor_un16：高液位状态
 *                  v_outTarget_f：输出目标数组
 * 【输出参数说明】v_outTarget_f：各油箱目标油量
 * 【其他说明】       超出分配能力或输入非法时返回失败
 * 【返回】          VALID：成功；INVALID：失败
 */
/* ***************************************************************** */
static Uint16 ReceiveModeBuildTargets(
    const float v_currVol_f[RECEIVE_TANK_COUNT],
    float v_presetTotal_f,
    union HLSensor_Data v_hlSensor_un16,
    float v_outTarget_f[RECEIVE_TANK_COUNT])
{
    Uint16 l_mask_u16 = 0U;
    Uint16 l_wingTankCnt_u16 = 0U;
    Uint16 l_tankIndex_u16;
    float l_totalCurrVol_f = 0.0F;
    float l_diffFuel_f = 0.0F;

    for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
    {
        Uint16 l_hlStatus_u16 = 0U;

        /* 高液位有效的油箱不再参与本轮目标分配。 */
        switch (l_tankIndex_u16)
        {
            case 0U: l_hlStatus_u16 = v_hlSensor_un16.bit.tank0_HL_sensor_u16; break;
            case 1U: l_hlStatus_u16 = v_hlSensor_un16.bit.tank1_HL_sensor_u16; break;
            case 2U: l_hlStatus_u16 = v_hlSensor_un16.bit.tank2_HL_sensor_u16; break;
            case 3U: l_hlStatus_u16 = v_hlSensor_un16.bit.tank3_HL_sensor_u16; break;
            case 4U: l_hlStatus_u16 = v_hlSensor_un16.bit.tank4_HL_sensor_u16; break;
            default: break;
        }

        if (0U == l_hlStatus_u16)
        {
            l_mask_u16 |= (1U << l_tankIndex_u16);
            if (0U != l_tankIndex_u16)
            {
                l_wingTankCnt_u16++;
            }
        }

        l_totalCurrVol_f += v_currVol_f[l_tankIndex_u16];
        v_outTarget_f[l_tankIndex_u16] = v_currVol_f[l_tankIndex_u16];
    }

    l_diffFuel_f = v_presetTotal_f - l_totalCurrVol_f;
    if (l_diffFuel_f <= 0.0F)
    {
        /* 预设总量不大于当前总量时，没有可分配的新增受油量，直接判非法。 */
        return INVALID;
    }

    if (v_presetTotal_f <= RECEIVE_ALLOC_TIER_LIMIT_KG)
    {
        float l_perWingDiff_f = 0.0F;
        float l_overflow_f = 0.0F;
        Uint16 l_overCnt_u16 = 0U;

        /* 中低预设量优先在四个翼箱间均分。 */
        if (0U == l_wingTankCnt_u16)
        {
            return INVALID;
        }

        l_perWingDiff_f = l_diffFuel_f / (float)l_wingTankCnt_u16;
        for (l_tankIndex_u16 = 1U; l_tankIndex_u16 <= 4U; l_tankIndex_u16++)
        {
            if (0U != (l_mask_u16 & (1U << l_tankIndex_u16)))
            {
                float l_realTarget_f = v_currVol_f[l_tankIndex_u16] + l_perWingDiff_f;
                if (l_realTarget_f > RECEIVE_ALLOC_WING_TANK_MAX_KG)
                {
                    l_overflow_f += (l_realTarget_f - RECEIVE_ALLOC_WING_TANK_MAX_KG);
                    v_outTarget_f[l_tankIndex_u16] = RECEIVE_ALLOC_WING_TANK_MAX_KG;
                    l_overCnt_u16++;
                }
                else
                {
                    v_outTarget_f[l_tankIndex_u16] = l_realTarget_f;
                }
            }
        }

        if (l_overflow_f > 0.0F)
        {
            Uint16 l_remainCnt_u16 = l_wingTankCnt_u16 - l_overCnt_u16;
            float l_addFuel_f = 0.0F;

            /* 若只有一路超上限，则把溢出量重新分摊给其余仍可分配的翼箱。 */
            if ((l_overCnt_u16 > 1U) || (0U == l_remainCnt_u16))
            {
                return INVALID;
            }

            l_addFuel_f = l_overflow_f / (float)l_remainCnt_u16;
            for (l_tankIndex_u16 = 1U; l_tankIndex_u16 <= 4U; l_tankIndex_u16++)
            {
                if ((0U != (l_mask_u16 & (1U << l_tankIndex_u16))) &&
                    (v_outTarget_f[l_tankIndex_u16] < RECEIVE_ALLOC_WING_TANK_MAX_KG))
                {
                    v_outTarget_f[l_tankIndex_u16] += l_addFuel_f;
                    if (v_outTarget_f[l_tankIndex_u16] > RECEIVE_ALLOC_WING_TANK_MAX_KG)
                    {
                        return INVALID;
                    }
                }
            }
        }
    }
    else
    {
        float l_baseTarget0_f = (v_presetTotal_f / 2.0F) - 8200.0F;
        float l_baseTarget23_f = v_presetTotal_f / 4.0F;
        Uint16 l_overCnt_u16 = 0U;
        float l_overflow_f = 0.0F;
        float l_reductionPerTank_f = 0.0F;

        /* 高预设量场景按需求固定 1/4 号 4100kg，2/3 号按总量四分之一，余量落到 0 号箱。 */
        if (0U == (l_mask_u16 & (1U << 0U)))
        {
            /* 高预设量分配强依赖0号箱承接余量，0号箱不可参与时无法构造合法目标。 */
            return INVALID;
        }

        v_outTarget_f[0U] = l_baseTarget0_f;
        if (0U != (l_mask_u16 & (1U << 1U)))
        {
            v_outTarget_f[1U] = RECEIVE_ALLOC_WING_TANK_MAX_KG;
        }
        else
        {
            v_outTarget_f[1U] = v_currVol_f[1U];
        }
        if (0U != (l_mask_u16 & (1U << 2U)))
        {
            v_outTarget_f[2U] = l_baseTarget23_f;
        }
        else
        {
            v_outTarget_f[2U] = v_currVol_f[2U];
        }
        if (0U != (l_mask_u16 & (1U << 3U)))
        {
            v_outTarget_f[3U] = l_baseTarget23_f;
        }
        else
        {
            v_outTarget_f[3U] = v_currVol_f[3U];
        }
        if (0U != (l_mask_u16 & (1U << 4U)))
        {
            v_outTarget_f[4U] = RECEIVE_ALLOC_WING_TANK_MAX_KG;
        }
        else
        {
            v_outTarget_f[4U] = v_currVol_f[4U];
        }

        for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
        {
            if (v_currVol_f[l_tankIndex_u16] > v_outTarget_f[l_tankIndex_u16])
            {
                l_overCnt_u16++;
                l_overflow_f += (v_currVol_f[l_tankIndex_u16] - v_outTarget_f[l_tankIndex_u16]);
                v_outTarget_f[l_tankIndex_u16] = v_currVol_f[l_tankIndex_u16];
            }
        }

        if (l_overCnt_u16 > 1U)
        {
            /* 高预设量补偿策略只允许单箱“已超基础目标”；多箱同时超出时任务书未定义补偿路径。 */
            return INVALID;
        }

        if (l_overflow_f > 0.0F)
        {
            /* 单油箱超出基础分配时，优先从 2/3 号箱等量扣回补偿，扣不动则判分配失败。 */
            l_reductionPerTank_f = l_overflow_f / 2.0F;

            if (((0U != (l_mask_u16 & (1U << 2U))) && ((v_outTarget_f[2U] - l_reductionPerTank_f) < v_currVol_f[2U])) ||
                ((0U != (l_mask_u16 & (1U << 3U))) && ((v_outTarget_f[3U] - l_reductionPerTank_f) < v_currVol_f[3U])))
            {
                return INVALID;
            }

            if (0U != (l_mask_u16 & (1U << 2U)))
            {
                v_outTarget_f[2U] -= l_reductionPerTank_f;
            }
            if (0U != (l_mask_u16 & (1U << 3U)))
            {
                v_outTarget_f[3U] -= l_reductionPerTank_f;
            }
        }
    }

    return VALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveStageStandby
 *
 * 【功能描述】受油模式初始化
 *             建立受油模式默认输出和上下文初值
 * 【输入参数说明】v_p_ConData_t：系统控制数据指针
 * 【输出参数说明】无
 * 【其他说明】       当前进入受油模式后默认令三通阀转入受油位
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveStageStandby(ConData_t *v_p_ConData_t)
{
    /* 空指针时不进入受油初始化。 */
    if (NULL == v_p_ConData_t)
    {
        return;
    }

    /* 先清掉上一轮受油的全部上下文。 */
    ReceiveModeContextReset();
    /* 默认把RIU过程状态恢复到空闲。 */
    s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_IDLE;
    s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_NONE;
    /* 默认清除全部受油活门命令。 */
    s_RIUSendData_t.RCVcmd_t.all = 0U;
    /* 默认清除全部故障位。 */
    s_RIUSendData_t.RIUfltInfo1_t.all = 0U;
    s_RIUSendData_t.RIUfltInfo2_t.all = 0U;
    /* 进入受油模式后，先要求三通阀转到受油位。 */
    s_RIUSendData_t.ValveCtrl_t.bit.ST_ctrl_u16 = RECEIVE_ST_CMD_RECEIVE_POS;
    /* 连通阀默认保持关闭。 */
    s_RIUSendData_t.ValveCtrl_t.bit.LT_ctrl_u16 = VALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveModeTriggerFaultWithIsolation
 *
 * 【功能描述】触发受油故障并按指定隔离策略收口
 *             可按任务书口径选择“仅关三通阀”或“全关RCV并关三通阀”
 * 【输入参数说明】v_p_ConData_t：系统控制数据指针
 *                  v_reason_u16：故障原因码
 *                  v_closeAllRcv_u16：VALID-保持全部RCV关闭 / INVALID-仅关闭三通阀
 * 【输出参数说明】无
 * 【其他说明】       该函数会同时建立故障保持上下文
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveModeTriggerFaultWithIsolation(ConData_t *v_p_ConData_t,
                                                 Uint16 v_reason_u16,
                                                 Uint16 v_closeAllRcv_u16)
{
    Uint16 l_tankIndex_u16 = 0U; /* 油箱索引，用于按需要逐箱下发关闭命令。 */

    /* 一旦进入受油故障，就锁存故障标志和本次隔离策略。 */
    s_receiveCtx_t.faultActive_u16 = VALID;
    s_receiveCtx_t.faultCloseAllRcv_u16 = v_closeAllRcv_u16;

    if (VALID == v_closeAllRcv_u16)
    {
        for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
        {
            /* 需要“全关RCV”的故障场景下，逐箱下发关闭+断电关闭命令。 */
            ReceiveModeSetRcvClose(l_tankIndex_u16, VALID);
        }
    }

    /* 任务书明确要求的故障隔离动作统一至少关闭三通阀。 */
    s_RIUSendData_t.ValveCtrl_t.bit.ST_ctrl_u16 = RECEIVE_ST_CMD_CLOSED_POS;
    /* 故障输出统一上报为受油故障态，并保留原因码供告警字打包使用。 */
    s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_FAULT;
    s_RIUSendData_t.checkState_u16 = v_reason_u16;
    /* 置位完成标志，避免后续再走正常完成链。 */
    s_receiveCtx_t.completionIssued_u16 = VALID;
    s_receiveCtx_t.completionSettled_u16 = VALID;

    if (NULL != v_p_ConData_t)
    {
        /* 受油故障统一通过conFunc切入TASK_END，避免在多个阶段各自做不同收口。 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
        v_p_ConData_t->conFunc_u16 = CON_FUNC_4_TASK_END;
        v_p_ConData_t->workModeTime_u32 = sysTime();
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveStagePreCheck
 *
 * 【功能描述】受油模式任务前检查
 *             主动下发关键阀关闭目标，确认RCV全开、三通阀受油位、连通阀关闭等前置条件
 * 【输入参数说明】v_p_ConData_t：系统控制数据指针
 * 【输出参数说明】无
 * 【其他说明】       前检失败按测量故障或阀超时分别处理
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveStagePreCheck(ConData_t *v_p_ConData_t)
{
    RedunData_t l_redunData_t;               /* 冗余池数据，用于暂存冗余池读取结果。 */
    union RCV_Data l_rcvData_un16;           /* 受油活门反馈，用于暂存受油活门状态。 */
    union valve1_Data l_valve1Data_un16;     /* 第一组阀位反馈，用于暂存第一组阀位反馈。 */
    union valve2_Data l_valve2Data_un32;     /* 第二组阀位反馈，用于暂存第二组阀位反馈。 */
    union faultInfo_Data l_faultInfo_un16;   /* 故障反馈，用于暂存故障反馈。 */
    Uint16 l_rcvAllOpen_u16;                 /* 活门全开结果，用于标记5路受油活门是否全部在开位。 */
    Uint16 l_stValveOk_u16;                  /* 三通阀到位结果，用于标记三通阀是否已切到受油位。 */
    Uint16 l_ltValveClosed_u16;              /* 连通阀关闭结果，用于标记连通阀是否已关闭。 */
    Uint16 l_emergencyValveClosed_u16;       /* 应急阀关闭结果，用于标记左右应急放油切断阀是否都关闭。 */
    Uint16 l_podCutoffClosed_u16;            /* 吊舱阀关闭结果，用于标记左右吊舱切断阀是否都关闭。 */
    Uint16 l_pumpCutoffClosed_u16;           /* 泵阀关闭结果，用于标记四路加油泵切断阀是否都关闭。 */
    Uint16 l_ventValveOpen_u16;              /* 通气阀打开结果，用于标记左右电动通气阀是否都打开。 */
    Uint16 l_measureOk_u16;                  /* 测量正常结果，用于标记测量系统是否正常。 */
    Uint16 l_allPreCheckOk_u16;              /* 前检汇总结果，用于汇总所有前检结果。 */

    /* 空指针时不推进前检。 */
    if (NULL == v_p_ConData_t)
    {
        return;
    }

    if (VALID != ReceiveModeTaskValidCheck())
    {
        /* 受油模式指令撤销后，前检不再继续推进，统一切入任务结束态收口。 */
        ReceiveModeExitToTaskEnd(v_p_ConData_t);
        return;
    }

    /* 首次进入前检时，先建立空闲过程态并重申目标阀位命令。 */
    if (v_p_ConData_t->conFuncLast_u16 != v_p_ConData_t->conFunc_u16)
    {
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_IDLE;
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_NONE;

        /* 受油前检需要主动下发“关闭”目标，接口220定义 1=关闭。 */
        s_RIUSendData_t.ValveCtrl_t.bit.Pump0_Lcutoff_ctrl_u16 = VALID;
        s_RIUSendData_t.ValveCtrl_t.bit.Pump0_Rcutoff_ctrl_u16 = VALID;
        s_RIUSendData_t.ValveCtrl_t.bit.Pump2_cutoff_ctrl_u16 = VALID;
        s_RIUSendData_t.ValveCtrl_t.bit.Pump3_cutoff_ctrl_u16 = VALID;
        s_RIUSendData_t.ValveCtrl_t.bit.LPQD_ctrl_u16 = VALID;
        s_RIUSendData_t.ValveCtrl_t.bit.RPQD_ctrl_u16 = VALID;
        s_RIUSendData_t.ValveCtrl_t.bit.LYJFY_ctrl_u16 = VALID;
        s_RIUSendData_t.ValveCtrl_t.bit.RYJFY_ctrl_u16 = VALID;
        /* 消费入口沿，避免首拍初始化每拍重复执行。 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    }

    /* 前检每拍都先清掉旧故障位，再按当前反馈重算。 */
    s_RIUSendData_t.RIUfltInfo1_t.all = 0U;
    s_RIUSendData_t.RIUfltInfo2_t.all = 0U;

    /* 读取5路受油活门的上电/状态反馈。 */
    l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_RCV);
    l_rcvData_un16.all = (Uint16)(l_redunData_t.dataU_u32 & 0xFFFFU);
    /* 受油前检要求5路受油活门都处于打开状态。 */
    l_rcvAllOpen_u16 = l_rcvData_un16.bit.RCV0_state_u16 & l_rcvData_un16.bit.RCV1_state_u16 &
                       l_rcvData_un16.bit.RCV2_state_u16 & l_rcvData_un16.bit.RCV3_state_u16 &
                       l_rcvData_un16.bit.RCV4_state_u16;

    /* 读取三通阀、连通阀和通气阀反馈。 */
    l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_VALVE1);
    l_valve1Data_un16.all = (Uint16)(l_redunData_t.dataU_u32 & 0xFFFFU);
    l_stValveOk_u16 = (RECEIVE_ST_STATE_RECEIVE_POS == l_valve1Data_un16.bit.ST_state_u16);
    l_ltValveClosed_u16 = (RECEIVE_VALVE_STATE_CLOSED == l_valve1Data_un16.bit.LT_state_u16);
    l_ventValveOpen_u16 = (RECEIVE_VALVE_STATE_OPEN == l_valve1Data_un16.bit.LDDTQ_state_u16) &
                          (RECEIVE_VALVE_STATE_OPEN == l_valve1Data_un16.bit.RDDTQ_state_u16);

    /* 读取应急放油阀、吊舱切断阀和泵切断阀反馈。 */
    l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_VALVE2);
    l_valve2Data_un32.all = l_redunData_t.dataU_u32 & 0x3FFFFUL;
    l_emergencyValveClosed_u16 = (RECEIVE_VALVE_STATE_CLOSED == l_valve2Data_un32.bit.LYJFY_state_u32) &
                                 (RECEIVE_VALVE_STATE_CLOSED == l_valve2Data_un32.bit.RYJFY_state_u32);
    l_podCutoffClosed_u16 = (RECEIVE_VALVE_STATE_CLOSED == l_valve2Data_un32.bit.LPQD_state_u32) &
                            (RECEIVE_VALVE_STATE_CLOSED == l_valve2Data_un32.bit.RPQD_state_u32);
    l_pumpCutoffClosed_u16 =
        (RECEIVE_VALVE_STATE_CLOSED == l_valve2Data_un32.bit.Pump0_Lcutoff_state_u32) &
        (RECEIVE_VALVE_STATE_CLOSED == l_valve2Data_un32.bit.Pump0_Rcutoff_state_u32) &
        (RECEIVE_VALVE_STATE_CLOSED == l_valve2Data_un32.bit.Pump2_cutoff_state_u32) &
        (RECEIVE_VALVE_STATE_CLOSED == l_valve2Data_un32.bit.Pump3_cutoff_state_u32);

    /* 读取测量系统故障位，前检把故障、降级和传感器故障统一视为异常。 */
    l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FAULTINFO);
    l_faultInfo_un16.all = (Uint16)(l_redunData_t.dataU_u32 & 0xFFFFU);
    if (VALID == ReceiveModeMeasureFaultExists(l_faultInfo_un16))
    {
        l_measureOk_u16 = INVALID;
    }
    else
    {
        l_measureOk_u16 = VALID;
    }

    /* 只有所有前检条件同时满足，才允许进入受油预设。 */
    l_allPreCheckOk_u16 =
        l_rcvAllOpen_u16 & l_stValveOk_u16 & l_ltValveClosed_u16 & l_emergencyValveClosed_u16 &
        l_podCutoffClosed_u16 & l_pumpCutoffClosed_u16 & l_ventValveOpen_u16 & l_measureOk_u16;

    if (VALID == l_allPreCheckOk_u16)
    {
        /* 所有前检项满足后进入受油预设阶段。 */
        ReceiveModeContextReset();
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_REQUEST_PRESET;
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
        v_p_ConData_t->conFunc_u16 = CON_FUNC_2_FUEL_PRESET;
        v_p_ConData_t->workModeTime_u32 = sysTime();
    }
    else if ((sysTime() - v_p_ConData_t->workModeTime_u32) > PRE_TASK_CHECK_TIMEOUT_MS)
    {
        /* 超时后按未到位项分别置故障位，再切入受油故障链。 */
        if (INVALID == l_stValveOk_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.ST_fault_u16 = 1U;
        }
        if (INVALID == l_ltValveClosed_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.LT_fault_u16 = 1U;
        }
        if (RECEIVE_VALVE_STATE_CLOSED != l_valve2Data_un32.bit.LYJFY_state_u32)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.LYJFY_fault_u16 = 1U;
        }
        if (RECEIVE_VALVE_STATE_CLOSED != l_valve2Data_un32.bit.RYJFY_state_u32)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.RYJFY_fault_u16 = 1U;
        }
        if (RECEIVE_VALVE_STATE_CLOSED != l_valve2Data_un32.bit.LPQD_state_u32)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.LPQD_fault_u16 = 1U;
        }
        if (RECEIVE_VALVE_STATE_CLOSED != l_valve2Data_un32.bit.RPQD_state_u32)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.RPQD_fault_u16 = 1U;
        }
        if (RECEIVE_VALVE_STATE_OPEN != l_valve1Data_un16.bit.LDDTQ_state_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.LDDTQ_fault_u16 = 1U;
        }
        if (RECEIVE_VALVE_STATE_OPEN != l_valve1Data_un16.bit.RDDTQ_state_u16)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.RDDTQ_fault_u16 = 1U;
        }
        if (RECEIVE_VALVE_STATE_CLOSED != l_valve2Data_un32.bit.Pump0_Lcutoff_state_u32)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Lcutoff_fault_u16 = 1U;
        }
        if (RECEIVE_VALVE_STATE_CLOSED != l_valve2Data_un32.bit.Pump0_Rcutoff_state_u32)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump0_Rcutoff_fault_u16 = 1U;
        }
        if (RECEIVE_VALVE_STATE_CLOSED != l_valve2Data_un32.bit.Pump2_cutoff_state_u32)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump2_cutoff_fault_u16 = 1U;
        }
        if (RECEIVE_VALVE_STATE_CLOSED != l_valve2Data_un32.bit.Pump3_cutoff_state_u32)
        {
            s_RIUSendData_t.RIUfltInfo1_t.bit.Pump3_cutoff_fault_u16 = 1U;
        }
        if (INVALID == l_measureOk_u16)
        {
            /* 前检若由测量系统异常触发失败，同步把0232测量故障位置1。 */
            s_RIUSendData_t.RIUfltInfo2_t.bit.oilMS_falut_u16 = 1U;
            ReceiveModeTriggerFaultWithIsolation(v_p_ConData_t, RECEIVE_RIU_REASON_MEASURE, VALID);
        }
        else
        {
            ReceiveModeTriggerFaultWithIsolation(v_p_ConData_t, RECEIVE_RIU_REASON_VALVE_TIMEOUT, VALID);
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveStagePreset
 *
 * 【功能描述】受油模式预设分配
 *             获取总预设量并计算各箱目标油量，建立后续受油关闭策略
 * 【输入参数说明】v_p_ConData_t：系统控制数据指针
 * 【输出参数说明】无
 * 【其他说明】       预设无效或分配失败时进入受油故障链
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveStagePreset(ConData_t *v_p_ConData_t)
{
    union HLSensor_Data l_hlSensor_un16;       /* 高液位状态，用于暂存高液位状态。 */
    float l_presetTotal_f;                     /* 总预设量，用于记录当前总预设量。 */
    float l_currVol_af[RECEIVE_TANK_COUNT];    /* 各箱油量，用于缓存当前各箱油量。 */
    float l_totalVol_f = 0.0F;                 /* 当前总油量，用于累计当前总油量。 */
    Uint16 l_tankIndex_u16;                    /* 油箱索引，用于遍历5个油箱。 */

    /* 空指针时不推进预设。 */
    if (NULL == v_p_ConData_t)
    {
        return;
    }

    if (VALID != ReceiveModeTaskValidCheck())
    {
        /* 预设阶段若上位撤销受油模式，直接结束本轮受油流程。 */
        ReceiveModeExitToTaskEnd(v_p_ConData_t);
        return;
    }

    /* 预设首拍先要求RIU进入“请求预设”状态。 */
    if (v_p_ConData_t->conFuncLast_u16 != v_p_ConData_t->conFunc_u16)
    {
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_REQUEST_PRESET;
        s_receiveCtx_t.presetReady_u16 = INVALID;
        /* 首拍动作只执行一次。 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    }

    /* 读取RIU给出的总预设量。 */
    l_presetTotal_f = RedunDataGet(REDUN_INDEX_RIU_PRV).dataF_f;
    for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
    {
        /* 累加当前各箱油量，供预设合法性判断和分配计算共用。 */
        l_currVol_af[l_tankIndex_u16] = ReceiveModeLoadTankVolume(l_tankIndex_u16);
        l_totalVol_f += l_currVol_af[l_tankIndex_u16];
    }

    if ((l_presetTotal_f <= l_totalVol_f) || (l_presetTotal_f > RECEIVE_ALLOC_MAX_TOTAL_KG))
    {
        /* 预设值不合法时立即按预设失败处理，不再长时间停留在预设阶段等待刷新。 */
        ReceiveModeTriggerFaultWithIsolation(v_p_ConData_t, RECEIVE_RIU_REASON_PRESET_FAIL, VALID);
        return;
    }

    /* 读取高液位状态后，按任务书规则计算各箱目标油量。 */
    l_hlSensor_un16.all = (Uint16)(RedunDataGet(REDUN_INDEX_RIU_HL_SENSOR).dataU_u32 & 0xFFU);
    if (VALID != ReceiveModeBuildTargets(l_currVol_af, l_presetTotal_f, l_hlSensor_un16, s_receiveCtx_t.perTankTargetKg_f))
    {
        ReceiveModeTriggerFaultWithIsolation(v_p_ConData_t, RECEIVE_RIU_REASON_PRESET_FAIL, VALID);
        return;
    }

    s_receiveCtx_t.presetTotalKg_f = l_presetTotal_f;
    s_receiveCtx_t.initialTotalKg_f = l_totalVol_f;
    s_receiveCtx_t.presetReady_u16 = VALID;

    for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
    {
        /* 预设阶段先把已达到目标的油箱直接标记为关活门目标。 */
        if (l_currVol_af[l_tankIndex_u16] >= s_receiveCtx_t.perTankTargetKg_f[l_tankIndex_u16])
        {
            ReceiveModeSetRcvClose(l_tankIndex_u16, VALID);
        }
        else
        {
            ReceiveModeSetRcvClose(l_tankIndex_u16, INVALID);
        }
    }

    /* 预设完成后进入受油执行态。 */
    s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_ACTIVE;
    v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    v_p_ConData_t->conFunc_u16 = CON_FUNC_3_REFUEL_PROCESS;
    v_p_ConData_t->workModeTime_u32 = sysTime();
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveModeFaultLatchedHold
 *
 * 【功能描述】受油故障锁存保持
 *             在任务结束态保持故障输出和隔离命令，避免故障仅存在一拍
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       仅在故障已触发的受油任务结束路径调用
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveModeFaultLatchedHold(void)
{
    /* 循环索引用于逐箱保持关闭命令。 */
    Uint16 l_tankIndex_u16 = 0U;

    if (VALID == s_receiveCtx_t.faultCloseAllRcv_u16)
    {
        for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
        {
            /* 需要全关RCV的故障场景下，故障保持期间持续要求每一路受油活门关闭。 */
            ReceiveModeSetRcvClose(l_tankIndex_u16, VALID);
        }
    }

    /* 故障保持期间三通阀必须保持关闭位。 */
    s_RIUSendData_t.ValveCtrl_t.bit.ST_ctrl_u16 = RECEIVE_ST_CMD_CLOSED_POS;
    /* 故障保持期间过程状态始终上报故障。 */
    s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_FAULT;
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveStageProcess
 *
 * 【功能描述】受油执行阶段处理
 *             负责高液位保护、关活门确认、不平衡检测和完成判定
 * 【输入参数说明】v_p_ConData_t：系统控制数据指针
 * 【输出参数说明】无
 * 【其他说明】       完成判据按总油量达到预设总量处理
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveStageProcess(ConData_t *v_p_ConData_t)
{
    float l_currVol_af[RECEIVE_TANK_COUNT]; /* 各箱油量，用于缓存当前各箱油量。 */
    float l_totalVol_f = 0.0F;              /* 当前总油量，用于累计当前总油量。 */
    float l_imbalanceDiff_f = 0.0F;         /* 不平衡差值，用于记录左右翼箱总量差值绝对值。 */
    Uint16 l_tankIndex_u16 = 0U;            /* 油箱索引，用于逐箱处理受油逻辑。 */
    Uint16 l_hlFaultTriggered_u16 = INVALID;/* 高液位触发标志，用于标记高液位是否已触发故障。 */
    union HLSensor_Data l_hlSensor_un16;    /* 高液位反馈，用于暂存高液位反馈快照。 */
    union faultInfo_Data l_faultInfo_un16;  /* 测量故障反馈，用于暂存测量系统故障快照。 */

    /* 空指针时不推进执行态。 */
    if (NULL == v_p_ConData_t)
    {
        return;
    }

    if (VALID != ReceiveModeTaskValidCheck())
    {
        /* 执行态一旦检测到受油模式无效，立即切任务结束态。 */
        ReceiveModeExitToTaskEnd(v_p_ConData_t);
        return;
    }

    /* 进入执行态首拍时，默认把过程状态切到受油进行中。 */
    if (v_p_ConData_t->conFuncLast_u16 != v_p_ConData_t->conFunc_u16)
    {
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_ACTIVE;
        /* 消费入口沿，避免重复执行首拍逻辑。 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    }

    for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
    {
        /* 每拍都重读各箱油量，并更新当前总油量。 */
        l_currVol_af[l_tankIndex_u16] = ReceiveModeLoadTankVolume(l_tankIndex_u16);
        l_totalVol_f += l_currVol_af[l_tankIndex_u16];
    }

    /* 测量系统、机电系统通信和控制器故障都直接中止受油过程。 */
    l_hlSensor_un16.all = (Uint16)(RedunDataGet(REDUN_INDEX_RIU_HL_SENSOR).dataU_u32 & 0xFFU);
    l_faultInfo_un16.all = (Uint16)(RedunDataGet(REDUN_INDEX_RIU_FAULTINFO).dataU_u32 & 0xFFFFU);

    if (VALID == ReceiveModeMeasureFaultExists(l_faultInfo_un16))
    {
        s_RIUSendData_t.RIUfltInfo2_t.bit.oilMS_falut_u16 = 1U;
        /* 受油巡检测量故障按任务书口径只要求关三通阀并上报受油故障。 */
        ReceiveModeTriggerFaultWithIsolation(v_p_ConData_t, RECEIVE_RIU_REASON_MEASURE, INVALID);
        return;
    }

    for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
    {
        Uint16 l_hlStatus_u16 = 0U;

        /* 逐箱监测高液位，命中后直接转入故障分支，不再额外下发单箱RCV关闭命令。 */
        switch (l_tankIndex_u16)
        {
            case 0U: l_hlStatus_u16 = l_hlSensor_un16.bit.tank0_HL_sensor_u16; break;
            case 1U: l_hlStatus_u16 = l_hlSensor_un16.bit.tank1_HL_sensor_u16; break;
            case 2U: l_hlStatus_u16 = l_hlSensor_un16.bit.tank2_HL_sensor_u16; break;
            case 3U: l_hlStatus_u16 = l_hlSensor_un16.bit.tank3_HL_sensor_u16; break;
            case 4U: l_hlStatus_u16 = l_hlSensor_un16.bit.tank4_HL_sensor_u16; break;
            default: break;
        }

        if (VALID == l_hlStatus_u16)
        {
            /* 高液位命中后仅记录触发，由后续故障收口统一执行“关三通阀 + 上报关闭故障”。 */
            l_hlFaultTriggered_u16 = VALID;
        }
    }

    if (VALID == l_hlFaultTriggered_u16)
    {
        /* 高液位触发仅关闭三通阀并上报受油关闭故障。 */
        ReceiveModeTriggerFaultWithIsolation(v_p_ConData_t, RECEIVE_RIU_REASON_HL_SENSOR, INVALID);
        return;
    }

    if (VALID == s_receiveCtx_t.presetReady_u16)
    {
        union RCV_Data l_rcvData_un16;

        /* 进入正式受油后，按每箱目标油量逐步关闭对应受油活门。 */
        l_rcvData_un16.all = (Uint16)(RedunDataGet(REDUN_INDEX_RIU_RCV).dataU_u32 & 0xFFFFU);
        for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
        {
            if ((s_receiveCtx_t.perTankTargetKg_f[l_tankIndex_u16] > 0.0F) &&
                (l_currVol_af[l_tankIndex_u16] >= s_receiveCtx_t.perTankTargetKg_f[l_tankIndex_u16]))
            {
                /* 某箱达到目标后，统一向RIU下发“关闭 + 断电关闭”命令，并继续保持受油正常过程态。 */
                ReceiveModeSetRcvClose(l_tankIndex_u16, VALID);
            }

            if (s_receiveCtx_t.rcvCloseCmdTime_u32[l_tankIndex_u16] > 0UL)
            {
                Uint16 l_valveFeedback_u16 = 0U;

                switch (l_tankIndex_u16)
                {
                    case 0U: l_valveFeedback_u16 = l_rcvData_un16.bit.RCV0_Close_u16; break;
                    case 1U: l_valveFeedback_u16 = l_rcvData_un16.bit.RCV1_Close_u16; break;
                    case 2U: l_valveFeedback_u16 = l_rcvData_un16.bit.RCV2_Close_u16; break;
                    case 3U: l_valveFeedback_u16 = l_rcvData_un16.bit.RCV3_Close_u16; break;
                    case 4U: l_valveFeedback_u16 = l_rcvData_un16.bit.RCV4_Close_u16; break;
                    default: break;
                }

                if ((RECEIVE_VALVE_STATE_CLOSED != l_valveFeedback_u16) &&
                    ((sysTime() - s_receiveCtx_t.rcvCloseCmdTime_u32[l_tankIndex_u16]) > 10000UL))
                {
                    /* 10s仍未关到位时，把对应0232 RCV关闭故障位置1。 */
                    ReceiveModeRcvCloseFaultSet(l_tankIndex_u16, 1U);
                    /* 关活门命令发出后10s仍未到位，则按阀超时故障处理。 */
                    ReceiveModeTriggerFaultWithIsolation(v_p_ConData_t, RECEIVE_RIU_REASON_VALVE_TIMEOUT, VALID);
                    return;
                }
            }
        }
    }

    l_imbalanceDiff_f = (l_currVol_af[1] + l_currVol_af[2]) - (l_currVol_af[3] + l_currVol_af[4]);
    if (l_imbalanceDiff_f < 0.0F)
    {
        l_imbalanceDiff_f = -l_imbalanceDiff_f;
    }

    /* 受油过程中的左右不平衡按任务书阈值直接触发故障。 */
    if (l_imbalanceDiff_f >= RECEIVE_IMBALANCE_THRESHOLD_KG)
    {
        /* 左右总量差达到门限时，仅关闭三通阀并上报燃油不平衡告警。 */
        ReceiveModeTriggerFaultWithIsolation(v_p_ConData_t, RECEIVE_RIU_REASON_IMBALANCE, INVALID);
        return;
    }

    if ((VALID == s_receiveCtx_t.presetReady_u16) &&
        (l_totalVol_f >= s_receiveCtx_t.presetTotalKg_f) &&
        (INVALID == s_receiveCtx_t.completionIssued_u16))
    {
        /* 达到预设总量后，先统一关闭各箱受油活门，再启动完成延时窗口。 */
        for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
        {
            /* 总量完成时统一下发全部油箱的关闭+断电关闭命令。 */
            ReceiveModeSetRcvClose(l_tankIndex_u16, VALID);
        }
        /* 先向RIU上报受油完成，再进入三通阀延时关闭阶段。 */
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_COMPLETE;
        s_receiveCtx_t.completionIssued_u16 = VALID;
        s_receiveCtx_t.completionTimestamp_u32 = sysTime();
    }

    if (VALID == s_receiveCtx_t.completionIssued_u16)
    {
        /* 完成确认阶段先保持原三通阀位，只有延时满10s后才下发关闭位并切入任务结束。 */
        if ((INVALID == s_receiveCtx_t.completionSettled_u16) &&
            ((sysTime() - s_receiveCtx_t.completionTimestamp_u32) >= RECEIVE_COMPLETE_DELAY_MS))
        {
            /* 完成延时到达后才关闭三通阀，并由任务结束链统一完成模式回收。 */
            s_RIUSendData_t.ValveCtrl_t.bit.ST_ctrl_u16 = RECEIVE_ST_CMD_CLOSED_POS;
            s_receiveCtx_t.completionSettled_u16 = VALID;
            v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
            v_p_ConData_t->conFunc_u16 = CON_FUNC_4_TASK_END;
            v_p_ConData_t->workModeTime_u32 = sysTime();
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveStageTaskEnd
 *
 * 【功能描述】受油任务结束处理
 *             正常结束时清理上下文并回待机，故障结束时保持故障锁存
 * 【输入参数说明】v_p_ConData_t：系统控制数据指针
 * 【输出参数说明】无
 * 【其他说明】       故障路径不立即清空故障状态
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveStageTaskEnd(ConData_t *v_p_ConData_t)
{
    Uint16 l_tankIndex_u16 = 0U; /* 油箱索引，用于逐箱清除所有受油活门命令。 */

    /* 空指针时不推进任务结束。 */
    if (NULL == v_p_ConData_t)
    {
        return;
    }

    if (VALID == s_receiveCtx_t.faultActive_u16)
    {
        /* 受油故障进入TASK_END后保持故障与隔离命令，直到模式真正退出。 */
        ReceiveModeFaultLatchedHold();
        return;
    }

    if (v_p_ConData_t->conFuncLast_u16 != v_p_ConData_t->conFunc_u16)
    {
        for (l_tankIndex_u16 = 0U; l_tankIndex_u16 < RECEIVE_TANK_COUNT; l_tankIndex_u16++)
        {
            /* 正常结束时，主动清掉所有关闭命令和关闭确认计时。 */
            ReceiveModeSetRcvClose(l_tankIndex_u16, INVALID);
        }

        /* 正常结束时把RIU过程状态恢复为空闲。 */
        s_RIUSendData_t.currState_u16 = RECEIVE_RIU_STATE_IDLE;
        s_RIUSendData_t.checkState_u16 = RECEIVE_RIU_REASON_NONE;
        /* 三通阀在任务结束时回到关闭位。 */
        s_RIUSendData_t.ValveCtrl_t.bit.ST_ctrl_u16 = RECEIVE_ST_CMD_CLOSED_POS;
        /* 最后清空受油上下文，为下轮任务做准备。 */
        ReceiveModeContextReset();

        /* 模式回收统一在任务结束阶段完成。 */
        ControlModeReentryLatchSet(v_p_ConData_t->workMode_u16);
        v_p_ConData_t->workModeLast_u16 = v_p_ConData_t->workMode_u16;
        v_p_ConData_t->workMode_u16 = WORK_MODE_STANDBY;
        /* 任务结束首拍收口只执行一次。 */
        v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    }

    /* 任务结束最后一拍统一回待机功能态。 */
    v_p_ConData_t->conFuncLast_u16 = v_p_ConData_t->conFunc_u16;
    v_p_ConData_t->conFunc_u16 = CON_FUNC_0_STANDBY;
    v_p_ConData_t->workModeTime_u32 = sysTime();
}

/* ***************************************************************** */
/**
 * 【函数名】:ReceiveStageDispatch
 *
 * 【功能描述】受油模式阶段分发
 *             按当前控制功能调用受油初始化、前检、预设、执行和结束处理
 * 【输入参数说明】v_p_ConData_t：系统控制数据指针
 * 【输出参数说明】无
 * 【其他说明】       只负责分发，不在此函数内判断进入条件
 * 【返回】          无
 */
/* ***************************************************************** */
static void ReceiveStageDispatch(ConData_t *v_p_ConData_t)
{
    switch (v_p_ConData_t->conFunc_u16)
    {
        case CON_FUNC_0_STANDBY:        ReceiveStageStandby(v_p_ConData_t); break;
        case CON_FUNC_1_PRE_TASK_CHECK: ReceiveStagePreCheck(v_p_ConData_t); break;
        case CON_FUNC_2_FUEL_PRESET:    ReceiveStagePreset(v_p_ConData_t); break;
        case CON_FUNC_3_REFUEL_PROCESS: ReceiveStageProcess(v_p_ConData_t); break;
        case CON_FUNC_4_TASK_END:       ReceiveStageTaskEnd(v_p_ConData_t); break;
        default:
            /* conFunc 非法值(内存扰动/注入异常)统一回待机收口,避免卡死 */
            s_sysConData_t.conFuncLast_u16 = s_sysConData_t.conFunc_u16;
            s_sysConData_t.conFunc_u16 = CON_FUNC_0_STANDBY;
            s_sysConData_t.workModeTime_u32 = sysTime();
            break;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:WorkModeProcessReceive
 *
 * 【功能描述】受油模式处理入口
 *             统一调用受油模式阶段分发函数
 * 【输入参数说明】v_p_ConData_t：系统控制数据指针
 * 【输出参数说明】无
 * 【其他说明】       历史命名保持不变
 * 【返回】          无
 */
/* ***************************************************************** */
void WorkModeProcessReceive(ConData_t *v_p_ConData_t)
{
    if (NULL != v_p_ConData_t)
    {
        ReceiveStageDispatch(v_p_ConData_t);
    }
}
