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
* 文件名称:   PuBIT
*
* 文件日期:   REDACTED
*
*
* 程序版本:      V2.00
*
**********************************************************************************
*
* 功能说明:
*
* 上电BIT检测相关定义
*
*********************************************************************************/

#ifndef PUBIT_H_
#define PUBIT_H_

/*********************************************************************/
/* 定义上电自检相关宏定义*/

#define PUBIT_INDEX_CPU				    (0U)			/* 上电自检 CPU检测                      */
#define PUBIT_INDEX_FLASH 		 	    (1U)		    /* 上电自检 FLASH检测                 */
#define PUBIT_INDEX_CCDL_TX	     	    (2U)		    /* 上电自检  CCDL检测                        */
#define PUBIT_INDEX_CPLD	     	    (3U)		    /* 上电自检 CPLD检测                        */
#define PUBIT_INDEX_CCDL_CPLD			(4U)			/*上电自检 与CPLD的CCDL检测*/
#define PUBIT_INDEX_SYNC                (5U)            /* 上电自检 通道同步检测                 */
#define PUBIT_INDEX_AD                  (6U)            /* 上电自检 片上AD检测                    */
#define PUBIT_INDEX_P5V                 (7U)            /* 上电自检 5V电源检测                    */
#define PUBIT_INDEX_3V3                 (8U)            /* 上电自检 3.3V电源检测                  */
#define PUBIT_INDEX_2V5                 (9U)            /* 上电自检 2.5V电源检测                  */
#define PUBIT_INDEX_1V2                 (10U)           /* 上电自检 1.2V电源检测                  */
#define PUBIT_INDEX_ROLE_IDENTIFY       (11U)           /* 上电自检 主备通道状态识别检测          */


#define PUBIT_INDEX_NUM				    (12U)			/* 上电自检总检测数  */

/*********************************************************************/
/* 定义上电自检结果*/
#define PUBIT_TEST_OK                    BIT_TEST_OK        /* 上电自检结果正常         */
#define PUBIT_TEST_ERR                   BIT_TEST_ERR       /* 上电自检结果异常         */

#define PUBIT_KEY_FAULT_CODE            ((0x01U << PUBIT_INDEX_CPU) | \
                                         (0x01U << PUBIT_INDEX_CPLD) | \
                                         (0x01U << PUBIT_INDEX_AD) | \
                                         (0x01U << PUBIT_INDEX_P5V) | \
                                         (0x01U << PUBIT_INDEX_ROLE_IDENTIFY))    /* 上电BIT关键故障掩码  */

/* ***************************************************************** */
#define PUBIT_RECOABLE               BIT_RECOABLE    /* 该IFBIT测试项故障时可恢复 */
#define PUBIT_UN_RECOABLE            BIT_UN_RECOABLE /* 该IFBIT测试项故障时不可恢复   */

#define PUBIT_FLEVEL_0               (0U)     /* 周期BIT自检故障等级 */
#define PUBIT_FLEVEL_1               (1U)     /* 周期BIT自检故障等级，控制切换 */
#define PUBIT_FLEVEL_2               (2U)     /* 周期BIT自检故障等级，控制切换   */
/************************************************************************/

#define PUBIT_CCDL_TIME				(200000UL)	/*200ms*/
#define PUBIT_TEST_RETRY_MAX            (3U)            /* 上电BIT重试次数 */
#define PUBIT_TEST_PASS_MIN             (2U)            /* 上电BIT判正常最小通过次数 */

/* PuBIT检测相关结构体定义 */

typedef struct _PiBITDataConf    /* 周期BIT配置信息结构体    */
{
    Uint16 recoAble_u16;            /* 该检测项故障时是否可恢复 */
    Uint16 faultValidCount_u16;     /* 该检测项检测报故次数     */
    Uint16 recoValidCount_u16;      /* 该检测项故障恢复次数     */
    Uint16 faultLevel_u16;          /* 该检测项故障处理等级     */

}PuBITDataConf_t;

typedef struct _PuBITData            /* 周期BIT数据结构体            */
{
    Uint16 currState_u16;           /* 该IFBIT检测项当前状态      */
    Uint16 recoAble_u16;            /* 该IFBIT检测项是否可恢复   */
    Uint16 faultCount_u16;          /* 该检测项当前故障连续计数  */
    Uint16 faultValidCount_u16;     /* 该检测项检测报故次数          */
    Uint16 recoCount_u16;           /* 该检测项当前故障恢复计数   */
    Uint16 recoValidCount_u16;      /* 该检测项故障恢复次数           */
    Uint16 faultLevel_u16;          /* 该检测项故障处理等级           */
    Uint32 errInfo_u32;             /* 该检测项故障相关信息            */

}PuBITData_t;
/**
 * 供外部调用函数接口
 */
/* ***************************************************************** */
extern Uint16 PuBITTest(void);
extern void   PuBITHotResetBypassInit(void);
extern Uint16 PuBITDataGet(void);
extern Uint16 PUBITInfoGet(Uint16 v_index_u16);
extern void   PuBITForceResultUpdate(Uint16 v_index_u16, Uint16 v_result_u16);
/*********************************************************************/
#endif /* end of include guard: PUBIT_H_*/

/* ===================================================================================== */
/* END OF FILE */
/* ===================================================================================== */
