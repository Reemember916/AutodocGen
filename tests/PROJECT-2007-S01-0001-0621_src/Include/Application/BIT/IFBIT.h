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
* 文件名称:   IFBIT
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
* 周期BIT检测相关定义
*
*********************************************************************************/

#ifndef IFBIT_

#define IFBIT_

#include "BITCommon.h"


/************************************************************************/
/* 周期BIT检测项索引 */

#define IFBIT_INDEX_P5V		 	          (0U)		/* 0周期自检  +5V电源检测                  */
#define IFBIT_INDEX_3V3   			      (1U)		/* 1周期自检  3.3V电源检测                 */
#define IFBIT_INDEX_2V5			          (2U)		/* 2周期自检  2.5V电源检测                 */
#define IFBIT_INDEX_1V2			          (3U)		/* 3周期自检  1.2V电源检测                 */
#define IFBIT_INDEX_POWER_SEC		 	  (4U)		/* 4周期自检  二次电源检测                 */
#define IFBIT_INDEX_POWER_THR		 	  (5U)		/* 5周期自检  三次电源检测                 */
#define IFBIT_INDEX_CPLD_HEART            (6U)     /* 6周期自检  CPLD心跳检测                 */
#define IFBIT_INDEX_COMM_CCDL_SCI         (7U)     /* 7周期自检  板件SCI通讯检测              */
#define IFBIT_INDEX_COMM_DPV_HEART        (8U)     /* 8周期自检  板间心跳检测                 */
#define IFBIT_INDEX_COMM_CCDL_CPLD        (9U)     /* 9周期自检  与CPLD的CCDL通讯检测         */
#define IFBIT_INDEX_FRAME_SYNC            (10U)    /* 10周期自检 帧同步检测                   */
#define IFBIT_INDEX_COMM_429RIU_1         (11U)    /* 11周期自检 RIU通道1检测                 */
#define IFBIT_INDEX_COMM_429RIU_2         (12U)    /* 12周期自检 RIU通道2检测                 */
#define IFBIT_INDEX_COMM_429RIU_3         (13U)    /* 13周期自检 RIU通道3检测                 */
#define IFBIT_INDEX_COMM_429RIU           (14U)    /* 14周期自检 RIU综合检测                  */
#define IFBIT_INDEX_COMM_429LEFT_RX       (15U)    /* 15周期自检 左吊舱接收检测               */
#define IFBIT_INDEX_COMM_429RIGHT_RX      (16U)    /* 16周期自检 右吊舱接收检测               */
#define IFBIT_INDEX_COMM_429KZZZ          (17U)    /* 17周期自检 KZZZ接收综合检测             */
#define IFBIT_INDEX_AD                    (18U)    /* 18周期自检 片上AD通道检测               */
#define IFBIT_INDEX_COMM_429TX_RIU        (19U)    /* 19周期自检 RIU发送回绕检测              */
#define IFBIT_INDEX_COMM_429TX_LEFT       (20U)    /* 20周期自检 左吊舱发送回绕检测           */
#define IFBIT_INDEX_COMM_429TX_RIGHT      (21U)    /* 21周期自检 右吊舱发送回绕检测           */
#define IFBIT_INDEX_COMM_429TX            (22U)    /* 22周期自检 429发送综合检测              */
#define IFBIT_NUM                         (23U)    /* IFBIT总检测项数                         */


#define POWER_BIT_NUM                     (5U)      /* 周期电源检测数量      */

/************************************************************************/
/* BIT检测配置相关宏定义 */

#define IFBIT_TEST_OK                BIT_TEST_OK        /* 周期自检正常(0) */
#define IFBIT_TEST_ERR               BIT_TEST_ERR       /* 周期自检异常(1) */
#define IFBIT_RECOABLE               BIT_RECOABLE       /* 该IFBIT测试项故障时可恢复(0) */
#define IFBIT_UN_RECOABLE            BIT_UN_RECOABLE    /* 该IFBIT测试项故障时不可恢复(1) */

#define IFBIT_FLEVEL_0               (0U)     /* 周期BIT自检故障等级 */
#define IFBIT_FLEVEL_1               (1U)     /* 周期BIT自检故障等级，控制切换 */

#define IFBIT_DINDEX_FLEVEL           (0U)     /* 周期BIT故障处理等级 */
#define IFBIT_DINDEX_RESULTS_BIT32_1  (1U)     /* 周期BIT结果数据低32位索引    */

/************************************************************************/
/* 周期BIT检测相关结构体定义 */

typedef struct _IFBITDataConf    /* 周期BIT配置信息结构体    */
{
    Uint16 recoAble_u16;            /* 该检测项故障时是否可恢复 */
    Uint16 faultValidCount_u16;     /* 该检测项检测报故次数     */
    Uint16 recoValidCount_u16;      /* 该检测项故障恢复次数     */
    Uint16 faultLevel_u16;          /* 该检测项故障处理等级     */

}IFBITDataConf_t;

typedef BITCommonData_t IFBITData_t; /* 周期BIT数据结构体 */

/* ***************************************************************** */
/**
 * 供外部调用函数接口
 */
/* ***************************************************************** */

extern void   IFBITTest(void);
extern Uint32 IFBITResultGet(Uint16 v_index_u16);
extern Uint32 IFBITInfoGet(Uint16 v_index_u16);
extern void   IFBITDataInit(void);
extern void IFBITStateUpdate(Uint16 v_index_u16, Uint16 v_newState_u16, Uint32 v_info_u32);


#endif

/* =============================================================================== */
/* END OF FILE */
/* =============================================================================== */
