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
 * 文件名称:    Comm429KZZZ.c
 *
 * 文件日期:    REDACTED
 *
 *
 * 程序版本:   V1.00
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 *
 *********************************************************************************/

#include "Global.h"
#include "Comm429KZZZ.h"

/* ***************************************************************** */
/* 控制装置通信ID配置表 */
Uint16  s_KZZZCommIDConf_u16[COMM429_KZZZ_NUM] =
            { COMMDRI_429_ID_10,
            COMMDRI_429_ID_11

            };

A429Info_t s_Comm429KZZZInfo_t[COMM429_KZZZ_NUM];    /* KZZZ429接收信息数组   */

KZZZ429InfoData_t s_Comm429KZZZData_t[COMM429_KZZZ_NUM]; /* 来自KZZZ429的通信数据 */

KZZZ429OrigData_t s_KZZZ429OrigData_t[COMM429_KZZZ_NUM]; /* 来自KZZZ429的通信数据 */
static Uint32 s_lastTxWordKZZZ_u32[COMM429_KZZZ_NUM] = {0UL, 0UL}; /* 最近一次发送的429原始字 */

static void Comm429KZZZRxWordMark(Uint16 v_ID_u16, Uint16 v_index_u16, Uint32 v_msgData_u32)
{
    if ((v_ID_u16 < COMM429_KZZZ_NUM) && (v_index_u16 < KZZZ_R_DATA_NUM))
    {
        s_KZZZ429OrigData_t[v_ID_u16].Orig_Rx_t[v_index_u16].OrigData_u32 = v_msgData_u32;
        s_KZZZ429OrigData_t[v_ID_u16].Orig_Rx_t[v_index_u16].Cnt_u16++;
        s_Comm429KZZZInfo_t[v_ID_u16].rxCount_u32++;
        s_Comm429KZZZInfo_t[v_ID_u16].rxTime_u32 = sysTime();
    }
}

/* 接收数据标号配置表 (依据任务书精简) */
Uint16  s_KZZZ429Rx_labelConf_u16[KZZZ_R_DATA_NUM] =
            {
                    KZZZ_LABEL_R_CURRENT_TIME,
                    KZZZ_LABEL_R_MAINTENANCE_BIT_FB,
                    KZZZ_LABEL_R_UPLOAD_MAINTENANCE_BIT,
                    KZZZ_LABEL_R_CTRL_SW_VERSION,
                    KZZZ_LABEL_R_MOTOR_CTRL_SW_VERSION,
                    KZZZ_LABEL_R_FUEL_LEVEL_SIGNAL_BOX,
                    KZZZ_LABEL_R_BRAKE_CTRL_SW_VERSION,
                    KZZZ_LABEL_R_BIT_APP_SW_VERSION,
                    KZZZ_LABEL_R_LOGIC_SW_VERSION,
                    KZZZ_LABEL_R_UPGRADE_APP_SW_VERSION,
                    KZZZ_LABEL_R_MOTOR_LOGIC_SW_VERSION,
                    KZZZ_LABEL_R_SEL_FUEL_RECEIVE_FB,
                    KZZZ_LABEL_R_REMAINING_FLIGHT_HRS,
                    KZZZ_LABEL_R_REMAINING_CALENDAR_LIFE,
                    KZZZ_LABEL_R_FUEL_RESET_RECEIVE_FB,
                    KZZZ_LABEL_R_TURBINE_SPEED,
                    KZZZ_LABEL_R_FUEL_PRESSURE,
                    KZZZ_LABEL_R_TURBINE_PUMP_PRESSURE,
                    KZZZ_LABEL_R_FUEL_FLOW,
                    KZZZ_LABEL_R_FUEL_LEVEL,
                    KZZZ_LABEL_R_TOTAL_FUEL,
                    KZZZ_LABEL_R_FUEL_TEMP,
                    KZZZ_LABEL_R_RG_LEN,
                    KZZZ_LABEL_R_COMPONENT_STATUS,
                    KZZZ_LABEL_R_FAULT_WARN,
                    KZZZ_LABEL_R_FAULT_WARN_I,
                    KZZZ_LABEL_R_FAULT_WARN_II,
                    KZZZ_LABEL_R_REFUEL_DEV_STATE,
                    KZZZ_LABEL_R_CMD_SIGNAL_FB,
                    KZZZ_LABEL_R_MOTOR_SPEED,
                    KZZZ_LABEL_R_MOTOR_TEMP
            };

/* KZZZ429发送标号配置表 */
Uint16 s_KZZZ429TxLabel_u16[KZZZ_T_DATA_NUM] =
            {
                KZZZ_LABEL_T_CURR_DATE,
                KZZZ_LABEL_T_CURR_TIME,
                KZZZ_LABEL_T_MBIT_RUN,
                KZZZ_LABEL_T_PZXX,
                KZZZ_LABEL_T_PRE_FUEL,
                KZZZ_LABEL_T_FUEL_DENSITY,
                KZZZ_LABEL_T_CTRL_CMD,
                KZZZ_LABEL_T_LIFE_INFO,
                KZZZ_LABEL_T_FUEL_RESET
            };
Uint32 s_KZZZ429TxCnt_u32[KZZZ_T_DATA_NUM];
Uint32 s_KZZZ429TimeoutCnt_u32[COMM429_KZZZ_NUM];

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429KZZZLabelSsmGet
 *    【功能描述】:   获取KZZZ发送标号对应的ICD SSM编码
 *    【输入参数说明】:v_label_u16 ---- 发送标号
 *    【输出参数说明】:NONE
 *    【其他说明】:   BNR周期量按11发送，其余当前接口量按00发送
 *    【返回】:       SSM编码
 */
/* ***************************************************************** */
static Uint16 Comm429KZZZLabelSsmGet(Uint16 v_label_u16)
{
    Uint16 l_ssm_u16 = 0U;

    switch(v_label_u16)
    {
        case KZZZ_LABEL_T_PRE_FUEL:
        case KZZZ_LABEL_T_FUEL_DENSITY:
            l_ssm_u16 = SSM_NORM;
            break;

        default:
            l_ssm_u16 = 0U;
            break;
    }

    return l_ssm_u16;
}

/* ***************************************************************** */
/**
 *    【函数名】:    Comm429KZZZRxSsmValidGet
 *    【功能描述】:  KZZZ接收字SSM有效性判定
 *    【输入参数说明】v_data_un ---- 接收的429字联合
 *    【输出参数说明】NONE
 *    【其他说明】   业务型标签SSM必须为NORM，否则返回INVALID
 *    【返回】       VALID/INVALID
 */
/* ***************************************************************** */
static Uint16 Comm429KZZZRxSsmValidGet(union arinc429Data v_data_un)
{
    Uint16 l_valid_u16 = VALID;

    switch(v_data_un.bit.label)
    {
        case KZZZ_LABEL_R_REMAINING_FLIGHT_HRS:
        case KZZZ_LABEL_R_TURBINE_SPEED:
        case KZZZ_LABEL_R_FUEL_PRESSURE:
        case KZZZ_LABEL_R_TURBINE_PUMP_PRESSURE:
        case KZZZ_LABEL_R_FUEL_FLOW:
        case KZZZ_LABEL_R_FUEL_LEVEL:
        case KZZZ_LABEL_R_TOTAL_FUEL:
        case KZZZ_LABEL_R_FUEL_TEMP:
        case KZZZ_LABEL_R_RG_LEN:
        case KZZZ_LABEL_R_MOTOR_SPEED:
        case KZZZ_LABEL_R_MOTOR_TEMP:
            if(SSM_NORM != v_data_un.bit.ssm)
            {
                l_valid_u16 = INVALID;
            }
            break;

        default:
            break;
    }

    return l_valid_u16;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429KZZZSendFrame
 *    【功能描述】:   构造单路KZZZ 429发送字并完成校验/下发
 *    【输入参数说明】:v_ID_u16      ---- 吊舱通道号
 *                    v_label_u16   ---- 发送标号
 *                    v_data_u32    ---- 21bit数据域
 *                    v_ssm_u16     ---- SSM编码
 *    【输出参数说明】:NONE
 *    【其他说明】:   统一发送内核，所有KZZZ发送最终都走该入口
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void Comm429KZZZSendFrame(Uint16 v_ID_u16, Uint16 v_label_u16, Uint32 v_data_u32, Uint16 v_ssm_u16)
{
    union arinc429Data l_txData_un;
    Uint16 l_idx_u16 = 0U;

    if(v_ID_u16 < COMM429_KZZZ_NUM)
    {
        /* 发送字格式按 label + data + ssm + parity。 */
        l_txData_un.bit.label = v_label_u16;
        l_txData_un.bit.data  = v_data_u32;
        l_txData_un.bit.ssm   = v_ssm_u16;

        Ccdl429DataSend(s_KZZZCommIDConf_u16[v_ID_u16], l_txData_un);
        s_lastTxWordKZZZ_u32[v_ID_u16] = l_txData_un.msgData;

        for(l_idx_u16 = 0U; l_idx_u16 < KZZZ_T_DATA_NUM; l_idx_u16++)
        {
            if(s_KZZZ429TxLabel_u16[l_idx_u16] == v_label_u16)
            {
                s_KZZZ429TxCnt_u32[l_idx_u16]++;
                break;
            }
        }
    }
}
/* ***************************************************************** */
/**
 *    【函数名】:     Comm429KZZZTxLastWordGet
 *    【功能描述】:   获取指定吊舱通道最近一次发送的429原始字（含parity）
 *    【输入参数说明】:v_ID_u16  ---- 吊舱通道号 (0=左, 1=右)
 *    【输出参数说明】:NONE
 *    【其他说明】:   供周期BIT发送回绕检测比对使用
 *    【返回】:       最近一次发送的32位429原始字，通道非法返回0
 */
/* ***************************************************************** */
Uint32 Comm429KZZZTxLastWordGet(Uint16 v_ID_u16)
{
    if(v_ID_u16 < COMM429_KZZZ_NUM)
    {
        return s_lastTxWordKZZZ_u32[v_ID_u16];
    }
    return 0UL;
}


/* ***************************************************************** */
/**
 *    【函数名】:     Comm429KZZZSendSingle
 *    【功能描述】:   将一帧KZZZ报文发送到指定吊舱通道
 *    【输入参数说明】:v_ID_u16      ---- 吊舱通道号
 *                    v_label_u16   ---- 发送标号
 *                    v_data_u32    ---- 21bit数据域
 *    【输出参数说明】:NONE
 *    【其他说明】:   SSM按标号映射到ICD固定编码
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void Comm429KZZZSendSingle(Uint16 v_ID_u16, Uint16 v_label_u16, Uint32 v_data_u32)
{
    Comm429KZZZSendFrame(v_ID_u16, v_label_u16, v_data_u32, Comm429KZZZLabelSsmGet(v_label_u16));
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429KZZZSendDual
 *    【功能描述】:   将同一帧KZZZ报文广播发送到左右吊舱两个通道
 *    【输入参数说明】:v_label_u16   ---- 发送标号
 *                    v_data_u32    ---- 21bit数据域
 *    【输出参数说明】:NONE
 *    【其他说明】:   目前用于空速等需要左右一致广播的报文
 *    【返回】:       NONE
 */
/* ***************************************************************** */
void Comm429KZZZSendDual(Uint16 v_label_u16, Uint32 v_data_u32)
{
    Uint16 l_ssm_u16 = Comm429KZZZLabelSsmGet(v_label_u16);

    Comm429KZZZSendFrame(COMM429_KZZZ_1, v_label_u16, v_data_u32, l_ssm_u16);
    Comm429KZZZSendFrame(COMM429_KZZZ_2, v_label_u16, v_data_u32, l_ssm_u16);
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429KZZZDecodeOrigSnapshot
 *    【功能描述】:   将一份KZZZ原始字快照解码成业务结构体
 *    【输入参数说明】:vp_orig_t   ---- 原始字快照
 *                    vp_data_t   ---- 解析结果
 *    【输出参数说明】:NONE
 *    【其他说明】:   用于CCDL镜像接管，不修改本地实时接收状态
 *    【返回】:       NONE
 */
/* ***************************************************************** */
static void Comm429KZZZDecodeOrigSnapshot(const KZZZ429OrigData_t *vp_orig_t, KZZZ429InfoData_t *vp_data_t)
{
    union arinc429Data l_rdata_un;

    if((NULL == vp_orig_t) || (NULL == vp_data_t))
    {
        return;
    }

    memset(vp_data_t, 0, sizeof(*vp_data_t));
    memset(&l_rdata_un, 0, sizeof(l_rdata_un));

    /* 逐标签按本地接收同构规则回放，确保CCDL镜像与本地解析口径一致。 */
    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_CURRENT_TIME].OrigData_u32;
    vp_data_t->currTimeAsk_u16 = (Uint16)(l_rdata_un.bit.data & 0x01UL);

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_MAINTENANCE_BIT_FB].OrigData_u32;
    vp_data_t->MBITFB_u16 = (Uint16)(l_rdata_un.bit.data & 0x07UL);
    vp_data_t->MBITStateLast_u16 = vp_data_t->MBITFB_u16;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_UPLOAD_MAINTENANCE_BIT].OrigData_u32;
    vp_data_t->MBITFInfo_1_t.all = l_rdata_un.bit.data;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_CTRL_SW_VERSION].OrigData_u32;
    vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_APP].all = l_rdata_un.bit.data;
    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_MOTOR_CTRL_SW_VERSION].OrigData_u32;
    vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_MOTOR_CTRL].all = l_rdata_un.bit.data;
    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_FUEL_LEVEL_SIGNAL_BOX].OrigData_u32;
    vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_SIGNAL_BOX].all = l_rdata_un.bit.data;
    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_BRAKE_CTRL_SW_VERSION].OrigData_u32;
    vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_BRAKE_CTRL].all = l_rdata_un.bit.data;
    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_BIT_APP_SW_VERSION].OrigData_u32;
    vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_BIT_APP].all = l_rdata_un.bit.data;
    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_LOGIC_SW_VERSION].OrigData_u32;
    vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_LOGIC].all = l_rdata_un.bit.data;
    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_UPGRADE_APP_SW_VERSION].OrigData_u32;
    vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_UPGRADE_APP].all = l_rdata_un.bit.data;
    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_MOTOR_LOGIC_SW_VERSION].OrigData_u32;
    vp_data_t->SoftV_t[KZZZ_SOFTV_INDEX_MOTOR_LOGIC].all = l_rdata_un.bit.data;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_SEL_FUEL_RECEIVE_FB].OrigData_u32;
    vp_data_t->Pre_FuelQtyRcv_FB_u16 = (Uint16)(l_rdata_un.bit.data & 0x01UL);

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_REMAINING_FLIGHT_HRS].OrigData_u32;
    vp_data_t->flightHours_u16 = (Uint16)((l_rdata_un.bit.data >> 5U) & 0x3FFFUL);

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_REMAINING_CALENDAR_LIFE].OrigData_u32;
    vp_data_t->remainLife_t.all = l_rdata_un.bit.data;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_FUEL_RESET_RECEIVE_FB].OrigData_u32;
    vp_data_t->oilReset_u16 = (Uint16)((l_rdata_un.bit.data >> 0U) & 0x03UL);

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_TURBINE_SPEED].OrigData_u32;
    vp_data_t->turbineSpeed_u16 = (Uint16)((l_rdata_un.bit.data >> 5U) & 0x3FFFUL);

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_FUEL_PRESSURE].OrigData_u32;
    vp_data_t->fuelPressure_u16 = (Uint16)((l_rdata_un.bit.data >> 7U) & 0x3FFFUL);

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_TURBINE_PUMP_PRESSURE].OrigData_u32;
    vp_data_t->turbinePumpPressure_u16 = (Uint16)((l_rdata_un.bit.data >> 7U) & 0x3FFFUL);

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_FUEL_FLOW].OrigData_u32;
    vp_data_t->fuelFlow_u16 = (Uint16)((l_rdata_un.bit.data >> 7U) & 0x03FFUL);

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_FUEL_LEVEL].OrigData_u32;
    vp_data_t->fuelLevel_u16 = (Uint16)((l_rdata_un.bit.data >> 8U) & 0x01FFUL);

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_TOTAL_FUEL].OrigData_u32;
    vp_data_t->totalFuel_u16 = (Uint16)((l_rdata_un.bit.data >> 8U) & 0x01FFUL);

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_FUEL_TEMP].OrigData_u32;
    vp_data_t->fuelTemperature_i16 = (Int16)((l_rdata_un.bit.data >> 11U) & 0x7FUL);
    if(0U != ((l_rdata_un.bit.data >> 18U) & 0x01UL))
    {
        vp_data_t->fuelTemperature_i16 = (Int16)(-vp_data_t->fuelTemperature_i16);
    }

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_RG_LEN].OrigData_u32;
    vp_data_t->rgLength_f = (float)((l_rdata_un.bit.data >> 9U) & 0x01FFUL) / KZZZ_RG_LENGTH_R_RATIO;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_COMPONENT_STATUS].OrigData_u32;
    vp_data_t->componentState_t.all = l_rdata_un.bit.data & 0xFFFFUL;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_FAULT_WARN].OrigData_u32;
    vp_data_t->faultInfo_t.all = l_rdata_un.bit.data & 0xFFFFUL;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_FAULT_WARN_I].OrigData_u32;
    vp_data_t->faultInfo_1_t.all = l_rdata_un.bit.data & 0xFFFFUL;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_FAULT_WARN_II].OrigData_u32;
    vp_data_t->faultInfo_2_t.all = l_rdata_un.bit.data & 0xFFFFUL;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_REFUEL_DEV_STATE].OrigData_u32;
    vp_data_t->jyzzState_t.all = l_rdata_un.msgData;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_CMD_SIGNAL_FB].OrigData_u32;
    vp_data_t->cmdSignalFb_t.all = l_rdata_un.msgData;

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_MOTOR_SPEED].OrigData_u32;
    vp_data_t->motorSpeed_i16 = (Int16)((l_rdata_un.bit.data >> 5U) & 0x3FFFUL);
    if(0U != ((l_rdata_un.bit.data >> 19U) & 0x01UL))
    {
        vp_data_t->motorSpeed_i16 = (Int16)(-vp_data_t->motorSpeed_i16);
    }

    l_rdata_un.msgData = vp_orig_t->Orig_Rx_t[KZZZ_R_DATA_MOTOR_TEMP].OrigData_u32;
    vp_data_t->motorTemp_i16 = (Int16)((l_rdata_un.bit.data >> 11U) & 0xFFUL);
    if(0U != ((l_rdata_un.bit.data >> 19U) & 0x01UL))
    {
        vp_data_t->motorTemp_i16 = (Int16)(-vp_data_t->motorTemp_i16);
    }
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429KZZZCcdlExtValidGet
 *    【功能描述】:   判断指定CCDL链路上的KZZZ扩展页是否完整且新鲜
 *    【输入参数说明】:v_ccdlID_u16  ---- CCDL链路ID
 *    【输出参数说明】:NONE
 *    【其他说明】:   判据为三页完整、帧计数非零且200ms内更新
 *    【返回】:       VALID / INVALID
 */
/* ***************************************************************** */
Uint16 Comm429KZZZCcdlExtValidGet(Uint16 v_ccdlID_u16, Uint16 v_kzzzID_u16)
{
    CCDLExtStatus_t l_info_t;
    Uint32 l_currTime_u32 = sysTime();

    memset(&l_info_t, 0, sizeof(l_info_t));
    if((v_ccdlID_u16 >= COMM_CCDL_NUM) || (v_kzzzID_u16 >= COMM429_KZZZ_NUM))
    {
        return INVALID;
    }

    l_info_t = CommCCDLKZZZExtStatusGet(v_ccdlID_u16, v_kzzzID_u16);
    if(COMM_CCDL_RX_OK != l_info_t.dataState_u16)
    {
        return INVALID;
    }
    if(COMM_CCDL_EXT_PAGE_NUM != l_info_t.pageTotal_u16)
    {
        return INVALID;
    }
    if((COMM_CCDL_PAGE0_MASK | COMM_CCDL_PAGE1_MASK | COMM_CCDL_PAGE2_MASK) != l_info_t.pageValidMask_u16)
    {
        return INVALID;
    }
    if(0U == l_info_t.frameCnt_u16)
    {
        return INVALID;
    }
    if((l_currTime_u32 - l_info_t.lastRxTime_u32) > ROLE_PEER_LOSS_TIMEOUT_MS)
    {
        return INVALID;
    }

    return VALID;
}

/* ***************************************************************** */
/**
 *    【函数名】:     Comm429KZZZCcdlExtDataGet
 *    【功能描述】:   获取并解码指定CCDL链路上的KZZZ扩展页数据
 *    【输入参数说明】:v_ccdlID_u16  ---- CCDL链路ID
 *    【输出参数说明】:NONE
 *    【其他说明】:   镜像无效时返回零值结构体
 *    【返回】:       KZZZ429InfoData_t
 */
/* ***************************************************************** */
KZZZ429InfoData_t Comm429KZZZCcdlExtDataGet(Uint16 v_ccdlID_u16, Uint16 v_kzzzID_u16)
{
    KZZZ429InfoData_t l_rslt_t;
    KZZZ429OrigData_t l_orig_t;

    memset(&l_rslt_t, 0, sizeof(l_rslt_t));
    memset(&l_orig_t, 0, sizeof(l_orig_t));

    if(VALID == Comm429KZZZCcdlExtValidGet(v_ccdlID_u16, v_kzzzID_u16))
    {
        l_orig_t = CommCCDLKZZZOrigDataGet(v_ccdlID_u16, v_kzzzID_u16);
        Comm429KZZZDecodeOrigSnapshot(&l_orig_t, &l_rslt_t);
    }

    return l_rslt_t;
}


/* ***************************************************************** */
/**
 *    【函数名】:	  Comm429KzzzRxDataGet
 *    【功能描述】:	  控制装置429通信数据获取
 *    【输入参数说明】:v_ID_u16  ---- 通道号ID
 *
 *	【输出参数说明】:NONE
 *    【其他说明】:	  NONE
 *    【返回】:	  控制装置通信数据
 */
/* ***************************************************************** */
KZZZ429InfoData_t Comm429KzzzRxDataGet(Uint16 v_ID_u16)
{
    KZZZ429InfoData_t l_rslt_t; /* 结果数据 */
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    /* 通道号有效时返回对应通道数据；无效通道返回零值结构体。 */
    if(v_ID_u16 < COMM429_KZZZ_NUM)
    {
        l_rslt_t = s_Comm429KZZZData_t[v_ID_u16]; /* 获取控制装置通信数据 */
    }

    /* 返回控制装置通信数据 */
    return l_rslt_t;
}

/* ***************************************************************** */
/**
 *    【函数名】:	  Comm429KzzzRxOrigDataGet
 *    【功能描述】:	  控制装置429通信原始数据获取
 *    【输入参数说明】:v_ID_u16  ---- 通道号ID
 *
 *	【输出参数说明】:NONE
 *    【其他说明】:	  NONE
 *    【返回】:	  控制装置通信数据
 */
/* ***************************************************************** */
KZZZ429OrigData_t Comm429KzzzRxOrigDataGet(Uint16 v_ID_u16)
{
    KZZZ429OrigData_t l_rslt_t; /* 结果数据 */
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    /* 通道号有效时返回对应通道原始数据；无效通道返回零值结构体。 */
    if(v_ID_u16 < COMM429_KZZZ_NUM)
    {
        l_rslt_t = s_KZZZ429OrigData_t[v_ID_u16]; /* 获取控制装置通信数据 */
    }

    /* 返回控制装置通信数据 */
    return l_rslt_t;
}

/**
 *    【函数名】:	  Comm429KZZZRxStateGet
 *    【功能描述】:	  控制装置429通信接收状态获取
 *    【输入参数说明】:v_ID_u16  ---- 通道号ID
 *
 *	【输出参数说明】:NONE
 *    【其他说明】:	  NONE
 *    【返回】:	  通信接收状态
 */
/* ***************************************************************** */
A429Info_t Comm429KZZZRxStateGet(Uint16 v_ID_u16)
{
    A429Info_t l_rslt_t; /* 结果数据 */
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    /* 通道号小于通道数  */
    if(v_ID_u16 < COMM429_KZZZ_NUM)
    {
        l_rslt_t = s_Comm429KZZZInfo_t[v_ID_u16]; /* 获取控制装置通信数据 */
    }
    else
    {
        l_rslt_t.rxTime_u32 = 0xFFFFFFFFU; /* 输入ID异常时返回接收时间异常值 */
    }

    /* 返回控制装置通信接收状态 */
    return l_rslt_t;
}


/* ***************************************************************** */
/**
 *    【函数名】:	  Comm429KZZZInit
 *    【功能描述】:	 控制装置429通信模块相关数据初始化
 *    【输入参数说明】:NONE
 *
 *	【输出参数说明】:NONE
 *    【其他说明】:	  NONE
 *    【返回】:	NONE
 */
/* ***************************************************************** */
void Comm429KZZZInit(void)
{
    Uint16 l_ID_u16    = 0U;  /*通道号 */
    Uint16 l_index_u16 = 0U;  /* 索引 */

    /* 对KZZZ429通信模块数据进行初始化 */
    for( l_ID_u16 = 0U; l_ID_u16 < COMM429_KZZZ_NUM; l_ID_u16++)
    {
        /* 接收信息初始化 */
        s_Comm429KZZZInfo_t[l_ID_u16].rxTime_u32   = sysTime();
        s_Comm429KZZZInfo_t[l_ID_u16].rxCount_u32  = 0UL;
        s_Comm429KZZZInfo_t[l_ID_u16].rxState_u16  = RX429_STATE_OK;

        /* 错误帧计数清零 */
        s_Comm429KZZZInfo_t[l_ID_u16].labelErrCount_u16 = 0U;    /* 标号错误帧计数清零 */
        s_Comm429KZZZInfo_t[l_ID_u16].ovflErrCount_u16  = 0U;  /* FIFO溢出错误计数清零 */

        /* 错误计数清零 */
        s_Comm429KZZZInfo_t[l_ID_u16].errCntSum_u32    = 0UL;
        s_Comm429KZZZInfo_t[l_ID_u16].errCnt_u32       = 0UL;
        s_Comm429KZZZInfo_t[l_ID_u16].errCntMax_u32    = 0UL;

        /* 接收原始数据信息初始化 */
        for( l_index_u16 = 0U; l_index_u16 < KZZZ_R_DATA_NUM; l_index_u16++)
        {
            s_KZZZ429OrigData_t[l_ID_u16].Orig_Rx_t[l_index_u16].label_u16     = s_KZZZ429Rx_labelConf_u16[l_index_u16]; /* 根据配置表初始化标号  */
            s_KZZZ429OrigData_t[l_ID_u16].Orig_Rx_t[l_index_u16].OrigData_u32  = 0UL; /* 原始数据初始化为0  */
            s_KZZZ429OrigData_t[l_ID_u16].Orig_Rx_t[l_index_u16].Cnt_u16       = 0U; /* 计数初始化为0  */
        }

        /* 接收数据初始化  */
        s_Comm429KZZZData_t[l_ID_u16].currTimeAsk_u16 = 0U;    /* 请求当前时间  */
        s_Comm429KZZZData_t[l_ID_u16].MBITStateLast_u16 = KZZZ_MBIT_UNKNOWN;  /* 维护BIT执行上一拍反馈  */
        s_Comm429KZZZData_t[l_ID_u16].MBITFB_u16 = KZZZ_MBIT_UNKNOWN;     /* 维护BIT执行反馈  */
        s_Comm429KZZZData_t[l_ID_u16].MBITFInfo_1_t.all = 0UL;   /* 维护BIT结果1  */

        /* 控制装置软件版本初始化  */
        for(l_index_u16 = 0U; l_index_u16 < KZZZ_SOFTV_NUM; l_index_u16++)
        {
            s_Comm429KZZZData_t[l_ID_u16].SoftV_t[l_index_u16].all = 0UL;   /* 控制装置软件版本  */
        }

        s_Comm429KZZZData_t[l_ID_u16].rgLength_f = 0.0F;         /* 软管长度  */
        s_Comm429KZZZData_t[l_ID_u16].jyzzState_t.all = 0UL;   /* 加油装置状态 */
        s_Comm429KZZZData_t[l_ID_u16].componentState_t.all = 0U;
        s_Comm429KZZZData_t[l_ID_u16].faultInfo_t.all = 0U;   /* 故障信息 */
        s_Comm429KZZZData_t[l_ID_u16].faultInfo_1_t.all = 0U; /* 故障信息I */
        s_Comm429KZZZData_t[l_ID_u16].faultInfo_2_t.all = 0U; /* 故障信息II */
        s_Comm429KZZZData_t[l_ID_u16].turbineSpeed_u16 = 0U;
        s_Comm429KZZZData_t[l_ID_u16].fuelPressure_u16 = 0U;
        s_Comm429KZZZData_t[l_ID_u16].fuelTemperature_i16 = 0;
        s_Comm429KZZZData_t[l_ID_u16].turbinePumpPressure_u16 = 0U;
        s_Comm429KZZZData_t[l_ID_u16].fuelFlow_u16 = 0U;
        s_Comm429KZZZData_t[l_ID_u16].fuelLevel_u16 = 0U;
        s_Comm429KZZZData_t[l_ID_u16].totalFuel_u16 = 0U;
        s_Comm429KZZZData_t[l_ID_u16].remainLife_t.all = 0UL;    /* 剩余日历寿命  */
        s_Comm429KZZZData_t[l_ID_u16].jyzzState_t.all = 0UL;    /* 加油设备状态 0250 */
        s_Comm429KZZZData_t[l_ID_u16].cmdSignalFb_t.all = 0UL;  /* 指令信号反馈 0255 */
        s_Comm429KZZZData_t[l_ID_u16].motorSpeed_i16 = 0;       /* 电机转速 0256 */
        s_Comm429KZZZData_t[l_ID_u16].motorTemp_i16 = 0;        /* 控制器温度 0257 */
    }

    for(l_index_u16 = 0U; l_index_u16 < KZZZ_T_DATA_NUM; l_index_u16++)
    {
        s_KZZZ429TxCnt_u32[l_index_u16] = 0UL;
    }

    for(l_ID_u16 = 0U; l_ID_u16 < COMM429_KZZZ_NUM; l_ID_u16++)
    {
        s_KZZZ429TimeoutCnt_u32[l_ID_u16] = 0UL;
    }
}

/* ***************************************************************** */
/**
 *    【函数名】:	  Comm429KZZZRxStateCheck
 *    【功能描述】:	  控制装置429通信 接收状态检查
 *    【输入参数说明】:v_ID_u16  ---- 通道号ID
 *
 *	【输出参数说明】:NONE
 *    【其他说明】:	  NONE
 *    【返回】:	NONE
 */
/* ***************************************************************** */

void Comm429KZZZRxStateCheck(void)
{
    Uint16 l_ID_u16 = 0U;  /*通道号 */
    Uint32 l_checkTime_u32 = 0UL;  /* 检查时间 */
    Uint16 l_rData_u16 = RX429_STATE_OK;  /* 通信接收状态  */

    /* 获取当前系统时间计数作为检查时间 */
    l_checkTime_u32 = sysTime();

    /* 轮询每个通道 */
    for(l_ID_u16 = 0U;l_ID_u16 < COMM429_KZZZ_NUM;l_ID_u16++)
    {
        l_rData_u16 = RX429_STATE_OK;  /* 通信接收状态初始正常  */

        /* 未接收数据时 */
        if( (l_checkTime_u32 - s_Comm429KZZZInfo_t[l_ID_u16].rxTime_u32) >= COMM429_KZZZ_TIMEOUT_MS)
        {
            /* 通信接收状态置为异常 */
            l_rData_u16 = RX429_STATE_ERR;

            /* 连续错误计数加1 */
            s_Comm429KZZZInfo_t[l_ID_u16].errCnt_u32 = s_Comm429KZZZInfo_t[l_ID_u16].errCnt_u32 + 1UL;

            /* 错误计数总数加1 */
            s_Comm429KZZZInfo_t[l_ID_u16].errCntSum_u32 = s_Comm429KZZZInfo_t[l_ID_u16].errCntSum_u32 + 1UL;

            /* 连续错误计数大于最大连续错误计数时 */
            if(s_Comm429KZZZInfo_t[l_ID_u16].errCnt_u32 > s_Comm429KZZZInfo_t[l_ID_u16].errCntMax_u32)
            {
                /* 最大连续错误计数更新为连续错误计数 */
                s_Comm429KZZZInfo_t[l_ID_u16].errCntMax_u32 = s_Comm429KZZZInfo_t[l_ID_u16].errCnt_u32;
            }
        }
        else /* 通信接收状态置正常 */
        {
            /* 连续错误计数清零 */
            s_Comm429KZZZInfo_t[l_ID_u16].errCnt_u32 = 0UL;
        }

        if((RX429_STATE_ERR == l_rData_u16) && (RX429_STATE_ERR != s_Comm429KZZZInfo_t[l_ID_u16].rxState_u16))
        {
            s_KZZZ429TimeoutCnt_u32[l_ID_u16] = s_KZZZ429TimeoutCnt_u32[l_ID_u16] + 1UL;
        }
        /* 更新接收状态  */
        s_Comm429KZZZInfo_t[l_ID_u16].rxState_u16 = l_rData_u16;
    }
}

/* ***************************************************************** */
/**
 *    【函数名】:	  Comm429KZZZDataProcess
 *    【功能描述】:	  控制装置429通信数据处理
 *    【输入参数说明】:v_ID_u16  ---- 通道号ID
 *
 *	【输出参数说明】:NONE
 *    【其他说明】:	  NONE
 *    【返回】:	NONE
 */
/* ***************************************************************** */
void Comm429KZZZDataProcess(void)
{
    /* 整体流程：
     * 1. 轮询左右吊舱两路 KZZZ 429 通道（COMM429_KZZZ_1/2），先获取接收 FIFO 溢出状态；
     * 2. FIFO 未溢出时读取本路 429 原始字，更新接收数据状态为正常并记录时间戳；
     * 3. 对每帧依次执行奇偶校验、SSM 有效性检查，失败则累计 labelErrCount 并跳过；
     * 4. 按标签索引匹配并更新 s_Comm429KZZZData_t 各字段（吊舱状态/部件/故障/涡轮转速/加油压力/流量等）；
     * 5. 同步刷新原始字缓存 s_KZZZ429OrigData_t 与接收计数，供余度管理与 CCDL 镜像比对使用。
     */
    Uint16 l_rxFifoState_u16 = DRI429_R_FIFO_OVFL;  /* 接收状态，默认FIFO接收溢出 */
    Uint16 l_rxDataNum_u16   = 0U;   /* 接收数据个数 */
    Uint16 l_ID_u16 = 0U;  /*通道号 */
    Uint16 l_ii_u16 = 0U;  /* 索引 */
    union  arinc429Data l_rdata_un[A429_RX_DATA_NUM_MAX];

    /* 轮询每个通道 */
    for(l_ID_u16 = 0U;l_ID_u16 < COMM429_KZZZ_NUM;l_ID_u16++)
    {
        /* 接收FIFO溢出状态获取  */
        l_rxFifoState_u16 = Ccdl429RxFifoStatusGet(s_KZZZCommIDConf_u16[l_ID_u16]);

        /* 当接收FIFO未溢出时，进行数据处理 */
        if(DRI429_R_FIFO_OK == l_rxFifoState_u16)
        {
            /* 读取429通信数据 */
            l_rxDataNum_u16 = Ccdl429ReadBuff(s_KZZZCommIDConf_u16[l_ID_u16],l_rdata_un);

            /* 判断接收个数大于0时 */
            if(l_rxDataNum_u16 > 0U)
            {
                /* 更新接收数据状态为正常 */
                s_Comm429KZZZInfo_t[l_ID_u16].rxDataState_u16  = RX429_STATE_OK;

                /* 按标签逐帧解析KZZZ报文，并同步原始字/计数/时间戳。 */
                for(l_ii_u16 = 0U;l_ii_u16 < l_rxDataNum_u16;l_ii_u16++)
                {
                    if(1U != Ccdl429ParityCheck(l_rdata_un[l_ii_u16], PARITY_ODD))
                    {
                        s_Comm429KZZZInfo_t[l_ID_u16].labelErrCount_u16 = s_Comm429KZZZInfo_t[l_ID_u16].labelErrCount_u16 + 1U;
                        continue;
                    }

                    if(VALID != Comm429KZZZRxSsmValidGet(l_rdata_un[l_ii_u16]))
                    {
                        s_Comm429KZZZInfo_t[l_ID_u16].labelErrCount_u16 = s_Comm429KZZZInfo_t[l_ID_u16].labelErrCount_u16 + 1U;
                        continue;
                    }

                    switch(l_rdata_un[l_ii_u16].bit.label)
                    {
                        case KZZZ_LABEL_R_CURRENT_TIME:  /* 请求当前时间 */
                            {
                                /* 解析当前时间请求标志。 */
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_CURRENT_TIME, l_rdata_un[l_ii_u16].msgData);

                                /* 获取请求当前时间 */
                                s_Comm429KZZZData_t[l_ID_u16].currTimeAsk_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x01UL);

                            }
                            break;

                        case KZZZ_LABEL_R_MAINTENANCE_BIT_FB:  /* 维护BIT执行反馈 */
                            {
                                /* 解析维护BIT执行反馈，并保留上一拍反馈值。 */
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_MAINTENANCE_BIT_FB, l_rdata_un[l_ii_u16].msgData);

                                /* 获取维护BIT执行反馈 */
                                s_Comm429KZZZData_t[l_ID_u16].MBITStateLast_u16 = s_Comm429KZZZData_t[l_ID_u16].MBITFB_u16;
                                s_Comm429KZZZData_t[l_ID_u16].MBITFB_u16 = (Uint16)(l_rdata_un[l_ii_u16].bit.data & 0x07UL);

                            }
                            break;

                        case KZZZ_LABEL_R_UPLOAD_MAINTENANCE_BIT:  /* 维护BIT结果 */
                            {
                                /* 解析维护BIT结果扩展字。 */
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_UPLOAD_MAINTENANCE_BIT, l_rdata_un[l_ii_u16].msgData);

                                /* 获取维护BIT结果1 */
                                s_Comm429KZZZData_t[l_ID_u16].MBITFInfo_1_t.all = l_rdata_un[l_ii_u16].bit.data;
                            }
                            break;


                        case KZZZ_LABEL_R_CTRL_SW_VERSION:  /*控制装置应用软件版本信息  */
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_CTRL_SW_VERSION, l_rdata_un[l_ii_u16].msgData);

                                /* 获取 控制装置应用软件版本 */
                                s_Comm429KZZZData_t[l_ID_u16].SoftV_t[KZZZ_SOFTV_INDEX_APP].all = l_rdata_un[l_ii_u16].bit.data ;

                            }
                            break;

                        case KZZZ_LABEL_R_MOTOR_CTRL_SW_VERSION: /*电驱动控制器软件版本信息  */
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_MOTOR_CTRL_SW_VERSION, l_rdata_un[l_ii_u16].msgData);

                                /* 获取电驱动控制器软件版本 */
                                s_Comm429KZZZData_t[l_ID_u16].SoftV_t[KZZZ_SOFTV_INDEX_MOTOR_CTRL].all = l_rdata_un[l_ii_u16].bit.data;
                            }
                            break;

                        case KZZZ_LABEL_R_LOGIC_SW_VERSION: /*控制装置逻辑软件版本信息  */
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_LOGIC_SW_VERSION, l_rdata_un[l_ii_u16].msgData);

                                /* 获取控制装置逻辑软件版本 */
                                s_Comm429KZZZData_t[l_ID_u16].SoftV_t[KZZZ_SOFTV_INDEX_LOGIC].all = l_rdata_un[l_ii_u16].bit.data ;


                            }
                            break;

                        case KZZZ_LABEL_R_FUEL_LEVEL_SIGNAL_BOX: /*油量测量信号盒软件版本信息  */
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_FUEL_LEVEL_SIGNAL_BOX, l_rdata_un[l_ii_u16].msgData);

                                /* 获取油量测量信号盒软件版本信息 */
                                s_Comm429KZZZData_t[l_ID_u16].SoftV_t[KZZZ_SOFTV_INDEX_SIGNAL_BOX].all = l_rdata_un[l_ii_u16].bit.data;

                            }
                            break;

                        case KZZZ_LABEL_R_BRAKE_CTRL_SW_VERSION: /*电液刹车驱动控制器软件版本信息*/
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_BRAKE_CTRL_SW_VERSION, l_rdata_un[l_ii_u16].msgData);

                                /* 获取电液刹车驱动控制器软件版本信息 */
                                s_Comm429KZZZData_t[l_ID_u16].SoftV_t[KZZZ_SOFTV_INDEX_BRAKE_CTRL].all = l_rdata_un[l_ii_u16].bit.data;
                            }
                            break;

                        case KZZZ_LABEL_R_BIT_APP_SW_VERSION: /*自检测装置应用软件版本信息*/
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_BIT_APP_SW_VERSION, l_rdata_un[l_ii_u16].msgData);

                                /* 获取自检测装置应用软件版本信息 */
                                s_Comm429KZZZData_t[l_ID_u16].SoftV_t[KZZZ_SOFTV_INDEX_BIT_APP].all = l_rdata_un[l_ii_u16].bit.data;
                            }
                            break;

                        case KZZZ_LABEL_R_UPGRADE_APP_SW_VERSION: /*控制装置在线升级应用软件版本信息*/
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_UPGRADE_APP_SW_VERSION, l_rdata_un[l_ii_u16].msgData);

                                /* 获取控制装置在线升级应用软件版本信息 */
                                s_Comm429KZZZData_t[l_ID_u16].SoftV_t[KZZZ_SOFTV_INDEX_UPGRADE_APP].all = l_rdata_un[l_ii_u16].bit.data;
                            }
                            break;

                        case KZZZ_LABEL_R_MOTOR_LOGIC_SW_VERSION: /*电驱动控制器逻辑软件版本信息*/
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_MOTOR_LOGIC_SW_VERSION, l_rdata_un[l_ii_u16].msgData);

                                /* 获取电驱动控制器逻辑软件版本信息 */
                                s_Comm429KZZZData_t[l_ID_u16].SoftV_t[KZZZ_SOFTV_INDEX_MOTOR_LOGIC].all = l_rdata_un[l_ii_u16].bit.data;
                            }
                            break;

                        case KZZZ_LABEL_R_SEL_FUEL_RECEIVE_FB:/* 预选油量接收反馈  */
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_SEL_FUEL_RECEIVE_FB, l_rdata_un[l_ii_u16].msgData);

                                /* 获取预选油量接收反馈标志 */
                                s_Comm429KZZZData_t[l_ID_u16].Pre_FuelQtyRcv_FB_u16 = l_rdata_un[l_ii_u16].bit.data & 0x1UL;
                            }
                            break;

                        case KZZZ_LABEL_R_REMAINING_FLIGHT_HRS:/*剩余飞行小时 */
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_REMAINING_FLIGHT_HRS, l_rdata_un[l_ii_u16].msgData);

                                /* 获取飞行小时信息 */
                                s_Comm429KZZZData_t[l_ID_u16].flightHours_u16 = (l_rdata_un[l_ii_u16].bit.data >> 5U) & 0x3FFFUL;
                            }
                            break;

                        case KZZZ_LABEL_R_FUEL_RESET_RECEIVE_FB:/*油量重置接收反馈 */
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_FUEL_RESET_RECEIVE_FB, l_rdata_un[l_ii_u16].msgData);

                                /* 获取油量重置接收反馈信息（bit9/bit10 -> 双bit编码） */
                                s_Comm429KZZZData_t[l_ID_u16].oilReset_u16 = (l_rdata_un[l_ii_u16].bit.data >> 0U) & 0x3UL;
                            }
                            break;

                        case KZZZ_LABEL_R_TURBINE_SPEED: /* 涡轮转速 */
                        {
                            Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_TURBINE_SPEED, l_rdata_un[l_ii_u16].msgData);

                            /* 提取涡轮转速数据 */
                            s_Comm429KZZZData_t[l_ID_u16].turbineSpeed_u16 = (l_rdata_un[l_ii_u16].bit.data >> 5U) & 0x3FFFUL;
                        } break;

                        case KZZZ_LABEL_R_FUEL_PRESSURE: /* 加油压力 */
                        {
                            Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_FUEL_PRESSURE, l_rdata_un[l_ii_u16].msgData);

                            /* 提取燃油压力数据 */
                            s_Comm429KZZZData_t[l_ID_u16].fuelPressure_u16 = (l_rdata_un[l_ii_u16].bit.data >> 7U) & 0x3FFFUL;
                        } break;

                        case KZZZ_LABEL_R_TURBINE_PUMP_PRESSURE: /* 涡轮泵出口压力 */
                        {
                            Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_TURBINE_PUMP_PRESSURE, l_rdata_un[l_ii_u16].msgData);

                            /* 提取涡轮泵压力数据 */
                            s_Comm429KZZZData_t[l_ID_u16].turbinePumpPressure_u16 = (l_rdata_un[l_ii_u16].bit.data >> 7U) & 0x3FFFUL;
                        } break;

                        case KZZZ_LABEL_R_FUEL_FLOW: /* 加油流量 */
                        {
                            Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_FUEL_FLOW, l_rdata_un[l_ii_u16].msgData);

                            /* 提取加油流量数据 */
                            s_Comm429KZZZData_t[l_ID_u16].fuelFlow_u16 = (l_rdata_un[l_ii_u16].bit.data >> 7U) & 0x3FFUL;
                        } break;

                        case KZZZ_LABEL_R_FUEL_LEVEL: /* 已加油量 */
                        {
                            Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_FUEL_LEVEL, l_rdata_un[l_ii_u16].msgData);

                            /* 提取已加油量数据 */
                            s_Comm429KZZZData_t[l_ID_u16].fuelLevel_u16 = (l_rdata_un[l_ii_u16].bit.data >> 8U) & 0x1FFUL;
                        } break;

                        case KZZZ_LABEL_R_TOTAL_FUEL: /* 累计加油量 */
                        {
                            Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_TOTAL_FUEL, l_rdata_un[l_ii_u16].msgData);

                            /* 提取累计加油量数据 */
                            s_Comm429KZZZData_t[l_ID_u16].totalFuel_u16 = (l_rdata_un[l_ii_u16].bit.data >> 8U) & 0x1FFUL;
                        } break;

                        case KZZZ_LABEL_R_FUEL_TEMP: /* 燃油温度 */
                        {
                            /* 解析燃油温度，并按符号位恢复正负值。 */
                            Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_FUEL_TEMP, l_rdata_un[l_ii_u16].msgData);

                            /* 提取累计加油量数据 */
                            s_Comm429KZZZData_t[l_ID_u16].fuelTemperature_i16 = (l_rdata_un[l_ii_u16].bit.data >> 11U) & 0x7FUL;
                            /*符号位判断 0正1负*/
                            if((l_rdata_un[l_ii_u16].bit.data >>18) & 0x1UL == 1U)
                            {
                                s_Comm429KZZZData_t[l_ID_u16].fuelTemperature_i16 = -s_Comm429KZZZData_t[l_ID_u16].fuelTemperature_i16;
                            }
                        } break;

                        case KZZZ_LABEL_R_RG_LEN:/* 软管长度  */
                            {
                                    /* 解析软管长度，并按比例还原为浮点工程值。 */
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_RG_LEN, l_rdata_un[l_ii_u16].msgData);

                                /* 获取软管长度信息 */
                                s_Comm429KZZZData_t[l_ID_u16].rgLength_f = (float)((l_rdata_un[l_ii_u16].bit.data >> 9U) & 0x1FFUL) / KZZZ_RG_LENGTH_R_RATIO;
                            }
                            break;



                        case KZZZ_LABEL_R_COMPONENT_STATUS:/* 部件状态  */
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_COMPONENT_STATUS, l_rdata_un[l_ii_u16].msgData);

                                /* 获取部件状态，保持与CCDL快照解码口径一致。 */
                                s_Comm429KZZZData_t[l_ID_u16].componentState_t.all = l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL;
                            }
                            break;

                        case KZZZ_LABEL_R_FAULT_WARN: /* 故障告警  */
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_FAULT_WARN, l_rdata_un[l_ii_u16].msgData);

                                /* 获取故障告警信息 */
                                s_Comm429KZZZData_t[l_ID_u16].faultInfo_t.all = l_rdata_un[l_ii_u16].bit.data&0xFFFF;
                            }
                            break;

                        case KZZZ_LABEL_R_FAULT_WARN_I: /* 故障信息Ⅰ */
                            {
                                /* 解析故障信息Ⅰ扩展字。 */
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_FAULT_WARN_I, l_rdata_un[l_ii_u16].msgData);

                                /* 获取故障信息Ⅰ */
                                s_Comm429KZZZData_t[l_ID_u16].faultInfo_1_t.all = l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL;
                            }
                            break;

                        case KZZZ_LABEL_R_FAULT_WARN_II: /* 故障信息Ⅱ */
                            {
                                /* 解析故障信息Ⅱ扩展字。 */
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_FAULT_WARN_II, l_rdata_un[l_ii_u16].msgData);

                                /* 获取故障信息Ⅱ */
                                s_Comm429KZZZData_t[l_ID_u16].faultInfo_2_t.all = l_rdata_un[l_ii_u16].bit.data & 0xFFFFUL;
                            }
                            break;

                        case KZZZ_LABEL_R_REFUEL_DEV_STATE: /* 加油设备状态 0250 */
                            {
                                /* 解析加油设备状态：工作状态/工作模式/信号灯/地维护等。 */
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_REFUEL_DEV_STATE, l_rdata_un[l_ii_u16].msgData);

                                /* msgData整字落到结构体，按位域自动分布；位域口径已与ICD bit11-23对齐。 */
                                s_Comm429KZZZData_t[l_ID_u16].jyzzState_t.all = l_rdata_un[l_ii_u16].msgData;
                            }
                            break;

                        case KZZZ_LABEL_R_CMD_SIGNAL_FB: /* 指令信号反馈 0255 */
                            {
                                /* 解析指令信号反馈8个离散位。 */
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_CMD_SIGNAL_FB, l_rdata_un[l_ii_u16].msgData);

                                s_Comm429KZZZData_t[l_ID_u16].cmdSignalFb_t.all = l_rdata_un[l_ii_u16].msgData;
                            }
                            break;

                        case KZZZ_LABEL_R_MOTOR_SPEED: /* 电驱动电机转速 0256 BNR */
                            {
                                /* 解析电机转速 bit15-28 数据 + bit29 符号位，按 1 r/min 分辨率落入有符号值。 */
                                Uint32 l_raw_u32 = 0UL;
                                Int16  l_speed_i16 = 0;

                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_MOTOR_SPEED, l_rdata_un[l_ii_u16].msgData);

                                /* bit15-28 数据(14bit)，bit数据域中相对位为 bit5-bit18(data域从bit9开始)。 */
                                l_raw_u32 = (l_rdata_un[l_ii_u16].bit.data >> 5UL) & 0x3FFFUL;
                                l_speed_i16 = (Int16)l_raw_u32;
                                if((l_rdata_un[l_ii_u16].bit.data >> 19UL) & 0x1UL) /* bit29 符号位 */
                                {
                                    l_speed_i16 = (Int16)(-l_speed_i16);
                                }
                                s_Comm429KZZZData_t[l_ID_u16].motorSpeed_i16 = l_speed_i16;
                            }
                            break;

                        case KZZZ_LABEL_R_MOTOR_TEMP: /* 电驱动控制器温度 0257 BNR */
                            {
                                /* 解析控制器温度 bit21-28 数据 + bit29 符号位，按 1℃ 分辨率落入有符号值。 */
                                Uint32 l_raw_u32 = 0UL;
                                Int16  l_temp_i16 = 0;

                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_MOTOR_TEMP, l_rdata_un[l_ii_u16].msgData);

                                /* bit21-28 数据(8bit)，data域内相对位为 bit11-bit18。 */
                                l_raw_u32 = (l_rdata_un[l_ii_u16].bit.data >> 11UL) & 0xFFUL;
                                l_temp_i16 = (Int16)l_raw_u32;
                                if((l_rdata_un[l_ii_u16].bit.data >> 19UL) & 0x1UL) /* bit29 符号位 */
                                {
                                    l_temp_i16 = (Int16)(-l_temp_i16);
                                }
                                s_Comm429KZZZData_t[l_ID_u16].motorTemp_i16 = l_temp_i16;
                            }
                            break;

                        case KZZZ_LABEL_R_REMAINING_CALENDAR_LIFE: /* 剩余日历寿命 */
                            {
                                Comm429KZZZRxWordMark(l_ID_u16, KZZZ_R_DATA_REMAINING_CALENDAR_LIFE, l_rdata_un[l_ii_u16].msgData);

                                /* 获取剩余日历寿命 */
                                s_Comm429KZZZData_t[l_ID_u16].remainLife_t.all = l_rdata_un[l_ii_u16].bit.data;

                            }
                            break;

                        default:
                            {
                                /* 记录收到未定义或已精简标号的报文 */
                                s_Comm429KZZZInfo_t[l_ID_u16].labelErrCount_u16 = s_Comm429KZZZInfo_t[l_ID_u16].labelErrCount_u16 + 1U;
                            }
                            break;
                    }
                }
            }
            else
            {
                /* 更新无数据状态为异常 */
                s_Comm429KZZZInfo_t[l_ID_u16].rxDataState_u16  = RX429_STATE_ERR;
            }
        }
        else
        {
            /* FIFO溢出错误计数加1 */
            s_Comm429KZZZInfo_t[l_ID_u16].ovflErrCount_u16 =s_Comm429KZZZInfo_t[l_ID_u16].ovflErrCount_u16 +  1U;

            /* 接收FIFO有数时，将FIFO剩下数据读空 */
            Ccdl429RFIFOReset(s_KZZZCommIDConf_u16[l_ID_u16]);
        }

        /* 接收状态检测 */
        Comm429KZZZRxStateCheck();
    }
}

/* 函数名: Comm429KZZZSendPreFuel 功能描述: 控制装置429预选油量发送 输入参数说明: v_kzzzID_u16 --- 吊舱通道号 v_data_f --- 预选油量 输出参数说明: NONE 其他说明:    ICD定义分辨率100kg数据位从bit19开始 返回:        NONE */

void Comm429KZZZSendPreFuel(Uint16 v_kzzzID_u16, float v_data_f)
{
    Uint32 l_tData_u32 = 0UL;

    if(v_data_f < 0.0F)
    {
        v_data_f = 0.0F;
    }
    else if(v_data_f > KZZZ_PRE_FUEL_MAX_KG)
    {
        v_data_f = KZZZ_PRE_FUEL_MAX_KG;
    }

    l_tData_u32 = ((Uint32)(v_data_f / OIL_RATIO) & 0x3FFUL) << 8U;
    Comm429KZZZSendSingle(v_kzzzID_u16, KZZZ_LABEL_T_PRE_FUEL, l_tData_u32);
}

/* ***************************************************************** */
/**
 *【函数名】: Comm429KZZZSendFuelDensity
 *【功能描述】控制装置429燃油密度发送
 *【输入参数说明】v_data_f --- 燃油密度，单位kg/m3
 *【输出参数说明】NONE
 *【其他说明】:       ICD定义分辨率1kg/m3，数据位从bit19开始
 *【返回】:              NONE
***************************************************************** */
void Comm429KZZZSendFuelDensity(float v_data_f)
{
    Uint32 l_tData_u32 = 0UL;

    if(v_data_f < 0.0F)
    {
        v_data_f = 0.0F;
    }
    else if(v_data_f > KZZZ_FUEL_DENSITY_MAX)
    {
        v_data_f = KZZZ_FUEL_DENSITY_MAX;
    }

    l_tData_u32 = ((Uint32)(v_data_f) & 0x3FFUL) << 8U;
    Comm429KZZZSendDual(KZZZ_LABEL_T_FUEL_DENSITY, l_tData_u32);
}

/* ***************************************************************** */
/**
 *【函数名】: Comm429KZZZSendCtrlCmd
 *【功能描述】控制装置429控制指令发送
 *【输入参数说明】v_lowFuel_u16   --- 飞机余油低
 *                v_air_u16      --- 空地信号（1：空中，0：地面）
 *                v_fuelReset_u16--- 累计加油量清零
 *【输出参数说明】NONE
 *【其他说明】:       ICD定义bit11/13/14分别对应三类控制指令
 *【返回】:              NONE
***************************************************************** */
void Comm429KZZZSendCtrlCmd(Uint16 v_lowFuel_u16, Uint16 v_air_u16, Uint16 v_fuelReset_u16)
{
    Uint32 l_tData_u32 = 0UL;

    /* 0267数据位定义（data[0]/[2]/[3] 对应ARINC bit11/13/14）：
     * bit11 飞机余油低、bit13 空地信号(1=空中)、bit14 累计加油量清零。 */
    l_tData_u32 |= (Uint32)(v_lowFuel_u16 & 0x1U);
    l_tData_u32 |= (Uint32)(v_air_u16 & 0x1U) << 2U;
    l_tData_u32 |= (Uint32)(v_fuelReset_u16 & 0x1U) << 3U;

    Comm429KZZZSendDual(KZZZ_LABEL_T_CTRL_CMD, l_tData_u32);
}

/* ***************************************************************** */
/**
 *【函数名】: Comm429KZZZCurrTimeTx
 *【功能描述】控制装置429当前时间发送
 *【输入参数说明】v_RIU429RxData_t  --- RIU数据
 *【输出参数说明】NONE
 *【其他说明】:       NONE
 *【返回】:             NONE
***************************************************************** */
void Comm429KZZZCurrTimeTx(Uint16 v_kzzzID_u16, RIU429InfoData_t v_RIU429RxData_t)
{
    RemainLife_t l_date_t; /* 当前日期 */
    CurrTime_t l_time_t;   /* 当前时间 */

    /****************************日期时间数据发送*************************************/
    /* 先按KZZZ日期/时间字定义重排RIU时间，再分别发送日期和时间两帧。 */
    /* 日期数据获取 */
    l_date_t.bit.gwYear_u32  = v_RIU429RxData_t.DTData_t.Year_u16 % 10U;
    l_date_t.bit.swYear_u32  = v_RIU429RxData_t.DTData_t.Year_u16 / 10U;
    l_date_t.bit.gwMonth_u32 = v_RIU429RxData_t.DTData_t.Month_u16 % 10U;
    l_date_t.bit.swMonth_u32 = v_RIU429RxData_t.DTData_t.Month_u16 / 10U;
    l_date_t.bit.gwDay_u32   = v_RIU429RxData_t.DTData_t.Day_u16 % 10U;
    l_date_t.bit.swDay_u32   = v_RIU429RxData_t.DTData_t.Day_u16 / 10U;
    l_date_t.bit.rsvd_u32    =  0U;

    /* 日期发送 */
    Comm429KZZZSendSingle(v_kzzzID_u16, KZZZ_LABEL_T_CURR_DATE, l_date_t.all);

    /*************************/
    /* 时间数据获取 */
    l_time_t.bit.rsvd_1_u32   =  0U;
    l_time_t.bit.gwHour_u32  = v_RIU429RxData_t.DTData_t.Hour_u16 % 10U;
    l_time_t.bit.swHour_u32  = v_RIU429RxData_t.DTData_t.Hour_u16 / 10U;
    l_time_t.bit.gwMin_u32   = v_RIU429RxData_t.DTData_t.Minute_u16 % 10U;
    l_time_t.bit.swMin_u32   = v_RIU429RxData_t.DTData_t.Minute_u16 / 10U;
    l_time_t.bit.rsvd_2_u32    = 0U;

    /* 时间发送 */
    Comm429KZZZSendSingle(v_kzzzID_u16, KZZZ_LABEL_T_CURR_TIME, l_time_t.all);
}

/* ***************************************************************** */
/**
 *【函数名】: Comm429KZZZSendLifeInfo
 *【功能描述】控制装置429寿命信息发送
 *【输入参数说明】v_data_t --- 寿命信息字
 *【输出参数说明】NONE
 *【其他说明】:       直接透传结构体打包结果
 *【返回】:              NONE
 ***************************************************************** */
void Comm429KZZZSendLifeInfo(Uint16 v_kzzzID_u16, Uint16 v_valid_u16)
{
    Comm429KZZZSendSingle(v_kzzzID_u16, KZZZ_LABEL_T_LIFE_INFO, (Uint32)(v_valid_u16 & 0x1U));
}

/* ***************************************************************** */
/**
 *【函数名】: Comm429KZZZSendOilReset
 *【功能描述】控制装置429油量重置命令发送
 *【输入参数说明】v_kzzzID_u16 --- 吊舱通道号
 *                v_valid_u16  --- 油量重置有效位
 *【输出参数说明】NONE
 *【其他说明】:       ICD要求bit11为油量重置有效位
 *【返回】:              NONE
***************************************************************** */
void Comm429KZZZSendOilReset(Uint16 v_kzzzID_u16, Uint16 v_valid_u16)
{
    Comm429KZZZSendSingle(v_kzzzID_u16, KZZZ_LABEL_T_FUEL_RESET, (Uint32)(v_valid_u16 & 0x1U));
}

/* ========================================================================== */
/* 文件结束 */
/* ========================================================================== */
