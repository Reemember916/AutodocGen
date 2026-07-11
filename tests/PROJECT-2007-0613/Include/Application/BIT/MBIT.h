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
* 文件名称:   MBIT
*
* 文件日期:   REDACTED
*
*
* 程序版本:   V2.00
*
**********************************************************************************
*
* 功能说明:
*
* 维护BIT检测相关定义
*
*********************************************************************************/
#ifndef MBIT_

#define MBIT_

#include "BITCommon.h"

/************************************************************************/
/* 维护BIT数据结构  */
/************************************************************************/
/* 维护BIT检测项索引 */


#define MBIT_INDEX_P5V		 	          (0U)		/* 0维护自检  +5V电源检测                  */
#define MBIT_INDEX_3V3   			      (1U)		/* 1维护自检  3.3V电源检测                 */
#define MBIT_INDEX_2V5			          (2U)		/* 2维护自检  2.5V电源检测                 */
#define MBIT_INDEX_1V2			          (3U)		/* 3维护自检  1.2V电源检测                 */


#define MBIT_INDEX_POWER_SEC		 	  (4U)		/* 4维护自检  二次电源检测                 */
#define MBIT_INDEX_POWER_THR		 	  (5U)		/* 5维护自检  三次电源检测                 */
#define MBIT_INDEX_CPLD_HEART            (6U)     /* 6维护自检  CPLD心跳检测                 */
#define MBIT_INDEX_COMM_CCDL_SCI         (7U)     /* 7维护自检  板件SCI通讯检测              */
#define MBIT_INDEX_COMM_DPV_HEART        (8U)     /* 8维护自检  板间心跳检测                 */
#define MBIT_INDEX_COMM_CCDL_CPLD        (9U)     /* 9维护自检  与CPLD的CCDL通讯检测         */
#define MBIT_INDEX_FRAME_SYNC            (10U)    /* 10维护自检 帧同步检测                   */
#define MBIT_INDEX_COMM_429RIU_1         (11U)    /* 11维护自检 RIU通道1检测                 */
#define MBIT_INDEX_COMM_429RIU_2         (12U)    /* 12维护自检 RIU通道2检测                 */
#define MBIT_INDEX_COMM_429RIU_3         (13U)    /* 13维护自检 RIU通道3检测                 */
#define MBIT_INDEX_COMM_429RIU           (14U)    /* 14维护自检 RIU综合检测                  */
#define MBIT_INDEX_COMM_429LEFT_RX       (15U)    /* 15维护自检 左吊舱接收检测               */
#define MBIT_INDEX_COMM_429RIGHT_RX      (16U)    /* 16维护自检 右吊舱接收检测               */
#define MBIT_INDEX_COMM_429KZZZ          (17U)    /* 17维护自检 KZZZ接收综合检测             */
#define MBIT_INDEX_AD                    (18U)    /* 18维护自检 片上AD通道检测               */
#define MBIT_INDEX_COMM_429TX_RIU        (19U)    /* 19维护自检 RIU发送回绕检测              */
#define MBIT_INDEX_COMM_429TX_LEFT       (20U)    /* 20维护自检 左吊舱发送回绕检测           */
#define MBIT_INDEX_COMM_429TX_RIGHT      (21U)    /* 21维护自检 右吊舱发送回绕检测           */
#define MBIT_INDEX_COMM_429TX            (22U)    /* 22维护自检 429发送综合检测              */
#define MBIT_NUM                         (23U)    /* MBIT总检测项数                          */



/************************************************************************/
/* BIT检测配置相关宏定义 */

#define MBIT_TEST_OK                BIT_TEST_OK        /* 维护自检正常(0) */
#define MBIT_TEST_ERR               BIT_TEST_ERR       /* 维护自检异常(1) */
#define MBIT_RECOABLE               BIT_RECOABLE       /* 该MBIT测试项故障时可恢复(0) */
#define MBIT_UN_RECOABLE            BIT_UN_RECOABLE    /* 该MBIT测试项故障时不可恢复(1) */

#define MBIT_FLEVEL_0               (0U)     /* 维护BIT自检故障等级 */
#define MBIT_FLEVEL_1               (1U)     /* 维护BIT自检故障等级，控制切换 */

#define MBIT_DINDEX_FLEVEL           (0U)     /* 维护BIT故障处理等级 */
#define MBIT_DINDEX_RESULTS_BIT32_1  (1U)     /* 维护BIT结果数据低32位索引    */
#define MBIT_DINDEX_RESULTS_BIT32_2  (2U)     /* 维护BIT总检测结果32-63位索引    */
#define MBIT_DINDEX_RESULTS_BIT32_3  (3U)     /* 维护BIT总检测结果64-95位索引    */
#define MBIT_DINDEX_RESULTS_BIT32_4  (4U)     /* 维护BIT总检测结果96-127位索引    */

/************************************************************************/
/* 维护BIT检测相关结构体定义 */

typedef struct _MBITDataConf    /* 维护BIT配置信息结构体    */
{
    Uint16 recoAble_u16;            /* 该检测项故障时是否可恢复 */
    Uint16 faultValidCount_u16;     /* 该检测项检测报故次数     */
    Uint16 recoValidCount_u16;      /* 该检测项故障恢复次数     */
    Uint16 faultLevel_u16;          /* 该检测项故障处理等级     */

}MBITDataConf_t;

typedef BITCommonData_t MBITData_t; /* 维护BIT数据结构体 */



/* ***************************************************************** */
/**
 * 供外部调用函数接口
 */
/* ***************************************************************** */

extern void   MBITTest(void);
extern Uint32 MBITResultGet(Uint16 v_index_u16);
extern Uint32 MBITInfoGet(Uint16 v_index_u16);
extern void   MBITDataInit(void);
extern void MBITStateUpdate(Uint16 v_index_u16, Uint16 v_newState_u16, Uint32 v_info_u32);

#endif
/* =============================================================================== */
/* END OF FILE */
/* =============================================================================== */
