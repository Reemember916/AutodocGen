/**********************************************************************************
 *
 * 文件名称:    Comm429RIU.c
 * 文件日期:   REDACTED
 * 程序版本:   V2.00
 * 功能说明:   远程接口单元(RIU)ARINC429通信收发处理
 *
 *********************************************************************************/

#include "Global.h"
#include "Comm429RIU.h"

extern RIU429InfoData_t s_Comm429RIUData_t[COMM429_RIU_NUM];

/* ***************************************************************** */
/* 模块内私有数据定义 */
/* ***************************************************************** */

/* 远程接口单元通信ID配置表 */
Uint16  s_RIUCommIDConf_u16[COMM429_RIU_NUM] =
            {
            COMMDRI_429_ID_9,
            COMMDRI_429_NUM,
            COMMDRI_429_NUM
            };

A429Info_t s_Comm429RIUInfo_t[COMM429_RIU_NUM];    /* RIU429接收信息数组   */

RIU429InfoData_t s_Comm429RIUData_t[COMM429_RIU_NUM]; /* 来自RIU429的通信数据 */

RIU429OrigData_t s_RIUOrigData_t[COMM429_RIU_NUM]; /* 来自RIU429的通信数据 */

RIU429Data_Type s_RIU429Data_t[COMM429_RIU_NUM][RIU429_IDATA_NUM]; /* RIU429信息数据 */

static Uint32 s_lastTxWord_u32 = 0UL;                     /* 最近一次发送的429原始字 */

/* 接收数据标号配置表 */
Uint16  s_RIU429Rx_labelConf_u16[RIU_R_DATA_NUM] =
            {
                    RIU_LABEL_R_DATE_YMD,
                    RIU_LABEL_R_TIME_HMS,
                    RIU_LABEL_R_MAINT_CMD,
                    RIU_LABEL_R_WHEEL_LOAD,
                    RIU_LABEL_R_HEART,
                    RIU_LABEL_R_MBIT_EXEC,
                    RIU_LABEL_R_SOFTV_REQ_INFO,
                    RIU_LABEL_R_OIL_RESET,
                    RIU_LABEL_R_LIFE_INFO,
                    RIU_LABEL_R_CTRL_CMD,
                    RIU_LABEL_R_RCV,
                    RIU_LABEL_R_VALVE1,
                    RIU_LABEL_R_HL_SENSOR,
                    RIU_LABEL_R_VALVE2,
                    RIU_LABEL_R_FUELPUMP,
                    RIU_LABEL_R_FAULTINFO,
                    RIU_LABEL_R_FQ_TANK0,
                    RIU_LABEL_R_FQ_TANK1,
                    RIU_LABEL_R_FQ_TANK2,
                    RIU_LABEL_R_FQ_TANK3,
                    RIU_LABEL_R_FQ_TANK4,
                    RIU_LABEL_R_TOTAL_FUEL,
                    RIU_LABEL_R_PRV,
                    RIU_LABEL_R_LP_PFV,
                    RIU_LABEL_R_RP_PFV,
                    RIU_LABEL_R_IAS,
                    RIU_LABEL_R_FUEL_DENSITY,
                    RIU_LABEL_R_LP_BRIGHTNESS,
                    RIU_LABEL_R_RP_BRIGHTNESS
            };

/* 发送数据标号配置 */
Uint16 s_RIU429TxLabel_u16[RIU_T_DATA_NUM] =
            {
                RIU_LABEL_T_BUS_HEART,
                RIU_LABEL_T_PUBIT_ALARM_1,
                RIU_LABEL_T_MBIT_EXEC_FB,
                RIU_LABEL_T_UPLOAD_MBIT_RESULT,
                RIU_LABEL_T_CTRL_CMD_1,
                RIU_LABEL_T_CTRL_CMD_2,
                RIU_LABEL_T_CTRL_CMD_3,
                RIU_LABEL_T_STATUS_INFO,
                RIU_LABEL_T_FAULT_INFO_1,
                RIU_LABEL_T_FAULT_INFO_2,
                RIU_LABEL_T_WARN_INFO,
                RIU_LABEL_T_TIP_INFO,
                RIU_LABEL_T_CTRL_SWV_CH1,
                RIU_LABEL_T_CTRL_SWV_CH2,
                RIU_LABEL_T_LOGIC_SWV_CH1,
                RIU_LABEL_T_LOGIC_SWV_CH2,
                RIU_LABEL_T_LP_SOFTV_CTRL,
                RIU_LABEL_T_LP_SOFTV_MOTOR_CTRL,
                RIU_LABEL_T_LP_SOFTV_SIGNAL_BOX,
                RIU_LABEL_T_LP_SOFTV_BRAKE_CTRL,
                RIU_LABEL_T_LP_SOFTV_BIT_APP,
                RIU_LABEL_T_LP_SOFTV_CTRL_LOGIC,
                RIU_LABEL_T_LP_SOFTV_MOTOR_LOGIC,
                RIU_LABEL_T_LP_SOFTV_CTRL_UPGRADE_APP,
                RIU_LABEL_T_LP_PRE_FUEL_RCV_FB,
                RIU_LABEL_T_LP_REMAIN_FLIGHT_HOUR,
                RIU_LABEL_T_LP_REMAIN_CALENDAR_LIFE,
                RIU_LABEL_T_LP_OIL_RESET_RCV_FB,
                RIU_LABEL_T_LP_TURBINE_SPEED,
                RIU_LABEL_T_LP_FUEL_PRESS,
                RIU_LABEL_T_LP_PUMP_PRESS,
                RIU_LABEL_T_LP_FUEL_FLOW,
                RIU_LABEL_T_LP_FUEL_LEVEL,
                RIU_LABEL_T_LP_TOTAL_FUEL,
                RIU_LABEL_T_LP_FUEL_TEMP,
                RIU_LABEL_T_LP_RG_LEN,
                RIU_LABEL_T_LP_JYZZ_STATE,
                RIU_LABEL_T_LP_COMPONENT_STATE,
                RIU_LABEL_T_LP_FAULT_WARN,
                RIU_LABEL_T_LP_FAULT_INFO_1,
                RIU_LABEL_T_LP_FAULT_INFO_2,
                RIU_LABEL_T_LP_CMD_FB,
                RIU_LABEL_T_LP_MOTOR_SPEED,
                RIU_LABEL_T_LP_CTRL_TEMP,
                RIU_LABEL_T_RP_SOFTV_CTRL,
                RIU_LABEL_T_RP_SOFTV_MOTOR_CTRL,
                RIU_LABEL_T_RP_SOFTV_SIGNAL_BOX,
                RIU_LABEL_T_RP_SOFTV_BRAKE_CTRL,
                RIU_LABEL_T_RP_SOFTV_BIT_APP,
                RIU_LABEL_T_RP_SOFTV_CTRL_LOGIC,
                RIU_LABEL_T_RP_SOFTV_MOTOR_LOGIC,
                RIU_LABEL_T_RP_SOFTV_CTRL_UPGRADE_APP,
                RIU_LABEL_T_RP_PRE_FUEL_RCV_FB,
                RIU_LABEL_T_RP_REMAIN_FLIGHT_HOUR,
                RIU_LABEL_T_RP_REMAIN_CALENDAR_LIFE,
                RIU_LABEL_T_RP_OIL_RESET_RCV_FB,
                RIU_LABEL_T_RP_TURBINE_SPEED,
                RIU_LABEL_T_RP_FUEL_PRESS,
                RIU_LABEL_T_RP_PUMP_PRESS,
                RIU_LABEL_T_RP_FUEL_FLOW,
                RIU_LABEL_T_RP_FUEL_LEVEL,
                RIU_LABEL_T_RP_TOTAL_FUEL,
                RIU_LABEL_T_RP_FUEL_TEMP,
                RIU_LABEL_T_RP_RG_LEN,
                RIU_LABEL_T_RP_JYZZ_STATE,
                RIU_LABEL_T_RP_COMPONENT_STATE,
                RIU_LABEL_T_RP_FAULT_WARN,
                RIU_LABEL_T_RP_FAULT_INFO_1,
                RIU_LABEL_T_RP_FAULT_INFO_2,
                RIU_LABEL_T_RP_CMD_FB,
                RIU_LABEL_T_RP_MOTOR_SPEED,
                RIU_LABEL_T_RP_CTRL_TEMP
            };

Uint32 s_RIU429TxCnt_u32[RIU_T_DATA_NUM];           /* 各发送标号累计发送计数 */
Uint32 s_RIU429TimeoutCnt_u32[COMM429_RIU_NUM];     /* 各通道接收超时计数 */
Uint32 s_RIU429Press34PlaceholderCnt_u32 = 0UL;     /* 压力3/4占位发送计数 */


/* ***************************************************************** */
/* 模块内私有 helper */
/* ***************************************************************** */

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUSsmGet
 *    【功能描述】:   根据有效标志返回RIU发送SSM编码
 *    【输入参数说明】:valid ---- VALID/INVALID
 *    【输出参数说明】:NONE
 *    【其他说明】:   ARINC429标准语义: 有效=SSM_NORM(11), 无效=SSM_NOCOMDATA(01)
 *    【返回】:       SSM_NORM / SSM_NOCOMDATA
 */
/* ***************************************************************** */
static Uint16 Comm429RIUSsmGet(Uint16 valid)
{
    Uint16 l_ssm_u16 = SSM_NOCOMDATA;

    if (VALID == valid)
    {
        /* RIU只把SSM_NORM当作有效数据，其余状态都按无通信数据处理。 */
        l_ssm_u16 = SSM_NORM;
    }

    return l_ssm_u16;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUUnsignedPack
 *    【功能描述】:   无符号数据限幅打包
 *    【输入参数说明】:value ---- 原始值
 *                    width ---- 位宽(1~21)
 *    【输出参数说明】:NONE
 *    【其他说明】:   超过位宽最大值时限幅到最大值
 *    【返回】:       限幅后的数据
 */
/* ***************************************************************** */
static Uint32 Comm429RIUUnsignedPack(Uint32 value, Uint16 width)
{
    Uint32 l_max_u32 = 0UL;
    Uint32 l_value_u32 = 0UL;

    if (0U != width)
    {
        /* 位宽≥21时直接取21位最大值，否则按位宽计算 */
        if (width >= 21U)
        {
            l_max_u32 = 0x1FFFFFUL;
        }
        else
        {
            l_max_u32 = (1UL << width) - 1UL;
        }

        if (value > l_max_u32)
        {
            /* 上位机字段宽度固定，超范围时限幅比截断更容易排查。 */
            l_value_u32 = l_max_u32;
        }
        else
        {
            l_value_u32 = value;
        }
    }
    return l_value_u32;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUSignedMagnitudePack
 *    【功能描述】:   有符号整数按符号-幅度格式打包为ARINC429数据字段
 *    【输入参数说明】:v_value_i16 ---- 有符号输入值
 *                    v_width_u16 ---- 幅度位宽
 *    【输出参数说明】:NONE
 *    【其他说明】:   符号位bit20，幅度由无符号打包函数填入
 *    【返回】:       打包后的32位数据字
 */
/* ***************************************************************** */
static Uint32 Comm429RIUSignedMagnitudePack(Int16 v_value_i16, Uint16 v_width_u16)
{
    Uint32 l_data_u32 = 0UL;
    Uint32 l_abs_u32 = 0UL;

    /* 负数置符号位，取绝对值 */
    if(v_value_i16 < 0)
    {
        l_abs_u32 = (Uint32)(-v_value_i16);
        l_data_u32 |= (1UL << 20U);  /* DOCX bit29 符号位，对应data bit20 */
    }
    else
    {
        l_abs_u32 = (Uint32)v_value_i16;
    }

    /* 幅度按位宽限幅后填入 */
    l_data_u32 |= Comm429RIUUnsignedPack(l_abs_u32, v_width_u16);
    return l_data_u32;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUVersionRawPack
 *    【功能描述】:   版本号位域重组打包
 *    【输入参数说明】:version ---- 原始版本号字
 *    【输出参数说明】:NONE
 *    【其他说明】:   将版本号4段4bit重新排列到连续16bit
 *    【返回】:       重组后的版本号数据
 */
/* ***************************************************************** */
static Uint32 Comm429RIUVersionRawPack(Uint32 version)
{
    /* 任务书版本号只取4个小段，重排后作为连续16bit数据发送。 */
    return ((((Uint32)((version >> 14U) & 0x0FU)) << 0U) |
            (((Uint32)((version >> 11U) & 0x0FU)) << 4U) |
            (((Uint32)((version >> 8U) & 0x0FU)) << 8U) |
            (((Uint32)(version & 0x0FU)) << 12U));
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIURxWordMark
 *    【功能描述】:   接收字标记：记录原始接收数据、累计接收计数与最近接收时间
 *    【输入参数说明】:v_ID_u16 ---- 端口号
 *                    v_index_u16 ---- 接收数据索引
 *                    v_msgData_u32 ---- 原始接收字
 *    【输出参数说明】:NONE
 *    【其他说明】:   供健康监测与故障判定使用
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void Comm429RIURxWordMark(Uint16 v_ID_u16, Uint16 v_index_u16, Uint32 v_msgData_u32)
{
    if((v_ID_u16 < COMM429_RIU_NUM) && (v_index_u16 < RIU_R_DATA_NUM))
    {
        /* 原始字、计数和接收时间一起刷新，后续BIT才能判断数据是否持续更新。 */
        s_RIUOrigData_t[v_ID_u16].Orig_Rx_t[v_index_u16].OrigData_u32 = v_msgData_u32;
        s_RIUOrigData_t[v_ID_u16].Orig_Rx_t[v_index_u16].Cnt_u16++;
        s_Comm429RIUInfo_t[v_ID_u16].rxCount_u32++;
        s_Comm429RIUInfo_t[v_ID_u16].rxTime_u32 = sysTime();
    }
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIURxSsmValidGet
 *    【功能描述】:   接收字SSM有效性判定：全标签统一校验SSM=SSM_NORM
 *    【输入参数说明】:v_data_un ---- 接收到的ARINC429联合数据
 *    【输出参数说明】:NONE
 *    【其他说明】:   与KZZZ一致，所有接收标签均要求SSM_NORM，否则判无效
 *    【返回】:       VALID 表示SSM有效, INVALID 表示SSM无效
 */
/* ***************************************************************** */
static Uint16 Comm429RIURxSsmValidGet(union arinc429Data v_data_un)
{
    Uint16 l_valid_u16 = VALID;

    if(SSM_NORM != v_data_un.bit.ssm)
    {
        /* SSM不是正常值时，即使label正确也不能参与控制和余度选择。 */
        l_valid_u16 = INVALID;
    }

    return l_valid_u16;
}


/* ***************************************************************** */
/* 发送打包函数 */
/* ***************************************************************** */

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUCtrlCmd1Pack
 *    【功能描述】:   控制命令1打包：组装泵切断阀控制位
 *    【输入参数说明】:vp_sendData_t ---- 待发送数据指针
 *    【输出参数说明】:NONE
 *    【其他说明】:   0220字段，bit0~bit9对应各阀控制指令
 *    【返回】:       打包后的32位控制命令1字
 */
/* ***************************************************************** */
static Uint32 Comm429RIUCtrlCmd1Pack(const RIU429SendData_t *vp_sendData_t)
{
    Uint32 l_data_u32 = 0UL;

    if(NULL != vp_sendData_t)
    {
        /* 0220按任务书顺序压入泵/阀控制位，未使用高位保持0。 */
        l_data_u32 |= ((Uint32)(vp_sendData_t->ValveCtrl_t.bit.Pump2_cutoff_ctrl_u16 & 0x1U)) << 0U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->ValveCtrl_t.bit.Pump0_Lcutoff_ctrl_u16 & 0x1U)) << 1U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->ValveCtrl_t.bit.Pump0_Rcutoff_ctrl_u16 & 0x1U)) << 2U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->ValveCtrl_t.bit.Pump3_cutoff_ctrl_u16 & 0x1U)) << 3U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->ValveCtrl_t.bit.LPQD_ctrl_u16 & 0x1U)) << 4U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->ValveCtrl_t.bit.RPQD_ctrl_u16 & 0x1U)) << 5U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->ValveCtrl_t.bit.LYJFY_ctrl_u16 & 0x1U)) << 6U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->ValveCtrl_t.bit.RYJFY_ctrl_u16 & 0x1U)) << 7U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->ValveCtrl_t.bit.LT_ctrl_u16 & 0x1U)) << 8U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->ValveCtrl_t.bit.ST_ctrl_u16 & 0x1U)) << 9U;
    }
    return l_data_u32;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUCtrlCmd2Pack
 *    【功能描述】:   控制命令2打包：组装RCV0-4关闭命令位
 *    【输入参数说明】:vp_sendData_t ---- 待发送数据指针
 *    【输出参数说明】:NONE
 *    【其他说明】:   0221字段，bit0~bit4对应RCV0~4关闭指令
 *    【返回】:       打包后的32位控制命令2字
 */
/* ***************************************************************** */
static Uint32 Comm429RIUCtrlCmd2Pack(const RIU429SendData_t *vp_sendData_t)
{
    Uint32 l_data_u32 = 0UL;

    if (NULL != vp_sendData_t)
    {
        /* 0221只承载RCV0~4关闭命令，其他控制位不混入该字。 */
        l_data_u32 |= (Uint32)(vp_sendData_t->RCVcmd_t.bit.RCV0_CloseCmd_u16 & 0x1U) << 0U;
        l_data_u32 |= (Uint32)(vp_sendData_t->RCVcmd_t.bit.RCV1_CloseCmd_u16 & 0x1U) << 1U;
        l_data_u32 |= (Uint32)(vp_sendData_t->RCVcmd_t.bit.RCV2_CloseCmd_u16 & 0x1U) << 2U;
        l_data_u32 |= (Uint32)(vp_sendData_t->RCVcmd_t.bit.RCV3_CloseCmd_u16 & 0x1U) << 3U;
        l_data_u32 |= (Uint32)(vp_sendData_t->RCVcmd_t.bit.RCV4_CloseCmd_u16 & 0x1U) << 4U;
    }
    return l_data_u32;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUCtrlCmd3Pack
 *    【功能描述】:   控制命令3打包：组装泵启停码
 *    【输入参数说明】:vp_conData_t ---- 控制数据指针
 *                    vp_sendData_t ---- 待发送数据指针
 *    【输出参数说明】:NONE
 *    【其他说明】:   0222字段，2bit/路泵启停码(0无效/1低压/2高压)
 *                    加受油模式未激活或阀关闭时输出0
 *    【返回】:       打包后的32位控制命令3字
 */
/* ***************************************************************** */
static Uint32 Comm429RIUCtrlCmd3Pack(const ConData_t *vp_conData_t, const RIU429SendData_t *vp_sendData_t)
{
    Uint32 l_data_u32 = 0UL;
    Uint16 l_workMode_u16 = WORK_MODE_STANDBY;
    Uint16 l_oilMode_u16 = 0U;
    Uint16 l_airRefuelActive_u16 = INVALID;
    Uint16 l_pumpCmd_u16 = 0U;

    if ((NULL != vp_conData_t) && (NULL != vp_sendData_t))
    {
        l_workMode_u16 = vp_conData_t->workMode_u16;
        l_oilMode_u16 = vp_conData_t->OilMode_u16;

        /* 判断加油模式是否激活 */
        if ((WORK_MODE_LP_FIXEDWING == l_workMode_u16) ||
            (WORK_MODE_RP_FIXEDWING == l_workMode_u16) ||
            (WORK_MODE_LRP_FIXEDWING == l_workMode_u16) ||
            (WORK_MODE_LP_HELI == l_workMode_u16) ||
            (WORK_MODE_RP_HELI == l_workMode_u16) ||
            (WORK_MODE_LRP_HELI == l_workMode_u16))
        {
            l_airRefuelActive_u16 = VALID;
        }

        /* 2号油箱加油泵：data[1:0] */
        l_pumpCmd_u16 = 0U;
        if ((VALID == l_airRefuelActive_u16) && (0U == vp_sendData_t->ValveCtrl_t.bit.Pump2_cutoff_ctrl_u16))
        {
            if (AIR_OIL_MODE_L == l_oilMode_u16) { l_pumpCmd_u16 = 1U; }
            else if (AIR_OIL_MODE_H == l_oilMode_u16) { l_pumpCmd_u16 = 2U; }
        }
        l_data_u32 |= ((Uint32)(l_pumpCmd_u16 & 0x3U)) << 0U;

        /* 0号油箱左加油泵：data[3:2] */
        l_pumpCmd_u16 = 0U;
        if ((VALID == l_airRefuelActive_u16) && (0U == vp_sendData_t->ValveCtrl_t.bit.Pump0_Lcutoff_ctrl_u16))
        {
            if (AIR_OIL_MODE_L == l_oilMode_u16) { l_pumpCmd_u16 = 1U; }
            else if (AIR_OIL_MODE_H == l_oilMode_u16) { l_pumpCmd_u16 = 2U; }
        }
        l_data_u32 |= ((Uint32)(l_pumpCmd_u16 & 0x3U)) << 2U;

        /* 0号油箱右加油泵：data[5:4] */
        l_pumpCmd_u16 = 0U;
        if ((VALID == l_airRefuelActive_u16) && (0U == vp_sendData_t->ValveCtrl_t.bit.Pump0_Rcutoff_ctrl_u16))
        {
            if (AIR_OIL_MODE_L == l_oilMode_u16) { l_pumpCmd_u16 = 1U; }
            else if (AIR_OIL_MODE_H == l_oilMode_u16) { l_pumpCmd_u16 = 2U; }
        }
        l_data_u32 |= ((Uint32)(l_pumpCmd_u16 & 0x3U)) << 4U;

        /* 3号油箱加油泵：data[7:6] */
        l_pumpCmd_u16 = 0U;
        if ((VALID == l_airRefuelActive_u16) && (0U == vp_sendData_t->ValveCtrl_t.bit.Pump3_cutoff_ctrl_u16))
        {
            if (AIR_OIL_MODE_L == l_oilMode_u16) { l_pumpCmd_u16 = 1U; }
            else if (AIR_OIL_MODE_H == l_oilMode_u16) { l_pumpCmd_u16 = 2U; }
        }
        l_data_u32 |= ((Uint32)(l_pumpCmd_u16 & 0x3U)) << 6U;
    }
    return l_data_u32;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUFaultInfo1Pack
 *    【功能描述】:   故障信息1打包：泵切断阀故障位
 *    【输入参数说明】:vp_sendData_t ---- 待发送数据指针
 *    【输出参数说明】:NONE
 *    【其他说明】:   0231字段，bit0~bit11对应各阀故障状态
 *    【返回】:       打包后的32位故障信息1字
 */
/* ***************************************************************** */
static Uint32 Comm429RIUFaultInfo1Pack(const RIU429SendData_t *vp_sendData_t)
{
    Uint32 l_data_u32 = 0UL;

    if(NULL != vp_sendData_t)
    {
        /* 0231按阀/泵故障逐位上送，便于上位机直接定位故障对象。 */
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.Pump2_cutoff_fault_u16 & 0x1U)) << 0U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.Pump0_Lcutoff_fault_u16 & 0x1U)) << 1U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.Pump0_Rcutoff_fault_u16 & 0x1U)) << 2U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.LT_fault_u16 & 0x1U)) << 3U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.ST_fault_u16 & 0x1U)) << 4U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.Pump3_cutoff_fault_u16 & 0x1U)) << 5U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.LPQD_fault_u16 & 0x1U)) << 6U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.RPQD_fault_u16 & 0x1U)) << 7U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.LYJFY_fault_u16 & 0x1U)) << 8U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.RYJFY_fault_u16 & 0x1U)) << 9U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.LDDTQ_fault_u16 & 0x1U)) << 10U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo1_t.bit.RDDTQ_fault_u16 & 0x1U)) << 11U;
    }
    return l_data_u32;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUFaultInfo2Pack
 *    【功能描述】:   故障信息2打包：RCV故障+429通道BIT故障
 *    【输入参数说明】:vp_conData_t ---- 控制数据指针(用于BIT故障查询)
 *                    vp_sendData_t ---- 待发送数据指针(用于RCV故障位)
 *    【输出参数说明】:NONE
 *    【其他说明】:   0232字段，维护态查MBIT，非维护态查IFBIT
 *                    bit6:RIU通道1, bit7:RIU通道2, bit10:左吊舱接收, bit11:右吊舱接收
 *    【返回】:       打包后的32位故障信息2字
 */
/* ***************************************************************** */
static Uint32 Comm429RIUFaultInfo2Pack(const ConData_t *vp_conData_t, const RIU429SendData_t *vp_sendData_t)
{
    static const struct { Uint16 ifIdx; Uint16 mIdx; Uint16 bitPos; } l_bitMap[4] =
    {
        { IFBIT_INDEX_COMM_429RIU_1,  MBIT_INDEX_COMM_429RIU_1,  6U  },
        { IFBIT_INDEX_COMM_429RIU_2,  MBIT_INDEX_COMM_429RIU_2,  7U  },
        { IFBIT_INDEX_COMM_429LEFT_RX, MBIT_INDEX_COMM_429LEFT_RX, 10U },
        { IFBIT_INDEX_COMM_429RIGHT_RX,MBIT_INDEX_COMM_429RIGHT_RX,11U },
    };
    Uint32 l_data_u32 = 0UL;
    Uint16 l_bitFault_u16 = INVALID;
    Uint16 l_isMaint_u16 = INVALID;
    Uint16 l_ii_u16 = 0U;

    /* 判断当前是否维护态 */
    if ((NULL != vp_conData_t) && (SYS_STATE_3MAINTG == vp_conData_t->sysState_u16))
    {
        /* 维护态上送维护BIT结果，工作态上送周期BIT结果，避免两个口径混在一起。 */
        l_isMaint_u16 = VALID;
    }

    /* RCV0~4故障 + 燃油测量系统故障 */
    if(NULL != vp_sendData_t)
    {
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo2_t.bit.RCV0_fault_u16 & 0x1U)) << 0U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo2_t.bit.RCV1_fault_u16 & 0x1U)) << 1U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo2_t.bit.RCV2_fault_u16 & 0x1U)) << 2U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo2_t.bit.RCV3_fault_u16 & 0x1U)) << 3U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo2_t.bit.RCV4_fault_u16 & 0x1U)) << 4U;
        l_data_u32 |= ((Uint32)(vp_sendData_t->RIUfltInfo2_t.bit.oilMS_falut_u16 & 0x1U)) << 5U;
    }

    /* 429通道BIT故障：维护态查MBIT，非维护态查IFBIT。 */
    for (l_ii_u16 = 0U; l_ii_u16 < 4U; l_ii_u16++)
    {
        l_bitFault_u16 = INVALID;
        if (VALID == l_isMaint_u16)
        {
            if (MBIT_TEST_ERR == MBITInfoGet(l_bitMap[l_ii_u16].mIdx)) { l_bitFault_u16 = VALID; }
        }
        else
        {
            if (IFBIT_TEST_ERR == IFBITInfoGet(l_bitMap[l_ii_u16].ifIdx)) { l_bitFault_u16 = VALID; }
        }
        l_data_u32 |= ((Uint32)l_bitFault_u16) << l_bitMap[l_ii_u16].bitPos;
    }
    return l_data_u32;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUStatusInfoPack
 *    【功能描述】:   状态信息打包：工作模式、左右吊舱维护/在位/加油阀状态
 *    【输入参数说明】:vp_conData_t ---- 控制数据指针
 *    【输出参数说明】:NONE
 *    【其他说明】:   0230字段
 *                    bit0-2:工作模式, bit3:加受油对象, bit4-5:吊舱维护模式,
 *                    bit6-11:左右吊舱在位/加油阀/回油阀(本机离散量)
 *    【返回】:       打包后的32位状态信息字
 */
/* ***************************************************************** */
static Uint32 Comm429RIUStatusInfoPack(const ConData_t *vp_conData_t)
{
    Uint32 l_data_u32 = 0UL;
    Uint16 l_workMode_u16 = WORK_MODE_STANDBY;
    Uint32 l_mode_u32 = RIU429_MODE_OFF;
    A429Info_t l_leftState_t;
    A429Info_t l_rightState_t;
    Uint16 l_leftValid_u16 = INVALID;
    Uint16 l_rightValid_u16 = INVALID;
    KZZZ429InfoData_t l_leftData_t;
    KZZZ429InfoData_t l_rightData_t;

    memset(&l_leftState_t, 0, sizeof(l_leftState_t));
    memset(&l_rightState_t, 0, sizeof(l_rightState_t));
    memset(&l_leftData_t, 0, sizeof(l_leftData_t));
    memset(&l_rightData_t, 0, sizeof(l_rightData_t));

    if (NULL != vp_conData_t)
    {
        l_workMode_u16 = vp_conData_t->workMode_u16;
    }

    /* 左右吊舱有效判定 */
    l_leftState_t = Comm429KZZZRxStateGet(COMM429_KZZZ_1);
    if ((RX429_STATE_OK == l_leftState_t.rxState_u16) && (RX429_STATE_OK == l_leftState_t.rxDataState_u16))
    {
        l_leftValid_u16 = VALID;
    }
    l_rightState_t = Comm429KZZZRxStateGet(COMM429_KZZZ_2);
    if ((RX429_STATE_OK == l_rightState_t.rxState_u16) && (RX429_STATE_OK == l_rightState_t.rxDataState_u16))
    {
        l_rightValid_u16 = VALID;
    }
    l_leftData_t = Comm429KzzzRxDataGet(COMM429_KZZZ_1);
    l_rightData_t = Comm429KzzzRxDataGet(COMM429_KZZZ_2);

    /* bit0-2:工作模式编码(OFF/LP/RP/LRP/RECEIVE) */
    if ((WORK_MODE_LP_FIXEDWING == l_workMode_u16) || (WORK_MODE_LP_HELI == l_workMode_u16)) { l_mode_u32 = RIU429_MODE_LP; }
    else if ((WORK_MODE_RP_FIXEDWING == l_workMode_u16) || (WORK_MODE_RP_HELI == l_workMode_u16)) { l_mode_u32 = RIU429_MODE_RP; }
    else if ((WORK_MODE_LRP_FIXEDWING == l_workMode_u16) || (WORK_MODE_LRP_HELI == l_workMode_u16)) { l_mode_u32 = RIU429_MODE_LRP; }
    else if (WORK_MODE_RECEIVE == l_workMode_u16) { l_mode_u32 = RIU429_MODE_RECEIVE; }
    l_data_u32 |= ((Uint32)(l_mode_u32 & 0x7U)) << 0U;

    /* bit3:加受油对象(固定翼=1, 直升机=0) */
    if ((WORK_MODE_LP_FIXEDWING == l_workMode_u16) ||
        (WORK_MODE_RP_FIXEDWING == l_workMode_u16) ||
        (WORK_MODE_LRP_FIXEDWING == l_workMode_u16))
    {
        l_data_u32 |= (1UL << 3U);
    }

    /* bit4:左吊舱维护模式, bit5:右吊舱维护模式 */
    if (VALID == l_leftValid_u16)
    {
        l_data_u32 |= ((Uint16)(l_leftData_t.jyzzState_t.bit.podSystemMaintMode_u32 != 0U)) << 4U;
    }
    if (VALID == l_rightValid_u16)
    {
        l_data_u32 |= ((Uint16)(l_rightData_t.jyzzState_t.bit.podSystemMaintMode_u32 != 0U)) << 5U;
    }

    /* bit6-11:左右吊舱在位、加油阀、回油阀(本机离散量采集) */
    l_data_u32 |= ((Uint32)(IoDataGet(IO_DINDEX_LEFT_DCZW)  & 0x1U)) << 6U;
    l_data_u32 |= ((Uint32)(IoDataGet(IO_DINDEX_LEFT_JYF)   & 0x1U)) << 7U;
    l_data_u32 |= ((Uint32)(IoDataGet(IO_DINDEX_LEFT_HYF)   & 0x1U)) << 8U;
    l_data_u32 |= ((Uint32)(IoDataGet(IO_DINDEX_RIGHT_DCZW) & 0x1U)) << 9U;
    l_data_u32 |= ((Uint32)(IoDataGet(IO_DINDEX_RIGHT_JYF)  & 0x1U)) << 10U;
    l_data_u32 |= ((Uint32)(IoDataGet(IO_DINDEX_RIGHT_HYF)  & 0x1U)) << 11U;

    return l_data_u32;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUWarnInfoPack
 *    【功能描述】:   警告信息打包：受油关闭故障、受油故障、不平衡故障
 *    【输入参数说明】:vp_sendData_t ---- 待发送数据指针
 *    【输出参数说明】:NONE
 *    【其他说明】:   0233字段
 *                    bit0:受油关闭故障(任一RCV关闭故障或阀超时/高液位)
 *                    bit1:受油故障(测量/通信/巡检)
 *                    bit2:不平衡故障
 *    【返回】:       打包后的32位警告信息字
 */
/* ***************************************************************** */
static Uint32 Comm429RIUWarnInfoPack(const RIU429SendData_t *vp_sendData_t)
{
    Uint32 l_data_u32 = 0UL;
    Uint16 l_closeFault_u16 = 0U;
    Uint16 l_receiveFault_u16 = 0U;
    Uint16 l_imbalanceFault_u16 = 0U;

    if (NULL != vp_sendData_t)
    {
        /* 受油关闭故障：任一RCV关闭故障或阀关闭超时/高液位触发 */
        l_closeFault_u16 = (Uint16)(
                (vp_sendData_t->RIUfltInfo2_t.bit.RCV0_fault_u16 != 0U) ||
                (vp_sendData_t->RIUfltInfo2_t.bit.RCV1_fault_u16 != 0U) ||
                (vp_sendData_t->RIUfltInfo2_t.bit.RCV2_fault_u16 != 0U) ||
                (vp_sendData_t->RIUfltInfo2_t.bit.RCV3_fault_u16 != 0U) ||
                (vp_sendData_t->RIUfltInfo2_t.bit.RCV4_fault_u16 != 0U) ||
                (RECEIVE_RIU_REASON_HL_SENSOR == vp_sendData_t->checkState_u16) ||
                (RECEIVE_RIU_REASON_VALVE_TIMEOUT == vp_sendData_t->checkState_u16));
        /* 受油故障：测量/通信/巡检测故障 */
        l_receiveFault_u16 = (Uint16)(RECEIVE_RIU_REASON_MEASURE == vp_sendData_t->checkState_u16);
        /* 不平衡故障 */
        l_imbalanceFault_u16 = (Uint16)(RECEIVE_RIU_REASON_IMBALANCE == vp_sendData_t->checkState_u16);
    }

    l_data_u32 |= ((Uint32)l_closeFault_u16) << 0U;
    l_data_u32 |= ((Uint32)l_receiveFault_u16) << 1U;
    l_data_u32 |= ((Uint32)l_imbalanceFault_u16) << 2U;
    return l_data_u32;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUTipInfoPack
 *    【功能描述】:   提示信息打包：受油预设进度与左右吊舱预选油量反馈
 *    【输入参数说明】:vp_conData_t ---- 控制数据指针
 *    【输出参数说明】:NONE
 *    【其他说明】:   0234字段
 *                    bit0:提示预设受油量, bit1:预设受油量成功,
 *                    bit2:预设加油量左吊舱, bit3:预设加油量右吊舱,
 *                    bit4:左吊舱预选油量接收反馈, bit5:右吊舱预选油量接收反馈,
 *                    bit6:燃油预位
 *    【返回】:       打包后的32位提示信息字
 */
/* ***************************************************************** */
static Uint32 Comm429RIUTipInfoPack(const ConData_t *vp_conData_t)
{
    Uint32 l_data_u32 = 0UL;
    A429Info_t l_leftState_t;
    A429Info_t l_rightState_t;
    Uint16 l_leftValid_u16 = INVALID;
    Uint16 l_rightValid_u16 = INVALID;
    Uint16 l_receivePresetSuccess_u16 = INVALID;
    KZZZ429InfoData_t l_leftData_t;
    KZZZ429InfoData_t l_rightData_t;

    memset(&l_leftState_t, 0, sizeof(l_leftState_t));
    memset(&l_rightState_t, 0, sizeof(l_rightState_t));
    memset(&l_leftData_t, 0, sizeof(l_leftData_t));
    memset(&l_rightData_t, 0, sizeof(l_rightData_t));

    /* 左右吊舱有效判定 */
    l_leftState_t = Comm429KZZZRxStateGet(COMM429_KZZZ_1);
    if ((RX429_STATE_OK == l_leftState_t.rxState_u16) && (RX429_STATE_OK == l_leftState_t.rxDataState_u16))
    {
        l_leftValid_u16 = VALID;
    }
    l_rightState_t = Comm429KZZZRxStateGet(COMM429_KZZZ_2);
    if ((RX429_STATE_OK == l_rightState_t.rxState_u16) && (RX429_STATE_OK == l_rightState_t.rxDataState_u16))
    {
        l_rightValid_u16 = VALID;
    }
    l_leftData_t = Comm429KzzzRxDataGet(COMM429_KZZZ_1);
    l_rightData_t = Comm429KzzzRxDataGet(COMM429_KZZZ_2);

    if (NULL != vp_conData_t)
    {
        /* bit0:提示预设受油量 */
        if ((WORK_MODE_RECEIVE == vp_conData_t->workMode_u16) &&
            (CON_FUNC_2_FUEL_PRESET == vp_conData_t->conFunc_u16))
        {
            l_data_u32 |= (1UL << 0U);
        }

        /* bit1:预设受油量成功(预设完成且无故障) */
        if ((WORK_MODE_RECEIVE == vp_conData_t->workMode_u16) &&
            (VALID == s_receiveCtx_t.presetReady_u16) &&
            (INVALID == s_receiveCtx_t.faultActive_u16))
        {
            if (CON_FUNC_3_REFUEL_PROCESS == vp_conData_t->conFunc_u16)
            {
                l_receivePresetSuccess_u16 = VALID;
            }
            else if ((CON_FUNC_4_TASK_END == vp_conData_t->conFunc_u16) &&
                     (VALID == s_receiveCtx_t.completionIssued_u16))
            {
                l_receivePresetSuccess_u16 = VALID;
            }
            else
            {
                /* 其余功能态不报 */
            }
        }

        if (VALID == l_receivePresetSuccess_u16)
        {
            l_data_u32 |= (1UL << 1U);
        }

        /* bit2:预设加油量左吊舱 */
        if ((WORK_MODE_LP_FIXEDWING == vp_conData_t->workMode_u16) ||
            (WORK_MODE_LP_HELI == vp_conData_t->workMode_u16) ||
            (WORK_MODE_LRP_FIXEDWING == vp_conData_t->workMode_u16) ||
            (WORK_MODE_LRP_HELI == vp_conData_t->workMode_u16))
        {
            l_data_u32 |= (1UL << 2U);
        }

        /* bit3:预设加油量右吊舱 */
        if ((WORK_MODE_RP_FIXEDWING == vp_conData_t->workMode_u16) ||
            (WORK_MODE_RP_HELI == vp_conData_t->workMode_u16) ||
            (WORK_MODE_LRP_FIXEDWING == vp_conData_t->workMode_u16) ||
            (WORK_MODE_LRP_HELI == vp_conData_t->workMode_u16))
        {
            l_data_u32 |= (1UL << 3U);
        }

        /* bit6:燃油预位 */
        if (((WORK_MODE_LP_FIXEDWING == vp_conData_t->workMode_u16) ||
             (WORK_MODE_RP_FIXEDWING == vp_conData_t->workMode_u16) ||
             (WORK_MODE_LRP_FIXEDWING == vp_conData_t->workMode_u16) ||
             (WORK_MODE_LP_HELI == vp_conData_t->workMode_u16) ||
             (WORK_MODE_RP_HELI == vp_conData_t->workMode_u16) ||
             (WORK_MODE_LRP_HELI == vp_conData_t->workMode_u16) ||
             (WORK_MODE_RECEIVE == vp_conData_t->workMode_u16)) &&
            (VALID == s_refuelCtx_t.presetReady_u16 ||
             ((WORK_MODE_RECEIVE == vp_conData_t->workMode_u16) &&
              (CON_FUNC_2_FUEL_PRESET == vp_conData_t->conFunc_u16))))
        {
            l_data_u32 |= (1UL << 6U);
        }
    }

    /* bit4:左吊舱预选油量接收反馈, bit5:右吊舱预选油量接收反馈 */
    if (VALID == l_leftValid_u16)
    {
        l_data_u32 |= ((Uint32)(l_leftData_t.Pre_FuelQtyRcv_FB_u16 & 0x1U)) << 4U;
    }
    if (VALID == l_rightValid_u16)
    {
        l_data_u32 |= ((Uint32)(l_rightData_t.Pre_FuelQtyRcv_FB_u16 & 0x1U)) << 5U;
    }
    return l_data_u32;
}


/* ***************************************************************** */
/* 发送底层与吊舱转发 */
/* ***************************************************************** */

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIURawSend
 *    【功能描述】:   原始帧发送：按label+data+ssm格式组帧并通过429通道发送
 *    【输入参数说明】:v_ID_u16 ---- 端口号
 *                    v_label_u16 ---- ARINC429标签
 *                    v_data_u32 ---- 数据载荷
 *                    v_ssm_u16 ---- SSM编码
 *    【输出参数说明】:NONE
 *    【其他说明】:   仅COMM429_RIU_1通道实际发送，记录最近发送字与标号计数
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void Comm429RIURawSend(Uint16 v_ID_u16, Uint16 v_label_u16, Uint32 v_data_u32, Uint16 v_ssm_u16)
{
    union arinc429Data l_txData_un;
    Uint16 l_idx_u16 = 0U;

    if((COMM429_RIU_1 == v_ID_u16) && (s_RIUCommIDConf_u16[v_ID_u16] < COMMDRI_429_NUM))
    {
        /* 发送字格式按 label + data + ssm + parity */
        l_txData_un.bit.label = v_label_u16;
        l_txData_un.bit.data  = v_data_u32;
        l_txData_un.bit.ssm   = v_ssm_u16;

        Ccdl429DataSend(s_RIUCommIDConf_u16[v_ID_u16], l_txData_un);
        s_lastTxWord_u32 = l_txData_un.msgData;

        /* 更新对应标号的发送计数 */
        for(l_idx_u16 = 0U; l_idx_u16 < RIU_T_DATA_NUM; l_idx_u16++)
        {
            if(s_RIU429TxLabel_u16[l_idx_u16] == v_label_u16)
            {
                s_RIU429TxCnt_u32[l_idx_u16]++;
                break;
            }
        }
    }
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUTxLastWordGet
 *    【功能描述】:   获取最近一次通过RIU发送的ARINC429原始32位字
 *    【输入参数说明】:NONE
 *    【输出参数说明】:NONE
 *    【其他说明】:   供周期BIT发送回绕检测比对使用
 *    【返回】:       最近一次发送的429原始字(label+data+ssm+parity)
 */
/* ***************************************************************** */
Uint32 Comm429RIUTxLastWordGet(void)
{
    return s_lastTxWord_u32;
}

/* 吊舱周期量左右label表：{左label, 右label} */
static const Uint16 s_podPeriodicLabelTable[RIU_POD_PERIODIC_FIELD_NUM][2] =
{
    { RIU_LABEL_T_LP_TURBINE_SPEED,   RIU_LABEL_T_RP_TURBINE_SPEED   },
    { RIU_LABEL_T_LP_FUEL_PRESS,      RIU_LABEL_T_RP_FUEL_PRESS      },
    { RIU_LABEL_T_LP_PUMP_PRESS,      RIU_LABEL_T_RP_PUMP_PRESS      },
    { RIU_LABEL_T_LP_FUEL_FLOW,       RIU_LABEL_T_RP_FUEL_FLOW       },
    { RIU_LABEL_T_LP_FUEL_LEVEL,      RIU_LABEL_T_RP_FUEL_LEVEL      },
    { RIU_LABEL_T_LP_TOTAL_FUEL,      RIU_LABEL_T_RP_TOTAL_FUEL      },
    { RIU_LABEL_T_LP_FUEL_TEMP,       RIU_LABEL_T_RP_FUEL_TEMP       },
    { RIU_LABEL_T_LP_RG_LEN,          RIU_LABEL_T_RP_RG_LEN          },
    { RIU_LABEL_T_LP_JYZZ_STATE,      RIU_LABEL_T_RP_JYZZ_STATE      },
    { RIU_LABEL_T_LP_COMPONENT_STATE, RIU_LABEL_T_RP_COMPONENT_STATE },
    { RIU_LABEL_T_LP_FAULT_WARN,      RIU_LABEL_T_RP_FAULT_WARN      },
    { RIU_LABEL_T_LP_FAULT_INFO_1,    RIU_LABEL_T_RP_FAULT_INFO_1    },
    { RIU_LABEL_T_LP_FAULT_INFO_2,    RIU_LABEL_T_RP_FAULT_INFO_2    },
    { RIU_LABEL_T_LP_CMD_FB,          RIU_LABEL_T_RP_CMD_FB          },
    { RIU_LABEL_T_LP_MOTOR_SPEED,     RIU_LABEL_T_RP_MOTOR_SPEED     },
    { RIU_LABEL_T_LP_CTRL_TEMP,       RIU_LABEL_T_RP_CTRL_TEMP       },
};

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUPodPeriodicInfoTx
 *    【功能描述】:   向RIU发送吊舱周期信息(表驱动，左右共用单循环)
 *    【输入参数说明】:v_ID_u16 ---- 端口号
 *                    v_kzzzID_u16 ---- KZZZ左右吊舱标识
 *                    v_valid_u16 ---- 数据有效标志
 *                    v_kzzzData_t ---- KZZZ吊舱429数据
 *    【输出参数说明】:NONE
 *    【其他说明】:   有效时打包16个周期量字段，按左右label表逐帧发送
 *                    无效时全发0+SSM无效
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void Comm429RIUPodPeriodicInfoTx(Uint16 v_ID_u16, Uint16 v_kzzzID_u16,
                                        Uint16 v_valid_u16, KZZZ429InfoData_t v_kzzzData_t)
{
    Uint32 l_data_u32[RIU_POD_PERIODIC_FIELD_NUM];
    Uint16 l_ssm_u16 = Comm429RIUSsmGet(v_valid_u16);
    Uint16 l_side_u16 = 0U;  /* 0=左,1=右 */
    Uint16 l_ii_u16 = 0U;
    FaultInfo1_t l_fi1;
    FaultInfo2_t l_fi2;
    CmdSignalFb_t l_cmdFb;

    /* 左右吊舱选通 */
    if (COMM429_KZZZ_2 == v_kzzzID_u16) { l_side_u16 = 1U; }
    else if (COMM429_KZZZ_1 == v_kzzzID_u16) { l_side_u16 = 0U; }
    else { return; }

    l_fi1 = v_kzzzData_t.faultInfo_1_t;
    l_fi2 = v_kzzzData_t.faultInfo_2_t;
    l_cmdFb = v_kzzzData_t.cmdSignalFb_t;

    /* 先清零 */
    for (l_ii_u16 = 0U; l_ii_u16 < RIU_POD_PERIODIC_FIELD_NUM; l_ii_u16++)
    {
        l_data_u32[l_ii_u16] = 0UL;
    }

    /* 有效时打包各周期量字段 */
    if (VALID == v_valid_u16)
    {
        l_data_u32[0]  = Comm429RIUSignedMagnitudePack((Int16)v_kzzzData_t.turbineSpeed_u16, 12U);
        l_data_u32[1]  = Comm429RIUSignedMagnitudePack((Int16)v_kzzzData_t.fuelPressure_u16, 11U);
        l_data_u32[2]  = Comm429RIUSignedMagnitudePack((Int16)v_kzzzData_t.turbinePumpPressure_u16, 11U);
        l_data_u32[3]  = Comm429RIUSignedMagnitudePack((Int16)v_kzzzData_t.fuelFlow_u16, 11U);
        l_data_u32[4]  = Comm429RIUSignedMagnitudePack((Int16)v_kzzzData_t.fuelLevel_u16, 10U);
        l_data_u32[5]  = Comm429RIUSignedMagnitudePack((Int16)v_kzzzData_t.totalFuel_u16, 10U);
        l_data_u32[6]  = Comm429RIUSignedMagnitudePack(v_kzzzData_t.fuelTemperature_i16, 9U);
        l_data_u32[7]  = Comm429RIUSignedMagnitudePack((Int16)((v_kzzzData_t.rgLength_f * KZZZ_RG_LENGTH_R_RATIO) + 0.5F), 10U);
        /* 加油设备状态：取21位data域右移2位后低10位 */
        l_data_u32[8]  = ((((Uint32)v_kzzzData_t.jyzzState_t.all >> 8U) & 0x1FFFFFUL) >> 2U) & 0x03FFUL;
        /* 部件状态 */
        l_data_u32[9]  = (v_kzzzData_t.componentState_t.all >> 2U) & 0x7FFFUL;
        /* 故障告警 */
        l_data_u32[10] = (v_kzzzData_t.faultInfo_t.all >> 2U) & 0x07FFUL;
        /* 故障信息1位映射 */
        l_data_u32[11] = (((((l_fi1).all >> 2U) & 0x01UL) << 0U) | ((((l_fi1).all >> 3U) & 0x01UL) << 1U) |
                          ((((l_fi1).all >> 4U) & 0x01UL) << 2U) | ((((l_fi1).all >> 6U) & 0x01UL) << 3U) |
                          ((((l_fi1).all >> 12U) & 0x01UL) << 4U));
        /* 故障信息2位映射 */
        l_data_u32[12] = (((((l_fi2).all >> 2U) & 0x01UL) << 0U) | ((((l_fi2).all >> 3U) & 0x01UL) << 1U) |
                          ((((l_fi2).all >> 4U) & 0x01UL) << 2U) | ((((l_fi2).all >> 5U) & 0x01UL) << 3U) |
                          ((((l_fi2).all >> 6U) & 0x01UL) << 4U) | ((((l_fi2).all >> 7U) & 0x01UL) << 5U) |
                          ((((l_fi2).all >> 8U) & 0x01UL) << 6U) | ((((l_fi2).all >> 9U) & 0x01UL) << 7U) |
                          ((((l_fi2).all >> 10U) & 0x01UL) << 8U) | ((((l_fi2).all >> 12U) & 0x01UL) << 9U) |
                          ((((l_fi2).all >> 13U) & 0x01UL) << 10U) | ((((l_fi2).all >> 14U) & 0x01UL) << 11U));
        /* 指令信号反馈位映射 */
        l_data_u32[13] = (((((Uint32)l_cmdFb.all >> 2U) & 0x01UL) << 0U) |
                          ((((Uint32)l_cmdFb.all >> 3U) & 0x01UL) << 1U) |
                          ((((Uint32)l_cmdFb.all >> 4U) & 0x01UL) << 2U) |
                          ((((Uint32)l_cmdFb.all >> 5U) & 0x01UL) << 3U) |
                          ((((Uint32)l_cmdFb.all >> 6U) & 0x01UL) << 4U) |
                          ((((Uint32)l_cmdFb.all >> 10U) & 0x01UL) << 5U) |
                          ((((Uint32)l_cmdFb.all >> 11U) & 0x01UL) << 6U) |
                          ((((Uint32)l_cmdFb.all >> 12U) & 0x01UL) << 7U));
        l_data_u32[14] = Comm429RIUSignedMagnitudePack(v_kzzzData_t.motorSpeed_i16, 14U);
        l_data_u32[15] = Comm429RIUSignedMagnitudePack(v_kzzzData_t.motorTemp_i16, 8U);
    }

    /* 按左右label表逐帧发送 */
    for (l_ii_u16 = 0U; l_ii_u16 < RIU_POD_PERIODIC_FIELD_NUM; l_ii_u16++)
    {
        Comm429RIURawSend(v_ID_u16, s_podPeriodicLabelTable[l_ii_u16][l_side_u16],
                          l_data_u32[l_ii_u16], l_ssm_u16);
    }
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUPodEventOneTx
 *    【功能描述】:   向RIU发送单条吊舱事件信息(单帧)
 *    【输入参数说明】:v_ID_u16 ---- 端口号
 *                    v_label_u16 ---- ARINC429标签
 *                    v_data_u32 ---- 数据载荷
 *                    v_valid_u16 ---- 数据有效标志
 *    【输出参数说明】:NONE
 *    【其他说明】:   无效时数据发0，SSM表达无效
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void Comm429RIUPodEventOneTx(Uint16 v_ID_u16, Uint16 v_label_u16,
                                    Uint32 v_data_u32, Uint16 v_valid_u16)
{
    Uint32 l_data_u32 = 0UL;

    if (VALID == v_valid_u16)
    {
        l_data_u32 = v_data_u32;
    }
    Comm429RIURawSend(v_ID_u16, v_label_u16, l_data_u32, Comm429RIUSsmGet(v_valid_u16));
}

/* 吊舱事件量软件版本左右label表 */
static const Uint16 s_podEventSoftVLabelTable[RIU_POD_EVENT_SOFTV_FIELD_NUM][2] =
{
    { RIU_LABEL_T_LP_SOFTV_CTRL,             RIU_LABEL_T_RP_SOFTV_CTRL             },
    { RIU_LABEL_T_LP_SOFTV_MOTOR_CTRL,       RIU_LABEL_T_RP_SOFTV_MOTOR_CTRL       },
    { RIU_LABEL_T_LP_SOFTV_SIGNAL_BOX,       RIU_LABEL_T_RP_SOFTV_SIGNAL_BOX       },
    { RIU_LABEL_T_LP_SOFTV_BRAKE_CTRL,       RIU_LABEL_T_RP_SOFTV_BRAKE_CTRL       },
    { RIU_LABEL_T_LP_SOFTV_BIT_APP,          RIU_LABEL_T_RP_SOFTV_BIT_APP          },
    { RIU_LABEL_T_LP_SOFTV_CTRL_LOGIC,       RIU_LABEL_T_RP_SOFTV_CTRL_LOGIC       },
    { RIU_LABEL_T_LP_SOFTV_MOTOR_LOGIC,      RIU_LABEL_T_RP_SOFTV_MOTOR_LOGIC      },
    { RIU_LABEL_T_LP_SOFTV_CTRL_UPGRADE_APP, RIU_LABEL_T_RP_SOFTV_CTRL_UPGRADE_APP },
};

/* 软件版本索引→SoftV_t数组索引映射表 */
static const Uint16 s_podSoftVIndexTable[RIU_POD_EVENT_SOFTV_FIELD_NUM] =
{
    KZZZ_SOFTV_INDEX_APP,
    KZZZ_SOFTV_INDEX_MOTOR_CTRL,
    KZZZ_SOFTV_INDEX_SIGNAL_BOX,
    KZZZ_SOFTV_INDEX_BRAKE_CTRL,
    KZZZ_SOFTV_INDEX_BIT_APP,
    KZZZ_SOFTV_INDEX_LOGIC,
    KZZZ_SOFTV_INDEX_MOTOR_LOGIC,
    KZZZ_SOFTV_INDEX_UPGRADE_APP,
};

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUPodEventInfoTx
 *    【功能描述】:   向RIU发送吊舱事件信息(表驱动，左右共用)
 *    【输入参数说明】:v_ID_u16 ---- 端口号
 *                    v_kzzzID_u16 ---- KZZZ左右吊舱标识
 *                    v_eventGroup_u16 ---- 事件分组标识
 *                    v_valid_u16 ---- 数据有效标志
 *                    v_kzzzData_t ---- KZZZ吊舱429数据
 *    【输出参数说明】:NONE
 *    【其他说明】:   按事件组分发软件版本/预选油量/寿命/油量重置事件
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void Comm429RIUPodEventInfoTx(Uint16 v_ID_u16, Uint16 v_kzzzID_u16,
                                     Uint16 v_eventGroup_u16, Uint16 v_valid_u16,
                                     KZZZ429InfoData_t v_kzzzData_t)
{
    Uint16 l_side_u16 = 0U;  /* 0=左,1=右 */
    Uint16 l_ii_u16 = 0U;
    Uint16 l_label_u16 = RIU_LABEL_T_RP_PRE_FUEL_RCV_FB;
    Uint16 l_fhLabel_u16 = RIU_LABEL_T_RP_REMAIN_FLIGHT_HOUR;
    Uint16 l_clLabel_u16 = RIU_LABEL_T_RP_REMAIN_CALENDAR_LIFE;
    SoftVData_t l_sv;
    RemainLife_t l_life_t = v_kzzzData_t.remainLife_t;

    /* 左右吊舱选通 */
    if (COMM429_KZZZ_2 == v_kzzzID_u16) { l_side_u16 = 1U; }
    else if (COMM429_KZZZ_1 == v_kzzzID_u16) { l_side_u16 = 0U; }
    else { return; }

    /* 软件版本事件：逐版本发送 */
    if (RIU_POD_EVENT_GROUP_SOFTV == v_eventGroup_u16)
    {
        for (l_ii_u16 = 0U; l_ii_u16 < RIU_POD_EVENT_SOFTV_FIELD_NUM; l_ii_u16++)
        {
            l_sv = v_kzzzData_t.SoftV_t[s_podSoftVIndexTable[l_ii_u16]];
            /* 软件版本信息位域打包：4段4bit拼连续16bit */
            Comm429RIUPodEventOneTx(v_ID_u16, s_podEventSoftVLabelTable[l_ii_u16][l_side_u16],
                ((((Uint32)(l_sv.bit.section1_u32 & 0x0FUL)) << 0U) |
                 (((Uint32)(l_sv.bit.section2_u32 & 0x0FUL)) << 4U) |
                 (((Uint32)(l_sv.bit.section3_u32 & 0x0FUL)) << 8U) |
                 (((Uint32)(l_sv.bit.section4_u32 & 0x0FUL)) << 12U)),
                v_valid_u16);
        }
    }
    /* 预选油量接收反馈 */
    else if (RIU_POD_EVENT_GROUP_PRE_FUEL == v_eventGroup_u16)
    {
        l_label_u16 = RIU_LABEL_T_RP_PRE_FUEL_RCV_FB;

        if (0U == l_side_u16)
        {
            l_label_u16 = RIU_LABEL_T_LP_PRE_FUEL_RCV_FB;
        }
        Comm429RIUPodEventOneTx(v_ID_u16, l_label_u16, (Uint32)(v_kzzzData_t.Pre_FuelQtyRcv_FB_u16 & 0xFFFFU), v_valid_u16);
    }
    /* 寿命信息：剩余飞行小时+剩余日历寿命 */
    else if (RIU_POD_EVENT_GROUP_LIFE == v_eventGroup_u16)
    {
        l_fhLabel_u16 = RIU_LABEL_T_RP_REMAIN_FLIGHT_HOUR;
        l_clLabel_u16 = RIU_LABEL_T_RP_REMAIN_CALENDAR_LIFE;

        if (0U == l_side_u16)
        {
            l_fhLabel_u16 = RIU_LABEL_T_LP_REMAIN_FLIGHT_HOUR;
            l_clLabel_u16 = RIU_LABEL_T_LP_REMAIN_CALENDAR_LIFE;
        }
        /* 剩余飞行小时：13bit限幅打包 */
        Comm429RIUPodEventOneTx(v_ID_u16, l_fhLabel_u16, Comm429RIUUnsignedPack((Uint32)v_kzzzData_t.flightHours_u16, 13U), v_valid_u16);
        /* 剩余日历寿命位域打包：年/月/日BCD编码 */
        Comm429RIUPodEventOneTx(v_ID_u16, l_clLabel_u16,
            ((((((l_life_t).bit.swYear_u32 * 10UL) + (l_life_t).bit.gwYear_u32) % 10UL) & 0x0FUL) |
             (((((((l_life_t).bit.swYear_u32 * 10UL) + (l_life_t).bit.gwYear_u32) / 10UL) % 10UL) & 0x0FUL) << 4U) |
             (((((l_life_t).bit.swMonth_u32 * 10UL) + (l_life_t).bit.gwMonth_u32) & 0x0FUL) << 8U) |
             (((((l_life_t).bit.swDay_u32 * 10UL) + (l_life_t).bit.gwDay_u32) % 10UL) << 12U) |
             (((((((l_life_t).bit.swDay_u32 * 10UL) + (l_life_t).bit.gwDay_u32) / 10UL) % 10UL) & 0x03UL) << 16U)),
            v_valid_u16);
    }
    /* 油量重置接收反馈 */
    else if (RIU_POD_EVENT_GROUP_OIL_RESET == v_eventGroup_u16)
    {
        l_label_u16 = RIU_LABEL_T_RP_OIL_RESET_RCV_FB;

        if (0U == l_side_u16)
        {
            l_label_u16 = RIU_LABEL_T_LP_OIL_RESET_RCV_FB;
        }
        Comm429RIUPodEventOneTx(v_ID_u16, l_label_u16, (Uint32)(v_kzzzData_t.oilReset_u16 & 0xFFFFU), v_valid_u16);
    }
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIULocalVersionInfoTx
 *    【功能描述】:   向RIU发送本地软件版本信息(DSP/CPLD及对端通道版本号)
 *    【输入参数说明】:v_ID_u16 ---- 端口号
 *                    vp_conData_t ---- 控制数据指针
 *    【输出参数说明】:NONE
 *    【其他说明】:   本通道发本机版本，对端通道发CCDL镜像的对端版本
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void Comm429RIULocalVersionInfoTx(Uint16 v_ID_u16, const ConData_t *vp_conData_t)
{
    union SoftwVData l_dspSoftV_un16 = SoftwVDataGet();
    Uint16 l_cpldSoftV_u16 = HardXintUint16Read(CPLD_ADDR_R_CPLD_VER);
    PeerBaseStatus_t l_peerBase_t = CommCCDLPeerBaseGet(COMM_CCDL_SCI);
    Uint16 l_ch1DspValid_u16 = VALID;
    Uint16 l_ch1CpldValid_u16 = VALID;
    Uint16 l_ch2DspValid_u16 = INVALID;
    Uint16 l_ch2CpldValid_u16 = INVALID;
    Uint32 l_ch1Dsp_u32 = Comm429RIUVersionRawPack(l_dspSoftV_un16.all);
    Uint32 l_ch1Cpld_u32 = Comm429RIUVersionRawPack(l_cpldSoftV_u16);
    Uint32 l_ch2Dsp_u32 = 0UL;
    Uint32 l_ch2Cpld_u32 = 0UL;

    /* SCI链路无对端时尝试CPLD链路 */
    if (VALID != l_peerBase_t.valid_u16)
    {
        l_peerBase_t = CommCCDLPeerBaseGet(COMM_CCDL_CPLD);
    }

    /* 本机为通道2时：通道2发本机版本，通道1发对端版本 */
    if ((NULL != vp_conData_t) && (SYS_CH_ID_2 == vp_conData_t->myChID_u16))
    {
        l_ch2DspValid_u16 = VALID;
        l_ch2CpldValid_u16 = VALID;
        l_ch2Dsp_u32 = Comm429RIUVersionRawPack(l_dspSoftV_un16.all);
        l_ch2Cpld_u32 = Comm429RIUVersionRawPack(l_cpldSoftV_u16);
        l_ch1DspValid_u16 = l_peerBase_t.valid_u16;
        l_ch1CpldValid_u16 = l_peerBase_t.valid_u16;
        l_ch1Dsp_u32 = Comm429RIUVersionRawPack(l_peerBase_t.softV_DSP_u16);
        l_ch1Cpld_u32 = Comm429RIUVersionRawPack(l_peerBase_t.softV_CPLD_u16);
    }
    /* 本机为通道1时：通道1发本机版本，通道2发对端版本 */
    else
    {
        if (VALID == l_peerBase_t.valid_u16)
        {
            l_ch2DspValid_u16 = VALID;
            l_ch2CpldValid_u16 = VALID;
            l_ch2Dsp_u32 = Comm429RIUVersionRawPack(l_peerBase_t.softV_DSP_u16);
            l_ch2Cpld_u32 = Comm429RIUVersionRawPack(l_peerBase_t.softV_CPLD_u16);
        }
    }

    /* 发送4路版本信息：通道1/2 DSP + 通道1/2 CPLD */
    Comm429RIURawSend(v_ID_u16, RIU_LABEL_T_CTRL_SWV_CH1, l_ch1Dsp_u32, Comm429RIUSsmGet(l_ch1DspValid_u16));
    Comm429RIURawSend(v_ID_u16, RIU_LABEL_T_CTRL_SWV_CH2, l_ch2Dsp_u32, Comm429RIUSsmGet(l_ch2DspValid_u16));
    Comm429RIURawSend(v_ID_u16, RIU_LABEL_T_LOGIC_SWV_CH1, l_ch1Cpld_u32, Comm429RIUSsmGet(l_ch1CpldValid_u16));
    Comm429RIURawSend(v_ID_u16, RIU_LABEL_T_LOGIC_SWV_CH2, l_ch2Cpld_u32, Comm429RIUSsmGet(l_ch2CpldValid_u16));
}


/* ***************************************************************** */
/* 对外接口函数 */
/* ***************************************************************** */

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIURxDataGet
 *    【功能描述】:   获取RIU429通信解析数据
 *    【输入参数说明】:v_ID_u16 ---- 通道号ID
 *    【输出参数说明】:NONE
 *    【其他说明】:   通道号非法时返回预留位异常值
 *    【返回】:       RIU429InfoData_t
 */
/* ***************************************************************** */
RIU429InfoData_t Comm429RIURxDataGet(Uint16 v_ID_u16)
{
    RIU429InfoData_t l_rslt_t;
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    /* 通道号小于通道数 */
    if (v_ID_u16 < COMM429_RIU_NUM)
    {
        l_rslt_t = s_Comm429RIUData_t[v_ID_u16];
    }
    else
    {
        /* 输入ID异常时返回预留位异常数值 */
        l_rslt_t.ryxtCMD_1_un32.bit.rsvd_3_u16 = 0xFFU;
    }
    return l_rslt_t;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIUOrigDataGet
 *    【功能描述】:   获取RIU429通信原始数据
 *    【输入参数说明】:v_ID_u16 ---- 通道号ID
 *    【输出参数说明】:NONE
 *    【其他说明】:   通道号非法时返回心跳异常数值
 *    【返回】:       RIU429OrigData_t
 */
/* ***************************************************************** */
RIU429OrigData_t Comm429RIUOrigDataGet(Uint16 v_ID_u16)
{
    RIU429OrigData_t l_rslt_t;
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    if (v_ID_u16 < COMM429_RIU_NUM)
    {
        l_rslt_t = s_RIUOrigData_t[v_ID_u16];
    }
    else
    {
        /* 输入ID异常时返回心跳异常数值 */
        l_rslt_t.Orig_Rx_t[RIU_R_DATA_INDEX_HEART].OrigData_u32 = 0xFFFFUL;
    }
    return l_rslt_t;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429RIURxStateGet
 *    【功能描述】:   获取RIU429通信接收状态
 *    【输入参数说明】:v_ID_u16 ---- 通道号ID
 *    【输出参数说明】:NONE
 *    【其他说明】:   通道号非法时返回接收时间异常值
 *    【返回】:       A429Info_t
 */
/* ***************************************************************** */
A429Info_t Comm429RIURxStateGet(Uint16 v_ID_u16)
{
    A429Info_t l_rslt_t;
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    if (v_ID_u16 < COMM429_RIU_NUM)
    {
        l_rslt_t = s_Comm429RIUInfo_t[v_ID_u16];
    }
    else
    {
        /* 输入ID异常时返回接收时间异常值 */
        l_rslt_t.rxTime_u32 = 0xFFFFFFFFU;
    }
    return l_rslt_t;
}

/* ***************************************************************** */
/**
 *    【函数名】:	  Comm429RIUInit
 *    【功能描述】:	 远程接口单元429通信模块相关数据初始化
 *    【输入参数说明】:NONE
 *
 *	【输出参数说明】:NONE
 *    【其他说明】:	  NONE
 *    【返回】:	NONE
 */
/* ***************************************************************** */
void Comm429RIUInit(void)
{
    Uint16 l_ID_u16 = 0U;  /*通道号 */
    Uint16 l_index_u16 = 0U;  /* 索引 */

    /* 对RIU429通信模块数据进行初始化 */
    for (l_ID_u16 = 0U; l_ID_u16 < COMM429_RIU_NUM; l_ID_u16++)
    {
        /* 接收信息初始化 */
        s_Comm429RIUInfo_t[l_ID_u16].rxTime_u32 = sysTime();
        s_Comm429RIUInfo_t[l_ID_u16].rxCount_u32 = 0UL;
        s_Comm429RIUInfo_t[l_ID_u16].rxState_u16 = RX429_STATE_OK;
        s_Comm429RIUInfo_t[l_ID_u16].rxDataState_u16 = RX429_STATE_OK;

        /* 错误帧计数清零 */
        s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 = 0U;
        s_Comm429RIUInfo_t[l_ID_u16].ovflErrCount_u16 = 0U;

        /* 错误计数清零 */
        s_Comm429RIUInfo_t[l_ID_u16].errCntSum_u32 = 0UL;
        s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32 = 0UL;
        s_Comm429RIUInfo_t[l_ID_u16].errCntMax_u32 = 0UL;

        /* 接收解析数据数组初始化 */
        for (l_index_u16 = 0U; l_index_u16 < RIU429_IDATA_NUM; l_index_u16++)
        {
            s_RIU429Data_t[l_ID_u16][l_index_u16].currState_u16 = RIU429_INFODATA_UPDATE_ERR;
            s_RIU429Data_t[l_ID_u16][l_index_u16].checkState_u16 = RIU429_INFODATA_UPDATE_ERR;
            s_RIU429Data_t[l_ID_u16][l_index_u16].currData_u16 = 0U;
            s_RIU429Data_t[l_ID_u16][l_index_u16].checkTime_u32 = 0U;
            s_RIU429Data_t[l_ID_u16][l_index_u16].rxTime_u32 = 0U;
            s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16 = 0U;
        }

        /* 接收原始数据信息初始化 */
        for (l_index_u16 = 0U; l_index_u16 < RIU_R_DATA_NUM; l_index_u16++)
        {
            s_RIUOrigData_t[l_ID_u16].Orig_Rx_t[l_index_u16].label_u16 = s_RIU429Rx_labelConf_u16[l_index_u16];
            s_RIUOrigData_t[l_ID_u16].Orig_Rx_t[l_index_u16].OrigData_u32 = 0UL;
            s_RIUOrigData_t[l_ID_u16].Orig_Rx_t[l_index_u16].Cnt_u16 = 0U;
        }

        /* 日期时间数据初始化 */
        s_Comm429RIUData_t[l_ID_u16].heartB_u16 = 0xFFFU;
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Year_u16 = 2025U;
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Month_u16 = 1U;
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Day_u16 = 1U;
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Hour_u16 = 1U;
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Minute_u16 = 1U;
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Second_u16 = 1U;
        s_Comm429RIUData_t[l_ID_u16].DTData_t.MillSec_u16 = 0U;
        s_Comm429RIUData_t[l_ID_u16].RCV_t.all = 0U;
        s_Comm429RIUData_t[l_ID_u16].valve1_t.all = 0U;
        s_Comm429RIUData_t[l_ID_u16].valve2_t.all = 0U;
        s_Comm429RIUData_t[l_ID_u16].PRV_f = 0.0F;
        s_Comm429RIUData_t[l_ID_u16].lpPFV_f = 0.0F;
        s_Comm429RIUData_t[l_ID_u16].rpPFV_f = 0.0F;
        s_Comm429RIUData_t[l_ID_u16].PFV_f = 0.0F;
        s_Comm429RIUData_t[l_ID_u16].tank0_vol_f = 0.0F;
        s_Comm429RIUData_t[l_ID_u16].tank1_vol_f = 0.0F;
        s_Comm429RIUData_t[l_ID_u16].tank2_vol_f = 0.0F;
        s_Comm429RIUData_t[l_ID_u16].tank3_vol_f = 0.0F;
        s_Comm429RIUData_t[l_ID_u16].tank4_vol_f = 0.0F;
        s_Comm429RIUData_t[l_ID_u16].totalFuel_f = 0.0F;
        s_Comm429RIUData_t[l_ID_u16].maintCmd_u16 = 0U;
        s_Comm429RIUData_t[l_ID_u16].softVersionReq_u16 = 0U;
        s_Comm429RIUData_t[l_ID_u16].ctrlCmd_u16 = 0U;
        s_Comm429RIUData_t[l_ID_u16].softVersion_deploy = 0U;
    }

    /* 发送计数初始化 */
    for (l_index_u16 = 0U; l_index_u16 < RIU_T_DATA_NUM; l_index_u16++)
    {
        s_RIU429TxCnt_u32[l_index_u16] = 0UL;
    }
    for (l_ID_u16 = 0U; l_ID_u16 < COMM429_RIU_NUM; l_ID_u16++)
    {
        s_RIU429TimeoutCnt_u32[l_ID_u16] = 0UL;
    }
    s_RIU429Press34PlaceholderCnt_u32 = 0UL;
}

/* ***************************************************************** */
/**
 *    【函数名】:	  Comm429RIURxStateCheck
 *    【功能描述】:	  远程接口单元429通信 接收状态检查
 *    【输入参数说明】:NONE
 *
 *	  【输出参数说明】:NONE
 *    【其他说明】:	  NONE
 *    【返回】:	NONE
 */
/* ***************************************************************** */
void Comm429RIURxStateCheck(void)
{
    Uint16 l_ID_u16 = 0U;  /*通道号 */
    Uint32 l_checkTime_u32 = sysTime();  /* 检查时间 */
    Uint16 l_rData_u16 = RX429_STATE_OK;  /* 通信接收状态 */

    /* 轮询每个通道 */
    for (l_ID_u16 = 0U; l_ID_u16 < COMM429_RIU_NUM; l_ID_u16++)
    {
        l_rData_u16 = RX429_STATE_OK;  /* 通信接收状态初始正常 */

        /* 超过两个周期未接收数据时 */
        if ((l_checkTime_u32 - s_Comm429RIUInfo_t[l_ID_u16].rxTime_u32) >= (2U * COMM429_RIU_PRIOD))
        {
            l_rData_u16 = RX429_STATE_ERR;
            s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32++;
            s_Comm429RIUInfo_t[l_ID_u16].errCntSum_u32++;
            if (s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32 > s_Comm429RIUInfo_t[l_ID_u16].errCntMax_u32)
            {
                s_Comm429RIUInfo_t[l_ID_u16].errCntMax_u32 = s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32;
            }
        }
        else
        {
            s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32 = 0UL;
        }

        /* 新发超时 */
        if ((RX429_STATE_ERR == l_rData_u16) && (RX429_STATE_ERR != s_Comm429RIUInfo_t[l_ID_u16].rxState_u16))
        {
            s_RIU429TimeoutCnt_u32[l_ID_u16]++;
        }
        s_Comm429RIUInfo_t[l_ID_u16].rxState_u16 = l_rData_u16;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:RIU429InfoDataStateCheck
 *
 * 【功能描述】RIU429接收数据刷新状态检查
 *             数据项状态连续5拍变化后才更新当前状态
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】       用于区分“链路有帧”与“具体数据项未刷新”
 * 【返回】          无
 */
/* ***************************************************************** */
void RIU429InfoDataStateCheck(void)
{
    Uint16 l_ID_u16 = 0U;  /*通道号 */
    Uint16 l_index_u16 = 0U; /* 索引 */

    /* 轮询每个通道 */
    for (l_ID_u16 = 0U; l_ID_u16 < COMM429_RIU_NUM; l_ID_u16++)
    {
        for (l_index_u16 = 0U; l_index_u16 < RIU429_IDATA_NUM; l_index_u16++)
        {
            /* 检查状态不等于当前状态 */
            if (s_RIU429Data_t[l_ID_u16][l_index_u16].currState_u16 != s_RIU429Data_t[l_ID_u16][l_index_u16].checkState_u16)
            {
                /* 状态改变计数未达门限 */
                if (s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16 < RIU429_IDATA_MAX_COUNT)
                {
                    s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16++;
                }
            }
            else
            {
                s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16 = 0U;
            }

            /* 状态改变计数达到门限值，更新当前状态 */
            if (s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16 >= RIU429_IDATA_MAX_COUNT)
            {
                s_RIU429Data_t[l_ID_u16][l_index_u16].currState_u16 = s_RIU429Data_t[l_ID_u16][l_index_u16].checkState_u16;
            }
        }
    }
}

/* ***************************************************************** */
/**
 *    【函数名】:	  Comm429RIUDataProcess
 *    【功能描述】:	  远程接口单元429通信数据处理
 *    【输入参数说明】:NONE
 *
 *	  【输出参数说明】:NONE
 *    【其他说明】:	  轮询三路通道(本通道直读FIFO + SCI/CPLD镜像)，
 *                    按标签switch-case解析，RxWordMark统一前置
 *    【返回】:	NONE
 */
/* ***************************************************************** */
void Comm429RIUDataProcess(void)
{
    Uint16 l_rxFifoState_u16 = DRI429_R_FIFO_OVFL;  /* 接收状态，默认FIFO接收溢出 */
    Uint16 l_rxDataNum_u16 = 0U;   /* 接收数据个数 */
    Uint16 l_ID_u16 = 0U;  /*通道号 */
    Uint16 l_ii_u16 = 0U;  /* 索引 */
    Uint16 l_jj_u16 = 0U;  /* 索引 */
    float l_temp_f = 0.0F;
    union arinc429Data l_rdata_un[A429_RX_DATA_NUM_MAX];
    RIU429OrigData_t l_CCDLRIUOrigData_t;   /* CCDL通信RIU镜像原始字 */
    Uint32 l_data_u32 = 0UL;

    memset(&l_CCDLRIUOrigData_t, 0, sizeof(l_CCDLRIUOrigData_t));

    /* 处理前置：周期数据置为未更新 */
    for (l_ID_u16 = 0U; l_ID_u16 < COMM429_RIU_NUM; l_ID_u16++)
    {
        for (l_jj_u16 = 0U; l_jj_u16 < RIU429_IDATA_NUM; l_jj_u16++)
        {
            s_RIU429Data_t[l_ID_u16][l_jj_u16].checkState_u16 = RIU429_INFODATA_UPDATE_ERR;
        }
    }

    /* 轮询每个通道 */
    for (l_ID_u16 = 0U; l_ID_u16 < COMM429_RIU_NUM; l_ID_u16++)
    {
        /* 0-本通道直读FIFO, 1-CCDL SCI镜像, 2-CCDL CPLD镜像 */
        /*
         * 三路数据最终都走同一套label解析表。
         * 本地429来自硬件FIFO，另外两路来自CCDL原始字镜像，便于上层按相同结构选源。
         */
        if (l_ID_u16 == 0U)
        {
            /* 接收FIFO溢出状态获取 */
            l_rxFifoState_u16 = Ccdl429RxFifoStatusGet(s_RIUCommIDConf_u16[l_ID_u16]);
        }
        else
        {
            l_rxFifoState_u16 = DRI429_R_FIFO_OK;
        }

        /* 当接收FIFO未溢出时，进行数据处理 */
        if (DRI429_R_FIFO_OK == l_rxFifoState_u16)
        {
            if (l_ID_u16 == 0U)
            {
                /* 读取429通信数据 */
                l_rxDataNum_u16 = Ccdl429ReadBuff(s_RIUCommIDConf_u16[l_ID_u16], l_rdata_un);
            }
            else if (l_ID_u16 == 1U)
            {
                /* CCDL SCI镜像数据读取 */
                l_CCDLRIUOrigData_t = CommCCDLRIUOrigDataGet(COMM_CCDL_SCI);
                l_rxDataNum_u16 = RIU_R_DATA_NUM;
                for (l_ii_u16 = 0U; l_ii_u16 < l_rxDataNum_u16; l_ii_u16++)
                {
                    /* 镜像里已经保存完整429原始字，复制到临时数组后复用本地解析流程。 */
                    l_rdata_un[l_ii_u16].msgData = l_CCDLRIUOrigData_t.Orig_Rx_t[l_ii_u16].OrigData_u32;
                }
            }
            else
            {
                /* CCDL CPLD镜像数据读取 */
                l_CCDLRIUOrigData_t = CommCCDLRIUOrigDataGet(COMM_CCDL_CPLD);
                l_rxDataNum_u16 = RIU_R_DATA_NUM;
                for (l_ii_u16 = 0U; l_ii_u16 < l_rxDataNum_u16; l_ii_u16++)
                {
                    /* CPLD镜像和SCI镜像解析口径一致，差异只体现在前面的链路新鲜度判断。 */
                    l_rdata_un[l_ii_u16].msgData = l_CCDLRIUOrigData_t.Orig_Rx_t[l_ii_u16].OrigData_u32;
                }
            }

            /* 判断接收个数大于0时 */
            if (l_rxDataNum_u16 > 0U)
            {
                /* 按标签逐帧解析 */
                for (l_ii_u16 = 0U; l_ii_u16 < l_rxDataNum_u16; l_ii_u16++)
                {
                    /* 奇偶校验：与KZZZ一致，校验失败累计错误并跳过 */
                    if(1U != Ccdl429ParityCheck(l_rdata_un[l_ii_u16], PARITY_ODD))
                    {
                        /* 校验失败的原始字不进入业务缓存，防止错误label污染当前源数据。 */
                        s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 = s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 + 1U;
                        continue;
                    }

                    /* SSM有效性校验：部分标签要求特定SSM编码 */
                    if(VALID != Comm429RIURxSsmValidGet(l_rdata_un[l_ii_u16]))
                    {
                        s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 = s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 + 1U;
                        continue;
                    }

                    switch (l_rdata_un[l_ii_u16].bit.label)
                    {
                        case RIU_LABEL_R_DATE_YMD:  /* 年、月、日 */
                            /* 更新原始数据、计数、时间戳 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_DATE_YMD, l_rdata_un[l_ii_u16].msgData);
                            /* BCD日期解码：年/月/日 */
                            l_data_u32 = l_rdata_un[l_ii_u16].bit.data;
                            s_Comm429RIUData_t[l_ID_u16].DTData_t.Year_u16  = (Uint16)(l_data_u32 & 0x7FUL) + 2000U;
                            s_Comm429RIUData_t[l_ID_u16].DTData_t.Month_u16 = (Uint16)((l_data_u32 >> 7U) & 0x3FUL);
                            s_Comm429RIUData_t[l_ID_u16].DTData_t.Day_u16   = (Uint16)((l_data_u32 >> 13U) & 0x3FUL);
                            break;

                        case RIU_LABEL_R_TIME_HMS:  /* 时、分、秒 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_TIME_HMS, l_rdata_un[l_ii_u16].msgData);
                            /* BCD时间解码：时/分/秒 */
                            l_data_u32 = l_rdata_un[l_ii_u16].bit.data;
                            s_Comm429RIUData_t[l_ID_u16].DTData_t.Hour_u16   = (Uint16)(l_data_u32 & 0x7FUL);
                            s_Comm429RIUData_t[l_ID_u16].DTData_t.Minute_u16 = (Uint16)((l_data_u32 >> 7U) & 0x3FUL);
                            s_Comm429RIUData_t[l_ID_u16].DTData_t.Second_u16 = (Uint16)((l_data_u32 >> 13U) & 0x3FUL);
                            break;

                        case RIU_LABEL_R_MAINT_CMD:  /* 维护指令 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_MAINT_CMD, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].maintCmd_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL);
                            break;

                        case RIU_LABEL_R_WHEEL_LOAD:  /* 轮载状态 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_WHEEL_LOAD, l_rdata_un[l_ii_u16].msgData);
                            /* 解析轮载三路3bit状态 */
                            l_data_u32 = l_rdata_un[l_ii_u16].bit.data;
                            s_Comm429RIUData_t[l_ID_u16].wheelLoadNose_u16 = (Uint16)((l_data_u32 >> 4U) & 0x7UL);
                            s_Comm429RIUData_t[l_ID_u16].wheelLoadLeftMain_u16 = (Uint16)((l_data_u32 >> 7U) & 0x7UL);
                            s_Comm429RIUData_t[l_ID_u16].wheelLoadRightMain_u16 = (Uint16)((l_data_u32 >> 10U) & 0x7UL);
                            /* 仅三轮全空中才报空中 */
                            if ((SSM_NORM == l_rdata_un[l_ii_u16].bit.ssm) &&
                                (RIU_WHEEL_LOAD_AIR == s_Comm429RIUData_t[l_ID_u16].wheelLoadNose_u16) &&
                                (RIU_WHEEL_LOAD_AIR == s_Comm429RIUData_t[l_ID_u16].wheelLoadLeftMain_u16) &&
                                (RIU_WHEEL_LOAD_AIR == s_Comm429RIUData_t[l_ID_u16].wheelLoadRightMain_u16))
                            {
                                s_Comm429RIUData_t[l_ID_u16].wheelLoad_u16 = RIU_DK_AIR;
                            }
                            else
                            {
                                s_Comm429RIUData_t[l_ID_u16].wheelLoad_u16 = RIU_DK_GROUND;
                            }
                            break;

                        case RIU_LABEL_R_HEART:  /* 健康状态字 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_HEART, l_rdata_un[l_ii_u16].msgData);
                            /* 心跳重复值检测接收停滞 */
                            if (s_Comm429RIUData_t[l_ID_u16].heartB_u16 == (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0xFFUL))
                            {
                                s_Comm429RIUInfo_t[l_ID_u16].rxDataState_u16 = RX429_STATE_ERR;
                            }
                            else
                            {
                                s_Comm429RIUInfo_t[l_ID_u16].rxDataState_u16 = RX429_STATE_OK;
                            }
                            /* 获取设备心跳 */
                            s_Comm429RIUData_t[l_ID_u16].heartB_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0xFFUL);
                            break;

                        case RIU_LABEL_R_MBIT_EXEC:  /* 执行维护BIT */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_MBIT_EXEC, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].mbitExec_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x3UL);
                            break;

                        case RIU_LABEL_R_SOFTV_REQ_INFO:  /* 软件版本请求信息 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_SOFTV_REQ, l_rdata_un[l_ii_u16].msgData);
                            l_data_u32 = l_rdata_un[l_ii_u16].bit.data;
                            s_Comm429RIUData_t[l_ID_u16].softVersionReq_u16 = (Uint16)(l_data_u32 & 0xFFFFUL);
                            s_Comm429RIUData_t[l_ID_u16].softVersion_deploy = (Uint32)(l_data_u32 & 0x1UL);
                            break;

                        case RIU_LABEL_R_OIL_RESET:  /* 油量重置 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_OIL_RESET, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].oilResetCmd_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x3UL);
                            break;

                        case RIU_LABEL_R_LIFE_INFO:  /* 发送寿命信息 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_LIFE_INFO, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].lifeInfo_u32 = l_rdata_un[l_ii_u16].bit.data;
                            break;

                        case RIU_LABEL_R_CTRL_CMD:  /* 控制指令 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_CTRL_CMD, l_rdata_un[l_ii_u16].msgData);
                            l_data_u32 = l_rdata_un[l_ii_u16].bit.data;
                            s_Comm429RIUData_t[l_ID_u16].ctrlCmd_u16 = (Uint16)(l_data_u32 & 0xFFFFUL);
                            /* 获取加受油对象 */
                            s_Comm429RIUData_t[l_ID_u16].fuelCmd_t.bit.fuelObject_u8 = l_data_u32 & 0x1UL;
                            /* 获取加受油模式 */
                            s_Comm429RIUData_t[l_ID_u16].fuelCmd_t.bit.fuelMode_u8 = (l_data_u32 >> 3UL) & 0x7UL;
                            break;

                        case RIU_LABEL_R_RCV:  /* 压力加油控制活门状态 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_RCV, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].RCV_t.all = l_rdata_un[l_ii_u16].bit.data & 0xFFFUL;
                            break;

                        case RIU_LABEL_R_VALVE1:  /* 阀状态信号1 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_VALVE1, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].valve1_t.all = l_rdata_un[l_ii_u16].bit.data & 0xFFUL;
                            break;

                        case RIU_LABEL_R_HL_SENSOR:  /* 高油面信号器信号 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_HL_SENSOR, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].HLSensor_t.all = l_rdata_un[l_ii_u16].bit.data & 0x1FUL;
                            break;

                        case RIU_LABEL_R_VALVE2:  /* 阀状态信号2 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_VALVE2, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].valve2_t.all = l_rdata_un[l_ii_u16].bit.data & 0x3FFFFUL;
                            break;

                        case RIU_LABEL_R_FUELPUMP:  /* 加油泵状态信号 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FUELPUMP, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].fuelPump_t.all = l_rdata_un[l_ii_u16].bit.data & 0xFUL;
                            break;

                        case RIU_LABEL_R_FAULTINFO:  /* 故障信息 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FAULTINFO, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].faultInfo_t.all = l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL;
                            break;

                        case RIU_LABEL_R_FQ_TANK0:  /* 0号油箱油量值 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FQ_TANK0, l_rdata_un[l_ii_u16].msgData);
                            /* 获取0号油箱油量并刷新总油量 */
                            l_temp_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9UL) & 0x3FFUL);
                            s_Comm429RIUData_t[l_ID_u16].tank0_vol_f = l_temp_f * OIL_RATIO;
                            s_Comm429RIUData_t[l_ID_u16].totalFuel_f =
                                s_Comm429RIUData_t[l_ID_u16].tank0_vol_f + s_Comm429RIUData_t[l_ID_u16].tank1_vol_f +
                                s_Comm429RIUData_t[l_ID_u16].tank2_vol_f + s_Comm429RIUData_t[l_ID_u16].tank3_vol_f +
                                s_Comm429RIUData_t[l_ID_u16].tank4_vol_f;
                            break;

                        case RIU_LABEL_R_FQ_TANK1:  /* 1号油箱油量值 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FQ_TANK1, l_rdata_un[l_ii_u16].msgData);
                            l_temp_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9UL) & 0x3FFUL);
                            s_Comm429RIUData_t[l_ID_u16].tank1_vol_f = l_temp_f * OIL_RATIO;
                            s_Comm429RIUData_t[l_ID_u16].totalFuel_f =
                                s_Comm429RIUData_t[l_ID_u16].tank0_vol_f + s_Comm429RIUData_t[l_ID_u16].tank1_vol_f +
                                s_Comm429RIUData_t[l_ID_u16].tank2_vol_f + s_Comm429RIUData_t[l_ID_u16].tank3_vol_f +
                                s_Comm429RIUData_t[l_ID_u16].tank4_vol_f;
                            break;

                        case RIU_LABEL_R_FQ_TANK2:  /* 2号油箱油量值 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FQ_TANK2, l_rdata_un[l_ii_u16].msgData);
                            l_temp_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9UL) & 0x3FFUL);
                            s_Comm429RIUData_t[l_ID_u16].tank2_vol_f = l_temp_f * OIL_RATIO;
                            s_Comm429RIUData_t[l_ID_u16].totalFuel_f =
                                s_Comm429RIUData_t[l_ID_u16].tank0_vol_f + s_Comm429RIUData_t[l_ID_u16].tank1_vol_f +
                                s_Comm429RIUData_t[l_ID_u16].tank2_vol_f + s_Comm429RIUData_t[l_ID_u16].tank3_vol_f +
                                s_Comm429RIUData_t[l_ID_u16].tank4_vol_f;
                            break;

                        case RIU_LABEL_R_FQ_TANK3:  /* 3号油箱油量值 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FQ_TANK3, l_rdata_un[l_ii_u16].msgData);
                            l_temp_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9UL) & 0x3FFUL);
                            s_Comm429RIUData_t[l_ID_u16].tank3_vol_f = l_temp_f * OIL_RATIO;
                            s_Comm429RIUData_t[l_ID_u16].totalFuel_f =
                                s_Comm429RIUData_t[l_ID_u16].tank0_vol_f + s_Comm429RIUData_t[l_ID_u16].tank1_vol_f +
                                s_Comm429RIUData_t[l_ID_u16].tank2_vol_f + s_Comm429RIUData_t[l_ID_u16].tank3_vol_f +
                                s_Comm429RIUData_t[l_ID_u16].tank4_vol_f;
                            break;

                        case RIU_LABEL_R_FQ_TANK4:  /* 4号油箱油量值 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FQ_TANK4, l_rdata_un[l_ii_u16].msgData);
                            l_temp_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9UL) & 0x3FFUL);
                            s_Comm429RIUData_t[l_ID_u16].tank4_vol_f = l_temp_f * OIL_RATIO;
                            s_Comm429RIUData_t[l_ID_u16].totalFuel_f =
                                s_Comm429RIUData_t[l_ID_u16].tank0_vol_f + s_Comm429RIUData_t[l_ID_u16].tank1_vol_f +
                                s_Comm429RIUData_t[l_ID_u16].tank2_vol_f + s_Comm429RIUData_t[l_ID_u16].tank3_vol_f +
                                s_Comm429RIUData_t[l_ID_u16].tank4_vol_f;
                            break;

                        case RIU_LABEL_R_TOTAL_FUEL:  /* 全机总油量 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_TOTAL_FUEL, l_rdata_un[l_ii_u16].msgData);
                            l_temp_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9UL) & 0x3FFUL);
                            s_Comm429RIUData_t[l_ID_u16].totalFuel_f = l_temp_f * OIL_RATIO;
                            break;

                        case RIU_LABEL_R_PRV:  /* 预设受油量值 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_PRV, l_rdata_un[l_ii_u16].msgData);
                            l_temp_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9UL) & 0x3FFUL);
                            s_Comm429RIUData_t[l_ID_u16].PRV_f = l_temp_f * OIL_RATIO;
                            break;

                        case RIU_LABEL_R_LP_PFV:  /* 左吊舱预选油量 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_LP_PFV, l_rdata_un[l_ii_u16].msgData);
                            l_temp_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9UL) & 0x3FFUL);
                            s_Comm429RIUData_t[l_ID_u16].lpPFV_f = l_temp_f * OIL_RATIO;
                            /* 同步综合PFV */
                            s_Comm429RIUData_t[l_ID_u16].PFV_f = s_Comm429RIUData_t[l_ID_u16].lpPFV_f;
                            break;

                        case RIU_LABEL_R_RP_PFV:  /* 右吊舱预选油量 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_RP_PFV, l_rdata_un[l_ii_u16].msgData);
                            l_temp_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9UL) & 0x3FFUL);
                            s_Comm429RIUData_t[l_ID_u16].rpPFV_f = l_temp_f * OIL_RATIO;
                            break;

                        case RIU_LABEL_R_IAS:  /* 指示空速 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_IAS, l_rdata_un[l_ii_u16].msgData);
                            l_temp_f = (float)(l_rdata_un[l_ii_u16].bit.data & 0x3FFFUL);
                            s_Comm429RIUData_t[l_ID_u16].airSpeed_f = l_temp_f * AIR_SPEED_RATIO;
                            break;

                        case RIU_LABEL_R_FUEL_DENSITY:  /* 燃油密度 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FUEL_DENSITY, l_rdata_un[l_ii_u16].msgData);
                            l_temp_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9U) & 0x3FFUL);
                            s_Comm429RIUData_t[l_ID_u16].oilMD_f = l_temp_f * OIL_MD_RATIO;
                            break;

                        case RIU_LABEL_R_LP_BRIGHTNESS:  /* 左吊舱通道灯亮度调节 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_LP_BRIGHTNESS, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].lpBrightness_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL);
                            break;

                        case RIU_LABEL_R_RP_BRIGHTNESS:  /* 右吊舱通道灯亮度调节 */
                            Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_RP_BRIGHTNESS, l_rdata_un[l_ii_u16].msgData);
                            s_Comm429RIUData_t[l_ID_u16].rpBrightness_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL);
                            break;

                        default:
                            /* 记录收到异常标号的报文 */
                            s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16++;
                            break;
                    }
                }
            }
        }
        else
        {
            /* FIFO溢出错误计数加1 */
            s_Comm429RIUInfo_t[l_ID_u16].ovflErrCount_u16++;
            /* 接收FIFO有数时，将FIFO剩下数据读空 */
            /* 溢出后直接复位FIFO，下一周期重新收新帧，避免半截旧帧继续参与解析。 */
            Ccdl429RFIFOReset(s_RIUCommIDConf_u16[l_ID_u16]);
        }
    }

    /* 接收数据状态检测 */
    /* 先判数据项是否刷新，再判链路总体状态，便于故障区分“无帧”和“帧不更新”。 */
    RIU429InfoDataStateCheck();

    /* 通信接收状态检测 */
    Comm429RIURxStateCheck();
}


/* ***************************************************************** */
/* 周期发送 */
/* ***************************************************************** */

/* 事件请求计数→接收索引映射表 */
static const Uint16 s_eventReqIndexTable[RIU_EVENT_REQ_NUM] =
{
    RIU_R_DATA_INDEX_MBIT_EXEC,
    RIU_R_DATA_INDEX_SOFTV_REQ,
    RIU_R_DATA_INDEX_OIL_RESET,
    RIU_R_DATA_INDEX_LIFE_INFO,
    RIU_R_DATA_INDEX_LP_PFV,
    RIU_R_DATA_INDEX_RP_PFV,
};

/* ***************************************************************** */
/**
 *    【函数名】:	  Comm429RIUPeriodInfoTx
 *    【功能描述】:	  远程接口单元429通信周期发送
 *    【输入参数说明】:NONE
 *
 *	  【输出参数说明】:NONE
 *    【其他说明】:	  门控(授权+节拍)后发送周期量(心跳/控制指令/状态/故障/告警/提示/吊舱周期数据)
 *                    和事件量(边沿检测触发软件版本/预选油量/寿命/油量重置)
 *    【返回】:	NONE
 */
/* ***************************************************************** */
void Comm429RIUPeriodInfoTx(void)
{
    Uint16 l_ID_u16 = COMM429_RIU_1;
    Uint16 l_ii_u16 = 0U;
    const ConData_t *lc_p_conData_t = ConDataGet();
    const RIU429SendData_t *lc_p_RIU429SendData_t = RIU429SendDataGet();
    static Uint32 s_lastTxTime_u32 = 0UL;
    static RIUEventReqTrack_t s_eventReqTrack[RIU_EVENT_REQ_NUM];
    static Uint16 s_trackInited_u16 = INVALID;
    RIU429OrigData_t l_riuOrigData_t;
    A429Info_t l_leftState_t;
    A429Info_t l_rightState_t;
    Uint16 l_leftValid_u16 = INVALID;
    Uint16 l_rightValid_u16 = INVALID;
    KZZZ429InfoData_t l_leftData_t;
    KZZZ429InfoData_t l_rightData_t;
    Uint32 l_now_u32 = 0UL;
    Uint32 l_tData_u32 = 0UL;
    Uint16 l_valid_u16 = INVALID;
    union arinc429Data l_reqData_un;
    Uint16 l_softvReqValid_u16 = INVALID;
    Uint16 l_oilResetLeftReq_u16 = INVALID;
    Uint16 l_oilResetRightReq_u16 = INVALID;
    Uint16 l_lifeLeftReq_u16 = INVALID;
    Uint16 l_lifeRightReq_u16 = INVALID;
    static Uint16 l_s_heartPhase_u16[COMM429_RIU_NUM] = {0,0,0};  /* 心跳相位，0/1交替 */

    memset(&l_riuOrigData_t, 0, sizeof(l_riuOrigData_t));
    memset(&l_leftState_t, 0, sizeof(l_leftState_t));
    memset(&l_rightState_t, 0, sizeof(l_rightState_t));
    memset(&l_leftData_t, 0, sizeof(l_leftData_t));
    memset(&l_rightData_t, 0, sizeof(l_rightData_t));
    memset(&l_reqData_un, 0, sizeof(l_reqData_un));

    /* 门控：授权检查 + 节拍控制 */
    l_now_u32 = sysTime();
    if ((NULL == lc_p_conData_t) || (CON_OUT_STATE_VALID != lc_p_conData_t->ConOutData_t.conOutState_u16))
    {
        /* 控制输出无效时停止429上报，并让事件边沿下次重新建基线，避免恢复后补发旧请求。 */
        s_trackInited_u16 = INVALID;
        return;
    }
    if ((0UL != s_lastTxTime_u32) && ((l_now_u32 - s_lastTxTime_u32) < RIU_TX_PERIOD_MS))
    {
        /* 周期发送由本函数自带节拍门控，调用方即使更频繁进入也不会加快429刷新。 */
        return;
    }
    s_lastTxTime_u32 = l_now_u32;

    /* 首次初始化事件追踪数组 */
    if (INVALID == s_trackInited_u16)
    {
        /*
         * 事件量依靠接收原始字计数变化触发。首次进入只记录基线，
         * 不把上电前已经存在的计数误当成一次新请求。
         */
        for (l_ii_u16 = 0U; l_ii_u16 < RIU_EVENT_REQ_NUM; l_ii_u16++)
        {
            s_eventReqTrack[l_ii_u16].inited_u16 = INVALID;
        }
        s_trackInited_u16 = VALID;
    }

    l_riuOrigData_t = Comm429RIUOrigDataGet(l_ID_u16);

    /* 左右吊舱有效判定 */
    /* 吊舱周期量允许左右独立有效；左失效不会阻断右吊舱数据上报。 */
    l_leftState_t = Comm429KZZZRxStateGet(COMM429_KZZZ_1);
    if ((RX429_STATE_OK == l_leftState_t.rxState_u16) && (RX429_STATE_OK == l_leftState_t.rxDataState_u16))
    {
        l_leftValid_u16 = VALID;
    }
    l_rightState_t = Comm429KZZZRxStateGet(COMM429_KZZZ_2);
    if ((RX429_STATE_OK == l_rightState_t.rxState_u16) && (RX429_STATE_OK == l_rightState_t.rxDataState_u16))
    {
        l_rightValid_u16 = VALID;
    }
    l_leftData_t = Comm429KzzzRxDataGet(COMM429_KZZZ_1);
    l_rightData_t = Comm429KzzzRxDataGet(COMM429_KZZZ_2);

    /* === 周期量发送 === */

    /* 1.总线心跳：ICD要求0xAA/0x55交替，通信故障通过SSM表达 */
    l_tData_u32 = RIU_HEART_PATTERN_B;

    if (0U == l_s_heartPhase_u16[l_ID_u16])
    {
        l_tData_u32 = RIU_HEART_PATTERN_A;
    }
    l_s_heartPhase_u16[l_ID_u16] ^= 0x1U;

    l_valid_u16 = INVALID;
    if (IFBIT_TEST_OK == IFBITInfoGet(IFBIT_INDEX_COMM_429RIU_1 + l_ID_u16))
    {
        l_valid_u16 = VALID;
    }
    Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_BUS_HEART, l_tData_u32, Comm429RIUSsmGet(l_valid_u16));

    /* 2.上电BIT结果：仅上报BIT9综合故障有效位 */
    l_tData_u32 = 0UL;

    if (PUBIT_TEST_OK != (PuBITDataGet() & PUBIT_KEY_FAULT_CODE))
    {
        l_tData_u32 = 0x1UL;
    }
    Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_PUBIT_ALARM_1, l_tData_u32, Comm429RIUSsmGet(VALID));

    /* 3.控制指令反馈(0220/0221/0222) */
    Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_CTRL_CMD_1, Comm429RIUCtrlCmd1Pack(lc_p_RIU429SendData_t), Comm429RIUSsmGet(VALID));
    Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_CTRL_CMD_2, Comm429RIUCtrlCmd2Pack(lc_p_RIU429SendData_t), Comm429RIUSsmGet(VALID));
    Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_CTRL_CMD_3, Comm429RIUCtrlCmd3Pack(lc_p_conData_t, lc_p_RIU429SendData_t), Comm429RIUSsmGet(VALID));

    /* 4.状态与故障信息(0230/0231/0232) */
    Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_STATUS_INFO, Comm429RIUStatusInfoPack(lc_p_conData_t), Comm429RIUSsmGet(VALID));
    Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_FAULT_INFO_1, Comm429RIUFaultInfo1Pack(lc_p_RIU429SendData_t), Comm429RIUSsmGet(VALID));
    Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_FAULT_INFO_2, Comm429RIUFaultInfo2Pack(lc_p_conData_t, lc_p_RIU429SendData_t), Comm429RIUSsmGet(VALID));

    /* 5.告警与提示(0233/0234) */
    Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_WARN_INFO, Comm429RIUWarnInfoPack(lc_p_RIU429SendData_t), Comm429RIUSsmGet(VALID));
    Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_TIP_INFO, Comm429RIUTipInfoPack(lc_p_conData_t), Comm429RIUSsmGet(VALID));

    /* 6.左右吊舱周期运行数据(0260~0277 / 0360~0377) */
    Comm429RIUPodPeriodicInfoTx(l_ID_u16, COMM429_KZZZ_1, l_leftValid_u16, l_leftData_t);
    Comm429RIUPodPeriodicInfoTx(l_ID_u16, COMM429_KZZZ_2, l_rightValid_u16, l_rightData_t);

    /* === 事件量发送 === */

    /* 收集计数 + 边沿检测 */
    for (l_ii_u16 = 0U; l_ii_u16 < RIU_EVENT_REQ_NUM; l_ii_u16++)
    {
        /* 只比较接收计数，不直接比较数据值；上位机重复发送同值请求也能被识别。 */
        s_eventReqTrack[l_ii_u16].currCnt_u16 = l_riuOrigData_t.Orig_Rx_t[s_eventReqIndexTable[l_ii_u16]].Cnt_u16;
        if (INVALID == s_eventReqTrack[l_ii_u16].inited_u16)
        {
            /* 建基线这一拍不触发事件，下一拍计数变化才算真正请求。 */
            s_eventReqTrack[l_ii_u16].lastCnt_u16 = s_eventReqTrack[l_ii_u16].currCnt_u16;
            s_eventReqTrack[l_ii_u16].inited_u16 = VALID;
            s_eventReqTrack[l_ii_u16].changed_u16 = INVALID;
        }
        else
        {
            s_eventReqTrack[l_ii_u16].changed_u16 = INVALID;

            if (s_eventReqTrack[l_ii_u16].lastCnt_u16 != s_eventReqTrack[l_ii_u16].currCnt_u16)
            {
                /* 计数变化说明对应请求标签刷新过，后续再结合请求有效位决定是否回传事件量。 */
                s_eventReqTrack[l_ii_u16].changed_u16 = VALID;
            }
        }
    }

    /* 解析请求有效位 */
    l_reqData_un.msgData = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_SOFTV_REQ].OrigData_u32;
    l_softvReqValid_u16 = (Uint16)(l_reqData_un.bit.data & 0x1UL);
    l_reqData_un.msgData = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_OIL_RESET].OrigData_u32;
    l_oilResetLeftReq_u16 = (Uint16)(l_reqData_un.bit.data & 0x1UL);
    l_oilResetRightReq_u16 = (Uint16)((l_reqData_un.bit.data >> 1U) & 0x1UL);
    l_reqData_un.msgData = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_LIFE_INFO].OrigData_u32;
    l_lifeLeftReq_u16 = (Uint16)(l_reqData_un.bit.data & 0x1UL);
    l_lifeRightReq_u16 = (Uint16)((l_reqData_un.bit.data >> 1U) & 0x1UL);

    /* 软件版本请求：发送本地版本+左右吊舱版本 */
    if (VALID == s_eventReqTrack[1].changed_u16)
    {
        if (0U != l_softvReqValid_u16)
        {
            /* 软件版本请求一次性回本机版本和左右吊舱版本，便于维护端做同一时刻比对。 */
            Comm429RIULocalVersionInfoTx(l_ID_u16, lc_p_conData_t);
            Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_1, RIU_POD_EVENT_GROUP_SOFTV, l_leftValid_u16, l_leftData_t);
            Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_2, RIU_POD_EVENT_GROUP_SOFTV, l_rightValid_u16, l_rightData_t);
        }
        s_eventReqTrack[1].lastCnt_u16 = s_eventReqTrack[1].currCnt_u16;
    }

    /* 左吊舱预选油量 */
    if (VALID == s_eventReqTrack[4].changed_u16)
    {
        Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_1, RIU_POD_EVENT_GROUP_PRE_FUEL, l_leftValid_u16, l_leftData_t);
        s_eventReqTrack[4].lastCnt_u16 = s_eventReqTrack[4].currCnt_u16;
    }

    /* 右吊舱预选油量 */
    if (VALID == s_eventReqTrack[5].changed_u16)
    {
        Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_2, RIU_POD_EVENT_GROUP_PRE_FUEL, l_rightValid_u16, l_rightData_t);
        s_eventReqTrack[5].lastCnt_u16 = s_eventReqTrack[5].currCnt_u16;
    }

    /* 寿命信息请求 */
    if (VALID == s_eventReqTrack[3].changed_u16)
    {
        if (0U != l_lifeLeftReq_u16)
        {
            /* 寿命请求按左右请求位分开发送，避免只请求一侧时误刷新另一侧事件。 */
            Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_1, RIU_POD_EVENT_GROUP_LIFE, l_leftValid_u16, l_leftData_t);
        }
        if (0U != l_lifeRightReq_u16)
        {
            Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_2, RIU_POD_EVENT_GROUP_LIFE, l_rightValid_u16, l_rightData_t);
        }
        s_eventReqTrack[3].lastCnt_u16 = s_eventReqTrack[3].currCnt_u16;
    }

    /* 油量重置请求 */
    if (VALID == s_eventReqTrack[2].changed_u16)
    {
        if (0U != l_oilResetLeftReq_u16)
        {
            /* 油量重置事件同样按左右请求位拆开，保持与吊舱侧事件语义一致。 */
            Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_1, RIU_POD_EVENT_GROUP_OIL_RESET, l_leftValid_u16, l_leftData_t);
        }
        if (0U != l_oilResetRightReq_u16)
        {
            Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_2, RIU_POD_EVENT_GROUP_OIL_RESET, l_rightValid_u16, l_rightData_t);
        }
        s_eventReqTrack[2].lastCnt_u16 = s_eventReqTrack[2].currCnt_u16;
    }

    /* 维护BIT请求：发送MBIT反馈和结果字 */
    /* MBIT反馈编码：PASS→0x0, FAIL→0x3, 其他→0x2 */
    if (VALID == s_eventReqTrack[0].changed_u16)
    {
        /* 维护BIT执行反馈(0202) */
        l_tData_u32 = 0UL;
        l_valid_u16 = INVALID;
        if ((VALID == l_leftValid_u16) || (VALID == l_rightValid_u16))
        {
            l_valid_u16 = VALID;
            if (VALID == l_leftValid_u16)
            {
                /* MBIT反馈压缩成2bit编码，左右各占一组，RIU端按固定位置解读。 */
                if (KZZZ_MBIT_PASS == l_leftData_t.MBITFB_u16) { l_tData_u32 |= ((Uint32)0x0U) << 0U; }
                else if (KZZZ_MBIT_FAIL == l_leftData_t.MBITFB_u16) { l_tData_u32 |= ((Uint32)0x3U) << 0U; }
                else { l_tData_u32 |= ((Uint32)0x2U) << 0U; }
            }
            if (VALID == l_rightValid_u16)
            {
                if (KZZZ_MBIT_PASS == l_rightData_t.MBITFB_u16) { l_tData_u32 |= ((Uint32)0x0U) << 2U; }
                else if (KZZZ_MBIT_FAIL == l_rightData_t.MBITFB_u16) { l_tData_u32 |= ((Uint32)0x3U) << 2U; }
                else { l_tData_u32 |= ((Uint32)0x2U) << 2U; }
            }
        }
        Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_MBIT_EXEC_FB, l_tData_u32, Comm429RIUSsmGet(l_valid_u16));

        /* 上传维护BIT结果(0203) */
        l_tData_u32 = 0UL;
        l_valid_u16 = INVALID;
        if ((VALID == l_leftValid_u16) || (VALID == l_rightValid_u16))
        {
            l_valid_u16 = VALID;
            if (VALID == l_leftValid_u16)
            {
                /* 结果字只取吊舱维护BIT综合结果，详细故障仍走吊舱周期故障字。 */
                l_tData_u32 |= ((Uint32)(l_leftData_t.MBITFInfo_1_t.bit.mBitResult_u32 & 0x3U)) << 0U;
            }
            if (VALID == l_rightValid_u16)
            {
                l_tData_u32 |= ((Uint32)(l_rightData_t.MBITFInfo_1_t.bit.mBitResult_u32 & 0x3U)) << 2U;
            }
        }
        Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_UPLOAD_MBIT_RESULT, l_tData_u32, Comm429RIUSsmGet(l_valid_u16));
        s_eventReqTrack[0].lastCnt_u16 = s_eventReqTrack[0].currCnt_u16;
    }
}

/* ========================================================================== */
/* 文件结束 */
/* ========================================================================== */
