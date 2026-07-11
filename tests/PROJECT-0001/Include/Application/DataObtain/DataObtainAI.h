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
* 文件名称:   DataObtainAI.h
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
* 功能说明
*
*
*********************************************************************************/
#ifndef DATAOBTAINAI_

#define DATAOBTAINAI_

/***************************************************************************/
/* 模拟量采集数量相关宏定义 */

#define ANA_DATA_NUM_TOTAL               (5U)   /* 模拟量数据总个数                            */
#define ANA_DATA_NUM_DSP                 (5U)   /* DSP片上AD采集模拟量数据个数   */
#define ANA_DATA_NUM_EXTERN              (0U)   /* 片外采集模拟量数据个数        */

#define ANA_DATA_RECORD_NUM              (5U)   /* 模拟量数据记录个数                       */


/****************************************************************/
/* 模拟量数据返回索引 */

#define ANA_DINDEX_V28                            (0U)             /* 0模拟量 28V电源（片上AD）	 */
#define ANA_DINDEX_V5                            (1U)             /* 1模拟量 5V电源（片上AD）  	 */
#define ANA_DINDEX_3V3                            (2U)             /* 2模拟量 3.3V电源 （片上AD）          */
#define ANA_DINDEX_2V5                            (3U)             /* 3模拟量 2.5V电源（片上AD）           */
#define ANA_DINDEX_1V2                            (4U)             /* 4模拟量 1.2V电源（片上AD）          */

/****************************************************************/
/* 模拟量数据返回状态宏定义 */

#define ANA_DATA_STATE_OK           (0U)             /* 模拟量数据合理性判断正确       */
#define ANA_DATA_STATE_LIMIT_ERR    (0x01U << 0U)    /* 模拟量数据合理性判断超限       */
#define ANA_DATA_STATE_CHANGE_ERR   (0x01U << 1U)    /* 模拟量数据合理性判断变化率超限 */
#define ANA_DATA_STATE_UNKNOW_ERR   (0x01U << 2U)    /* 模拟量数据未知异常             */

/* 传感器数据状态异常位宏定义*/
#define SENSOR_DATA_STATE_OK                (0x00U)            /* 传感器数据状态正常        */
#define SENSOR_DATA_STATE_SUM_LIMIT_ERR     (0x01U << 0U)      /* 传感器数据和值超限异常 */
#define SENSOR_DATA_STATE_SUB_LIMIT_ERR     (0x01U << 1U)      /* 传感器数据差值超限异常 */
#define SENSOR_DATA_STATE_ORIG_ERR          (0x01U << 2U)      /* 传感器数据原始采集数据异常 */

/****************************************************************/
/* 模拟量数据处理相关结构体 */

typedef struct _AnaData                     /* 模拟量数据结构体   */
{
    float   currData_f;                       /* 最近一次数据          */
    float   fDataBuff_f[ANA_DATA_RECORD_NUM]; /* 原始记录数据          */
    Uint16  checkState_u16;                   /* 数据检查状态          */
    Uint32  count_u32;                        /* 数据记录计数          */
    float   lastData_f;                       /* 上一拍数据，用来进行低通滤波时使用*/
}AnaData_t;

typedef struct _AnaDataConf
{
    float   hiLimit_f;                        /* 数据上限     */
    float   lowLimit_f;                       /* 数据下限     */
    float   unknownlowLimit_f;                /* 未知状态数据下限     */
    float   ratio_k_f;                        /* 系数k     */
    float   ratio_b_f;                        /* 系数b     */
    Uint16  addr_u16;                         /* CPLD 地址*/

}AnaDataConf_t;

/* ***************************************************************** */
/**
 * 供外部调用函数接口
 */
/* ***************************************************************** */

extern void   AnaDataObtain(void);

extern Uint16 AnaDataStateGet(Uint16 v_index_u16);
extern void   AnaDataInit(void);
extern float FdataAverage(float *v_pBuff_f, Uint16 v_len_16);

#endif /* end of include guard: DATAOBTAINAI_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
