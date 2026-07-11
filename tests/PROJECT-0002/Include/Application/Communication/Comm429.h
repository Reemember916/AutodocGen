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
 * 文件名称:    comm429.h
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
 * 定义429通信结构体
 *
 *********************************************************************************/

#ifndef COMM429_H_
#define COMM429_H_



#define COMM429_RIU_NUM        (3U)    /* 任务计算机通信数量  */
#define COMM429_JYB_NUM        (1U)    /* 加油泵控制器通信数量  */
#define COMM429_KZZZ_NUM       (2U)    /*控制装置通信数量  */



#define COMM429_RIU_1          (0U)    /* 本通道任务计算机通信  */
#define COMM429_RIU_2          (1U)    /* 备份通道任务计算机通信SCI口  */
#define COMM429_RIU_3          (2U)    /* 备份通道任务计算机通信CPLD口  */

#define COMM429_JYB_1          (0U)    /* 加油泵控制器1通信  */
#define COMM429_JYB_2          (1U)    /* 加油泵控制器2通信  */

#define COMM429_KZZZ_1         (0U)    /*控制装置1通信  */
#define COMM429_KZZZ_2         (1U)    /*控制装置2通信  */


#define COMM429_RMC_PRIOD      (100U)  /* 任务计算机通信周期ms  */
#define COMM429_RIU_PRIOD      (200U)  /* RIU通信周期ms，按20260318需求口径收敛为200ms */
#define COMM429_DMP_PRIOD      (180U)  /* 数据采集管理处理机通信周期ms  */

#define COMM429_FAULT_CNT      (50U)   /* 429通信故障时间阈值 计数*周期  */
#define COMM429_JYB_PRIOD_MS   (100U)  /* 加油泵控制器通信周期ms  */
#define COMM429_KZZZ_PRIOD     (200U)  /* 控制装置通信周期ms；当前周期量发送与需求口径统一为200ms */

/* 接收状态检查相关宏定义 */
#define RX429_STATE_OK      (0x00U)    /* 状态正常 */
#define RX429_STATE_ERR     (0x01U)    /* 状态异常 */

/* SSM相关宏定义（ARINC429标准语义） */
#define SSM_FAULT      (0x00U)    /* 故障数据   */
#define SSM_NOCOMDATA  (0x01U)    /* 非计算数据 */
#define SSM_TEST       (0x02U)    /* 功能测试   */
#define SSM_NORM       (0x03U)    /* 正常数据   */

/* 429通信状态信息结构体 */
typedef struct _A429Info
{
	Uint32 rxCount_u32;             /* 接收计数 */
    Uint16 rxState_u16;             /* 接收状态 */
    Uint32 rxTime_u32;              /* 接收时间 */
    Uint16 rxDataState_u16;         /* 接收数据状态 */
    Uint16 ovflErrCount_u16;        /* FIFO溢出错误计数      */
    Uint16 labelErrCount_u16;       /* 标号错误计数 */

	Uint32 errCntSum_u32;           /* 接收错误总数 */
	Uint32 errCnt_u32;              /* 接收连续错误数 */
	Uint32 errCntMax_u32;           /* 接收连续最大错误数 */

}A429Info_t;

/* 万年历时间结构体 */
typedef struct _DateTime
{
	Uint16 Year_u16     ;       /* 年   */
	Uint16 Month_u16    ;       /* 月   */
	Uint16 Day_u16      ;       /* 日   */
	Uint16 Hour_u16     ;       /* 时   */
	Uint16 Minute_u16   ;       /* 分   */
	Uint16 Second_u16   ;       /* 秒   */
	Uint16 MillSec_u16  ;       /* 毫秒 */

}DateTime_t;



/* 剩余日历寿命联合体 */
typedef union{
    Uint32  all;
    struct{
        Uint32 gwYear_u32:4U;    /* bit0-3:年*1 */
        Uint32 swYear_u32:4U;    /* bit4-7:年*10 */
        Uint32 gwMonth_u32:4U;   /* bit8-11:月*1 */
        Uint32 swMonth_u32:1U;   /* bit12:月*10 */
        Uint32 gwDay_u32:4U;     /* bit13-16:日*1 */
        Uint32 swDay_u32:2U;     /* bit17-18:日*10 */
        Uint32 rsvd_u32:13U;     /* bit19-31:预留 */
    }bit;
}RemainLife_t;

/* 软件版本信息联合体 */
typedef union{
    Uint32  all;
    struct{
        Uint32 rsvd_1_u32:3U;        /* bit0-2:预留1 */
    	Uint32 section4_u32:8U;      /* bit3-10:第4段 */
        Uint32 section3_u32:3U;      /* bit11-13:第3段 */
        Uint32 section2_u32:3U;      /* bit14-16:第2段 */
        Uint32 section1_u32:2U;      /* bit17-18:第1段 */
        Uint32 rsvd_2_u32:13U;       /* bit19-31:预留2 */
    }bit;
}SoftVData_t;

typedef struct _Orig429Data        /* 429原始数据结构体 */
{
	Uint16 label_u16;              /* 标号  */
	Uint32 OrigData_u32;           /* 原始数据，包括整个429数据包32位数据  */
	Uint16 Cnt_u16;                /* 计数，发送或者接收对应标志数据时计数加1  */

}Orig429Data_t;

#endif /* COMM429_H_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
