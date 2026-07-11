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
 * 文件名称:    comm422.h
 *
 * 文件日期：      REDACTED
 *
 *
 * 程序版本:   V2.00
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 * 1.实现维护通信接收和发送
 *
 *********************************************************************************/

#ifndef COMM422_H_
#define COMM422_H_

#include "Global.h"

/*************************************************************************************/
#define COMM422_ID_NUM (2U)  /* 422通信数量  */

#define COMM422_ID_0 (0U) 	/* 422通信1  */
#define COMM422_ID_1 (1U)  	/* 422通信2  */

/* 端口号定义 */
#define COMM422_MAINT_ID (COMM422_ID_0)  	/* 维护通信端口ID     */
#define COMM422_CCDL_ID (COMM422_ID_1)		/*CCDL通信端口*/

/* 通信数据长度定义  */

#define COMM_MAINT_RX_FRAME_LEN (16U)   /* 维护通信接收报文长度          */
#define COMM_MAINT_RX_BUFF_LEN (32U)   /* 维护通信接收缓冲区长度      */
#define COMM_MAINT_TX_FRAME_LEN (16U)     /* 维护通信发送报文长度         */

#define COMM_CCDL_MAX_BUFF_LEN (192U)     /* CCDL通信发送/接收缓冲最大长度         */

#define COMM422_MAINT_PRIOD (100U)   /* 422维护通信接收周期ms  */

/*************************************************************************************/
/* 422通信状态定义 */
#define RS422_COMM_FRAM_NOT_EXIST (0xBBU)      /* 接收缓冲区不存在有效报文 */

#define RS422_COMM_RX_OK (0x00U)      /* RS422通信接收正常            */
#define RS422_COMM_RX_NO_BYTES_ERR (0x01U)      /* RS422接收无数据异常        */
#define RS422_COMM_RX_NO_FRAMES_ERR (0x02U)      /* RS422接收无报文异常        */
#define RS422_COMM_RX_UNKNOW_ERR (0x04U)      /* RS422接收未知异常            */



#define SCI_COMM_OK (0U)         /* SCI底层通信正常                 */
#define SCI_COMM_ERR (1U)         /* SCI底层通信错误                 */
#define SCI_COMM_OVF (2U)         /* SCI底层通信溢出                 */

/*************************************************************************************/
/* 422通信接收和发送报文帧头定义  */
#define RS422_COMM_FRAME_HEAD_1 (0xEBU)      /* RS422通信接收报文帧头1 */
#define RS422_COMM_FRAME_HEAD_2 (0x90U)      /* RS422通信接收报文帧头2 */

#define RS422_COMM_TX_FRAME_HEAD_1 (0x55U)      /* RS422通信发送报文帧头1 */
#define RS422_COMM_TX_FRAME_HEAD_2 (0xAAU)      /* RS422通信发送报文帧头2 */

#define RS422_COMM_TX_FLAG_OFF (0x00U)      /* RS422通信发送标志关闭      */
#define RS422_COMM_TX_FLAG_ON (0x01U)      /* RS422通信发送标志打开      */

/*************************************************************************************/
/* 维护通信接收数据宏定义 */

/* 维护状态码 */
#define MAINT_CODE_STATE_INVALID (0x00U)      /* 维护-无效                        */
#define MAINT_CODE_COMM_INFO (0x11U)      /* 维护-通信状态                */
#define MAINT_CODE_MAINT_STATE (0x22U)      /* 地面维护状态                   */

#define MAINT_CODE_CMD_INVALID (0x00U)      /* 维护-无效                        */
#define MAINT_CODE_MAINT_FUNC (0x99U)      /* 地面维护                           */
#define MAINT_CODE_GROUND_CON (0x66U)      /* 地面控制                           */

/* 地面维护功能码 */
#define GROUND_MAINT_FUNC_INVALID (0x00U)      /* 地面维护功能无效                */
#define GROUND_MAINT_FUNC_SOFT_CRC (0x01U)      /* 地面维护功能软件CRC计算 */
#define GROUND_MAINT_FUNC_DATA_DOWNLOAD (0x02U)      /* 地面维护功能软件数据下载 */
#define GROUND_MAINT_FUNC_DATA_ERASE (0x03U)      /* 地面维护功能信息擦除         */
#define GROUND_MAINT_FUNC_HW_VERSION_ADJUST (0x04U)    /* 地面维护功能硬件版本调整 */
#define GROUND_MAINT_FUNC_BIT_CLEAR (0x05U)            /* 地面维护功能BIT信息清除 */
#define GROUND_MAINT_FUNC_PID_PARA_ADJUST GROUND_MAINT_FUNC_HW_VERSION_ADJUST
/* 地面维护功能执行结果 */
#define MAINT_FUNC_EXE_RESULT_NONE (0x00U)      /* 未执行 */
#define MAINT_FUNC_EXE_RESULT_OK (0x01U)      /* 执行成功 */
#define MAINT_FUNC_EXE_RESULT_UNSUPPORTED (0x02U)      /* 功能暂不支持 */
#define MAINT_FUNC_EXE_RESULT_INVALID_PARA (0x03U)      /* 参数无效 */
#define MAINT_FUNC_EXE_RESULT_FAIL (0x04U)      /* 执行失败 */

#define MAINT_CMD_INVALID (0x00U)      /* 维护指令无效                       */
#define MAINT_CMD_DATA_DOWN (0x01U)      /* 信息下载                               */
#define MAINT_CMD_DATA_ERAZE (0x02U)      /* 信息擦除                               */
#define MAINT_CMD_PID_PARA_ADJUST (0x03U)      /* 控制参数调整                       */

/*************************************************************************************/
/* 维护通信发送报文打包相关宏定义 */
#define COMM_MAINT_TX_PACK_NUM (15U)       /* 维护通信发送报文数量        */

#define COMM_MAINT_TX_PACK_FRAME_ID_0 (0U)    /* 维护通信发送报文包号0  */
#define COMM_MAINT_TX_PACK_FRAME_ID_1 (1U)    /* 维护通信发送报文包号1：主备轮值诊断 */
#define COMM_MAINT_TX_PACK_FRAME_ID_2 (2U)    /* 维护通信发送报文包号2：输出授权诊断 */
#define COMM_MAINT_TX_PACK_FRAME_ID_3 (3U)    /* 维护通信发送报文包号3：BIT/故障摘要 */
#define COMM_MAINT_TX_PACK_FRAME_ID_4 (4U)    /* 维护通信发送报文包号4：通信来源/余度来源 */
#define COMM_MAINT_TX_PACK_FRAME_ID_5 (5U)    /* 维护通信发送报文包号5：版本/CRC/执行结果 */
#define COMM_MAINT_TX_PACK_FRAME_ID_6 (6U)    /* 维护通信发送报文包号6：完整BIT位图 */

/*************************************************************************************/
/* 维护通信发送429通信信息打包相关宏定义 */
#define COMM_MAINT_TX_COMM429_INFO_NUM (8U)       /* 429通信发送信息数量        */

#define COMM_MAINT_TX_COMM429_INFO_RMC_1 (0U)    /* 维护通信429通信信息发送RMC1  */
#define COMM_MAINT_TX_COMM429_INFO_RMC_2 (1U)    /* 维护通信429通信信息发送RMC2  */

#define COMM_MAINT_TX_COMM429_INFO_RIU_1 (2U)    /* 维护通信429通信信息发送RIU1  */
#define COMM_MAINT_TX_COMM429_INFO_RIU_2 (3U)    /* 维护通信429通信信息发送RIU2  */

#define COMM_MAINT_TX_COMM429_INFO_JYB_1 (4U)    /* 维护通信429通信信息发送JYB1  */
#define COMM_MAINT_TX_COMM429_INFO_JYB_2 (5U)    /* 维护通信429通信信息发送JYB2  */

#define COMM_MAINT_TX_COMM429_INFO_DMP (6U)   /* 维护通信429通信信息发送DMP  */
#define COMM_MAINT_TX_COMM429_INFO_KZZZ (7U)   /* 维护通信429通信信息发送KZZZ  */

/*************************************************************************************/
/* 维护通信发送流量测量盒通信信息打包相关宏定义 */
#define COMM_MAINT_TX_COMMFLOWB_INFO_NUM (2U)    /* 流量测量盒通信发送信息数量        */

#define COMM_MAINT_TX_COMMFLOWB_INFO_1 (0U)    /* 维护通信流量测量盒通信信息发送1  */
#define COMM_MAINT_TX_COMMFLOWB_INFO_2 (1U)    /* 维护通信流量测量盒通信信息发送2  */

/*************************************************************************************/
/* 维护通信发送-维护控制指令信息ID相关宏定义 */

#define COMM_MAINT_R_CON_CMD_JYB_1 (0U)    /* 维护指令索引-加油泵1指令  */
#define COMM_MAINT_R_CON_CMD_JYB_2 (1U)    /* 维护指令索引-加油泵2指令  */
#define COMM_MAINT_R_CON_CMD_PQF (2U)    /* 维护指令索引-排气阀指令  */
#define COMM_MAINT_R_CON_CMD_SOV (3U)    /* 维护指令索引-电磁阀指令  */
#define COMM_MAINT_R_CON_CMD_KZZZ (4U)    /* 维护指令索引-控制装置指令  */
#define COMM_MAINT_R_CON_CMD_NUM (5U)    /* 维护控制指令数量   */

#define COMM_MAINT_R_CMD_FLAG_INVALID (0U)    /* 指令更新标志无效  */
#define COMM_MAINT_R_CMD_FLAG_VALID (0x34U) /* 指令更新标志有效  */

/*************************************************************************************/
/* 维护通信发送软件版本信息打包相关宏定义 */
#define COMM_MAINT_TX_VERSION_INFO_NUM (15U)       /* 软件版本发送信息数量        */

/* 软件CRC码ID定义 */
#define SOFTW_V_APP_ID (0U)  /* 应用软件CRC码ID     */
#define SOFTW_V_UPODATE_ID (1U)  /* 加载软件CRC码ID     */

/*************************************************************************************/
/* 维护通信接收数据结构体 */
typedef struct _RsMaintDataInfo
{
	Uint16 rxFrameCnt_u16;                        /* 接收帧计数                          */

	Uint16 MaintStateCode_u16;                    /* 维护状态码                           */
	Uint16 MaintCMDCode_u16;                      /* 维护指令码                           */
	Uint16 MaintFuncCode_u16;                     /* 维护功能码                           */

	Uint16 A429InfoID_u16;                       /* 429通信信息ID号          */
	Uint16 FlowB422InfoID_u16;                   /* 流量测量盒422通信信息ID号          */
	Uint32 readAddr_u32;                         /* 读取数据地址      */
	Uint16 RudunInfoID_u16;                      /* 余度数据索引      */
	Uint16 SoftVInfoID_u16;                      /* 软件版本信息ID号   */
	Uint16 AnaInfoID_u16;                        /* 模拟量信息ID号   */
	Uint16 BengInfoID_u16;                       /* 泵控制器信息ID号   */
	Uint16 A429RxLabel_u16;                      /* 429通信接收标号      */

	Uint16 cmdUpdateflag_u16;                    /* 指令更新标志            */
	Uint16 cmdInfoID_u16;                        /* 维护指令ID号           */

    Uint32 downLoadStartAddr_u32;                 /* 数据下载起始地址                 */
    Uint32 downLoadAddrLen_u32;                   /* 数据下载地址长度                 */
    Uint16 hardVersion_u16;                       /* 硬件版本调整值                   */
    Uint16 hardVersionChecksum_u16;               /* 硬件版本调整校验                 */
    Uint16 MaintFuncLastExe_u16;                  /* 最近一次执行的维护功能码         */
    Uint16 MaintFuncExeResult_u16;                /* 最近一次维护功能执行结果         */

}RsMaintDataInfo_t;

/*************************************************************************************/
/* 422通信数据结构体定义 */

/* 422通信缓存信息结构体  */
typedef struct _Rs422CommBuff
{
    Uint16 commBuff_u16[COMM_CCDL_MAX_BUFF_LEN]; /* 接收数据缓冲区               */
    Uint16 index_u16;                               /* 缓冲区索引                       */
    Uint16 timeOutCount_u16;                        /* 缓冲区超时清除数据计数 */
    Uint16 headErrCount_u16;                        /* 帧头错误清除数据计数     */
    Uint16 overCount_u16;                           /* 缓冲区溢出计数                 */

}Rs422CommBuff_t;

/* 422通信状态信息结构体  */
typedef struct _Rs422CommInfo
{
    Uint16  rxBytesCount_u16;                       /* 接收数据计数           */
    Uint32  rxBytesTime_u32;                        /* 接收数据时间           */
    Uint32  checkRxTime_u32;                        /* 接收检查数据时间    */
    Uint16  rxFrameCount_u16;                       /* 接收有效报文计数    */
    Uint32  rxFrameTime_u32;                        /* 接收有效报文时间    */
    Uint16  sciErrCount_u16;                        /* SCI接口错误计数    */
    Uint16  rxState_u16;                            /* 通信接收状态            */

}Rs422CommInfo_t;

/* 422通信长度配置信息结构体  */
typedef struct _Rs422CommLenConf
{
    Uint16  rxFrameLen_u16;    /* 接收报文长度           */
    Uint16  rxBuffLen_u16;     /* 接收缓存区长度       */

}Rs422CommLenConf_t;

/* ***************************************************************** */
/**
 * 供外部调用函数接口
 */
/* ***************************************************************** */

extern void   Comm422DataBuffRead(Uint16 v_commID_u16);
extern Uint16 Comm422FrameProcess(Uint16 v_commID_u16);
extern void   Comm422FrameCleanup(Uint16 v_commID_u16);
extern Uint16 * Comm422FrameBufferGet(Uint16 v_commID_u16);
extern Uint16 Comm422RxBufferIndexGet(Uint16 v_commID_u16);
extern void   Comm422RxBufferCompact(Uint16 v_commID_u16, Uint16 v_consumedLen_u16);
extern Rs422CommInfo_t Comm422CommInfoGet(Uint16 v_commID_u16);
extern void   Comm422Init(void);
extern void CommMaintCommSend(void);
extern void CommMaintTxDataPack(void);
extern void MaintRxDataProcess(Uint16 v_commID_u16,Uint16 v_sIndex_u16);
extern const RsMaintDataInfo_t * CommMaintDataGet(void);
extern union SoftwVData SoftwVDataGet(void);
extern void   DownLoadDataCommSend(Uint32 v_startAddr_u32,Uint32 v_addrLen_u32);
extern Uint16 GroundMaintProcessSoftwCRC(void);
extern Uint16 GroundMaintProcessDataDownLoad(void);
extern Uint16 GroundMaintProcessDataErase(void);
extern Uint16 GroundMaintProcessHardVersionAdjust(void);
extern Uint16 GroundMaintProcessBitClear(void);
extern void   CommMaintExecStatusUpdate(Uint16 v_func_u16, Uint16 v_result_u16);
extern Uint16 CommMaintSoftwCrcGet(Uint16 v_crcID_u16);
#endif /* COMM422_H_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
