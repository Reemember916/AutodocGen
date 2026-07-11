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
 * 文件名称:    commCCDL.h
 *
 * 文件日期:   REDACTED
 *
 *
 * 【程序版本】    V2.00
 *
 * 【功能描述】实现通道间422通信,422通信由CPLD实现，通信波特率为1M
 * 【其他说明】NONE
 *
 **********************************************************************************
 *
 * 功能说明:
 *
 * 1. 定义CCDL在SCI链路和CPLD链路上的收发参数、缓存结构和状态结构。
 * 2. 对外提供运行期收发调度、状态获取，以及初始化/PuBIT阶段所需的SCI链路复位接口。
 *
 *
 *********************************************************************************/

#ifndef CommCCDL_H_
#define CommCCDL_H_

#include "Global.h"

/* ***************************************************************** */
#define COMM_CCDL_NUM   (2U)  /* 通道间通信数量  */

#define COMM_CCDL_SCI   (0U)  /* 通道间SCI通信  */
#define COMM_CCDL_CPLD   (1U)  /* 通道间CPLD通信  */

#define COMM_CCDL_PRIOD_MS   (10U)  /* 通道间通信协议名义周期  */
#define COMM_CCDL_RX_CHECK_PERIOD_MS  (20U) /* 运行期CCDL接收检查节拍 */
#define COMM_CCDL_RX_TIMEOUT_MS       (40U) /* 运行期字节超时判据 */
#define COMM_CCDL_FRAME_TIMEOUT_MS    (40U) /* 运行期合法帧超时判据 */

#define COMM_CCDL_FRAME_CRC_LEN    (1U)       /* 帧校验字节数 */
#define COMM_CCDL_BASE_FRAME_LEN   (15U)      /* 基础帧长度 */
#define COMM_CCDL_EXT_PAGE_WORD_NUM    (10U)  /* 扩展分页每页承载的429原始字个数 */
#define COMM_CCDL_EXT_WORD_LEN     (4U)       /* 单个扩展字占用字节数 */
#define COMM_CCDL_RIU_EXT_FRAME_LEN    (45U)  /* RIU扩展分页帧长度 */
#define COMM_CCDL_KZZZ_EXT_FRAME_LEN   (45U)  /* KZZZ扩展分页帧长度 */
#define COMM_CCDL_FRAME_LEN_MAX    (45U)      /* CCDL最大发送帧长度 */
#define COMM_CCDL_RX_BUFF_LEN      (192U)     /* 接收缓冲区长度 */

#define COMM_CCDL_TX_FRAM_LEN      (COMM_CCDL_BASE_FRAME_LEN)      /* 基础帧发送长度         */
#define COMM_CCDL_TX_FRAM_LEN_MAX  (COMM_CCDL_FRAME_LEN_MAX)     /* 发送数据最大长度 */

#define COMM_CCDL_FRAME_HEAD1      (0xEBU)   /* 帧头1       */
#define COMM_CCDL_FRAME_HEAD2      (0x90U)   /* 帧头2       */
#define COMM_CCDL_RIU_EXT_PAGE0_ID    (0xE0U)   /* RIU扩展帧page0标识 */
#define COMM_CCDL_RIU_EXT_PAGE1_ID    (0xE1U)   /* RIU扩展帧page1标识 */
#define COMM_CCDL_RIU_EXT_PAGE2_ID    (0xE2U)   /* RIU扩展帧page2标识 */
#define COMM_CCDL_KZZZ1_EXT_PAGE0_ID  (0xF0U)   /* KZZZ_1扩展帧page0标识 */
#define COMM_CCDL_KZZZ1_EXT_PAGE1_ID  (0xF1U)   /* KZZZ_1扩展帧page1标识 */
#define COMM_CCDL_KZZZ1_EXT_PAGE2_ID  (0xF2U)   /* KZZZ_1扩展帧page2标识 */
#define COMM_CCDL_KZZZ2_EXT_PAGE0_ID  (0xF3U)   /* KZZZ_2扩展帧page0标识 */
#define COMM_CCDL_KZZZ2_EXT_PAGE1_ID  (0xF4U)   /* KZZZ_2扩展帧page1标识 */
#define COMM_CCDL_KZZZ2_EXT_PAGE2_ID  (0xF5U)   /* KZZZ_2扩展帧page2标识 */

#define COMM_CCDL_FRAM_NOT_EXIST   (0xCCU)    /* 不存在有效报文 */

#define COMM_CCDL_RX_OK            (0x00U)      /* CCDL通信接收正常   */
#define COMM_CCDL_RX_NO_BYTES_ERR  (0x01U)      /* CCDL接收无数据异常 */
#define COMM_CCDL_RX_NO_FRAMES_ERR (0x02U)      /* CCDL接收无报文异常 */
#define COMM_CCDL_RX_UNKNOW_ERR    (0x04U)      /* CCDL接收未知异常   */

#define COMM_CCDL_RUNTIME_TX_PHASE_NUM         (10U)
#define COMM_CCDL_RUNTIME_BASE_PHASE           (0U)
#define COMM_CCDL_RUNTIME_RIU_PAGE0_PHASE      (1U)
#define COMM_CCDL_RUNTIME_KZZZ_PAGE0_PHASE     (2U)
#define COMM_CCDL_RUNTIME_RIU_PAGE1_PHASE      (4U)
#define COMM_CCDL_RUNTIME_KZZZ_PAGE1_PHASE     (5U)
#define COMM_CCDL_RUNTIME_RIU_PAGE2_PHASE      (7U)
#define COMM_CCDL_RUNTIME_KZZZ_PAGE2_PHASE     (8U)
#define COMM_CCDL_SCI_TX_QUEUE_DEPTH           (7U)
#define COMM_CCDL_TX_MODE_NONE                 (0U)
#define COMM_CCDL_TX_MODE_DIRECT               (1U)
#define COMM_CCDL_TX_MODE_QUEUE                (2U)
#define COMM_CCDL_PAGE0_MASK                   (0x0001U)
#define COMM_CCDL_PAGE1_MASK                   (0x0002U)
#define COMM_CCDL_PAGE2_MASK                   (0x0004U)
#define COMM_CCDL_EXT_PAGE_NUM                 (3U)

#define COMM_CCDL_CTRLINFO_OWNER_BIT         (0U)   /* bit0: 对端当前是否持有控制权 */
#define COMM_CCDL_CTRLINFO_CONOUT_BIT        (1U)   /* bit1: 对端当前拍控制输出是否有效 */
#define COMM_CCDL_CTRLINFO_LOCAL_HEALTH_BIT  (2U)   /* bit2: 对端本地控制健康是否有效 */
#define COMM_CCDL_CTRLINFO_VALID_MASK        (0x07U)

/*****************************************************************************/
/* 通道间通信接收数据结构体  */
typedef struct _CCDLRXData
{
	Uint16 framCntLast_u16;   /* 上一拍接收报文帧计数   */
	Uint16 framCnt_u16;       /* 接收报文帧计数   */
	Uint16 sysState_u16;      /* 系统状态 */
    Uint16 ChType_u16;        /* 通道类型      */
    Uint16 ChTypeNvmData_u16; /* 冷启动默认主控协商值，仅用于启动期默认主备建立 */
    Uint16 randData_u16;      /* 历史兼容字段2，当前主备判定不使用 */
    Uint16 CPLDHeart_u16;     /* CPLD心跳字 */
	Uint16 softV_DSP_u16;     /* DSP控制软件版本    */
	Uint16 ctrlInfo_u16;      /* 基础帧控制信息字：控制权/输出授权/本地健康 */
	Uint16 softV_CPLD_u16;    /* CPLD逻辑软件版本 */

}CCDLRXData_t;

/* 通道间通信缓存信息结构体   */
typedef struct _CCDLCommBuff
{
	Uint16 commBuff_u16[COMM_CCDL_RX_BUFF_LEN];    /* 接收数据缓冲区                  */
    Uint16 index_u16;                              /* 缓冲区索引                         */
    Uint16 overCount_u16;                          /* 缓冲区溢出计数                  */

}CCDLCommBuff_t;

/* 通道间通信状态信息结构体   */
typedef struct _CCDLCommInfo
{
	Uint16  rxBytesCount_u16;       /* 接收数据计数               */
	Uint32  rxBytesTime_u32;        /* 接收数据时间               */
	Uint16  rxFrameCount_u16;       /* 接收有效报文计数        */
	Uint32  rxFrameTime_u32;        /* 接收有效报文时间        */
    Uint32  checkTime_u32;          /* 最近一次检查报文时间 */
	Uint16  ovflErrCount_u16;       /* FIFO溢出错误计数      */
	Uint16  rxState_u16;            /* 通信接收状态                 */

	Uint32 errCntSum_u32;           /* 接收错误总数 */
	Uint32 errCnt_u32;              /* 接收连续错误数 */
	Uint32 errCntMax_u32;           /* 接收连续最大错误数 */

}CCDLCommInfo_t;

/* 对端基础帧状态快照结构体。
 * 仅承载最近一次收到的对端基础帧内容与时效信息，供主备切换、初始化和热重连读取。 */
typedef struct _PeerBaseStatus
{
    Uint16 valid_u16;                /* 是否至少收到过1帧合法基础帧 */
    Uint32 lastRxTime_u32;           /* 最近一次收到合法基础帧的时刻 */
    Uint16 frameCntLast_u16;         /* 上一拍基础帧帧计数 */
    Uint16 frameCnt_u16;             /* 最近一次基础帧帧计数 */
    Uint16 sysState_u16;             /* 对端系统状态 */
    Uint16 chType_u16;               /* 对端通道类型 */
    Uint16 preferredMasterChId_u16;  /* 冷启动默认主控协商值 */
    Uint16 cpldHeart_u16;            /* 对端基础帧中的CPLD心跳字 */
    Uint16 softV_DSP_u16;            /* 对端DSP软件版本 */
    Uint16 ctrlInfo_u16;             /* 对端控制信息字 */
    Uint16 softV_CPLD_u16;           /* 对端CPLD版本 */
}PeerBaseStatus_t;

/* 扩展页状态结构体。
 * 仅承载指定业务扩展页的完整性与新鲜度信息，不承载基础帧语义。 */
typedef struct _CCDLExtStatus
{
    Uint16 frameCnt_u16;
    Uint16 pageValidMask_u16;
    Uint16 pageTotal_u16;
    Uint32 lastRxTime_u32;
    Uint16 dataState_u16;
}CCDLExtStatus_t;

/* 通道间通信配置信息结构体  */
typedef struct _CCDLCommConf
{
	Uint16  rxFrameHead_1_u16; /* 接收报文帧头1   */
	Uint16  rxFrameHead_2_u16; /* 接收报文帧头1   */
	Uint16 rxFrameCnt_u16;
	Uint16 rxFrameCntPre_u16;
    Uint16  rxFrameLen_u16;    /* 接收报文长度           */
    Uint16  rxBuffLen_u16;     /* 接收缓存区长度       */

}CCDLCommConf_t;

/* ***************************************************************** */
/**
 * 供外部调用函数接口
 */
/* ***************************************************************** */
extern void CommCCDLInit(void);
extern void CommCCDLDataBuffRead(Uint16 v_ccdlID_u16);
extern void CommCCDLDataSend(void);
extern void CommCCDLSCIDataSend(void);
/* 仅用于初始化/PuBIT独立起发，不用于运行期普通发送调度。 */
extern void CommCCDLSCIDataStartSend(void);
/* 仅用于初始化/PuBIT链路清场，不用于运行期普通收发路径。 */
extern void CommCCDLSCIChannelReset(void);
extern PeerBaseStatus_t CommCCDLPeerBaseGet(Uint16 v_ccdlID_u16);
extern Uint16 CommCCDLPeerBaseAdvancedGet(Uint16 v_ccdlID_u16);
extern CCDLExtStatus_t CommCCDLKZZZExtStatusGet(Uint16 v_ccdlID_u16, Uint16 v_kzzzID_u16);
extern RIU429OrigData_t CommCCDLRIUOrigDataGet(Uint16 v_ccdlID_u16);
extern KZZZ429OrigData_t CommCCDLKZZZOrigDataGet(Uint16 v_ccdlID_u16, Uint16 v_kzzzID_u16);
extern Uint16 CommCCDL422TxFlagGet(void);
extern void CommCCDLFrameProcess(Uint16 v_ccdlID_u16);
extern void CommCCDLRuntimeTxPhaseProcess(Uint16 v_phaseIn100ms_u16);
/* ***************************************************************** */
/* CommCCDL.c 私有函数式宏定义 */
/* ***************************************************************** */
#define CommCCDLExtPageMaskGet(page) \
    ((0U == (page)) ? COMM_CCDL_PAGE0_MASK : \
     ((1U == (page)) ? COMM_CCDL_PAGE1_MASK : ((2U == (page)) ? COMM_CCDL_PAGE2_MASK : 0U)))
#define CommCCDLExtFrameCntGet(currFrameCnt, page) \
    ((0U == (page)) ? (((currFrameCnt) + 1U) & 0xFFU) : (currFrameCnt))
#define CommCCDLKZZZExtFrameTypeGet(page, srcKzzzID) \
    ((((page) < COMM_CCDL_EXT_PAGE_NUM) && ((srcKzzzID) < COMM429_KZZZ_NUM)) ? \
     ((COMM429_KZZZ_1 == (srcKzzzID)) ? (Uint16)(COMM_CCDL_KZZZ1_EXT_PAGE0_ID + (page)) : \
                                       (Uint16)(COMM_CCDL_KZZZ2_EXT_PAGE0_ID + (page))) : \
     COMM_CCDL_FRAM_NOT_EXIST)
#define CommCCDLFrameRxStatUpdate(ccdlID) \
    do { \
        if((ccdlID) < COMM_CCDL_NUM) { \
            s_CCDLCommInfo_t[(ccdlID)].rxFrameCount_u16 = \
                (s_CCDLCommInfo_t[(ccdlID)].rxFrameCount_u16 + 1U) % (0xFFFFU); \
            s_CCDLCommInfo_t[(ccdlID)].rxFrameTime_u32 = sysTime(); \
        } \
    } while(0)
/* ***************************************************************** */
/**
 * 【函数名】:CommCCDLActiveTxSelect
 *
 * 【功能描述】当SCI发送空闲时，从运行期队列中取下一帧激活发送。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】    初始化/PuBIT直发模式不会走这里。
 * 【返回】        NONE
 */
/* ***************************************************************** */
#define CommCCDLActiveTxSelect() \
    do { \
        if((RS422_COMM_TX_FLAG_OFF == s_commCCDL422TxFlag_u16) && \
           (COMM_CCDL_TX_MODE_NONE == s_ccdlSciTxActiveMode_u16) && \
           (s_ccdlSciTxCount_u16 > 0U)) { \
            s_ccdlSciTxActiveLen_u16 = s_ccdlSciTxLen_u16[s_ccdlSciTxRd_u16]; \
            s_commCCDLSendIndex_u16 = 0U; \
            s_ccdlSciTxActiveMode_u16 = COMM_CCDL_TX_MODE_QUEUE; \
            s_commCCDL422TxFlag_u16 = RS422_COMM_TX_FLAG_ON; \
        } \
    } while(0)
#define CommCCDLExtStatusRefresh(status, frameCnt, page) \
    do { \
        if(NULL != (status)) { \
            if(((status))->frameCnt_u16 != (frameCnt)) { \
                ((status))->pageValidMask_u16 = 0U; \
            } \
            ((status))->frameCnt_u16 = (frameCnt); \
            ((status))->lastRxTime_u32 = sysTime(); \
            ((status))->pageValidMask_u16 |= CommCCDLExtPageMaskGet(page); \
            ((status))->pageTotal_u16 = COMM_CCDL_EXT_PAGE_NUM; \
        } \
    } while(0)
#define CommCCDLRxBufferClear(ccdlID) \
    do { \
        Uint16 l_clearIi_u16 = 0U; \
        if((ccdlID) < COMM_CCDL_NUM) { \
            s_CCDLCommBuff_t[(ccdlID)].index_u16 = 0U; \
            for(l_clearIi_u16 = 0U; \
                l_clearIi_u16 < s_CCDLCommConf_t[(ccdlID)].rxBuffLen_u16; \
                l_clearIi_u16++) { \
                s_CCDLCommBuff_t[(ccdlID)].commBuff_u16[l_clearIi_u16] = 0U; \
            } \
        } \
    } while(0)

#endif /* CommCCDL_H_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
