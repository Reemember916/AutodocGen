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
 * 文件名称:    commCCDL.c
 *
 * 文件日期:    REDACTED
 *
 *
 * 【程序版本】 V2.00
 *
 * 【功能描述】实现通道间422通信
 * 【其他说明】NONE
 *
 **********************************************************************************
 *
 * 功能说明:
 *
 * 1. 实现CCDL在SCI链路和CPLD链路上的收发、打包、解析与状态统计。
 * 2. 基础帧保持兼容，同时新增KZZZ原始429字的分页扩展帧收发与镜像缓存。
 *
 *********************************************************************************/
#include "Global.h"
#include "CommCCDL.h"

/* ***************************************************************** */


/* 通道间通信ID配置表 */
static Uint16  s_CCDLCommIDConf_u16[COMM_CCDL_NUM] =
            {
                COMM422_CCDL_ID,
                COMMDRI_422_ID_CCDL
            };

/* 通道间通信信息配置 */
static CCDLCommConf_t s_CCDLCommConf_t[COMM_CCDL_NUM] =
                {
                    { COMM_CCDL_FRAME_HEAD1, COMM_CCDL_FRAME_HEAD2, 0U, 0xFFU, COMM_CCDL_FRAME_LEN_MAX, COMM_CCDL_RX_BUFF_LEN },
                    { COMM_CCDL_FRAME_HEAD1, COMM_CCDL_FRAME_HEAD2, 0U, 0xFFU, COMM_CCDL_FRAME_LEN_MAX, COMM_CCDL_RX_BUFF_LEN }
                };

CCDLCommBuff_t s_CCDLCommBuff_t[COMM_CCDL_NUM];
CCDLCommInfo_t s_CCDLCommInfo_t[COMM_CCDL_NUM];
CCDLRXData_t s_ccdlRxBaseData_t[COMM_CCDL_NUM];
PeerBaseStatus_t s_peerBaseStatus_t[COMM_CCDL_NUM];           /* 最近一次收到的对端基础帧快照 */
CCDLExtStatus_t s_ccdlRIUExtStatus_t[COMM_CCDL_NUM];          /* RIU扩展页状态 */
CCDLExtStatus_t s_ccdlKZZZExtStatus_t[COMM_CCDL_NUM][COMM429_KZZZ_NUM]; /* KZZZ扩展页状态，按左右吊舱分别缓存 */
RIU429OrigData_t s_ccdlRIUOrigData_t[COMM_CCDL_NUM];          /* SCI/CPLD链路接收到的RIU镜像原始字 */
KZZZ429OrigData_t s_ccdlKZZZOrigData_t[COMM_CCDL_NUM][COMM429_KZZZ_NUM]; /* SCI/CPLD链路接收到的KZZZ镜像原始字，按左右吊舱分别缓存 */
Uint16 s_rxCCDLBuff_u16[CCDL_RX_DATA_NUM_MAX];                /* CPLD链路底层读取暂存数组 */
Uint8 s_CCDLTxBuff_u8[COMM_CCDL_TX_FRAM_LEN_MAX];             /* 初始化/PuBIT专用基础帧直发缓存 */
Uint8 s_ccdlSciTxQueue_u8[COMM_CCDL_SCI_TX_QUEUE_DEPTH][COMM_CCDL_TX_FRAM_LEN_MAX]; /* 运行期SCI发送队列 */
Uint16 s_ccdlSciTxLen_u16[COMM_CCDL_SCI_TX_QUEUE_DEPTH];      /* 运行期SCI队列中每帧的有效长度 */
Uint16 s_ccdlSciTxWr_u16 = 0U;                                /* 运行期SCI队列写指针 */
Uint16 s_ccdlSciTxRd_u16 = 0U;                                /* 运行期SCI队列读指针 */
Uint16 s_ccdlSciTxCount_u16 = 0U;                             /* 运行期SCI队列当前帧数 */
Uint16 s_ccdlSciTxActiveLen_u16 = 0U;                         /* 当前正在发送帧的有效长度 */
Uint16 s_ccdlSciTxActiveMode_u16 = COMM_CCDL_TX_MODE_NONE;    /* 当前发送来源：直发或运行期队列 */
Uint16 s_commCCDL422TxFlag_u16 = RS422_COMM_TX_FLAG_OFF;      /* SCI链路CCDL发送忙闲标志 */
Uint16 s_commCCDLSendIndex_u16 = 0U;                          /* 当前帧已送入SCI FIFO的字节索引 */
Uint32 s_ccdlSciTxDropCnt_u32 = 0UL;                          /* 运行期SCI队列满时的丢帧计数 */
Uint16 s_ccdlRIUExtFrameCnt_u16 = 0U;                         /* RIU扩展分页帧发送计数 */
Uint16 s_ccdlKZZZExtFrameCnt_u16 = 0U;                        /* KZZZ扩展分页帧发送计数 */
Uint16 s_ccdlKZZZExtTxSrcID_u16 = COMM429_KZZZ_NUM;           /* KZZZ扩展分页帧当前轮次发送源 */
Uint16 s_ccdlKZZZExtLastSrcID_u16 = COMM429_KZZZ_2;           /* KZZZ扩展分页帧上一次完整发送源，用于双源轮转 */
Uint16 s_ccdlTxRandData_u16[COMM_CCDL_NUM];                   /* 基础帧历史兼容随机数字段发送值 */

/* RIU分页镜像的固定索引顺序必须与 Comm429RIU.c 中原始字配置保持一致。 */
static const Uint16 s_ccdlRIULabelConf_u16[RIU_R_DATA_NUM] =
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

/* KZZZ分页镜像的固定索引顺序必须与 Comm429KZZZ.c 中原始字配置保持一致。 */
static const Uint16 s_ccdlKZZZLabelConf_u16[KZZZ_R_DATA_NUM] =
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

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDL422TxFlagGet
 *
 * 【功能描述】获取当前SCI链路CCDL发送忙闲状态。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】    该标志既用于初始化/PuBIT直发场景，也反映运行期队列当前是否有活动帧正在发送。
 * 【返回】        RS422_COMM_TX_FLAG_ON/OFF
 */
/* ***************************************************************** */
Uint16 CommCCDL422TxFlagGet(void)
{
    return s_commCCDL422TxFlag_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLPeerBaseGet
 *
 * 【功能描述】获取最近一次收到的对端基础帧状态快照。
 *
 * 【输入参数说明】v_ccdlID_u16  ---- CCDL链路ID
 * 【输出参数说明】NONE
 * 【其他说明】    主备切换、初始化重连等基础帧业务逻辑优先使用该接口。
 * 【返回】        PeerBaseStatus_t
 */
/* ***************************************************************** */
PeerBaseStatus_t CommCCDLPeerBaseGet(Uint16 v_ccdlID_u16)
{
    PeerBaseStatus_t l_rslt_t;
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    if(v_ccdlID_u16 < COMM_CCDL_NUM)
    {
        l_rslt_t = s_peerBaseStatus_t[v_ccdlID_u16];
    }

    return l_rslt_t;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLPeerBaseAdvancedGet
 *
 * 【功能描述】判断最近一拍基础帧是否发生推进。
 *
 * 【输入参数说明】v_ccdlID_u16  ---- CCDL链路ID
 * 【输出参数说明】NONE
 * 【其他说明】    供初始化、启动判型和BIT统一判断“本拍是否收到新的基础帧”。
 * 【返回】        VALID / INVALID
 */
/* ***************************************************************** */
Uint16 CommCCDLPeerBaseAdvancedGet(Uint16 v_ccdlID_u16)
{
    Uint16 l_rslt_u16 = INVALID;
    PeerBaseStatus_t l_peerBase_t;

    memset(&l_peerBase_t, 0, sizeof(l_peerBase_t));
    if(v_ccdlID_u16 < COMM_CCDL_NUM)
    {
        l_peerBase_t = s_peerBaseStatus_t[v_ccdlID_u16];
        if((VALID == l_peerBase_t.valid_u16) &&
           (l_peerBase_t.frameCnt_u16 != l_peerBase_t.frameCntLast_u16))
        {
            l_rslt_u16 = VALID;
        }
    }

    return l_rslt_u16;
}
/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLKZZZExtStatusGet
 *
 * 【功能描述】获取最近一轮KZZZ扩展页的完整性与新鲜度状态。
 *
 * 【输入参数说明】v_ccdlID_u16  ---- CCDL链路ID
 * 【输出参数说明】NONE
 * 【其他说明】    供KZZZ余度接管链使用，不承载基础帧业务语义。
 * 【返回】        CCDLExtStatus_t
 */
/* ***************************************************************** */
CCDLExtStatus_t CommCCDLKZZZExtStatusGet(Uint16 v_ccdlID_u16, Uint16 v_kzzzID_u16)
{
    CCDLExtStatus_t l_rslt_t;
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    if((v_ccdlID_u16 < COMM_CCDL_NUM) && (v_kzzzID_u16 < COMM429_KZZZ_NUM))
    {
        l_rslt_t = s_ccdlKZZZExtStatus_t[v_ccdlID_u16][v_kzzzID_u16];
        l_rslt_t.dataState_u16 = s_CCDLCommInfo_t[v_ccdlID_u16].rxState_u16;
    }

    return l_rslt_t;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLRIUOrigDataGet
 *
 * 【功能描述】获取某条CCDL链路上缓存的RIU原始429字镜像。
 *
 * 【输入参数说明】v_ccdlID_u16  ---- CCDL链路ID
 * 【输出参数说明】NONE
 * 【其他说明】    数据来自RIU扩展分页帧接收缓存，不回写到本地RIU接收链。
 * 【返回】        RIU429OrigData_t
 */
/* ***************************************************************** */
RIU429OrigData_t CommCCDLRIUOrigDataGet(Uint16 v_ccdlID_u16)
{
    RIU429OrigData_t l_rslt_t;
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    if(v_ccdlID_u16 < COMM_CCDL_NUM)
    {
        l_rslt_t = s_ccdlRIUOrigData_t[v_ccdlID_u16];
    }

    return l_rslt_t;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLKZZZOrigDataGet
 *
 * 【功能描述】获取某条CCDL链路上缓存的KZZZ原始429字镜像。
 *
 * 【输入参数说明】v_ccdlID_u16  ---- CCDL链路ID
 * 【输出参数说明】NONE
 * 【其他说明】    数据来自扩展分页帧接收缓存，不回写到现有 Comm429KZZZ 本地接收链。
 * 【返回】        KZZZ429OrigData_t
 */
/* ***************************************************************** */
KZZZ429OrigData_t CommCCDLKZZZOrigDataGet(Uint16 v_ccdlID_u16, Uint16 v_kzzzID_u16)
{
    KZZZ429OrigData_t l_rslt_t;
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    if((v_ccdlID_u16 < COMM_CCDL_NUM) && (v_kzzzID_u16 < COMM429_KZZZ_NUM))
    {
        l_rslt_t = s_ccdlKZZZOrigData_t[v_ccdlID_u16][v_kzzzID_u16];
    }

    return l_rslt_t;
}
/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLWToRsBuff
 *
 * 【功能描述】将CCDL底层接收到的字节流搬运到软件缓存。
 *
 * 【输入参数说明】v_ccdlID_u16  ---- CCDL链路ID
 *              v_pBuff_u8    ---- 待读入数据
 *              v_buffLen_u16 ---- 数据长度
 * 【输出参数说明】NONE
 * 【其他说明】    该函数仅做帧头过滤和缓存写入，不负责整帧判定。
 * 【返回】        NONE
 */
/* ***************************************************************** */
void CommCCDLWToRsBuff(Uint16 v_ccdlID_u16, Uint16 *v_pBuff_u8, Uint16 v_buffLen_u16)
{
    Uint16 l_len_u16 = 0U;
    Uint16 l_ii_u16 = 0U;
    Uint16 l_headErrCnt_u16 = 0U;

    if((v_ccdlID_u16 < COMM_CCDL_NUM) && (NULL != v_pBuff_u8) && (0U != v_buffLen_u16))
    {
        /* 先记录底层字节到达情况，再做软件缓存拼帧。 */
        s_CCDLCommInfo_t[v_ccdlID_u16].rxBytesCount_u16 += v_buffLen_u16;
        s_CCDLCommInfo_t[v_ccdlID_u16].rxBytesTime_u32 = sysTime();

        for(l_ii_u16 = 0U; l_ii_u16 < v_buffLen_u16; l_ii_u16++)
        {
            l_len_u16 = s_CCDLCommBuff_t[v_ccdlID_u16].index_u16;

            if(l_len_u16 < s_CCDLCommConf_t[v_ccdlID_u16].rxBuffLen_u16)
            {
                l_headErrCnt_u16 = 0U;

                if((0U == l_len_u16) &&
                   (s_CCDLCommConf_t[v_ccdlID_u16].rxFrameHead_1_u16 != (v_pBuff_u8[l_ii_u16] & 0xFFU)))
                {
                    l_headErrCnt_u16 += 1U;
                }

                if((1U == l_len_u16) &&
                   (s_CCDLCommConf_t[v_ccdlID_u16].rxFrameHead_2_u16 != (v_pBuff_u8[l_ii_u16] & 0xFFU)))
                {
                    /* 第二个帧头字节不匹配时，退回到“重新找帧头1”的状态。 */
                    l_len_u16 = 0U;
                    s_CCDLCommBuff_t[v_ccdlID_u16].index_u16 = 0U;

                    if(s_CCDLCommConf_t[v_ccdlID_u16].rxFrameHead_1_u16 != (v_pBuff_u8[l_ii_u16] & 0xFFU))
                    {
                        l_headErrCnt_u16 += 1U;
                    }
                }

                if(0U == l_headErrCnt_u16)
                {
                    s_CCDLCommBuff_t[v_ccdlID_u16].commBuff_u16[l_len_u16] = v_pBuff_u8[l_ii_u16] & 0xFFU;
                    s_CCDLCommBuff_t[v_ccdlID_u16].index_u16 += 1U;
                }
            }
            else
            {
                s_CCDLCommBuff_t[v_ccdlID_u16].overCount_u16 += (Uint16)(v_buffLen_u16 - l_ii_u16);
                break;
            }
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLChecksumCalcU8
 *
 * 【功能描述】计算发送缓存的低8位补码校验。
 *
 * 【输入参数说明】vp_buff_u8 ---- 待校验字节数组
 *              v_len_u16  ---- 参与校验的字节数
 * 【输出参数说明】NONE
 * 【其他说明】    基础帧、RIU扩展帧和KZZZ扩展帧均使用同一校验口径。
 * 【返回】        低8位补码校验值
 */
/* ***************************************************************** */
static Uint16 CommCCDLChecksumCalcU8(const Uint8 *vp_buff_u8, Uint16 v_len_u16)
{
    Uint16 l_sum_u16 = 0U;
    Uint16 l_ii_u16 = 0U;

    if(NULL != vp_buff_u8)
    {
        for(l_ii_u16 = 0U; l_ii_u16 < v_len_u16; l_ii_u16++)
        {
            l_sum_u16 = l_sum_u16 + (vp_buff_u8[l_ii_u16] & 0xFFU);
        }
    }

    return (((~l_sum_u16) + 1U) & 0xFFU);
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLChecksumCalcU16
 *
 * 【功能描述】计算接收缓存中某段数据的低8位补码校验。
 *
 * 【输入参数说明】vp_buff_u16      ---- 接收缓存
 *              v_startIndex_u16 ---- 起始索引
 *              v_len_u16        ---- 参与校验的长度
 * 【输出参数说明】NONE
 * 【其他说明】    接收扫描器通过该函数统一校验基础帧和扩展帧。
 * 【返回】        低8位补码校验值
 */
/* ***************************************************************** */
static Uint16 CommCCDLChecksumCalcU16(const Uint16 *vp_buff_u16, Uint16 v_startIndex_u16, Uint16 v_len_u16)
{
    Uint16 l_sum_u16 = 0U;
    Uint16 l_ii_u16 = 0U;

    if(NULL != vp_buff_u16)
    {
        for(l_ii_u16 = 0U; l_ii_u16 < v_len_u16; l_ii_u16++)
        {
            l_sum_u16 = l_sum_u16 + (vp_buff_u16[v_startIndex_u16 + l_ii_u16] & 0xFFU);
        }
    }

    return (((~l_sum_u16) + 1U) & 0xFFU);
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLRxStateCheck
 *
 * 【功能描述】依据最近收字节时间和收帧时间刷新链路状态。
 *
 * 【输入参数说明】v_ccdlID_u16 ---- CCDL链路ID
 * 【输出参数说明】NONE
 * 【其他说明】    保留旧判据口径，避免初始化/PuBIT/运行期状态判断含义变化。
 * 【返回】        NONE
 */
/* ***************************************************************** */
static void CommCCDLRxStateCheck(Uint16 v_ccdlID_u16)
{
    Uint16 l_rData_u16 = COMM_CCDL_RX_OK;

    if(v_ccdlID_u16 < COMM_CCDL_NUM)
    {
        s_CCDLCommInfo_t[v_ccdlID_u16].checkTime_u32 = sysTime();

        /* 字节超时说明底层链路可能已经无数据输入。 */
        if((s_CCDLCommInfo_t[v_ccdlID_u16].checkTime_u32 -
            s_CCDLCommInfo_t[v_ccdlID_u16].rxBytesTime_u32) >= COMM_CCDL_RX_TIMEOUT_MS)
        {
            l_rData_u16 = COMM_CCDL_RX_NO_BYTES_ERR;
        }
        /* 有字节但长时间收不到合法帧，说明当前更偏向帧级异常。 */
        else if((s_CCDLCommInfo_t[v_ccdlID_u16].checkTime_u32 -
                 s_CCDLCommInfo_t[v_ccdlID_u16].rxFrameTime_u32) >= COMM_CCDL_FRAME_TIMEOUT_MS)
        {
            l_rData_u16 = COMM_CCDL_RX_NO_FRAMES_ERR;
        }

        if(COMM_CCDL_RX_OK != l_rData_u16)
        {
            s_CCDLCommInfo_t[v_ccdlID_u16].errCnt_u32 += 1UL;
            s_CCDLCommInfo_t[v_ccdlID_u16].errCntSum_u32 += 1UL;

            if(s_CCDLCommInfo_t[v_ccdlID_u16].errCnt_u32 > s_CCDLCommInfo_t[v_ccdlID_u16].errCntMax_u32)
            {
                s_CCDLCommInfo_t[v_ccdlID_u16].errCntMax_u32 = s_CCDLCommInfo_t[v_ccdlID_u16].errCnt_u32;
            }
        }
        else
        {
            s_CCDLCommInfo_t[v_ccdlID_u16].errCnt_u32 = 0UL;
        }

        s_CCDLCommInfo_t[v_ccdlID_u16].rxState_u16 = l_rData_u16;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLBaseFramePack
 *
 * 【功能描述】打包纯基础状态CCDL基础帧。
 *
 * 【输入参数说明】v_pBuff_u8 ---- 输出缓存
 *              v_len_u16   ---- 缓存长度
 * 【输出参数说明】NONE
 * 【其他说明】    基础帧只承载板间状态，不再承载RIU/KZZZ业务镜像。
 * 【返回】        NONE
 */
/* ***************************************************************** */
static void CommCCDLBaseFramePack(Uint8 *v_pBuff_u8, Uint16 v_len_u16)
{
    static Uint16 l_s_txFrmCnt_u16 = 0U;
    const ConData_t *lc_p_conData_t = NULL;
    SpeData_t l_nvmData_t;
    union SoftwVData l_SoftwVData_un16;
    Uint16 l_temp_u16 = 0U;
    Uint8 l_ctrlInfo_u8 = 0U;

    if((NULL != v_pBuff_u8) && (v_len_u16 >= COMM_CCDL_TX_FRAM_LEN))
    {
        lc_p_conData_t = ConDataGet();

        v_pBuff_u8[0] = COMM_CCDL_FRAME_HEAD1;
        v_pBuff_u8[1] = COMM_CCDL_FRAME_HEAD2;
        v_pBuff_u8[2] = l_s_txFrmCnt_u16 & 0xFFU;
        v_pBuff_u8[3] = lc_p_conData_t->sysState_u16;
        v_pBuff_u8[4] = lc_p_conData_t->ChType_u16;

        /* byte[5] 固定上报冷启动默认主控协商值，启动期冲突时按 CH1 上报值收敛。 */
        SpeDataGet(SPE_DATA_DINDEX_CH_TYPE_CODE, &l_nvmData_t);
        v_pBuff_u8[5] = l_nvmData_t.dataU_u16;

        s_ccdlTxRandData_u16[COMM_CCDL_SCI] = RandomDataGenerate();
        v_pBuff_u8[6] = s_ccdlTxRandData_u16[COMM_CCDL_SCI];

        l_temp_u16 = HARD_XINT_UINT16(CPLD_ADDR_R_CPLD_HEART);
        v_pBuff_u8[7] = l_temp_u16 & 0xFFU;

        l_SoftwVData_un16 = SoftwVDataGet();
        v_pBuff_u8[8] = l_SoftwVData_un16.all & 0xFFU;
        v_pBuff_u8[9] = (l_SoftwVData_un16.all >> 8U) & 0xFFU;
        if(ROLE_MASTER == lc_p_conData_t->runtimeRole_u16)
        {
            l_ctrlInfo_u8 |= (Uint8)(0x01U << COMM_CCDL_CTRLINFO_OWNER_BIT);
        }
        if(CON_OUT_STATE_VALID == lc_p_conData_t->ConOutData_t.conOutState_u16)
        {
            l_ctrlInfo_u8 |= (Uint8)(0x01U << COMM_CCDL_CTRLINFO_CONOUT_BIT);
        }
        if((CHV_VALID == lc_p_conData_t->ConOutData_t.localChvPermit_u16) &&
           (CHV_VALID == lc_p_conData_t->CHVIn_un16.bit.myCHV_u16))
        {
            l_ctrlInfo_u8 |= (Uint8)(0x01U << COMM_CCDL_CTRLINFO_LOCAL_HEALTH_BIT);
        }
        v_pBuff_u8[10] = (Uint8)(l_ctrlInfo_u8 & COMM_CCDL_CTRLINFO_VALID_MASK);
        v_pBuff_u8[11] = 0U;

        l_temp_u16 = HARD_XINT_UINT16(CPLD_ADDR_R_CPLD_VER);
        v_pBuff_u8[12] = l_temp_u16 & 0xFFU;
        v_pBuff_u8[13] = (l_temp_u16 >> 8U) & 0xFFU;

        v_pBuff_u8[v_len_u16 - 1U] = CommCCDLChecksumCalcU8(v_pBuff_u8, v_len_u16 - 1U);
        l_s_txFrmCnt_u16 = (l_s_txFrmCnt_u16 + 1U) & 0xFFU;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLRIUExtFramePack
 *
 * 【功能描述】RIU扩展帧打包
 *
 * 【输入参数说明】v_pBuff_u8 ---- 输出缓存
 *             v_page_u16 ---- 页号
 *             v_srcRiuID_u16 ---- RIU源ID
 * 【输出参数说明】NONE
 * 【其他说明】把本地RIU429原始字打包成扩展分页帧
 * 【返回】NONE
 */
/* ***************************************************************** */
static void CommCCDLRIUExtFramePack(Uint8 *v_pBuff_u8, Uint16 v_page_u16, Uint16 v_srcRiuID_u16)
{
    Uint16 l_ii_u16 = 0U;
    Uint16 l_startIndex_u16 = 0U;
    Uint16 l_srcIndex_u16 = 0U;
    Uint16 l_frameCnt_u16 = 0U;
    RIU429OrigData_t l_RIUOrigData_t;

    if((NULL != v_pBuff_u8) &&
       (v_page_u16 < COMM_CCDL_EXT_PAGE_NUM) &&
       (v_srcRiuID_u16 < COMM429_RIU_NUM))
    {
        l_RIUOrigData_t = Comm429RIUOrigDataGet(v_srcRiuID_u16);
        l_startIndex_u16 = v_page_u16 * COMM_CCDL_EXT_PAGE_WORD_NUM;
        l_frameCnt_u16 = CommCCDLExtFrameCntGet(s_ccdlRIUExtFrameCnt_u16, v_page_u16);
        /* 页窗口固定为 [page*9, page*9+8]，与接收侧按同样公式回填镜像数组。 */

        v_pBuff_u8[0] = COMM_CCDL_FRAME_HEAD1;
        v_pBuff_u8[1] = COMM_CCDL_FRAME_HEAD2;
        v_pBuff_u8[2] = l_frameCnt_u16 & 0xFFU;

        if(0U == v_page_u16)
        {
            v_pBuff_u8[3] = COMM_CCDL_RIU_EXT_PAGE0_ID;
        }
        else if(1U == v_page_u16)
        {
            v_pBuff_u8[3] = COMM_CCDL_RIU_EXT_PAGE1_ID;
        }
        else
        {
            v_pBuff_u8[3] = COMM_CCDL_RIU_EXT_PAGE2_ID;
        }

        for(l_ii_u16 = 0U; l_ii_u16 < COMM_CCDL_EXT_PAGE_WORD_NUM; l_ii_u16++)
        {
            Uint32 l_data_u32 = 0UL;

            l_srcIndex_u16 = l_startIndex_u16 + l_ii_u16;
            if(l_srcIndex_u16 < RIU_R_DATA_NUM)
            {
                l_data_u32 = l_RIUOrigData_t.Orig_Rx_t[l_srcIndex_u16].OrigData_u32;
            }

            v_pBuff_u8[4U + 4U * l_ii_u16] = (l_data_u32 >> 0U) & 0xFFU;
            v_pBuff_u8[5U + 4U * l_ii_u16] = (l_data_u32 >> 8U) & 0xFFU;
            v_pBuff_u8[6U + 4U * l_ii_u16] = (l_data_u32 >> 16U) & 0xFFU;
            v_pBuff_u8[7U + 4U * l_ii_u16] = (l_data_u32 >> 24U) & 0xFFU;
        }

        v_pBuff_u8[COMM_CCDL_RIU_EXT_FRAME_LEN - 1U] =
            CommCCDLChecksumCalcU8(v_pBuff_u8, COMM_CCDL_RIU_EXT_FRAME_LEN - 1U);

        if(0U == v_page_u16)
        {
            s_ccdlRIUExtFrameCnt_u16 = l_frameCnt_u16;
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLKZZZExtFrameTypeDecode
 *
 * 【功能描述】解析KZZZ扩展帧类型，得到页号和吊舱源ID。
 *
 * 【输入参数说明】v_frameType_u16 ---- 扩展帧类型字节
 *              vp_page_u16     ---- 输出页号
 *              vp_srcKzzzID_u16 ---- 输出吊舱源ID
 * 【输出参数说明】NONE
 * 【其他说明】    返回VALID表示识别为KZZZ扩展帧，否则表示不是KZZZ扩展帧。
 * 【返回】        VALID / INVALID
 */
/* ***************************************************************** */
static Uint16 CommCCDLKZZZExtFrameTypeDecode(Uint16 v_frameType_u16, Uint16 *vp_page_u16, Uint16 *vp_srcKzzzID_u16)
{
    if((NULL == vp_page_u16) || (NULL == vp_srcKzzzID_u16))
    {
        return INVALID;
    }

    if((v_frameType_u16 >= COMM_CCDL_KZZZ1_EXT_PAGE0_ID) && (v_frameType_u16 <= COMM_CCDL_KZZZ1_EXT_PAGE2_ID))
    {
        *vp_srcKzzzID_u16 = COMM429_KZZZ_1;
        /* page号直接由 frameType 偏移恢复，保持与发送侧“起始ID + page”同构。 */
        *vp_page_u16 = (Uint16)(v_frameType_u16 - COMM_CCDL_KZZZ1_EXT_PAGE0_ID);
        return VALID;
    }

    if((v_frameType_u16 >= COMM_CCDL_KZZZ2_EXT_PAGE0_ID) && (v_frameType_u16 <= COMM_CCDL_KZZZ2_EXT_PAGE2_ID))
    {
        *vp_srcKzzzID_u16 = COMM429_KZZZ_2;
        *vp_page_u16 = (Uint16)(v_frameType_u16 - COMM_CCDL_KZZZ2_EXT_PAGE0_ID);
        return VALID;
    }

    return INVALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLKZZZExtFramePack
 *
 * 【功能描述】打包KZZZ原始429字扩展分页帧。
 *
 * 【输入参数说明】v_pBuff_u8        ---- 输出缓存
 *              v_page_u16        ---- 页号，0/1
 *              v_srcKzzzID_u16   ---- KZZZ数据源ID
 * 【输出参数说明】NONE
 * 【其他说明】    page0/page1/page2 分别承载固定索引窗口，不再与旧两页方案兼容。
 * 【返回】        NONE
 */
/* ***************************************************************** */
static void CommCCDLKZZZExtFramePack(Uint8 *v_pBuff_u8, Uint16 v_page_u16, Uint16 v_srcKzzzID_u16)
{
    Uint16 l_ii_u16 = 0U;
    Uint16 l_startIndex_u16 = 0U;
    Uint16 l_srcIndex_u16 = 0U;
    Uint16 l_frameCnt_u16 = 0U;
    KZZZ429OrigData_t l_KZZZOrigData_t;

    if((NULL != v_pBuff_u8) &&
       (v_page_u16 < COMM_CCDL_EXT_PAGE_NUM) &&
       (v_srcKzzzID_u16 < COMM429_KZZZ_NUM))
    {
        l_KZZZOrigData_t = Comm429KzzzRxOrigDataGet(v_srcKzzzID_u16);
        l_startIndex_u16 = v_page_u16 * COMM_CCDL_EXT_PAGE_WORD_NUM;
        l_frameCnt_u16 = CommCCDLExtFrameCntGet(s_ccdlKZZZExtFrameCnt_u16, v_page_u16);

        v_pBuff_u8[0] = COMM_CCDL_FRAME_HEAD1;
        v_pBuff_u8[1] = COMM_CCDL_FRAME_HEAD2;
        v_pBuff_u8[2] = l_frameCnt_u16 & 0xFFU;
        v_pBuff_u8[3] = CommCCDLKZZZExtFrameTypeGet(v_page_u16, v_srcKzzzID_u16) & 0xFFU;

        /* 扩展帧按固定索引顺序镜像KZZZ原始字，不再额外携带label。 */
        for(l_ii_u16 = 0U; l_ii_u16 < COMM_CCDL_EXT_PAGE_WORD_NUM; l_ii_u16++)
        {
            Uint32 l_data_u32 = 0UL;

            l_srcIndex_u16 = l_startIndex_u16 + l_ii_u16;
            if(l_srcIndex_u16 < KZZZ_R_DATA_NUM)
            {
                l_data_u32 = l_KZZZOrigData_t.Orig_Rx_t[l_srcIndex_u16].OrigData_u32;
            }

            v_pBuff_u8[4U + 4U * l_ii_u16] = (l_data_u32 >> 0U) & 0xFFU;
            v_pBuff_u8[5U + 4U * l_ii_u16] = (l_data_u32 >> 8U) & 0xFFU;
            v_pBuff_u8[6U + 4U * l_ii_u16] = (l_data_u32 >> 16U) & 0xFFU;
            v_pBuff_u8[7U + 4U * l_ii_u16] = (l_data_u32 >> 24U) & 0xFFU;
        }

        v_pBuff_u8[COMM_CCDL_KZZZ_EXT_FRAME_LEN - 1U] =
            CommCCDLChecksumCalcU8(v_pBuff_u8, COMM_CCDL_KZZZ_EXT_FRAME_LEN - 1U);

        if(0U == v_page_u16)
        {
            s_ccdlKZZZExtFrameCnt_u16 = l_frameCnt_u16;
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLRuntimeTxEnqueue
 *
 * 【功能描述】将运行期待发送帧压入SCI发送队列。
 *
 * 【输入参数说明】vp_buff_u8 ---- 待入队帧数据
 *              v_len_u16  ---- 帧长度
 * 【输出参数说明】NONE
 * 【其他说明】    队列满时当前帧直接丢弃并累计丢帧计数，不覆盖旧帧。
 * 【返回】        VALID/INVALID
 */
/* ***************************************************************** */
static Uint16 CommCCDLRuntimeTxEnqueue(const Uint8 *vp_buff_u8, Uint16 v_len_u16)
{
    Uint16 l_rslt_u16 = INVALID;
    Uint16 l_ii_u16 = 0U;

    if((NULL != vp_buff_u8) &&
       (v_len_u16 > 0U) &&
       (v_len_u16 <= COMM_CCDL_TX_FRAM_LEN_MAX))
    {
        if(s_ccdlSciTxCount_u16 < COMM_CCDL_SCI_TX_QUEUE_DEPTH)
        {
            /* 运行期发送队列只缓存完整帧，不做半帧拼接。 */
            for(l_ii_u16 = 0U; l_ii_u16 < v_len_u16; l_ii_u16++)
            {
                s_ccdlSciTxQueue_u8[s_ccdlSciTxWr_u16][l_ii_u16] = vp_buff_u8[l_ii_u16];
            }

            for(l_ii_u16 = v_len_u16; l_ii_u16 < COMM_CCDL_TX_FRAM_LEN_MAX; l_ii_u16++)
            {
                s_ccdlSciTxQueue_u8[s_ccdlSciTxWr_u16][l_ii_u16] = 0U;
            }

            s_ccdlSciTxLen_u16[s_ccdlSciTxWr_u16] = v_len_u16;
            s_ccdlSciTxWr_u16 = (s_ccdlSciTxWr_u16 + 1U) % COMM_CCDL_SCI_TX_QUEUE_DEPTH;
            s_ccdlSciTxCount_u16 += 1U;
            l_rslt_u16 = VALID;
        }
        else
        {
            /* 队列满时宁可丢当前周期新帧，也不覆盖已排队旧帧。 */
            s_ccdlSciTxDropCnt_u32 += 1UL;
        }
    }

    return l_rslt_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLRuntimeTxQueueReset
 *
 * 【功能描述】复位运行期SCI发送队列状态。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】    仅清运行期队列，不改变基础帧协议内容。
 * 【返回】        NONE
 */
/* ***************************************************************** */
static void CommCCDLRuntimeTxQueueReset(void)
{
    Uint16 l_ii_u16 = 0U;
    Uint16 l_jj_u16 = 0U;

    s_ccdlSciTxWr_u16 = 0U;
    s_ccdlSciTxRd_u16 = 0U;
    s_ccdlSciTxCount_u16 = 0U;
    s_ccdlSciTxActiveLen_u16 = 0U;
    s_ccdlSciTxActiveMode_u16 = COMM_CCDL_TX_MODE_NONE;

    /* 队列复位时显式清空内容，避免调试观察时残留旧帧数据干扰判断。 */
    for(l_ii_u16 = 0U; l_ii_u16 < COMM_CCDL_SCI_TX_QUEUE_DEPTH; l_ii_u16++)
    {
        s_ccdlSciTxLen_u16[l_ii_u16] = 0U;

        for(l_jj_u16 = 0U; l_jj_u16 < COMM_CCDL_TX_FRAM_LEN_MAX; l_jj_u16++)
        {
            s_ccdlSciTxQueue_u8[l_ii_u16][l_jj_u16] = 0U;
        }
    }
}
/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLFrameSendToCPLD
 *
 * 【功能描述】将已打包好的CCDL帧整帧送往CPLD链路。
 *
 * 【输入参数说明】vp_buff_u8 ---- 待发送帧
 *              v_len_u16  ---- 帧长度
 * 【输出参数说明】NONE
 * 【其他说明】    运行期基础帧和扩展帧都通过该函数镜像到CPLD。
 * 【返回】        NONE
 */
/* ***************************************************************** */
/* ***************************************************************** */
static void CommCCDLFrameSendToCPLD(const Uint8 *vp_buff_u8, Uint16 v_len_u16)
{
    Uint16 l_ii_u16 = 0U;
    Uint16 l_tempCcdlTxBuff_u16[COMM_CCDL_TX_FRAM_LEN_MAX];
    memset(l_tempCcdlTxBuff_u16, 0, sizeof(l_tempCcdlTxBuff_u16));

    if((NULL != vp_buff_u8) && (v_len_u16 <= COMM_CCDL_TX_FRAM_LEN_MAX))
    {
        /* CPLD侧仍按整帧口径收发，因此这里直接做一次性镜像。 */
        for(l_ii_u16 = 0U; l_ii_u16 < v_len_u16; l_ii_u16++)
        {
            l_tempCcdlTxBuff_u16[l_ii_u16] = vp_buff_u8[l_ii_u16];
        }

        Ccdl422SendBuff(s_CCDLCommIDConf_u16[COMM_CCDL_CPLD], l_tempCcdlTxBuff_u16, v_len_u16);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLBaseFrameDecode
 *
 * 【功能描述】按基础帧格式解析一帧有效CCDL数据。
 *
 * 【输入参数说明】v_ccdlID_u16 ---- CCDL链路ID
 *              vp_rxBuff_u16 ---- 接收缓存
 *              v_sIndex_u16  ---- 帧起始索引
 * 【输出参数说明】NONE
 * 【其他说明】    该解码器只负责基础状态字段，不再解析RIU业务镜像。
 * 【返回】        NONE
 */
/* ***************************************************************** */
static void CommCCDLBaseFrameDecode(Uint16 v_ccdlID_u16, const Uint16 *vp_rxBuff_u16, Uint16 v_sIndex_u16)
{
    Uint16 l_tempL_u16 = 0U;
    Uint16 l_tempH_u16 = 0U;

    if((v_ccdlID_u16 < COMM_CCDL_NUM) &&
       (NULL != vp_rxBuff_u16) &&
       ((v_sIndex_u16 + COMM_CCDL_BASE_FRAME_LEN) <= COMM_CCDL_RX_BUFF_LEN))
    {
        /* 基础帧负责初始化、PuBIT和板间状态仲裁，不再掺杂业务镜像。 */
        s_ccdlRxBaseData_t[v_ccdlID_u16].framCntLast_u16 =
            s_ccdlRxBaseData_t[v_ccdlID_u16].framCnt_u16;
        s_ccdlRxBaseData_t[v_ccdlID_u16].framCnt_u16 = vp_rxBuff_u16[v_sIndex_u16 + 2U];
        s_ccdlRxBaseData_t[v_ccdlID_u16].sysState_u16 = vp_rxBuff_u16[v_sIndex_u16 + 3U];
        s_ccdlRxBaseData_t[v_ccdlID_u16].ChType_u16 = vp_rxBuff_u16[v_sIndex_u16 + 4U];
        /* 启动期默认主控协商值，运行期主备切换不直接使用该字段。 */
        s_ccdlRxBaseData_t[v_ccdlID_u16].ChTypeNvmData_u16 = vp_rxBuff_u16[v_sIndex_u16 + 5U];
        s_ccdlRxBaseData_t[v_ccdlID_u16].randData_u16 = vp_rxBuff_u16[v_sIndex_u16 + 6U];
        s_ccdlRxBaseData_t[v_ccdlID_u16].CPLDHeart_u16 = vp_rxBuff_u16[v_sIndex_u16 + 7U];

        l_tempL_u16 = vp_rxBuff_u16[v_sIndex_u16 + 8U];
        l_tempH_u16 = vp_rxBuff_u16[v_sIndex_u16 + 9U];
        s_ccdlRxBaseData_t[v_ccdlID_u16].softV_DSP_u16 = (l_tempH_u16 << 8U) + l_tempL_u16;

        l_tempL_u16 = vp_rxBuff_u16[v_sIndex_u16 + 10U];
        l_tempH_u16 = vp_rxBuff_u16[v_sIndex_u16 + 11U];
        s_ccdlRxBaseData_t[v_ccdlID_u16].ctrlInfo_u16 = (l_tempH_u16 << 8U) + l_tempL_u16;

        l_tempL_u16 = vp_rxBuff_u16[v_sIndex_u16 + 12U];
        l_tempH_u16 = vp_rxBuff_u16[v_sIndex_u16 + 13U];
        s_ccdlRxBaseData_t[v_ccdlID_u16].softV_CPLD_u16 = (l_tempH_u16 << 8U) + l_tempL_u16;

        /* 基础帧状态统一收敛到一份最近快照，供主备/热重连直接读取。 */
        s_peerBaseStatus_t[v_ccdlID_u16].valid_u16 = VALID;
        s_peerBaseStatus_t[v_ccdlID_u16].lastRxTime_u32 = sysTime();
        s_peerBaseStatus_t[v_ccdlID_u16].frameCntLast_u16 = s_ccdlRxBaseData_t[v_ccdlID_u16].framCntLast_u16;
        s_peerBaseStatus_t[v_ccdlID_u16].frameCnt_u16 = s_ccdlRxBaseData_t[v_ccdlID_u16].framCnt_u16;
        s_peerBaseStatus_t[v_ccdlID_u16].sysState_u16 = s_ccdlRxBaseData_t[v_ccdlID_u16].sysState_u16;
        s_peerBaseStatus_t[v_ccdlID_u16].chType_u16 = s_ccdlRxBaseData_t[v_ccdlID_u16].ChType_u16;
        s_peerBaseStatus_t[v_ccdlID_u16].preferredMasterChId_u16 = s_ccdlRxBaseData_t[v_ccdlID_u16].ChTypeNvmData_u16;
        s_peerBaseStatus_t[v_ccdlID_u16].cpldHeart_u16 = s_ccdlRxBaseData_t[v_ccdlID_u16].CPLDHeart_u16;
        s_peerBaseStatus_t[v_ccdlID_u16].softV_DSP_u16 = s_ccdlRxBaseData_t[v_ccdlID_u16].softV_DSP_u16;
        s_peerBaseStatus_t[v_ccdlID_u16].ctrlInfo_u16 = s_ccdlRxBaseData_t[v_ccdlID_u16].ctrlInfo_u16;
        s_peerBaseStatus_t[v_ccdlID_u16].softV_CPLD_u16 = s_ccdlRxBaseData_t[v_ccdlID_u16].softV_CPLD_u16;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLRIUExtFrameDecode
 *
 * 【功能描述】解析RIU扩展分页帧并刷新镜像缓存。
 *
 * 【输入参数说明】v_ccdlID_u16 ---- CCDL链路ID
 *              vp_rxBuff_u16 ---- 接收缓存
 *              v_page_u16    ---- 页号，0/1/2
 *              v_sIndex_u16  ---- 帧起始索引
 * 【输出参数说明】NONE
 * 【其他说明】    仅更新CCDL内部RIU镜像，不回写基础帧结构。
 * 【返回】        NONE
 */
/* ***************************************************************** */
static void CommCCDLRIUExtFrameDecode(Uint16 v_ccdlID_u16, const Uint16 *vp_rxBuff_u16, Uint16 v_page_u16, Uint16 v_sIndex_u16)
{
    Uint16 l_ii_u16 = 0U;
    Uint16 l_destIndex_u16 = 0U;
    Uint32 l_data_u32 = 0UL;

    if((v_ccdlID_u16 < COMM_CCDL_NUM) &&
       (NULL != vp_rxBuff_u16) &&
       (v_page_u16 < COMM_CCDL_EXT_PAGE_NUM))
    {
        for(l_ii_u16 = 0U; l_ii_u16 < COMM_CCDL_EXT_PAGE_WORD_NUM; l_ii_u16++)
        {
            l_destIndex_u16 = (Uint16)(v_page_u16 * COMM_CCDL_EXT_PAGE_WORD_NUM) + l_ii_u16;

            if(l_destIndex_u16 < RIU_R_DATA_NUM)
            {
                l_data_u32 = (Uint32)(vp_rxBuff_u16[v_sIndex_u16 + 4U + 4U * l_ii_u16] & 0xFFU);
                l_data_u32 += (Uint32)(vp_rxBuff_u16[v_sIndex_u16 + 5U + 4U * l_ii_u16] & 0xFFU) << 8U;
                l_data_u32 += (Uint32)(vp_rxBuff_u16[v_sIndex_u16 + 6U + 4U * l_ii_u16] & 0xFFU) << 16U;
                l_data_u32 += (Uint32)(vp_rxBuff_u16[v_sIndex_u16 + 7U + 4U * l_ii_u16] & 0xFFU) << 24U;

                s_ccdlRIUOrigData_t[v_ccdlID_u16].Orig_Rx_t[l_destIndex_u16].OrigData_u32 = l_data_u32;
                s_ccdlRIUOrigData_t[v_ccdlID_u16].Orig_Rx_t[l_destIndex_u16].Cnt_u16 += 1U;
            }
        }

        CommCCDLExtStatusRefresh(&s_ccdlRIUExtStatus_t[v_ccdlID_u16],
                                 (vp_rxBuff_u16[v_sIndex_u16 + 2U] & 0xFFU),
                                 v_page_u16);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLKZZZExtFrameDecode
 *
 * 【功能描述】解析KZZZ扩展分页帧并刷新镜像缓存。
 *
 * 【输入参数说明】v_ccdlID_u16 ---- CCDL链路ID
 *              v_kzzzID_u16 ---- 吊舱源ID
 *              vp_rxBuff_u16 ---- 接收缓存
 *              v_page_u16    ---- 页号，0/1/2
 *              v_sIndex_u16  ---- 帧起始索引
 * 【输出参数说明】NONE
 * 【其他说明】    仅更新CCDL内部KZZZ镜像，不影响本地 Comm429KZZZ 接收链。
 * 【返回】        NONE
 */
/* ***************************************************************** */
static void CommCCDLKZZZExtFrameDecode(Uint16 v_ccdlID_u16,
                                       Uint16 v_kzzzID_u16,
                                       const Uint16 *vp_rxBuff_u16,
                                       Uint16 v_page_u16,
                                       Uint16 v_sIndex_u16)
{
    Uint16 l_ii_u16 = 0U;
    Uint16 l_destIndex_u16 = 0U;
    Uint32 l_data_u32 = 0UL;

    if((v_ccdlID_u16 < COMM_CCDL_NUM) &&
       (v_kzzzID_u16 < COMM429_KZZZ_NUM) &&
       (NULL != vp_rxBuff_u16) &&
       (v_page_u16 < COMM_CCDL_EXT_PAGE_NUM))
    {
        for(l_ii_u16 = 0U; l_ii_u16 < COMM_CCDL_EXT_PAGE_WORD_NUM; l_ii_u16++)
        {
            l_destIndex_u16 = (Uint16)(v_page_u16 * COMM_CCDL_EXT_PAGE_WORD_NUM) + l_ii_u16;

            if(l_destIndex_u16 < KZZZ_R_DATA_NUM)
            {
                /* 扩展页只刷新本页覆盖的原始字，并累计每个索引的接收计数。 */
                l_data_u32 = (Uint32)(vp_rxBuff_u16[v_sIndex_u16 + 4U + 4U * l_ii_u16] & 0xFFU);
                l_data_u32 += (Uint32)(vp_rxBuff_u16[v_sIndex_u16 + 5U + 4U * l_ii_u16] & 0xFFU) << 8U;
                l_data_u32 += (Uint32)(vp_rxBuff_u16[v_sIndex_u16 + 6U + 4U * l_ii_u16] & 0xFFU) << 16U;
                l_data_u32 += (Uint32)(vp_rxBuff_u16[v_sIndex_u16 + 7U + 4U * l_ii_u16] & 0xFFU) << 24U;

                s_ccdlKZZZOrigData_t[v_ccdlID_u16][v_kzzzID_u16].Orig_Rx_t[l_destIndex_u16].OrigData_u32 = l_data_u32;
                s_ccdlKZZZOrigData_t[v_ccdlID_u16][v_kzzzID_u16].Orig_Rx_t[l_destIndex_u16].Cnt_u16 += 1U;
            }
        }

        CommCCDLExtStatusRefresh(&s_ccdlKZZZExtStatus_t[v_ccdlID_u16][v_kzzzID_u16],
                                 (vp_rxBuff_u16[v_sIndex_u16 + 2U] & 0xFFU),
                                 v_page_u16);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLFramesScanAndDecode
 *
 * 【功能描述】在一段接收缓存中顺序扫描并解析基础帧/扩展帧。
 *
 * 【输入参数说明】v_ccdlID_u16 ---- CCDL链路ID
 *              vp_rxBuff_u16 ---- 接收缓存
 *              v_len_u16     ---- 当前有效字节数
 * 【输出参数说明】NONE
 * 【其他说明】    支持基础帧、RIU扩展帧和KZZZ扩展帧混合扫描。
 * 【返回】        已消费的前缀长度
 */
/* ***************************************************************** */
static Uint16 CommCCDLFramesScanAndDecode(Uint16 v_ccdlID_u16, const Uint16 *vp_rxBuff_u16, Uint16 v_len_u16)
{
    Uint16 l_scanIndex_u16 = 0U;
    Uint16 l_consumedLen_u16 = 0U;
    Uint16 l_frameLen_u16 = 0U;
    Uint16 l_frameType_u16 = 0U;
    Uint16 l_checksum_u16 = 0U;
    Uint16 l_kzzzPage_u16 = 0U;
    Uint16 l_kzzzSrcID_u16 = COMM429_KZZZ_NUM;

    if((v_ccdlID_u16 < COMM_CCDL_NUM) && (NULL != vp_rxBuff_u16))
    {
        /* 扫描器允许一个缓存中同时混入基础帧、扩展帧和半截尾帧。 */
        while(l_scanIndex_u16 < v_len_u16)
        {
            if((vp_rxBuff_u16[l_scanIndex_u16] & 0xFFU) != COMM_CCDL_FRAME_HEAD1)
            {
                l_scanIndex_u16 += 1U;
                l_consumedLen_u16 = l_scanIndex_u16;
                continue;
            }

            if((l_scanIndex_u16 + 1U) >= v_len_u16)
            {
                break;
            }

            if((vp_rxBuff_u16[l_scanIndex_u16 + 1U] & 0xFFU) != COMM_CCDL_FRAME_HEAD2)
            {
                l_scanIndex_u16 += 1U;
                l_consumedLen_u16 = l_scanIndex_u16;
                continue;
            }

            if((l_scanIndex_u16 + 3U) >= v_len_u16)
            {
                break;
            }

            l_frameType_u16 = vp_rxBuff_u16[l_scanIndex_u16 + 3U] & 0xFFU;
            if((COMM_CCDL_RIU_EXT_PAGE0_ID == l_frameType_u16) ||
               (COMM_CCDL_RIU_EXT_PAGE1_ID == l_frameType_u16) ||
               (COMM_CCDL_RIU_EXT_PAGE2_ID == l_frameType_u16))
            {
                l_frameLen_u16 = COMM_CCDL_RIU_EXT_FRAME_LEN;
            }
            else if(VALID == CommCCDLKZZZExtFrameTypeDecode(l_frameType_u16, &l_kzzzPage_u16, &l_kzzzSrcID_u16))
            {
                /* 通过 byte[3] 区分扩展分页帧与基础帧，避免改动底层帧头过滤。 */
                l_frameLen_u16 = COMM_CCDL_KZZZ_EXT_FRAME_LEN;
            }
            else
            {
                l_frameLen_u16 = COMM_CCDL_BASE_FRAME_LEN;
            }

            if((l_scanIndex_u16 + l_frameLen_u16) > v_len_u16)
            {
                /* 剩余字节不足一整帧时停止，交给下一轮接收继续拼接。 */
                break;
            }

            l_checksum_u16 = CommCCDLChecksumCalcU16(vp_rxBuff_u16, l_scanIndex_u16, l_frameLen_u16 - 1U);
            if(l_checksum_u16 == (vp_rxBuff_u16[l_scanIndex_u16 + l_frameLen_u16 - 1U] & 0xFFU))
            {
                CommCCDLFrameRxStatUpdate(v_ccdlID_u16);

                /* 校验通过后，按帧类型分发到基础帧、RIU镜像或KZZZ镜像解包。 */
                if(COMM_CCDL_RIU_EXT_PAGE0_ID == l_frameType_u16)
                {
                    CommCCDLRIUExtFrameDecode(v_ccdlID_u16, vp_rxBuff_u16, 0U, l_scanIndex_u16);
                }
                else if(COMM_CCDL_RIU_EXT_PAGE1_ID == l_frameType_u16)
                {
                    CommCCDLRIUExtFrameDecode(v_ccdlID_u16, vp_rxBuff_u16, 1U, l_scanIndex_u16);
                }
                else if(COMM_CCDL_RIU_EXT_PAGE2_ID == l_frameType_u16)
                {
                    CommCCDLRIUExtFrameDecode(v_ccdlID_u16, vp_rxBuff_u16, 2U, l_scanIndex_u16);
                }
                else if(VALID == CommCCDLKZZZExtFrameTypeDecode(l_frameType_u16, &l_kzzzPage_u16, &l_kzzzSrcID_u16))
                {
                    CommCCDLKZZZExtFrameDecode(v_ccdlID_u16,
                                               l_kzzzSrcID_u16,
                                               vp_rxBuff_u16,
                                               l_kzzzPage_u16,
                                               l_scanIndex_u16);
                }
                else
                {
                    CommCCDLBaseFrameDecode(v_ccdlID_u16, vp_rxBuff_u16, l_scanIndex_u16);
                }

                l_scanIndex_u16 = l_scanIndex_u16 + l_frameLen_u16;
                l_consumedLen_u16 = l_scanIndex_u16;
            }
            else
            {
                /* 校验失败时只前移1字节，继续尝试在后续数据中重新找同步。 */
                l_scanIndex_u16 += 1U;
                l_consumedLen_u16 = l_scanIndex_u16;
            }
        }
    }

    return l_consumedLen_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLFrameProcess
 *
 * 【功能描述】对指定CCDL链路的软件缓存执行帧级处理。
 *
 * 【输入参数说明】v_ccdlID_u16 ---- CCDL链路ID
 * 【输出参数说明】NONE
 * 【其他说明】    SCI 和 CPLD 均共用统一扫描器，只是底层缓存来源不同。
 * 【返回】        NONE
 */
/* ***************************************************************** */
void CommCCDLFrameProcess(Uint16 v_ccdlID_u16)
{
    Uint16 l_len_u16 = 0U;
    Uint16 l_consumedLen_u16 = 0U;
    Uint16 l_remain_u16 = 0U;
    Uint16 l_ii_u16 = 0U;
    Uint16 *l_pCommBuff_u16 = NULL;
    Rs422CommInfo_t l_sciInfo_t;
    memset(&l_sciInfo_t, 0, sizeof(l_sciInfo_t));

    if(COMM_CCDL_SCI == v_ccdlID_u16)
    {
        l_pCommBuff_u16 = Comm422FrameBufferGet(COMM422_CCDL_ID);
        l_len_u16 = Comm422RxBufferIndexGet(COMM422_CCDL_ID);

        if((NULL != l_pCommBuff_u16) && (l_len_u16 > 0U))
        {
            /* SCI链路只把 Comm422 当作字节缓存，CCDL 自己负责多帧长扫描。 */
            l_consumedLen_u16 = CommCCDLFramesScanAndDecode(COMM_CCDL_SCI, l_pCommBuff_u16, l_len_u16);
            Comm422RxBufferCompact(COMM422_CCDL_ID, l_consumedLen_u16);
        }

        l_sciInfo_t = Comm422CommInfoGet(COMM422_CCDL_ID);
        s_CCDLCommInfo_t[COMM_CCDL_SCI].rxBytesCount_u16 = l_sciInfo_t.rxBytesCount_u16;
        s_CCDLCommInfo_t[COMM_CCDL_SCI].rxBytesTime_u32 = l_sciInfo_t.rxBytesTime_u32;
        CommCCDLRxStateCheck(COMM_CCDL_SCI);
    }
    else if(COMM_CCDL_CPLD == v_ccdlID_u16)
    {
        l_len_u16 = s_CCDLCommBuff_t[v_ccdlID_u16].index_u16;

        if(l_len_u16 > 0U)
        {
            /* CPLD链路与SCI链路共用同一套帧级扫描规则，避免双实现分叉。 */
            l_consumedLen_u16 = CommCCDLFramesScanAndDecode(v_ccdlID_u16,
                                                            s_CCDLCommBuff_t[v_ccdlID_u16].commBuff_u16,
                                                            l_len_u16);
            if(l_consumedLen_u16 >= l_len_u16)
            {
                CommCCDLRxBufferClear(v_ccdlID_u16);
            }
            else
            {
                l_remain_u16 = l_len_u16 - l_consumedLen_u16;

                for(l_ii_u16 = 0U; l_ii_u16 < l_remain_u16; l_ii_u16++)
                {
                    s_CCDLCommBuff_t[v_ccdlID_u16].commBuff_u16[l_ii_u16] =
                        s_CCDLCommBuff_t[v_ccdlID_u16].commBuff_u16[l_consumedLen_u16 + l_ii_u16];
                }

                for(l_ii_u16 = l_remain_u16; l_ii_u16 < s_CCDLCommConf_t[v_ccdlID_u16].rxBuffLen_u16; l_ii_u16++)
                {
                    s_CCDLCommBuff_t[v_ccdlID_u16].commBuff_u16[l_ii_u16] = 0U;
                }

                s_CCDLCommBuff_t[v_ccdlID_u16].index_u16 = l_remain_u16;
            }
        }

        CommCCDLRxStateCheck(v_ccdlID_u16);
    }
    else
    {
        NOP;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLDataBuffRead
 *
 * 【功能描述】从SCI或CPLD底层读取CCDL字节流到软件缓存。
 *
 * 【输入参数说明】v_ccdlID_u16 ---- CCDL链路ID
 * 【输出参数说明】NONE
 * 【其他说明】    该函数只做底层搬运，不进行帧级解包。
 * 【返回】        NONE
 */
/* ***************************************************************** */
void CommCCDLDataBuffRead(Uint16 v_ccdlID_u16)
{
    Uint16 l_rxFifoState_u16 = CCDL_RX_FIFO_OVFL;
    Uint16 l_rxDataNum_u16 = 0U;
    Rs422CommInfo_t l_rs422Info_t;
    memset(&l_rs422Info_t, 0, sizeof(l_rs422Info_t));

    if(v_ccdlID_u16 < COMM_CCDL_NUM)
    {
        if(COMM_CCDL_CPLD == v_ccdlID_u16)
        {
            l_rxFifoState_u16 = Ccdl422RxFifoStatusGet(s_CCDLCommIDConf_u16[v_ccdlID_u16]);

            if(CCDL_RX_FIFO_OK == l_rxFifoState_u16)
            {
                l_rxDataNum_u16 = Ccdl422ReadBuff(s_CCDLCommIDConf_u16[v_ccdlID_u16], s_rxCCDLBuff_u16);

                if(l_rxDataNum_u16 > 0U)
                {
                    /* CPLD侧底层一次可能读到多帧，先整体搬运到软件缓存再统一扫描。 */
                    CommCCDLWToRsBuff(v_ccdlID_u16, s_rxCCDLBuff_u16, l_rxDataNum_u16);
                }
            }
            else
            {
                /* CPLD FIFO 溢出时直接复位底层FIFO，避免旧数据继续污染软件缓存。 */
                s_CCDLCommInfo_t[v_ccdlID_u16].ovflErrCount_u16 += 1U;
                Ccdl422RFIFOReset(s_CCDLCommIDConf_u16[v_ccdlID_u16]);
            }
        }
        else if(COMM_CCDL_SCI == v_ccdlID_u16)
        {
            Comm422DataBuffRead(s_CCDLCommIDConf_u16[v_ccdlID_u16]);
            /* SCI-CCDL 借用 Comm422 缓存链，因此字节接收计数/时间也要同步到 CCDL 侧统计口径。 */
            l_rs422Info_t = Comm422CommInfoGet(s_CCDLCommIDConf_u16[v_ccdlID_u16]);
            s_CCDLCommInfo_t[v_ccdlID_u16].rxBytesCount_u16 = l_rs422Info_t.rxBytesCount_u16;
            s_CCDLCommInfo_t[v_ccdlID_u16].rxBytesTime_u32 = l_rs422Info_t.rxBytesTime_u32;
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLSCIChannelReset
 *
 * 【功能描述】复位SCI-CCDL链路的发送和接收软件状态。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】    仅供初始化/PuBIT清场使用，不应用于运行期普通收发路径。
 * 【返回】        NONE
 */
/* ***************************************************************** */
void CommCCDLSCIChannelReset(void)
{
    SciReset(SCI_B_ID);
    s_commCCDL422TxFlag_u16 = RS422_COMM_TX_FLAG_OFF;
    s_commCCDLSendIndex_u16 = 0U;
    /* 清掉旧半帧和运行期队列，确保后续 PuBIT/初始化只看到本次新起发的数据。 */
    Comm422FrameCleanup(COMM422_CCDL_ID);
    Comm422RxBufferCompact(COMM422_CCDL_ID, Comm422RxBufferIndexGet(COMM422_CCDL_ID));
    CommCCDLRxBufferClear(COMM_CCDL_CPLD);
    CommCCDLRuntimeTxQueueReset();
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLSCIDataSend
 *
 * 【功能描述】推动一轮SCI FIFO装载，继续发送当前CCDL活动帧。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】    当前活动帧可能来自初始化/PuBIT直发缓存，也可能来自运行期发送队列。
 * 【返回】        NONE
 */
/* ***************************************************************** */
void CommCCDLSCIDataSend(void)
{
    Uint8 l_FiFoNum_u8 = 0U;
    Uint16 l_txNum_u16 = 0U;
    Uint8 l_tempTxBuff_u8[16];
    Uint16 l_index_u16 = 0U;
    const Uint8 *lp_activeBuff_u8 = NULL;
    memset(l_tempTxBuff_u8, 0, sizeof(l_tempTxBuff_u8));

    if(RS422_COMM_TX_FLAG_OFF == s_commCCDL422TxFlag_u16)
    {
        /* 运行期模式下，每次进入发送函数都先尝试捞起下一帧。 */
        CommCCDLActiveTxSelect();
    }

    if(RS422_COMM_TX_FLAG_ON == s_commCCDL422TxFlag_u16)
    {
        if(COMM_CCDL_TX_MODE_DIRECT == s_ccdlSciTxActiveMode_u16)
        {
            lp_activeBuff_u8 = s_CCDLTxBuff_u8;
        }
        else if(COMM_CCDL_TX_MODE_QUEUE == s_ccdlSciTxActiveMode_u16)
        {
            lp_activeBuff_u8 = s_ccdlSciTxQueue_u8[s_ccdlSciTxRd_u16];
        }
        else
        {
            s_commCCDL422TxFlag_u16 = RS422_COMM_TX_FLAG_OFF;
        }

        if(NULL != lp_activeBuff_u8)
        {
            l_FiFoNum_u8 = SciTxFIFOCount(SCI_B_ID);

            if(l_FiFoNum_u8 < 16U)
            {
                /* 单次只补到FIFO空位上限，剩余部分留待下一个任务时隙继续推进。 */
                l_txNum_u16 = 16U - l_FiFoNum_u8;

                if((s_commCCDLSendIndex_u16 + l_txNum_u16) > s_ccdlSciTxActiveLen_u16)
                {
                    l_txNum_u16 = s_ccdlSciTxActiveLen_u16 - s_commCCDLSendIndex_u16;
                }

                for(l_index_u16 = 0U; l_index_u16 < l_txNum_u16; l_index_u16++)
                {
                    l_tempTxBuff_u8[l_index_u16] = lp_activeBuff_u8[s_commCCDLSendIndex_u16 + l_index_u16];
                }

                if(l_txNum_u16 > 0U)
                {
                    SciSendBuff(SCI_B_ID, l_tempTxBuff_u8, l_txNum_u16);
                    s_commCCDLSendIndex_u16 += l_txNum_u16;
                }

                if(s_commCCDLSendIndex_u16 >= s_ccdlSciTxActiveLen_u16)
                {
                    if(COMM_CCDL_TX_MODE_QUEUE == s_ccdlSciTxActiveMode_u16)
                    {
                        /* 运行期队列模式下，整帧发完后再正式出队。 */
                        s_ccdlSciTxLen_u16[s_ccdlSciTxRd_u16] = 0U;
                        s_ccdlSciTxRd_u16 = (s_ccdlSciTxRd_u16 + 1U) % COMM_CCDL_SCI_TX_QUEUE_DEPTH;
                        if(s_ccdlSciTxCount_u16 > 0U)
                        {
                            s_ccdlSciTxCount_u16 -= 1U;
                        }
                    }

                    s_commCCDL422TxFlag_u16 = RS422_COMM_TX_FLAG_OFF;
                    s_commCCDLSendIndex_u16 = 0U;
                    s_ccdlSciTxActiveLen_u16 = 0U;
                    s_ccdlSciTxActiveMode_u16 = COMM_CCDL_TX_MODE_NONE;
                }
            }
            /* FIFO已满时本轮什么也不做，等下一任务时隙继续推进。 */
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLSCIDataStartSend
 *
 * 【功能描述】触发一次基础帧的SCI直发。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】    仅用于初始化/PuBIT，先打包基础帧，再由 `CommCCDLSCIDataSend()` 分片送入FIFO。
 * 【返回】        NONE
 */
/* ***************************************************************** */
void CommCCDLSCIDataStartSend(void)
{
    CommCCDLBaseFramePack(s_CCDLTxBuff_u8, COMM_CCDL_TX_FRAM_LEN);
    s_commCCDL422TxFlag_u16 = RS422_COMM_TX_FLAG_ON;
    s_commCCDLSendIndex_u16 = 0U;
    s_ccdlSciTxActiveLen_u16 = COMM_CCDL_TX_FRAM_LEN;
    s_ccdlSciTxActiveMode_u16 = COMM_CCDL_TX_MODE_DIRECT;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLDataSend
 *
 * 【功能描述】按旧接口语义发送一帧基础帧到CPLD链路。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】    保留给初始化链路兼容使用，不参与运行期分页调度。
 * 【返回】        NONE
 */
/* ***************************************************************** */
void CommCCDLDataSend(void)
{
    CommCCDLBaseFramePack(s_CCDLTxBuff_u8, COMM_CCDL_TX_FRAM_LEN);
    CommCCDLFrameSendToCPLD(s_CCDLTxBuff_u8, COMM_CCDL_TX_FRAM_LEN);
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLRuntimeTxPhaseProcess
 *
 * 【功能描述】执行一次运行期CCDL发送相位调度。
 *
 * 【输入参数说明】v_phaseIn100ms_u16 ---- 100ms大周期内的10ms相位号
 * 【输出参数说明】NONE
 * 【其他说明】    固定使用 phase0 发送基础帧，其余指定相位轮发 RIU/KZZZ 三页扩展帧。
 * 【返回】        NONE
 */
/* ***************************************************************** */
void CommCCDLRuntimeTxPhaseProcess(Uint16 v_phaseIn100ms_u16)
{
    Uint16 l_srcRiuID_u16 = COMM429_RIU_NUM;
    Uint16 l_srcKzzzID_u16 = COMM429_KZZZ_NUM;
    Uint16 l_leftOk_u16 = INVALID;
    Uint16 l_rightOk_u16 = INVALID;
    Uint8 l_txBuff_u8[COMM_CCDL_TX_FRAM_LEN_MAX];
    A429Info_t l_riuRxInfo_t;
    const ConData_t *lc_p_conData_t = ConDataGet();
    memset(l_txBuff_u8, 0, sizeof(l_txBuff_u8));
    memset(&l_riuRxInfo_t, 0, sizeof(l_riuRxInfo_t));

    if(COMM_CCDL_RUNTIME_BASE_PHASE == v_phaseIn100ms_u16)
    {
        /* 基础帧每100ms固定发1次，仅承担心跳、状态和版本信息。 */
        CommCCDLBaseFramePack(l_txBuff_u8, COMM_CCDL_TX_FRAM_LEN);
        CommCCDLRuntimeTxEnqueue(l_txBuff_u8, COMM_CCDL_TX_FRAM_LEN);
        CommCCDLFrameSendToCPLD(l_txBuff_u8, COMM_CCDL_TX_FRAM_LEN);
    }
    else if ((NULL != lc_p_conData_t) &&
             (CH_TYPE_INIT == lc_p_conData_t->ChType_u16))
    {
        /* 启动判型期间只保留基础帧，避免扩展页继续镜像未收敛的业务状态。 */
        NOP;
    }
    else if((COMM_CCDL_RUNTIME_RIU_PAGE0_PHASE == v_phaseIn100ms_u16) ||
            (COMM_CCDL_RUNTIME_RIU_PAGE1_PHASE == v_phaseIn100ms_u16) ||
            (COMM_CCDL_RUNTIME_RIU_PAGE2_PHASE == v_phaseIn100ms_u16))
    {
        l_riuRxInfo_t = Comm429RIURxStateGet(COMM429_RIU_1);
        if(RX429_STATE_OK == l_riuRxInfo_t.rxState_u16)
        {
            l_srcRiuID_u16 = COMM429_RIU_1;
        }
        else
        {
            l_riuRxInfo_t = Comm429RIURxStateGet(COMM429_RIU_2);
            if(RX429_STATE_OK == l_riuRxInfo_t.rxState_u16)
            {
                l_srcRiuID_u16 = COMM429_RIU_2;
            }
        }

        if(l_srcRiuID_u16 < COMM429_RIU_NUM)
        {
            if(COMM_CCDL_RUNTIME_RIU_PAGE0_PHASE == v_phaseIn100ms_u16)
            {
                CommCCDLRIUExtFramePack(l_txBuff_u8, 0U, l_srcRiuID_u16);
            }
            else if(COMM_CCDL_RUNTIME_RIU_PAGE1_PHASE == v_phaseIn100ms_u16)
            {
                CommCCDLRIUExtFramePack(l_txBuff_u8, 1U, l_srcRiuID_u16);
            }
            else
            {
                CommCCDLRIUExtFramePack(l_txBuff_u8, 2U, l_srcRiuID_u16);
            }

            CommCCDLRuntimeTxEnqueue(l_txBuff_u8, COMM_CCDL_RIU_EXT_FRAME_LEN);
            CommCCDLFrameSendToCPLD(l_txBuff_u8, COMM_CCDL_RIU_EXT_FRAME_LEN);
        }
    }
    else if((COMM_CCDL_RUNTIME_KZZZ_PAGE0_PHASE == v_phaseIn100ms_u16) ||
            (COMM_CCDL_RUNTIME_KZZZ_PAGE1_PHASE == v_phaseIn100ms_u16) ||
            (COMM_CCDL_RUNTIME_KZZZ_PAGE2_PHASE == v_phaseIn100ms_u16))
    {
        if(COMM_CCDL_RUNTIME_KZZZ_PAGE0_PHASE == v_phaseIn100ms_u16)
        {
            l_leftOk_u16 = (RX429_STATE_OK == Comm429KZZZRxStateGet(COMM429_KZZZ_1).rxState_u16) ? VALID : INVALID;
            l_rightOk_u16 = (RX429_STATE_OK == Comm429KZZZRxStateGet(COMM429_KZZZ_2).rxState_u16) ? VALID : INVALID;

            if((VALID == l_leftOk_u16) && (VALID == l_rightOk_u16))
            {
                s_ccdlKZZZExtTxSrcID_u16 =
                    (COMM429_KZZZ_1 == s_ccdlKZZZExtLastSrcID_u16) ? COMM429_KZZZ_2 : COMM429_KZZZ_1;
            }
            else if(VALID == l_leftOk_u16)
            {
                s_ccdlKZZZExtTxSrcID_u16 = COMM429_KZZZ_1;
            }
            else if(VALID == l_rightOk_u16)
            {
                s_ccdlKZZZExtTxSrcID_u16 = COMM429_KZZZ_2;
            }
            else
            {
                s_ccdlKZZZExtTxSrcID_u16 = COMM429_KZZZ_NUM;
            }

            if(s_ccdlKZZZExtTxSrcID_u16 < COMM429_KZZZ_NUM)
            {
                s_ccdlKZZZExtLastSrcID_u16 = s_ccdlKZZZExtTxSrcID_u16;
            }
        }

        l_srcKzzzID_u16 = s_ccdlKZZZExtTxSrcID_u16;

        if(l_srcKzzzID_u16 < COMM429_KZZZ_NUM)
        {
            /* KZZZ扩展帧每100ms完整镜像一侧吊舱；双侧都健康时按轮次交替发送左右两侧。 */
            if(COMM_CCDL_RUNTIME_KZZZ_PAGE0_PHASE == v_phaseIn100ms_u16)
            {
                CommCCDLKZZZExtFramePack(l_txBuff_u8, 0U, l_srcKzzzID_u16);
            }
            else if(COMM_CCDL_RUNTIME_KZZZ_PAGE1_PHASE == v_phaseIn100ms_u16)
            {
                CommCCDLKZZZExtFramePack(l_txBuff_u8, 1U, l_srcKzzzID_u16);
            }
            else
            {
                CommCCDLKZZZExtFramePack(l_txBuff_u8, 2U, l_srcKzzzID_u16);
            }

            CommCCDLRuntimeTxEnqueue(l_txBuff_u8, COMM_CCDL_KZZZ_EXT_FRAME_LEN);
            CommCCDLFrameSendToCPLD(l_txBuff_u8, COMM_CCDL_KZZZ_EXT_FRAME_LEN);
        }
        else if(COMM_CCDL_RUNTIME_KZZZ_PAGE0_PHASE == v_phaseIn100ms_u16)
        {
            s_ccdlKZZZExtTxSrcID_u16 = COMM429_KZZZ_NUM;
        }
        /* 没有有效KZZZ源时，本相位自然空转，保留上次镜像。 */
    }
    else
    {
        NOP;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLInit
 *
 * 【功能描述】初始化CCDL模块的收发缓存、运行期队列和扩展镜像状态。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】    初始化后基础帧数据、RIU/KZZZ镜像和发送状态均回到可预测的零态。
 * 【返回】        NONE
 */
/* ***************************************************************** */
void CommCCDLInit(void)
{
    Uint16 l_ii_u16 = 0U;
    Uint16 l_jj_u16 = 0U;
    Uint16 l_kk_u16 = 0U;

    for(l_ii_u16 = 0U; l_ii_u16 < COMM_CCDL_NUM; l_ii_u16++)
    {
        /* 每条链路都独立维护基础帧缓存、接收健康和扩展镜像状态。 */
        s_CCDLCommBuff_t[l_ii_u16].index_u16 = 0U;
        s_CCDLCommBuff_t[l_ii_u16].overCount_u16 = 0U;

        s_CCDLCommInfo_t[l_ii_u16].checkTime_u32 = 0UL;
        s_CCDLCommInfo_t[l_ii_u16].rxBytesCount_u16 = 0U;
        s_CCDLCommInfo_t[l_ii_u16].rxBytesTime_u32 = 0UL;
        s_CCDLCommInfo_t[l_ii_u16].rxFrameCount_u16 = 0U;
        s_CCDLCommInfo_t[l_ii_u16].rxFrameTime_u32 = 0UL;
        s_CCDLCommInfo_t[l_ii_u16].ovflErrCount_u16 = 0U;
        s_CCDLCommInfo_t[l_ii_u16].rxState_u16 = COMM_CCDL_RX_NO_BYTES_ERR;
        s_CCDLCommInfo_t[l_ii_u16].errCntSum_u32 = 0UL;
        s_CCDLCommInfo_t[l_ii_u16].errCnt_u32 = 0UL;
        s_CCDLCommInfo_t[l_ii_u16].errCntMax_u32 = 0UL;

        for(l_jj_u16 = 0U; l_jj_u16 < COMM_CCDL_RX_BUFF_LEN; l_jj_u16++)
        {
            s_CCDLCommBuff_t[l_ii_u16].commBuff_u16[l_jj_u16] = 0U;
        }

        s_ccdlRxBaseData_t[l_ii_u16].framCntLast_u16 = 0U;
        s_ccdlRxBaseData_t[l_ii_u16].framCnt_u16 = 0U;
        s_ccdlRxBaseData_t[l_ii_u16].sysState_u16 = SYS_STATE_0INIT;
        s_ccdlRxBaseData_t[l_ii_u16].ChType_u16 = CH_TYPE_INIT;
        s_ccdlRxBaseData_t[l_ii_u16].ChTypeNvmData_u16 = 0U;
        s_ccdlRxBaseData_t[l_ii_u16].randData_u16 = 0U;
        s_ccdlRxBaseData_t[l_ii_u16].CPLDHeart_u16 = 0U;
        s_ccdlRxBaseData_t[l_ii_u16].softV_DSP_u16 = 0U;
        s_ccdlRxBaseData_t[l_ii_u16].ctrlInfo_u16 = 0U;
        s_ccdlRxBaseData_t[l_ii_u16].softV_CPLD_u16 = 0U;
        s_ccdlTxRandData_u16[l_ii_u16] = 0U;

        s_peerBaseStatus_t[l_ii_u16].valid_u16 = INVALID;
        s_peerBaseStatus_t[l_ii_u16].lastRxTime_u32 = 0UL;
        s_peerBaseStatus_t[l_ii_u16].frameCntLast_u16 = 0U;
        s_peerBaseStatus_t[l_ii_u16].frameCnt_u16 = 0U;
        s_peerBaseStatus_t[l_ii_u16].sysState_u16 = SYS_STATE_0INIT;
        s_peerBaseStatus_t[l_ii_u16].chType_u16 = CH_TYPE_INIT;
        s_peerBaseStatus_t[l_ii_u16].preferredMasterChId_u16 = 0U;
        s_peerBaseStatus_t[l_ii_u16].cpldHeart_u16 = 0U;
        s_peerBaseStatus_t[l_ii_u16].softV_DSP_u16 = 0U;
        s_peerBaseStatus_t[l_ii_u16].ctrlInfo_u16 = 0U;
        s_peerBaseStatus_t[l_ii_u16].softV_CPLD_u16 = 0U;

        for(l_jj_u16 = 0U; l_jj_u16 < RIU_R_DATA_NUM; l_jj_u16++)
        {
            s_ccdlRIUOrigData_t[l_ii_u16].Orig_Rx_t[l_jj_u16].label_u16 = s_ccdlRIULabelConf_u16[l_jj_u16];
            s_ccdlRIUOrigData_t[l_ii_u16].Orig_Rx_t[l_jj_u16].OrigData_u32 = 0UL;
            s_ccdlRIUOrigData_t[l_ii_u16].Orig_Rx_t[l_jj_u16].Cnt_u16 = 0U;
        }

        s_ccdlRIUExtStatus_t[l_ii_u16].frameCnt_u16 = 0U;
        s_ccdlRIUExtStatus_t[l_ii_u16].pageValidMask_u16 = 0U;
        s_ccdlRIUExtStatus_t[l_ii_u16].pageTotal_u16 = 0U;
        s_ccdlRIUExtStatus_t[l_ii_u16].lastRxTime_u32 = 0UL;
        s_ccdlRIUExtStatus_t[l_ii_u16].dataState_u16 = COMM_CCDL_RX_NO_BYTES_ERR;

        for(l_kk_u16 = 0U; l_kk_u16 < COMM429_KZZZ_NUM; l_kk_u16++)
        {
            s_ccdlKZZZExtStatus_t[l_ii_u16][l_kk_u16].frameCnt_u16 = 0U;
            s_ccdlKZZZExtStatus_t[l_ii_u16][l_kk_u16].pageValidMask_u16 = 0U;
            s_ccdlKZZZExtStatus_t[l_ii_u16][l_kk_u16].pageTotal_u16 = 0U;
            s_ccdlKZZZExtStatus_t[l_ii_u16][l_kk_u16].lastRxTime_u32 = 0UL;
            s_ccdlKZZZExtStatus_t[l_ii_u16][l_kk_u16].dataState_u16 = COMM_CCDL_RX_NO_BYTES_ERR;

            /* 启动时先把KZZZ镜像的固定label顺序建立好，后续只更新原始字和值计数。 */
            for(l_jj_u16 = 0U; l_jj_u16 < KZZZ_R_DATA_NUM; l_jj_u16++)
            {
                s_ccdlKZZZOrigData_t[l_ii_u16][l_kk_u16].Orig_Rx_t[l_jj_u16].label_u16 = s_ccdlKZZZLabelConf_u16[l_jj_u16];
                s_ccdlKZZZOrigData_t[l_ii_u16][l_kk_u16].Orig_Rx_t[l_jj_u16].OrigData_u32 = 0UL;
                s_ccdlKZZZOrigData_t[l_ii_u16][l_kk_u16].Orig_Rx_t[l_jj_u16].Cnt_u16 = 0U;
            }
        }
    }

    for(l_jj_u16 = 0U; l_jj_u16 < CCDL_RX_DATA_NUM_MAX; l_jj_u16++)
    {
        s_rxCCDLBuff_u16[l_jj_u16] = 0U;
    }

    for(l_jj_u16 = 0U; l_jj_u16 < COMM_CCDL_TX_FRAM_LEN_MAX; l_jj_u16++)
    {
        s_CCDLTxBuff_u8[l_jj_u16] = 0U;
    }

    s_commCCDL422TxFlag_u16 = RS422_COMM_TX_FLAG_OFF;
    s_commCCDLSendIndex_u16 = 0U;
    s_ccdlSciTxDropCnt_u32 = 0UL;
    s_ccdlRIUExtFrameCnt_u16 = 0U;
    s_ccdlKZZZExtFrameCnt_u16 = 0U;
    s_ccdlKZZZExtTxSrcID_u16 = COMM429_KZZZ_NUM;
    s_ccdlKZZZExtLastSrcID_u16 = COMM429_KZZZ_2;
    /* 队列状态单独复位，和基础帧缓存初始化解耦。 */
    CommCCDLRuntimeTxQueueReset();
}

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
