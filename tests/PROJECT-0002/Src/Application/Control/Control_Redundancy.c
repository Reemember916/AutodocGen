#include "Global.h"
#include "Control_State.h"

RedunData_t s_redunData_t[REDUN_DATA_NUM];

/* ***************************************************************** */
/**
 * 【函数名】:RedundancyInit
 *
 * 【功能描述】初始化余度池
 *             清零全部余度槽位，并恢复默认来源状态
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       只处理本地缓存，不主动拉取外部通信数据
 * 【返回】	   无
 */
/* ***************************************************************** */
void RedundancyInit(void)
{
    Uint16 l_idx_u16 = 0U; /* 余度索引，用于遍历全部余度项。 */

    for (l_idx_u16 = 0U; l_idx_u16 < REDUN_DATA_NUM; l_idx_u16++)
    {
        /* 浮点型、整型和来源状态都在初始化时归零/置默认，避免旧内存残留影响首次判定。 */
        s_redunData_t[l_idx_u16].dataF_f = 0.0F;
        s_redunData_t[l_idx_u16].dataU_u32 = 0UL;
        s_redunData_t[l_idx_u16].dataState_u16 = REDUN_DATA_STATE_1;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RedunDataGet
 *
 * 【功能描述】获取单项余度数据
 *             按索引返回当前余度池中的可信值和来源状态
 * 【输入参数说明】v_idx_u16:余度索引
 * 【输出参数说明】无
 * 【其他说明】       索引越界时返回错误态数据
 * 【返回】	   对应余度项数据
 */
/* ***************************************************************** */
RedunData_t RedunDataGet(Uint16 v_idx_u16)
{
    RedunData_t l_res_t = {0.0F, 0UL, REDUN_DATA_STATE_ERR}; /* 返回结果，用于暂存单项余度数据。 */

    if (v_idx_u16 < REDUN_DATA_NUM)
    {
        l_res_t = s_redunData_t[v_idx_u16];
    }

    return l_res_t;
}

/* ***************************************************************** */
/**
 * 【函数名】:ControlCCDLActiveSourceSelect
 *
 * 【功能描述】选择当前有效的通道间CCDL来源
 *             优先使用DSP-DSP链路，异常时在CPLD迂回链路正常的前提下回退到CPLD
 * 【输入参数说明】vp_commID_u16：输出CCDL链路ID
 *                  vp_valid_u16：输出有效标志
 * 【输出参数说明】无
 * 【其他说明】       当前工程用IFBIT_INDEX_COMM_CCDL_CPLD承载“本DSP到本CPLD并经对端CPLD迂回”综合状态
 * 【返回】          REDUN_DATA_STATE_*，与余度池来源编码保持一致
 */
/* ***************************************************************** */
Uint16 ControlCCDLActiveSourceSelect(Uint16 *vp_commID_u16, Uint16 *vp_valid_u16)
{
    Uint16 l_state_u16 = REDUN_DATA_STATE_ERR; /* 来源状态，用于记录最终选中的CCDL来源编码。 */

    if (NULL != vp_commID_u16)
    {
        /* 先给出默认链路，保证调用者即使忽略valid标志，也拿到稳定返回值。 */
        *vp_commID_u16 = COMM_CCDL_SCI;
    }
    if (NULL != vp_valid_u16)
    {
        *vp_valid_u16 = INVALID;
    }

    /* 首选DSP-DSP CCDL；只有其异常时，才考虑退到CPLD迂回链路。 */
    if (IFBIT_TEST_OK == IFBITInfoGet(IFBIT_INDEX_COMM_CCDL_SCI))
    {
        if (NULL != vp_commID_u16)
        {
            *vp_commID_u16 = COMM_CCDL_SCI;
        }
        if (NULL != vp_valid_u16)
        {
            *vp_valid_u16 = VALID;
        }
        l_state_u16 = REDUN_DATA_STATE_1;
    }
    else if (IFBIT_TEST_OK == IFBITInfoGet(IFBIT_INDEX_COMM_CCDL_CPLD))
    {
        if (NULL != vp_commID_u16)
        {
            *vp_commID_u16 = COMM_CCDL_CPLD;
        }
        if (NULL != vp_valid_u16)
        {
            *vp_valid_u16 = VALID;
        }
        l_state_u16 = REDUN_DATA_STATE_2;
    }

    return l_state_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:RedundancyRIU
 *
 * 【功能描述】更新RIU余度数据
 *             复用控制主链当前选定的RIU源，将该源的解析结果写入RIU余度池
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       当前已与ControlRIUActiveSourceSelect()统一选源口径
 * 【返回】	   无
 */
/* ***************************************************************** */
static void RedundancyRIU(void)
{
    Uint16 l_idx_u16 = 0U;                         /* 余度索引，用于遍历RIU余度项。 */
    Uint16 l_dataState_u16 = REDUN_DATA_STATE_ERR; /* 来源状态，用于记录当前选中RIU来源的状态编码。 */
    RIU429InfoData_t l_raw_t;                      /* RIU原始数据，用于暂存当前选定RIU源的接收数据。 */
    Uint16 l_srcID_u16 = COMM429_RIU_1;            /* RIU通道号，用于记录当前选定的RIU通道。 */
    Uint16 l_valid_u16 = INVALID;                  /* RIU有效标志，用于标记当前是否找到有效RIU来源。 */
    memset(&l_raw_t, 0, sizeof(l_raw_t));

    /* RIU余度池不自己发明选源规则，直接复用控制链已经确认过的当前有效源。
     * 这样同一拍里控制判据和余度镜像看到的是同一份 RIU 快照，不会出现一边看本地一边看镜像。 */
    /* 余度链与控制链统一使用同一RIU源选择规则，避免一拍内混用不同通道快照。 */
    ControlRIUActiveSourceSelect(&l_srcID_u16, &l_valid_u16);
    if (VALID == l_valid_u16)
    {
        /* 先抓取当前控制链认定的同一RIU快照，再把来源状态编码同步映射进余度池。 */
        l_raw_t = Comm429RIURxDataGet(l_srcID_u16);
        if (COMM429_RIU_1 == l_srcID_u16)
        {
            l_dataState_u16 = REDUN_DATA_STATE_1;
        }
        else if (COMM429_RIU_2 == l_srcID_u16)
        {
            l_dataState_u16 = REDUN_DATA_STATE_2;
        }
        else if (COMM429_RIU_3 == l_srcID_u16)
        {
            l_dataState_u16 = REDUN_DATA_STATE_3;
        }
    }

    for (l_idx_u16 = 0U; l_idx_u16 < REDUN_RIU_NUM; l_idx_u16++)
    {
        /* 先整段刷新来源状态，确保单项值即使本拍未写入，也不会残留上拍来源编码。 */
        s_redunData_t[REDUN_INDEX_RIU_HEART + l_idx_u16].dataState_u16 = l_dataState_u16;
    }

    if (REDUN_DATA_STATE_ERR != l_dataState_u16)
    {
        /* 以下字段按RIU余度索引固定顺序展开写入，保持旧调用点索引语义不变。 */
        s_redunData_t[REDUN_INDEX_RIU_HEART].dataU_u32       = (Uint32)l_raw_t.heartB_u16;              /* RIU 心跳 */
        s_redunData_t[REDUN_INDEX_RIU_REFUEL_CMD].dataU_u32  = l_raw_t.fuelCmd_t.all;                 /* 补油命令 */
        s_redunData_t[REDUN_INDEX_RIU_RCV].dataU_u32         = l_raw_t.RCV_t.all;                      /* RCV 状态 */
        s_redunData_t[REDUN_INDEX_RIU_VALVE1].dataU_u32      = l_raw_t.valve1_t.all;                   /* 阀门1 */
        s_redunData_t[REDUN_INDEX_RIU_VALVE2].dataU_u32      = l_raw_t.valve2_t.all;                   /* 阀门2 */
        s_redunData_t[REDUN_INDEX_RIU_FUELPUMP].dataU_u32    = l_raw_t.fuelPump_t.all;                 /* 燃油泵 */
        s_redunData_t[REDUN_INDEX_RIU_HL_SENSOR].dataU_u32   = (Uint32)l_raw_t.HLSensor_t.all;         /* 液位传感器 */
        s_redunData_t[REDUN_INDEX_RIU_FAULTINFO].dataU_u32   = (Uint32)l_raw_t.faultInfo_t.all;       /* 故障信息 */
        s_redunData_t[REDUN_INDEX_RIU_PRV].dataF_f           = (float)l_raw_t.PRV_f;                   /* PRV 值 */
        s_redunData_t[REDUN_INDEX_RIU_FQ_TANK0].dataF_f      = (float)l_raw_t.tank0_vol_f;             /* 油箱0油量 */
        s_redunData_t[REDUN_INDEX_RIU_FQ_TANK1].dataF_f      = (float)l_raw_t.tank1_vol_f;             /* 油箱1油量 */
        s_redunData_t[REDUN_INDEX_RIU_FQ_TANK2].dataF_f      = (float)l_raw_t.tank2_vol_f;             /* 油箱2油量 */
        s_redunData_t[REDUN_INDEX_RIU_FQ_TANK3].dataF_f      = (float)l_raw_t.tank3_vol_f;             /* 油箱3油量 */
        s_redunData_t[REDUN_INDEX_RIU_FQ_TANK4].dataF_f      = (float)l_raw_t.tank4_vol_f;             /* 油箱4油量 */
        s_redunData_t[REDUN_INDEX_RIU_TOTAL_FUEL].dataF_f    = (float)l_raw_t.totalFuel_f;             /* 总油量 */
        s_redunData_t[REDUN_INDEX_RIU_AIR_SPEED].dataF_f     = (float)l_raw_t.airSpeed_f;              /* 空速 */
        s_redunData_t[REDUN_INDEX_RIU_OIL_MD].dataF_f        = (float)l_raw_t.oilMD_f;                 /* 油质/油量状态 */
        s_redunData_t[REDUN_INDEX_RIU_LP_PFV].dataF_f        = (float)l_raw_t.lpPFV_f;                 /* 左侧 PFV */
        s_redunData_t[REDUN_INDEX_RIU_RP_PFV].dataF_f        = (float)l_raw_t.rpPFV_f;                 /* 右侧 PFV */
        s_redunData_t[REDUN_INDEX_RIU_MAINT_CMD].dataU_u32   = (Uint32)l_raw_t.maintCmd_u16;          /* 维护命令 */
        s_redunData_t[REDUN_INDEX_RIU_WHEEL_LOAD].dataU_u32  = (Uint32)l_raw_t.wheelLoad_u16;         /* 轮载 */
        s_redunData_t[REDUN_INDEX_RIU_MBIT_EXEC].dataU_u32   = (Uint32)l_raw_t.mbitExec_u16;          /* MBIT 执行 */
        s_redunData_t[REDUN_INDEX_RIU_SOFTV_REQ].dataU_u32   = (Uint32)l_raw_t.softVersionReq_u16;    /* 软件版本请求 */
        s_redunData_t[REDUN_INDEX_RIU_OIL_RESET].dataU_u32   = (Uint32)l_raw_t.oilResetCmd_u16;       /* 油量复位命令 */
        s_redunData_t[REDUN_INDEX_RIU_LIFE_INFO].dataU_u32   = l_raw_t.lifeInfo_u32;                  /* 寿命信息 */
        s_redunData_t[REDUN_INDEX_RIU_CTRL_CMD].dataU_u32    = (Uint32)l_raw_t.ctrlCmd_u16;          /* 控制命令 */
        s_redunData_t[REDUN_INDEX_RIU_LP_BRIGHT].dataU_u32   = (Uint32)l_raw_t.lpBrightness_u16;     /* 左侧亮度 */
        s_redunData_t[REDUN_INDEX_RIU_RP_BRIGHT].dataU_u32   = (Uint32)l_raw_t.rpBrightness_u16;     /* 右侧亮度 */
        s_redunData_t[REDUN_INDEX_RIU_SC_CONFIG].dataU_u32   = l_raw_t.softVersion_deploy;           /* 部署软件版本 */
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RedundancyKZZZSideReset
 *
 * 【功能描述】清空单侧吊舱KZZZ余度区段
 *             在重新装载左右吊舱来源前，先把整侧索引区段刷成错误态和零值
 * 【输入参数说明】v_baseIdx_u16:该侧余度区段起始索引
 * 【输出参数说明】无
 * 【其他说明】       左右两侧索引布局同构，因此共用同一清零助手
 * 【返回】          无
 */
/* ***************************************************************** */
static void RedundancyKZZZSideReset(Uint16 v_baseIdx_u16)
{
    Uint16 l_idx_u16 = 0U; /* 单侧区段索引，用于遍历该侧全部KZZZ镜像项。 */

    for (l_idx_u16 = 0U; l_idx_u16 < REDUN_KZZZ_SIDE_NUM; l_idx_u16++)
    {
        /* 先清来源状态，再把数值域清零，避免本拍未覆盖字段残留上拍镜像。 */
        s_redunData_t[v_baseIdx_u16 + l_idx_u16].dataState_u16 = REDUN_DATA_STATE_ERR;
        s_redunData_t[v_baseIdx_u16 + l_idx_u16].dataU_u32 = 0UL;
        s_redunData_t[v_baseIdx_u16 + l_idx_u16].dataF_f = 0.0F;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RedundancyKZZZSideApply
 *
 * 【功能描述】按统一布局把单侧吊舱KZZZ数据写入余度池。
 *
 * 【输入参数说明】v_baseIdx_u16：该侧在余度池中的起始索引
 *               v_dataState_u16：来源状态编码
 *               vp_data_t：待写入的数据
 * 【输出参数说明】无
 * 【其他说明】       左右吊舱索引布局完全同构，因此共用同一写入助手
 * 【返回】          无
 */
/* ***************************************************************** */
static void RedundancyKZZZSideApply(Uint16 v_baseIdx_u16, Uint16 v_dataState_u16, const KZZZ429InfoData_t *vp_data_t)
{
    if ((REDUN_DATA_STATE_ERR == v_dataState_u16) || (NULL == vp_data_t))
    {
        /* 来源非法或数据指针为空时，调用者应保留前一步Reset后的错误态。 */
        return;
    }

    /* 单侧KZZZ余度布局按“请求/BIT/版本/寿命/部件/告警/量值”固定顺序写入，
     * 左右两侧仅通过v_baseIdx区分，保证接管时索引语义不变。 */
    s_redunData_t[v_baseIdx_u16 + 0U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 0U].dataU_u32 = (Uint32)vp_data_t->currTimeAsk_u16;          /* 请求时间 */
    s_redunData_t[v_baseIdx_u16 + 1U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 1U].dataU_u32 = (Uint32)vp_data_t->MBITFB_u16;               /* BIT 反馈 */
    s_redunData_t[v_baseIdx_u16 + 2U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 2U].dataU_u32 = vp_data_t->MBITFInfo_1_t.all;               /* MBIT 信息 */
    s_redunData_t[v_baseIdx_u16 + 3U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 3U].dataU_u32 = vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_APP].all;          /* APP 版本 */
    s_redunData_t[v_baseIdx_u16 + 4U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 4U].dataU_u32 = vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_MOTOR_CTRL].all;   /* 电机控制版本 */
    s_redunData_t[v_baseIdx_u16 + 5U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 5U].dataU_u32 = vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_SIGNAL_BOX].all;  /* 信号箱版本 */
    s_redunData_t[v_baseIdx_u16 + 6U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 6U].dataU_u32 = vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_BRAKE_CTRL].all;  /* 刹车控制版本 */
    s_redunData_t[v_baseIdx_u16 + 7U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 7U].dataU_u32 = vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_BIT_APP].all;    /* 自检 APP 版本 */
    s_redunData_t[v_baseIdx_u16 + 8U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 8U].dataU_u32 = vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_LOGIC].all;     /* 逻辑版本 */
    s_redunData_t[v_baseIdx_u16 + 9U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 9U].dataU_u32 = vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_UPGRADE_APP].all; /* 升级 APP 版本 */
    s_redunData_t[v_baseIdx_u16 + 10U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 10U].dataU_u32 = vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_MOTOR_LOGIC].all;/* 电机逻辑版本 */
    s_redunData_t[v_baseIdx_u16 + 11U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 11U].dataU_u32 = (Uint32)vp_data_t->Pre_FuelQtyRcv_FB_u16;       /* 预留油量反馈 */
    s_redunData_t[v_baseIdx_u16 + 12U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 12U].dataU_u32 = (Uint32)vp_data_t->flightHours_u16;            /* 飞行小时 */
    s_redunData_t[v_baseIdx_u16 + 13U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 13U].dataU_u32 = vp_data_t->remainLife_t.all;                    /* 剩余寿命 */
    s_redunData_t[v_baseIdx_u16 + 14U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 14U].dataF_f = vp_data_t->rgLength_f;                           /* 规程长度 */
    s_redunData_t[v_baseIdx_u16 + 15U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 15U].dataU_u32 = vp_data_t->jyzzState_t.all;                     /* 机务状态 */
    s_redunData_t[v_baseIdx_u16 + 16U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 16U].dataU_u32 = vp_data_t->componentState_t.all;                 /* 部件状态 */
    s_redunData_t[v_baseIdx_u16 + 17U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 17U].dataU_u32 = vp_data_t->faultInfo_t.all;                     /* 故障信息 */
    s_redunData_t[v_baseIdx_u16 + 18U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 18U].dataU_u32 = (Uint32)vp_data_t->turbineSpeed_u16;            /* 涡轮转速 */
    s_redunData_t[v_baseIdx_u16 + 19U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 19U].dataU_u32 = (Uint32)vp_data_t->fuelPressure_u16;             /* 燃油压力 */
    s_redunData_t[v_baseIdx_u16 + 20U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 20U].dataU_u32 = (Uint32)(Uint16)vp_data_t->fuelTemperature_i16;   /* 燃油温度 */
    s_redunData_t[v_baseIdx_u16 + 21U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 21U].dataU_u32 = (Uint32)vp_data_t->turbinePumpPressure_u16;      /* 涡轮泵压力 */
    s_redunData_t[v_baseIdx_u16 + 22U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 22U].dataU_u32 = (Uint32)vp_data_t->fuelFlow_u16;                 /* 燃油流量 */
    s_redunData_t[v_baseIdx_u16 + 23U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 23U].dataU_u32 = (Uint32)vp_data_t->fuelLevel_u16;                /* 燃油液位 */
    s_redunData_t[v_baseIdx_u16 + 24U].dataState_u16 = v_dataState_u16;
    s_redunData_t[v_baseIdx_u16 + 24U].dataU_u32 = (Uint32)vp_data_t->totalFuel_u16;                /* 总燃油量 */
}

/* ***************************************************************** */
/**
 * 【函数名】:RedundancyKZZZ
 *
 * 【功能描述】更新KZZZ余度数据
 *             左右吊舱先取本地429数据，本地失效且CCDL镜像有效时按侧接管对端镜像
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       dataState=1/2 表示本地左右吊舱，dataState=3 表示对端经CCDL镜像接管
 * 【返回】	   无
 */
/* ***************************************************************** */
static void RedundancyKZZZ(void)
{
    Uint16 l_ccdlID_u16 = COMM_CCDL_SCI;                          /* CCDL链路，用于记录当前选定的CCDL链路ID。 */
    Uint16 l_ccdlValid_u16 = INVALID;                             /* CCDL有效标志，用于标记当前是否存在可用对端镜像链路。 */
    Uint16 l_leftDataState_u16 = REDUN_DATA_STATE_ERR;            /* 左吊舱来源状态。 */
    Uint16 l_rightDataState_u16 = REDUN_DATA_STATE_ERR;           /* 右吊舱来源状态。 */
    KZZZ429InfoData_t l_leftData_t = {0};                         /* 左吊舱最终采用的数据。 */
    KZZZ429InfoData_t l_rightData_t = {0};                        /* 右吊舱最终采用的数据。 */

    /* 左右吊舱虽然都叫 KZZZ，但在控制语义上是两个独立对象。
     * 一侧本地链路失效时，只允许该侧单独退到 CCDL 镜像，另一侧继续保持自己的最优来源。 */
    /* 左右吊舱是独立对象，因此本地/对端镜像接管也必须逐侧判定。 */
    (void)ControlCCDLActiveSourceSelect(&l_ccdlID_u16, &l_ccdlValid_u16);

    /* 左侧优先使用本地左KZZZ 429；本地异常时，再单独判断是否允许左侧镜像接管。 */
    if (RX429_STATE_OK == Comm429KZZZRxStateGet(COMM429_KZZZ_1).rxState_u16)
    {
        l_leftDataState_u16 = REDUN_DATA_STATE_1;
        l_leftData_t = Comm429KzzzRxDataGet(COMM429_KZZZ_1);
    }
    else if ((VALID == l_ccdlValid_u16) &&
             (VALID == Comm429KZZZCcdlExtValidGet(l_ccdlID_u16, COMM429_KZZZ_1)))
    {
        /* 左侧本地链路失效时，仅左侧回退到CCDL镜像，不影响右侧来源选择。 */
        l_leftDataState_u16 = REDUN_DATA_STATE_3;
        l_leftData_t = Comm429KZZZCcdlExtDataGet(l_ccdlID_u16, COMM429_KZZZ_1);
    }

    /* 右侧同理独立选源，左右两侧不会因为对方链路异常而一起切来源。 */
    if (RX429_STATE_OK == Comm429KZZZRxStateGet(COMM429_KZZZ_2).rxState_u16)
    {
        l_rightDataState_u16 = REDUN_DATA_STATE_2;
        l_rightData_t = Comm429KzzzRxDataGet(COMM429_KZZZ_2);
    }
    else if ((VALID == l_ccdlValid_u16) &&
             (VALID == Comm429KZZZCcdlExtValidGet(l_ccdlID_u16, COMM429_KZZZ_2)))
    {
        /* 右侧同理逐侧接管，避免“任一侧异常导致双侧一起切镜像”。 */
        l_rightDataState_u16 = REDUN_DATA_STATE_3;
        l_rightData_t = Comm429KZZZCcdlExtDataGet(l_ccdlID_u16, COMM429_KZZZ_2);
    }

    /* 每拍都先整侧清空，再按最终选源结果回填，保证失效侧不会残留旧镜像。 */
    RedundancyKZZZSideReset(REDUN_INDEX_KZZZ_L_CURR_TIME_REQ);
    RedundancyKZZZSideReset(REDUN_INDEX_KZZZ_R_CURR_TIME_REQ);
    /* 左右两侧最终数据各自写回自己的索引区段。 */
    RedundancyKZZZSideApply(REDUN_INDEX_KZZZ_L_CURR_TIME_REQ, l_leftDataState_u16, &l_leftData_t);
    RedundancyKZZZSideApply(REDUN_INDEX_KZZZ_R_CURR_TIME_REQ, l_rightDataState_u16, &l_rightData_t);
}

/* ***************************************************************** */
/**
 * 【函数名】:RedundancyCCDL
 *
 * 【功能描述】更新CCDL余度数据
 *             在SCI与CPLD两条CCDL链路中选择有效源，并写入基础帧余度数据
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       仅处理CCDL基础帧状态，不在此消费RIU/KZZZ扩展镜像
 * 【返回】	   无
 */
/* ***************************************************************** */
static void RedundancyCCDLDefaultApply(void)
{
    Uint16 l_idx_u16 = 0U; /* 余度索引，用于遍历CCDL余度项。 */

    for (l_idx_u16 = 0U; l_idx_u16 < REDUN_CCDL_NUM; l_idx_u16++)
    {
        s_redunData_t[REDUN_INDEX_CCDL_SYSST + l_idx_u16].dataState_u16 = REDUN_DATA_STATE_ERR;
    }

    /* CCDL故障时强制写入默认值，避免余度池残留旧镜像。历史兼容字段一并清零。 */
    s_redunData_t[REDUN_INDEX_CCDL_SYSST].dataU_u32  = (Uint32)SYS_STATE_1WORK;
    s_redunData_t[REDUN_INDEX_CCDL_CHTYPE].dataU_u32 = (Uint32)CH_TYPE_INIT;
    s_redunData_t[REDUN_INDEX_CCDL_CHNVM].dataU_u32  = (Uint32)TYPEJUDGE_CODE_NONE;
    s_redunData_t[REDUN_INDEX_CCDL_RADM].dataU_u32   = 0UL;
    s_redunData_t[REDUN_INDEX_CCDL_SOFTVC].dataU_u32 = 0UL;
    s_redunData_t[REDUN_INDEX_CCDL_SOFTVO].dataU_u32 = 0UL;
    s_redunData_t[REDUN_INDEX_CCDL_SOFTVL].dataU_u32 = 0UL;
}

/* ***************************************************************** */
/**
 * 【函数名】:RedundancyCCDL
 *
 * 【功能描述】更新CCDL余度数据
 *             优先使用DSP-DSP CCDL；其异常时在CPLD迂回链路正常的前提下回退到CPLD
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       通道间CCDL整体故障时，将基础状态镜像刷成任务书要求的安全默认值
 * 【返回】	   无
 */
/* ***************************************************************** */
static void RedundancyCCDL(void)
{
    Uint16 l_idx_u16 = 0U;                         /* 余度索引，用于遍历CCDL余度项。 */
    Uint16 l_ccdlID_u16 = COMM_CCDL_SCI;           /* CCDL链路，用于记录当前选定的CCDL链路ID。 */
    Uint16 l_ccdlValid_u16 = INVALID;              /* CCDL有效标志，用于标记当前是否找到有效CCDL来源。 */
    Uint16 l_dataState_u16 = REDUN_DATA_STATE_ERR; /* 来源状态，用于记录当前选中CCDL来源的状态编码。 */
    PeerBaseStatus_t l_peerBase_t;                 /* 对端基础状态，用于暂存对端CCDL基础帧数据。 */
    memset(&l_peerBase_t, 0, sizeof(l_peerBase_t));

    /* CCDL余度只镜像“对端基础状态”这一层事实，不在这里顺手混入 RIU/KZZZ 业务数据。
     * 这样做是为了把主备仲裁链和业务接管链分开，避免一条链路抖动时把两类判断一起带乱。 */
    /* CCDL只承载基础帧状态仲裁，不在这里消费业务镜像，避免主备链和业务链交叉污染。 */
    l_dataState_u16 = ControlCCDLActiveSourceSelect(&l_ccdlID_u16, &l_ccdlValid_u16);
    if (VALID == l_ccdlValid_u16)
    {
        l_peerBase_t = CommCCDLPeerBaseGet(l_ccdlID_u16);
    }

    for (l_idx_u16 = 0U; l_idx_u16 < REDUN_CCDL_NUM; l_idx_u16++)
    {
        /* 基础帧整组一起刷新来源状态，防止链路切换时出现半组旧数据。 */
        s_redunData_t[REDUN_INDEX_CCDL_SYSST + l_idx_u16].dataState_u16 = l_dataState_u16;
    }

    if (VALID == l_ccdlValid_u16)
    {
        /* 当前拍只把“同一条CCDL链路”上的整组基础状态一起写入，避免出现混搭镜像。 */
        s_redunData_t[REDUN_INDEX_CCDL_SYSST].dataU_u32   = (Uint32)l_peerBase_t.sysState_u16;
        s_redunData_t[REDUN_INDEX_CCDL_CHTYPE].dataU_u32  = (Uint32)l_peerBase_t.chType_u16;
        s_redunData_t[REDUN_INDEX_CCDL_CHNVM].dataU_u32   = (Uint32)l_peerBase_t.preferredMasterChId_u16;
        s_redunData_t[REDUN_INDEX_CCDL_RADM].dataU_u32    = (Uint32)l_peerBase_t.randData_u16;
        s_redunData_t[REDUN_INDEX_CCDL_SOFTVC].dataU_u32  = (Uint32)l_peerBase_t.softV_DSP_u16;
        s_redunData_t[REDUN_INDEX_CCDL_SOFTVO].dataU_u32  = (Uint32)l_peerBase_t.ctrlInfo_u16;
        s_redunData_t[REDUN_INDEX_CCDL_SOFTVL].dataU_u32  = (Uint32)l_peerBase_t.softV_CPLD_u16;
    }
    else
    {
        RedundancyCCDLDefaultApply();
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:Redundancy
 *
 * 【功能描述】执行全量余度更新
 *             依次刷新RIU、KZZZ和CCDL三组余度数据
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       主循环每拍调用一次，作为控制链唯一可信值刷新入口
 * 【返回】	   无
 */
/* ***************************************************************** */
void Redundancy(void)
{
    /* RIU、KZZZ、CCDL 三组余度按固定顺序刷新，供后续控制链使用同一拍可信事实源。 */
    RedundancyRIU();
    RedundancyKZZZ();
    RedundancyCCDL();
}

