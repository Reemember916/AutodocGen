/**********************************************************************************
 *
 *             ***     **      **   **     ******
 *             ***     **     **    **   ***   ***
 *            ****     **     **   **   **      **
 *           ** **     **    **    **  **       **
 *          *** **     **   **     **  **
 *          **  **     **   **    **  **
 *         **   **     **  **     **  **
 *        ***   **     ** **      **  **
 *        ********     ** **     **   **      **
 *       **     **     ****      **   **     **
 *      **      **     ***       **   ***   **
 *      **      **     ***      **     ******
 *
 **********************************************************************************
 *
 * 文件名称:    Comm429RIU.c
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V2.00
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 *
 *********************************************************************************/

#include "Global.h"
#include "Comm429RIU.h"

/* ***************************************************************** */
/* 远程接口单元通信ID配置表 */
Uint16  s_RIUCommIDConf_u16[COMM429_RIU_NUM] =
            { COMMDRI_429_ID_9,
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

void Comm429RIUInit(void)
{
    Uint16 l_ID_u16 = 0U;  /*通道号 */
    Uint16 l_index_u16 = 0U;  /* 索引 */

    /* 对RIU429通信模块数据进行初始化 */
    for( l_ID_u16 = 0U; l_ID_u16 < COMM429_RIU_NUM; l_ID_u16++)
    {
        /* 接收信息初始化 */
        s_Comm429RIUInfo_t[l_ID_u16].rxTime_u32   = sysTime();
        s_Comm429RIUInfo_t[l_ID_u16].rxCount_u32  = 0UL;
        s_Comm429RIUInfo_t[l_ID_u16].rxState_u16  = RX429_STATE_OK;
        s_Comm429RIUInfo_t[l_ID_u16].rxDataState_u16  = RX429_STATE_OK;

        /* 错误帧计数清零 */
        s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 = 0U;    /* 标号错误帧计数清零 */
        s_Comm429RIUInfo_t[l_ID_u16].ovflErrCount_u16  = 0U;  /* FIFO溢出错误计数清零 */

        /* 错误计数清零 */
        s_Comm429RIUInfo_t[l_ID_u16].errCntSum_u32    = 0UL;
        s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32       = 0UL;
        s_Comm429RIUInfo_t[l_ID_u16].errCntMax_u32    = 0UL;

        /* 接收解析数据数组初始化 */
        for( l_index_u16 = 0U; l_index_u16 < RIU429_IDATA_NUM; l_index_u16++)
        {
            s_RIU429Data_t[l_ID_u16][l_index_u16].currState_u16  = RIU429_INFODATA_UPDATE_ERR; /* 信息数据检查正常 */
            s_RIU429Data_t[l_ID_u16][l_index_u16].checkState_u16 = RIU429_INFODATA_UPDATE_ERR; /* 信息数据检查正常 */
            s_RIU429Data_t[l_ID_u16][l_index_u16].currData_u16  = 0U; /* 信息数据检查正常 */
            s_RIU429Data_t[l_ID_u16][l_index_u16].checkTime_u32 = 0U; /* 时间清零  */
            s_RIU429Data_t[l_ID_u16][l_index_u16].rxTime_u32 = 0U; /* 时间清零  */
            s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16 = 0U; /* 计数清零  */
        }

        /* 接收原始数据信息初始化 */
        for( l_index_u16 = 0U; l_index_u16 < RIU_R_DATA_NUM; l_index_u16++)
        {
            s_RIUOrigData_t[l_ID_u16].Orig_Rx_t[l_index_u16].label_u16     = s_RIU429Rx_labelConf_u16[l_index_u16]; /* 根据配置表初始化标号  */
            s_RIUOrigData_t[l_ID_u16].Orig_Rx_t[l_index_u16].OrigData_u32  = 0UL; /* 原始数据初始化为0  */
            s_RIUOrigData_t[l_ID_u16].Orig_Rx_t[l_index_u16].Cnt_u16       = 0U; /* 计数初始化为0  */
        }

        s_Comm429RIUData_t[l_ID_u16].heartB_u16 = 0xFFFU;  /* 设备心跳,初始化为0-255外数据     */

        /* 日期时间数据初始化 */
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Year_u16  = 2025U; /* 年   */
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Month_u16 = 1U; /* 月   */
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Day_u16   = 1U; /* 日   */
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Hour_u16  = 1U; /* ʱ   */
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Minute_u16  = 1U; /* 分   */
        s_Comm429RIUData_t[l_ID_u16].DTData_t.Second_u16  = 1U; /* 秒   */
        s_Comm429RIUData_t[l_ID_u16].DTData_t.MillSec_u16 = 0U; /* 毫秒 */
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
            s_Comm429RIUData_t[l_ID_u16].fuelLow_u16 = 0U;
            s_Comm429RIUData_t[l_ID_u16].fuelReset_u16 = 0U;
            s_Comm429RIUData_t[l_ID_u16].softVersion_deploy = 0U;
        }

    for(l_index_u16 = 0U; l_index_u16 < RIU_T_DATA_NUM; l_index_u16++)
    {
        s_RIU429TxCnt_u32[l_index_u16] = 0UL;
    }

    for(l_ID_u16 = 0U; l_ID_u16 < COMM429_RIU_NUM; l_ID_u16++)
    {
        s_RIU429TimeoutCnt_u32[l_ID_u16] = 0UL;
    }

    s_RIU429Press34PlaceholderCnt_u32 = 0UL;
}

/* ***************************************************************** */
/**
 *    [函数名]：	  Comm429RIURxStateCheck
 *    [功能描述]：	  远程接口单元429通信 接收状态检查
 *    [输入参数说明]：NONE
 *
 *	  [输出参数说明]：NONE
 *    [其他说明]：	  NONE
 *    [返回]：	NONE
 */
/* ***************************************************************** */

void Comm429RIURxStateCheck(void)
{
    Uint16 l_ID_u16 = 0U;  /*通道号 */
    Uint32 l_checkTime_u32 = 0UL;  /* 检查时间 */
    Uint16 l_rData_u16 = RX429_STATE_OK;  /* 通信接收状态  */

    /* 获取当前系统时间计数作为检查时间 */
    l_checkTime_u32 = sysTime();

    /* 轮询每个通道 */
    for(l_ID_u16 = 0U;l_ID_u16 < COMM429_RIU_NUM;l_ID_u16++)
    {
        l_rData_u16 = RX429_STATE_OK;  /* 通信接收状态初始正常  */

        /* 一个周期未接收数据时 */
        if( (l_checkTime_u32 - s_Comm429RIUInfo_t[l_ID_u16].rxTime_u32) >= (2U * COMM429_RIU_PRIOD) )
        {
            /* 通信接收状态置为异常 */
            l_rData_u16 = RX429_STATE_ERR;

            /* 连续错误计数加1 */
            s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32 = s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32 + 1UL;

            /* 错误计数总数加1 */
            s_Comm429RIUInfo_t[l_ID_u16].errCntSum_u32 = s_Comm429RIUInfo_t[l_ID_u16].errCntSum_u32 + 1UL;

            /* 连续错误计数大于最大连续错误计数时 */
            if(s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32 > s_Comm429RIUInfo_t[l_ID_u16].errCntMax_u32)
            {
                /* 最大连续错误计数更新为连续错误计数 */
                s_Comm429RIUInfo_t[l_ID_u16].errCntMax_u32 = s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32;
            }
        }
        else /* 通信接收状态置正常 */
        {
            /* 连续错误计数清零 */
            s_Comm429RIUInfo_t[l_ID_u16].errCnt_u32 = 0UL;
        }
        if((RX429_STATE_ERR == l_rData_u16) && (RX429_STATE_ERR != s_Comm429RIUInfo_t[l_ID_u16].rxState_u16))
        {
            s_RIU429TimeoutCnt_u32[l_ID_u16] = s_RIU429TimeoutCnt_u32[l_ID_u16] + 1UL;
        }


        s_Comm429RIUInfo_t[l_ID_u16].rxState_u16 = l_rData_u16;
    }
}



/* ***************************************************************** */
/**
 *    [函数名]：	 RIU429InfoDataStateCheck
 *    [功能描述]：	 RIU429接收数据状态检查
 *    			数据状态5拍恢复更新
 *    [输入参数说明]：NONE
 *
 *	  [输出参数说明]：NONE
 *    [其他说明]：	 NONE
 *    [返回]：	NONE
 */
/* ***************************************************************** */
void RIU429InfoDataStateCheck(void)
{
    Uint16 l_ID_u16 = 0U;  /*通道号 */
    Uint16 l_index_u16 = 0U; /* 索引 */

    /* 轮询每个通道 */
    for(l_ID_u16 = 0U;l_ID_u16 < COMM429_RIU_NUM;l_ID_u16++)
    {
        for( l_index_u16 = 0U; l_index_u16 < RIU429_IDATA_NUM; l_index_u16++ )
        {
            /* 检查状态不等于当前状态 */
            if( s_RIU429Data_t[l_ID_u16][l_index_u16].currState_u16 != s_RIU429Data_t[l_ID_u16][l_index_u16].checkState_u16)
            {
                /* 状态改变计数小于数量 */
                if( s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16 < RIU429_IDATA_MAX_COUNT )
                {
                    /* 状态改变计数加1 */
                    s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16 = s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16 + 1U;
                }
            }
            else
            {
                s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16 = 0U; /* 状态改变计数清零 */
            }

            /* 状态改变计数达到门限值*/
            if(s_RIU429Data_t[l_ID_u16][l_index_u16].StateChangeCount_u16 >= RIU429_IDATA_MAX_COUNT)
            {
                /* 更新当前状态 */
                s_RIU429Data_t[l_ID_u16][l_index_u16].currState_u16 = s_RIU429Data_t[l_ID_u16][l_index_u16].checkState_u16;
            }
        }
    }
}

/* ***************************************************************** */
/*
 *【函数名】 Comm429RIUSendHeart
 *【功能描述】RIU429通信心跳字发送
 *【输入参数说明】v_ID_u16 --- 端口号
 *【输出参数说明】NONE
 *【其他说明】       NONE
 *【返回】              NONE
***************************************************************** */
void Comm429RIUSendHeart(Uint16 v_ID_u16)
{
    static Uint16 l_s_heartPhase_u16[COMM429_RIU_NUM];  /* 心跳相位，0/1交替 */
    Uint32 l_tData_u32 = 0UL;  /* 临时数据 */
    Uint16 l_valid_u16 = INVALID;

    /* 输入ID号小于ID数量 */
    if( v_ID_u16 < COMM429_RIU_NUM )
    {
        /* ICD要求心跳数据在0xAA/0x55之间交替。 */
        l_tData_u32 = (0U == l_s_heartPhase_u16[v_ID_u16]) ? RIU_HEART_PATTERN_A : RIU_HEART_PATTERN_B;
        l_s_heartPhase_u16[v_ID_u16] ^= 0x1U;

        /* 通道通信故障通过SSM表达有效/无效，不再占用数据位。 */
        l_valid_u16 = (IFBIT_TEST_OK == IFBITInfoGet(IFBIT_INDEX_COMM_429RIU_1 + v_ID_u16)) ? VALID : INVALID;

        Comm429RIURawSend(v_ID_u16, RIU_LABEL_T_BUS_HEART, l_tData_u32, Comm429RIUSsmGet(l_valid_u16));
    }
}

/* ***************************************************************** */
/**
 *    [函数名]：	  Comm429RIUDataProcess
 *    [功能描述]：	  远程接口单元429通信数据处理
 *    [输入参数说明]：v_ID_u16  ---- 通道号ID
 *
 *	  [输出参数说明]：NONE
 *    [其他说明]：	  NONE
 *    [返回]：	NONE
 */
/* ***************************************************************** */
void Comm429RIUDataProcess(void)
{
    Uint16 l_rxFifoState_u16 = DRI429_R_FIFO_OVFL;  /* 接收状态，默认FIFO接收溢出 */
    Uint16 l_rxDataNum_u16   = 0U;   /* 接收数据个数 */
    Uint16 l_ID_u16 = 0U;  /*通道号 */
    Uint16 l_ii_u16 = 0U;  /* 索引 */
    Uint16 l_jj_u16 = 0U;  /* 索引jj */
    float l_temp_f	= 0.0F;
    union  arinc429Data l_rdata_un[A429_RX_DATA_NUM_MAX];
    RIU429OrigData_t l_CCDLRIUOrigData_t;   /* CCDL通信RIU镜像原始字 */
    memset(&l_CCDLRIUOrigData_t, 0, sizeof(l_CCDLRIUOrigData_t));
    /* 整体流程：
     * 1. 先将全部通道周期数据置为未更新（RIU429_INFODATA_UPDATE_ERR），确保本拍结论由本轮接收重新生成；
     * 2. 轮询三路 RIU 数据源（ID=0 本路 429 FIFO、ID=1 CCDL-SCI 镜像、ID=2 CCDL-CPLD 镜像），优先本路；
     * 3. 对每路接收数据依次执行奇偶校验、SSM 有效性检查，失败则累计 labelErrCount 并跳过该字；
     * 4. 按标签索引匹配并更新 s_Comm429RIUData_t 各字段（日期/时间/指令/轮载/油量等），同时记录原始字与接收计数；
     * 5. 最终刷新各路接收状态 s_Comm429RIUInfo_t，供 IFBIT 与余度管理使用。
     */

     /* 在进行本周期数据处理前，首先将周期数据置为未更新状态 */
    for(l_ID_u16 = 0U;l_ID_u16 < COMM429_RIU_NUM;l_ID_u16++)
    {
        for(l_jj_u16 = 0U;l_jj_u16 < RIU429_IDATA_NUM;l_jj_u16++)
        {
            s_RIU429Data_t[l_ID_u16][l_jj_u16].checkState_u16 = RIU429_INFODATA_UPDATE_ERR;
        }
    }

    /* 轮询每个通道 */
    for(l_ID_u16 = 0U;l_ID_u16 < COMM429_RIU_NUM;l_ID_u16++)
    {
        /*0-本，1-ccdl sci，2-ccdl cpld*/
        if(l_ID_u16 == 0U)
        {
            /* 接收FIFO溢出状态获取  */
            l_rxFifoState_u16 = Ccdl429RxFifoStatusGet(s_RIUCommIDConf_u16[l_ID_u16]);
        }
        else
        {
            l_rxFifoState_u16 = DRI429_R_FIFO_OK;
        }

        /* 当接收FIFO未溢出时，进行数据处理 */
        if(DRI429_R_FIFO_OK == l_rxFifoState_u16)
        {
            if(l_ID_u16 == 0U)
            {
                /* 读取429通信数据 */
                l_rxDataNum_u16 = Ccdl429ReadBuff(s_RIUCommIDConf_u16[l_ID_u16],l_rdata_un);
            }
            /*ccdl数据读取 sci底层*/
            else if(l_ID_u16 == 1U)
            {
                l_CCDLRIUOrigData_t = CommCCDLRIUOrigDataGet(COMM_CCDL_SCI);
                l_rxDataNum_u16 = RIU_R_DATA_NUM;
                for(l_ii_u16 = 0U;l_ii_u16 < l_rxDataNum_u16;l_ii_u16++)
                {
                    l_rdata_un[l_ii_u16].msgData = l_CCDLRIUOrigData_t.Orig_Rx_t[l_ii_u16].OrigData_u32;
                }
            }
            /*ccdl数据读取 cpld底层*/
            else
            {
                l_CCDLRIUOrigData_t = CommCCDLRIUOrigDataGet(COMM_CCDL_CPLD);
                l_rxDataNum_u16 = RIU_R_DATA_NUM;
                for(l_ii_u16 = 0U;l_ii_u16 < l_rxDataNum_u16;l_ii_u16++)
                {
                    l_rdata_un[l_ii_u16].msgData = l_CCDLRIUOrigData_t.Orig_Rx_t[l_ii_u16].OrigData_u32;
                }
            }
            /* 判断接收个数大于0时 */
            if(l_rxDataNum_u16 > 0U)
            {
                /* 按标签统一解析本地429数据或CCDL镜像数据。 */
                for(l_ii_u16 = 0U;l_ii_u16 < l_rxDataNum_u16;l_ii_u16++)
                {
                    if(1U != Ccdl429ParityCheck(l_rdata_un[l_ii_u16], PARITY_ODD))
                    {
                        s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 = s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 + 1U;
                        continue;
                    }

                    if(VALID != Comm429RIURxSsmValidGet(l_rdata_un[l_ii_u16]))
                    {
                        s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 = s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 + 1U;
                        continue;
                    }

                    switch(l_rdata_un[l_ii_u16].bit.label)
                    {
                        case RIU_LABEL_R_DATE_YMD: /* 年、月、日 */
                            {
                                /* 解析日期字：year=data[6:0]+2000, month=data[12:7], day={data[19:13]@bit21-MSB+data[6:0]@bit22-LSB}。
                                 * docx 20260127 表2: 年=bit9-15(7bit), 月=bit16-20(5bit), 日=bit21 MSB + bit22-27 LSB(7bit)。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_DATE_YMD, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].DTData_t.Year_u16 =
                                        (Uint16)(((l_rdata_un[l_ii_u16].bit.data >> 0U) & 0x7FUL) + 2000UL);
                                s_Comm429RIUData_t[l_ID_u16].DTData_t.Month_u16 =
                                        (Uint16)((l_rdata_un[l_ii_u16].bit.data >> 7U) & 0x1FUL);
                                /* 日: bit21 是 MSB, bit22-27 是低 6 bit (data>>12 第 6 位, data>>13 的低 6 位) */
                                s_Comm429RIUData_t[l_ID_u16].DTData_t.Day_u16 =
                                        (Uint16)(((l_rdata_un[l_ii_u16].bit.data >> 13U) & 0x3FUL) |
                                                ((l_rdata_un[l_ii_u16].bit.data >> 20U) & 0x40U));
                            }
                            break;

                        case RIU_LABEL_R_TIME_HMS: /* 时、分、秒 */
                            {
                                /* 解析时间字：hour=data[5:0], minute={data[12:6]@bit15-MSB+data[6:0]@bit16-LSB}, second=data[6:0]@bit22-27。
                                 * docx 20260127 表3: 时=bit9-14(6bit), 分=bit15 MSB + bit16-21 LSB(7bit), 秒=bit22-27(6bit)。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_TIME_HMS, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].DTData_t.Hour_u16 =
                                        (Uint16)((l_rdata_un[l_ii_u16].bit.data >> 0U) & 0x3FUL);
                                /* 分: bit15 是 MSB (data>>6 第 6 位), bit16-21 是低 6 bit (data>>7 的低 6 位) */
                                s_Comm429RIUData_t[l_ID_u16].DTData_t.Minute_u16 =
                                        (Uint16)(((l_rdata_un[l_ii_u16].bit.data >> 7U) & 0x3FUL) |
                                                ((l_rdata_un[l_ii_u16].bit.data >> 6U) & 0x40U));
                                s_Comm429RIUData_t[l_ID_u16].DTData_t.Second_u16 =
                                        (Uint16)((l_rdata_un[l_ii_u16].bit.data >> 13U) & 0x3FUL);
                            }
                            break;

                        case RIU_LABEL_R_MAINT_CMD: /* 维护指令 */
                            {
                                /* 解析维护指令原始字。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_MAINT_CMD, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].maintCmd_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0xFFUL);
                            }
                            break;

                        case RIU_LABEL_R_WHEEL_LOAD: /* 轮载状态 */
                            {
                                /* 解析轮载三路2bit状态，并生成兼容空地聚合量。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_WHEEL_LOAD, l_rdata_un[l_ii_u16].msgData);

                            s_Comm429RIUData_t[l_ID_u16].wheelLoadNose_u16 =
                                    (Uint16)((l_rdata_un[l_ii_u16].bit.data >> 4U) & 0x7UL);
                            s_Comm429RIUData_t[l_ID_u16].wheelLoadLeftMain_u16 =
                                    (Uint16)((l_rdata_un[l_ii_u16].bit.data >> 7U) & 0x7UL);
                            s_Comm429RIUData_t[l_ID_u16].wheelLoadRightMain_u16 =
                                    (Uint16)((l_rdata_un[l_ii_u16].bit.data >> 10U) & 0x7UL);
                            /* RIU 004 轮载字按ARINC位号解码：
                             * bit13~15 前轮、bit16~18 左主轮、bit19~21 右主轮。
                             * 解码后继续按“仅三轮全空中才报空中”的兼容规则生成wheelLoad_u16。 */
                            s_Comm429RIUData_t[l_ID_u16].wheelLoad_u16 =
                                    Comm429RIUWheelLoadCompatAggregateGet(
                                            s_Comm429RIUData_t[l_ID_u16].wheelLoadNose_u16,
                                                s_Comm429RIUData_t[l_ID_u16].wheelLoadLeftMain_u16,
                                                s_Comm429RIUData_t[l_ID_u16].wheelLoadRightMain_u16,
                                                l_rdata_un[l_ii_u16].bit.ssm);
                            }
                            break;

                        case RIU_LABEL_R_MBIT_EXEC: /* 执行维护BIT */
                            {
                                /* 解析维护BIT执行请求，按ICD保留2bit命令码。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_MBIT_EXEC, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].mbitExec_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x3UL);
                            }
                            break;

                        case RIU_LABEL_R_SOFTV_REQ_INFO: /* 软件版本请求信息 */
                            {
                                /* 解析软件版本请求及部署选择位。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_SOFTV_REQ, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].softVersionReq_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x1UL);
                                s_Comm429RIUData_t[l_ID_u16].softVersion_deploy = (Uint32)(l_rdata_un[l_ii_u16].bit.data & 0x1UL);
                            }
                            break;

                        case RIU_LABEL_R_OIL_RESET: /* 油量重置 */
                            {
                                /* 解析油量重置双bit命令。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_OIL_RESET, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].oilResetCmd_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x3UL);
                            }
                            break;

                        case RIU_LABEL_R_LIFE_INFO: /* 发送寿命信息 */
                            {
                                /* 解析寿命信息透传字。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_LIFE_INFO, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].lifeInfo_u32 = l_rdata_un[l_ii_u16].bit.data;
                            }
                            break;

                        case RIU_LABEL_R_IAS: /* 指示空速 */
                            {
                                /* 解析指示空速并换算为工程值。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_IAS, l_rdata_un[l_ii_u16].msgData);

                                l_temp_f = (float)(l_rdata_un[l_ii_u16].bit.data & 0x7FFFUL);
                                s_Comm429RIUData_t[l_ID_u16].airSpeed_f = l_temp_f * AIR_SPEED_RATIO;
                            }
                            break;

                        case RIU_LABEL_R_FUEL_DENSITY: /* 燃油密度 */
                            {
                                /* 解析燃油密度并换算为工程值。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FUEL_DENSITY, l_rdata_un[l_ii_u16].msgData);

                                l_temp_f = (float)(l_rdata_un[l_ii_u16].bit.data & 0x3FFUL);
                                s_Comm429RIUData_t[l_ID_u16].oilMD_f = l_temp_f * OIL_MD_RATIO;
                            }
                            break;

                        case RIU_LABEL_R_LP_BRIGHTNESS: /* 左吊舱通道灯亮度调节 */
                            {
                                /* 解析左吊舱亮度调节字。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_LP_BRIGHTNESS, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].lpBrightness_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x7FFFUL);
                            }
                            break;

                        case RIU_LABEL_R_RP_BRIGHTNESS: /* 右吊舱通道灯亮度调节 */
                            {
                                /* 解析右吊舱亮度调节字。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_RP_BRIGHTNESS, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].rpBrightness_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x7FFFUL);
                            }
                            break;

                        case RIU_LABEL_R_HEART:  /* 健康状态字     */
                            {
                                /* 解析RIU心跳，并用重复值检测接收停滞。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_HEART, l_rdata_un[l_ii_u16].msgData);

                                /* 心跳未更新时 */
                                if((s_Comm429RIUData_t[l_ID_u16].heartB_u16 == (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0xFFUL)))
                                {
                                    /* 429通信数据异常 */
                                    s_Comm429RIUInfo_t[l_ID_u16].rxDataState_u16  = RX429_STATE_ERR;
                                }
                                else
                                {
                                    /* 429通信数据异常标志清零 */
                                    s_Comm429RIUInfo_t[l_ID_u16].rxDataState_u16  = RX429_STATE_OK;
                                }

                                /* 获取设备心跳 */
                                s_Comm429RIUData_t[l_ID_u16].heartB_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0xFFUL);
                            }
                            break;

                        case RIU_LABEL_R_CTRL_CMD:  /* 控制指令 */
                            {
                                /* 解析控制指令总字及加受油对象/模式/飞余油低/累计加油量清零。
                                 * docx 20260127 表10: bit9 加油对象; bit12-14 加受油模式; bit18 飞余油低; bit19 累计加油量清零。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_CTRL_CMD, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].ctrlCmd_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL);

                                /* 获取加受油对象 */
                                s_Comm429RIUData_t[l_ID_u16].fuelCmd_t.bit.fuelObject_u8 = l_rdata_un[l_ii_u16].bit.data & 0x1UL;

                                /* 获取加受油模式 */
                                s_Comm429RIUData_t[l_ID_u16].fuelCmd_t.bit.fuelMode_u8 = (l_rdata_un[l_ii_u16].bit.data >> 3UL) & 0x7UL;

                                /* 获取飞机余油低 (bit18) */
                                s_Comm429RIUData_t[l_ID_u16].fuelLow_u16 = (Uint16)((l_rdata_un[l_ii_u16].bit.data >> 9UL) & 0x1UL);

                                /* 获取累计加油量清零 (bit19) */
                                s_Comm429RIUData_t[l_ID_u16].fuelReset_u16 = (Uint16)((l_rdata_un[l_ii_u16].bit.data >> 10UL) & 0x1UL);
                            }
                            break;

                        case RIU_LABEL_R_RCV:  /* 压力加油控制活门状态 */
                            {
                                /* 解析压力加油控制活门状态字。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_RCV, l_rdata_un[l_ii_u16].msgData);

                                /* 获取压力加油控制活门状态信息 */
                                s_Comm429RIUData_t[l_ID_u16].RCV_t.all = l_rdata_un[l_ii_u16].bit.data & 0xFFFUL;

                            }
                            break;

                        case RIU_LABEL_R_VALVE1: /* 阀状态信号1  */
                            {
                                /* 解析阀状态信号1中的位置量集合。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_VALVE1, l_rdata_un[l_ii_u16].msgData);

                                /* 获取阀状态信号1（0260：4个两位位置量） */
                                s_Comm429RIUData_t[l_ID_u16].valve1_t.all = l_rdata_un[l_ii_u16].bit.data & 0xFFUL;
                            }
                            break;

                        case RIU_LABEL_R_VALVE2:   /* 阀状态信号2  */
                            {
                                /* 解析阀状态信号2中的位置量集合。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_VALVE2, l_rdata_un[l_ii_u16].msgData);

                                /* 获取阀状态信号2（0262：9个两位位置量） */
                                s_Comm429RIUData_t[l_ID_u16].valve2_t.all = l_rdata_un[l_ii_u16].bit.data & 0x3FFFFUL;
                            }
                            break;

                        case RIU_LABEL_R_FUELPUMP:   /* 加油泵状态信号  */
                            {
                                /* 解析加油泵状态字。
                                 * docx 20260127 表15: bit9-10 0号左泵状态(2bit, 00默认/01待机/10运行/11故障);
                                 *                       bit11-12 0号右泵; bit13-14 2号泵; bit15-16 3号泵;
                                 *                       bit17-20 4个低压(0=无效/1=低压)。
                                 * 共 12 bit (bit9-20)。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FUELPUMP, l_rdata_un[l_ii_u16].msgData);

                                /* 获取加油泵状态信号  */
                                s_Comm429RIUData_t[l_ID_u16].fuelPump_t.all = l_rdata_un[l_ii_u16].bit.data & 0xFFFUL;
                            }
                            break;

                        case RIU_LABEL_R_HL_SENSOR:/* 高油面信号器信号   */
                            {
                                /* 解析高油面及超压信号字。
                                 * docx 20260127 表13: bit9-13 0-4号高油面(5bit, 0=正常/1=高油面);
                                 *                       bit14-17 4个超压(压1/压2/左通气/右通气, 0=无效/1=超压);
                                 *                       bit18-19 压1/压2低压(0=无效/1=低压)。
                                 * 共 11 bit (bit9-19)。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_HL_SENSOR, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].HLSensor_t.all = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x7FFUL);
                            }
                            break;
                        case RIU_LABEL_R_FAULTINFO: /* 故障信息 */
                            {
                                /* 解析 RIU 故障信息字。
                                 * docx 20260127 表16: bit9-12 1-4号信号转换盒故障;
                                 *                          bit13-16 rsvd;
                                 *                          bit17-21 0-4号油量传感器故障;
                                 *                          共 13 bit (bit9-21)。
                                 * 注: 头文件旧版有 oilMS_falut/oilMS_downGrade, 实际属 0o232 故障信息2。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FAULTINFO, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429RIUData_t[l_ID_u16].faultInfo_t.all = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x1FFFUL);
                            }
                            break;

                        case RIU_LABEL_R_PRV: /* 预设受油量值 */
                            {
                                /* 解析预设受油量并换算为工程值。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_PRV, l_rdata_un[l_ii_u16].msgData);

                                /* 获取预设受油量值 */
                                l_temp_f=(float)(l_rdata_un[l_ii_u16].bit.data & 0x3FFUL);
                                s_Comm429RIUData_t[l_ID_u16].PRV_f = l_temp_f * OIL_RATIO;
                            }
                            break;

                        case RIU_LABEL_R_LP_PFV: /* 左吊舱预选油量 */
                            {
                                /* 解析左吊舱预选油量，并同步综合PFV。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_LP_PFV, l_rdata_un[l_ii_u16].msgData);

                                /* 获取左吊舱预选油量值 */
                                l_temp_f=(float)(l_rdata_un[l_ii_u16].bit.data & 0x3FFUL);
                                s_Comm429RIUData_t[l_ID_u16].lpPFV_f = l_temp_f * OIL_RATIO;
                                s_Comm429RIUData_t[l_ID_u16].PFV_f = s_Comm429RIUData_t[l_ID_u16].lpPFV_f;
                            }
                            break;

                        case RIU_LABEL_R_RP_PFV: /* 右吊舱预选油量 */
                            {
                                /* 解析右吊舱预选油量工程值。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_RP_PFV, l_rdata_un[l_ii_u16].msgData);

                                /* 获取右吊舱预选油量值 */
                                l_temp_f=(float)(l_rdata_un[l_ii_u16].bit.data & 0x3FFUL);
                                s_Comm429RIUData_t[l_ID_u16].rpPFV_f = l_temp_f * OIL_RATIO;
                            }
                            break;

                        case RIU_LABEL_R_FQ_TANK0: /* 0号油箱油量值  */
                            {
                                /* 解析0号油箱油量并刷新综合总油量。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FQ_TANK0, l_rdata_un[l_ii_u16].msgData);

                                /* 获取0号油箱油量值 */
                            l_temp_f=(float)(l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL);
                                s_Comm429RIUData_t[l_ID_u16].tank0_vol_f = l_temp_f * OIL_TANK_RATIO;
                                Comm429RIUUpdateTotalFuel(l_ID_u16);
                            }
                            break;

                        case RIU_LABEL_R_FQ_TANK1: /* 1号油箱油量值  */
                            {
                                /* 解析1号油箱油量并刷新综合总油量。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FQ_TANK1, l_rdata_un[l_ii_u16].msgData);

                                /* 获取0号油箱油量值 */
                            l_temp_f=(float)(l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL);
                                s_Comm429RIUData_t[l_ID_u16].tank1_vol_f = l_temp_f * OIL_TANK_RATIO;
                                Comm429RIUUpdateTotalFuel(l_ID_u16);
                            }
                            break;

                        case RIU_LABEL_R_FQ_TANK2: /* 2号油箱油量值  */
                            {
                                /* 解析2号油箱油量并刷新综合总油量。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FQ_TANK2, l_rdata_un[l_ii_u16].msgData);

                                /* 获取0号油箱油量值 */
                            l_temp_f=(float)(l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL);
                                s_Comm429RIUData_t[l_ID_u16].tank2_vol_f = l_temp_f * OIL_TANK_RATIO;
                                Comm429RIUUpdateTotalFuel(l_ID_u16);
                            }
                            break;

                        case RIU_LABEL_R_FQ_TANK3: /* 3号油箱油量值  */
                            {
                                /* 解析3号油箱油量并刷新综合总油量。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FQ_TANK3, l_rdata_un[l_ii_u16].msgData);

                                /* 获取0号油箱油量值 */
                            l_temp_f=(float)(l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL);
                                s_Comm429RIUData_t[l_ID_u16].tank3_vol_f = l_temp_f * OIL_TANK_RATIO;
                                Comm429RIUUpdateTotalFuel(l_ID_u16);
                            }
                            break;

                        case RIU_LABEL_R_FQ_TANK4: /* 4号油箱油量值  */
                            {
                                /* 解析4号油箱油量并刷新综合总油量。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_FQ_TANK4, l_rdata_un[l_ii_u16].msgData);

                                /* 获取0号油箱油量值 */
                            l_temp_f=(float)(l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL);
                                s_Comm429RIUData_t[l_ID_u16].tank4_vol_f = l_temp_f * OIL_TANK_RATIO;
                                Comm429RIUUpdateTotalFuel(l_ID_u16);
                            }
                            break;

                        case RIU_LABEL_R_TOTAL_FUEL: /* 全机总油量 */
                            {
                                /* 解析全机总油量工程值。 */
                                Comm429RIURxWordMark(l_ID_u16, RIU_R_DATA_INDEX_TOTAL_FUEL, l_rdata_un[l_ii_u16].msgData);

                                /* 获取全机总油量 */
                                l_temp_f=(float)(l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL);
                                s_Comm429RIUData_t[l_ID_u16].totalFuel_f = l_temp_f * OIL_TANK_RATIO;
                            }
                            break;

                        default:
                            {
                                /* 记录收到异常标号的报文 */
s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 = s_Comm429RIUInfo_t[l_ID_u16].labelErrCount_u16 + 1U;
                            }
                            break;
                    }
                }
            }
        }
        else
        {
            /* FIFO溢出错误计数加1 */
            s_Comm429RIUInfo_t[l_ID_u16].ovflErrCount_u16 =s_Comm429RIUInfo_t[l_ID_u16].ovflErrCount_u16 +  1U;

            /* 接收FIFO有数时，将FIFO剩下数据读空 */
            Ccdl429RFIFOReset(s_RIUCommIDConf_u16[l_ID_u16]);
        }
    }

     /* 接收数据状态检测 */
    RIU429InfoDataStateCheck();

    /* 通信接收状态检测 */
    Comm429RIURxStateCheck();
}


/* ***************************************************************** */
/**
 *    [函数名]：     Comm429RIUPeriodInfoTx
 *    [功能描述]：   周期发送RIU状态、故障和控制反馈类报文
 *    [输入参数说明]：NONE
 *    [输出参数说明]：NONE
 *    [其他说明]：   仅输出授权有效时发送，按固定标签顺序组织
 *    [返回]：       NONE
 */
/* ***************************************************************** */
void Comm429RIUPeriodInfoTx(void)
{
    Uint16 l_ID_u16 = COMM429_RIU_1;
    const ConData_t *lc_p_conData_t = ConDataGet();
    const RIU429SendData_t *lc_p_RIU429SendData_t = RIU429SendDataGet();
    static Uint32 s_lastTxTime_u32 = 0UL;
    static Uint16 s_riuEventReqCntInit_u16 = INVALID;
    static Uint16 s_lastMbitReqCnt_u16 = 0U;
    static Uint16 s_lastSoftvReqCnt_u16 = 0U;
    static Uint16 s_lastOilResetReqCnt_u16 = 0U;
    static Uint16 s_lastLifeReqCnt_u16 = 0U;
    static Uint16 s_lastLeftPreFuelReqCnt_u16 = 0U;
    static Uint16 s_lastRightPreFuelReqCnt_u16 = 0U;
    RIU429OrigData_t l_riuOrigData_t;
    Uint32 l_tData_u32 = 0UL;
    Uint16 l_valid_u16 = VALID;
    Uint16 l_leftValid_u16 = Comm429RIUKzzzSideValidGet(COMM429_KZZZ_1);
    Uint16 l_rightValid_u16 = Comm429RIUKzzzSideValidGet(COMM429_KZZZ_2);
    KZZZ429InfoData_t l_leftData_t = Comm429KzzzRxDataGet(COMM429_KZZZ_1);
    KZZZ429InfoData_t l_rightData_t = Comm429KzzzRxDataGet(COMM429_KZZZ_2);
    Uint32 l_now_u32 = sysTime();
    Uint16 l_mbitReqCnt_u16 = 0U;
    Uint16 l_softvReqCnt_u16 = 0U;
    Uint16 l_oilResetReqCnt_u16 = 0U;
    Uint16 l_lifeReqCnt_u16 = 0U;
    Uint16 l_leftPreFuelReqCnt_u16 = 0U;
    Uint16 l_rightPreFuelReqCnt_u16 = 0U;
    Uint16 l_mbitReqChanged_u16 = INVALID;
    Uint16 l_softvReqChanged_u16 = INVALID;
    Uint16 l_oilResetReqChanged_u16 = INVALID;
    Uint16 l_lifeReqChanged_u16 = INVALID;
    Uint16 l_leftPreFuelReqChanged_u16 = INVALID;
    Uint16 l_rightPreFuelReqChanged_u16 = INVALID;
    union arinc429Data l_softvReqData_un;
    union arinc429Data l_oilResetReqData_un;
    union arinc429Data l_lifeReqData_un;
    Uint16 l_softvReqValid_u16 = INVALID;
    Uint16 l_oilResetLeftReq_u16 = INVALID;
    Uint16 l_oilResetRightReq_u16 = INVALID;
    Uint16 l_lifeLeftReq_u16 = INVALID;
    Uint16 l_lifeRightReq_u16 = INVALID;

    /* 整体流程：
     * 1. 获取当前控制数据与 RIU 发送上下文，读取左右吊舱 KZZZ 接收数据作为转发来源；
     * 2. 周期发送节拍由调用方（任务3 50ms）控制，本函数组装并发送周期信息帧；
     * 3. 依次组装并发送：心跳/控制指令/故障信息/状态信息/告警/提示/软件版本等周期量；
     * 4. 事件量（吊舱请求）通过边沿检测（计数值变化）触发非周期发送；
     * 5. 发送前校验输出授权状态（conOutState），未授权时跳过对外发送。
     */
    if ((NULL == lc_p_conData_t) ||
        (CON_OUT_STATE_VALID != lc_p_conData_t->ConOutData_t.conOutState_u16))
    {
        s_riuEventReqCntInit_u16 = INVALID;
        return;
    }

    if ((0UL != s_lastTxTime_u32) && ((l_now_u32 - s_lastTxTime_u32) < RIU_TX_PERIOD_MS))
    {
        return;
    }
    s_lastTxTime_u32 = l_now_u32;

    l_riuOrigData_t = Comm429RIUOrigDataGet(l_ID_u16);
    l_mbitReqCnt_u16 = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_MBIT_EXEC].Cnt_u16;
    l_softvReqCnt_u16 = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_SOFTV_REQ].Cnt_u16;
    l_oilResetReqCnt_u16 = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_OIL_RESET].Cnt_u16;
    l_lifeReqCnt_u16 = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_LIFE_INFO].Cnt_u16;
    l_leftPreFuelReqCnt_u16 = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_LP_PFV].Cnt_u16;
    l_rightPreFuelReqCnt_u16 = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_RP_PFV].Cnt_u16;

    l_softvReqData_un.msgData = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_SOFTV_REQ].OrigData_u32;
    l_oilResetReqData_un.msgData = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_OIL_RESET].OrigData_u32;
    l_lifeReqData_un.msgData = l_riuOrigData_t.Orig_Rx_t[RIU_R_DATA_INDEX_LIFE_INFO].OrigData_u32;
    l_softvReqValid_u16 = (Uint16)(l_softvReqData_un.bit.data & 0x1UL);
    l_oilResetLeftReq_u16 = (Uint16)(l_oilResetReqData_un.bit.data & 0x1UL);
    l_oilResetRightReq_u16 = (Uint16)((l_oilResetReqData_un.bit.data >> 1U) & 0x1UL);
    l_lifeLeftReq_u16 = (Uint16)(l_lifeReqData_un.bit.data & 0x1UL);
    l_lifeRightReq_u16 = (Uint16)((l_lifeReqData_un.bit.data >> 1U) & 0x1UL);

    if(VALID != s_riuEventReqCntInit_u16)
    {
        s_lastMbitReqCnt_u16 = l_mbitReqCnt_u16;
        s_lastSoftvReqCnt_u16 = l_softvReqCnt_u16;
        s_lastOilResetReqCnt_u16 = l_oilResetReqCnt_u16;
        s_lastLifeReqCnt_u16 = l_lifeReqCnt_u16;
        s_lastLeftPreFuelReqCnt_u16 = l_leftPreFuelReqCnt_u16;
        s_lastRightPreFuelReqCnt_u16 = l_rightPreFuelReqCnt_u16;
        s_riuEventReqCntInit_u16 = VALID;
    }
    else
    {
        l_mbitReqChanged_u16 = (s_lastMbitReqCnt_u16 != l_mbitReqCnt_u16) ? VALID : INVALID;
        l_softvReqChanged_u16 = (s_lastSoftvReqCnt_u16 != l_softvReqCnt_u16) ? VALID : INVALID;
        l_oilResetReqChanged_u16 = (s_lastOilResetReqCnt_u16 != l_oilResetReqCnt_u16) ? VALID : INVALID;
        l_lifeReqChanged_u16 = (s_lastLifeReqCnt_u16 != l_lifeReqCnt_u16) ? VALID : INVALID;
        l_leftPreFuelReqChanged_u16 = (s_lastLeftPreFuelReqCnt_u16 != l_leftPreFuelReqCnt_u16) ? VALID : INVALID;
        l_rightPreFuelReqChanged_u16 = (s_lastRightPreFuelReqCnt_u16 != l_rightPreFuelReqCnt_u16) ? VALID : INVALID;
    }

    {
        /* 1. 总线心跳 (Label 0200) */
        Comm429RIUSendHeart(l_ID_u16);

        /* 2. 上电BIT结果 (Label 0201)：仅上报BIT9综合故障有效位。 */
        l_tData_u32 = (PUBIT_TEST_OK != (PuBITDataGet() & PUBIT_KEY_FAULT_CODE)) ? 0x1UL : 0UL;
        Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_PUBIT_ALARM_1, l_tData_u32, Comm429RIUSsmGet(VALID));

        /* 3. 维护BIT反馈/结果 (Label 0202/0203)：由0205执行维护BIT请求触发。 */
        l_tData_u32 = 0UL;
        l_valid_u16 = INVALID;
        if ((VALID == l_leftValid_u16) || (VALID == l_rightValid_u16))
        {
            l_valid_u16 = VALID;
            if (VALID == l_leftValid_u16)
            {
                l_tData_u32 |= ((Uint32)(Comm429RIUMaintFbMap(l_leftData_t.MBITFB_u16) & 0x3U)) << 0U;
            }
            if (VALID == l_rightValid_u16)
            {
                l_tData_u32 |= ((Uint32)(Comm429RIUMaintFbMap(l_rightData_t.MBITFB_u16) & 0x3U)) << 2U;
            }
        }
        if(VALID == l_mbitReqChanged_u16)
        {
            Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_MBIT_EXEC_FB, l_tData_u32, Comm429RIUSsmGet(l_valid_u16));
        }

        l_tData_u32 = 0UL;
        l_valid_u16 = INVALID;
        if ((VALID == l_leftValid_u16) || (VALID == l_rightValid_u16))
        {
            l_valid_u16 = VALID;
            if (VALID == l_leftValid_u16)
            {
                l_tData_u32 |= ((Uint32)(l_leftData_t.MBITFInfo_1_t.bit.mBitResult_u32 & 0x3U)) << 0U;
            }
            if (VALID == l_rightValid_u16)
            {
                l_tData_u32 |= ((Uint32)(l_rightData_t.MBITFInfo_1_t.bit.mBitResult_u32 & 0x3U)) << 2U;
            }
        }
        if(VALID == l_mbitReqChanged_u16)
        {
            Comm429RIURawSend(l_ID_u16, RIU_LABEL_T_UPLOAD_MBIT_RESULT, l_tData_u32, Comm429RIUSsmGet(l_valid_u16));
            s_lastMbitReqCnt_u16 = l_mbitReqCnt_u16;
        }

        /* 4. 控制指令反馈 (Label 0220/0221/0222) */
        /* 0220 发送ValveCtrl_t原始控制语义；0221/0222分别封装活门关闭命令与泵启动命令。 */
        Comm429RIURawSend(l_ID_u16,
                          RIU_LABEL_T_CTRL_CMD_1,
                          Comm429RIUCtrlCmd1Pack(lc_p_RIU429SendData_t),
                          Comm429RIUSsmGet(VALID));
        Comm429RIURawSend(l_ID_u16,
                          RIU_LABEL_T_CTRL_CMD_2,
                          Comm429RIUCtrlCmd2Pack(lc_p_RIU429SendData_t),
                          Comm429RIUSsmGet(VALID));
        Comm429RIURawSend(l_ID_u16,
                          RIU_LABEL_T_CTRL_CMD_3,
                          Comm429RIUCtrlCmd3Pack(lc_p_conData_t, lc_p_RIU429SendData_t),
                          Comm429RIUSsmGet(VALID));

        /* 5. 状态与故障信息 (Label 0230/0231/0232) */
        Comm429RIURawSend(l_ID_u16,
                          RIU_LABEL_T_STATUS_INFO,
                          Comm429RIUStatusInfoPack(lc_p_conData_t),
                          Comm429RIUSsmGet(VALID));
        Comm429RIURawSend(l_ID_u16,
                          RIU_LABEL_T_FAULT_INFO_1,
                          Comm429RIUFaultInfo1Pack(lc_p_RIU429SendData_t),
                          Comm429RIUSsmGet(VALID));
        Comm429RIURawSend(l_ID_u16,
                          RIU_LABEL_T_FAULT_INFO_2,
                          Comm429RIUFaultInfo2Pack(lc_p_conData_t, lc_p_RIU429SendData_t),
                          Comm429RIUSsmGet(VALID));

        /* 6. 健康告警与提示 (Label 0233/0234) */
        Comm429RIURawSend(l_ID_u16,
                          RIU_LABEL_T_WARN_INFO,
                          Comm429RIUWarnInfoPack(lc_p_RIU429SendData_t),
                          Comm429RIUSsmGet(VALID));

        Comm429RIURawSend(l_ID_u16,
                          RIU_LABEL_T_TIP_INFO,
                          Comm429RIUTipInfoPack(lc_p_conData_t),
                          Comm429RIUSsmGet(VALID));

        /* 7. 事件类信息：按RIU请求接收计数触发发送。 */
        if(VALID == l_softvReqChanged_u16)
        {
            if(0U != l_softvReqValid_u16)
            {
                Comm429RIULocalVersionInfoTx(l_ID_u16, lc_p_conData_t);
                Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_1, RIU_POD_EVENT_GROUP_SOFTV, l_leftValid_u16, l_leftData_t);
                Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_2, RIU_POD_EVENT_GROUP_SOFTV, l_rightValid_u16, l_rightData_t);
            }
            s_lastSoftvReqCnt_u16 = l_softvReqCnt_u16;
        }

        if(VALID == l_leftPreFuelReqChanged_u16)
        {
            Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_1, RIU_POD_EVENT_GROUP_PRE_FUEL, l_leftValid_u16, l_leftData_t);
            s_lastLeftPreFuelReqCnt_u16 = l_leftPreFuelReqCnt_u16;
        }

        if(VALID == l_rightPreFuelReqChanged_u16)
        {
            Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_2, RIU_POD_EVENT_GROUP_PRE_FUEL, l_rightValid_u16, l_rightData_t);
            s_lastRightPreFuelReqCnt_u16 = l_rightPreFuelReqCnt_u16;
        }

        if(VALID == l_lifeReqChanged_u16)
        {
            if(0U != l_lifeLeftReq_u16)
            {
                Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_1, RIU_POD_EVENT_GROUP_LIFE, l_leftValid_u16, l_leftData_t);
            }
            if(0U != l_lifeRightReq_u16)
            {
                Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_2, RIU_POD_EVENT_GROUP_LIFE, l_rightValid_u16, l_rightData_t);
            }
            s_lastLifeReqCnt_u16 = l_lifeReqCnt_u16;
        }

        if(VALID == l_oilResetReqChanged_u16)
        {
            if(0U != l_oilResetLeftReq_u16)
            {
                Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_1, RIU_POD_EVENT_GROUP_OIL_RESET, l_leftValid_u16, l_leftData_t);
            }
            if(0U != l_oilResetRightReq_u16)
            {
                Comm429RIUPodEventInfoTx(l_ID_u16, COMM429_KZZZ_2, RIU_POD_EVENT_GROUP_OIL_RESET, l_rightValid_u16, l_rightData_t);
            }
            s_lastOilResetReqCnt_u16 = l_oilResetReqCnt_u16;
        }

        /* 8. 左右吊舱周期运行数据 (Label 0260~0277 / 0360~0377) */
        Comm429RIUPodPeriodicInfoTx(l_ID_u16, COMM429_KZZZ_1, l_leftValid_u16, l_leftData_t);
        Comm429RIUPodPeriodicInfoTx(l_ID_u16, COMM429_KZZZ_2, l_rightValid_u16, l_rightData_t);
    }
}
/* ========================================================================== */
/* 文件结束 */
/* ========================================================================== */
