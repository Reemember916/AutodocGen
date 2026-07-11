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
 * 文件名称:    Main.h
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V0.0.1.3
 *
 **********************************************************************************
 *
 * 功能说明:    Main.c 的私有定义头文件
 *
 *    集中存放 Main.c 内部使用的任务时间片配置宏、本地变量 extern 声明
 *    及内部函数原型，供 Main.c 自身引用，不对外部模块开放。
 *
 *********************************************************************************/

#ifndef MAIN_H_

#define MAIN_H_

#include "Global.h"

/* ******************************************************************************** */
/* 配置第1步：配置任务时间片数量和索引！！！ */

/* 任务时间数据索引定义  */
#define TASK_TIME_PERIOD              (100000UL)   /*  任务主周期时间，单位us  */
#define TASK_DATASAPLE_TIME_PERIOD    (10000UL)    /* 数据采集周期时间单位us  */
#define TASK_COMM_RX_TIME_PERIOD      (20000UL)    /* 通信缓存数据接收周期时间单位us  */
#define TASK_CON_TIME_PERIOD          (50000UL)    /*  控制任务周期时间，单位us  */
#define TASK_COMM_TX_TIME_PERIOD      (10000UL)    /*  通信发送任务周期时间，单位us  */
#define TASK_MAINT_TX_TIME_PERIOD     (10000UL)    /*  维护通信发送任务周期时间，单位us  */

/* 任务时间片数量 */
#define TASK_TIME_NUM                 (7U)

#define TASK_TIME_INDEX_SAMPLE        (0U)   /* 任务时间片索引  数据采集                        */
#define TASK_TIME_INDEX_COMM_RX       (1U)   /* 任务时间片索引  通信接收                        */
#define TASK_TIME_INDEX_CON           (2U)   /* 任务时间片索引  系统控制                       */
#define TASK_TIME_INDEX_COMM_TX       (3U)   /* 任务时间片索引  通信发送          */
#define TASK_TIME_INDEX_MAINT_TX      (4U)   /* 任务时间片索引  维护通信发送   */
#define TASK_TIME_INDEX_STORE         (5U)   /* 任务时间片索引 数据存储                        */
#define TASK_TIME_INDEX_LED           (6U)   /* 任务时间片索引 心跳灯闪烁                    */

#define LED_TOGGLE_COUNT_BACKUP       (5U)   /* 备份态每500ms翻转一次，整周期1s */
#define LED_TOGGLE_COUNT_MASTER       (2U)   /* 主控态每200ms翻转一次，整周期400ms */

/* ******************************************************************************** */
/* Main.c 本地变量 extern 声明 */

extern Uint32 s_taskTimeData_u32[TASK_TIME_NUM];  /* 任务时间数据                                            */
extern Uint32 s_syncTime_u32;                     /* 同步时间           */
extern Uint32 s_taskTimeConf_u32[TASK_TIME_NUM];  /* 任务配置时间，以同步完成时间为基准 */

extern Uint16 s_ConCnt_u16;        /* 系统控制计数   */
extern Uint16 s_ccdlTxPhase_u16;   /* CCDL运行期发送相位(100ms内10个10ms子相位) */
extern Uint16 s_429RIUTxCnt_u16;   /* RIU通信发送计数 */
extern Uint16 s_429RIURxCnt_u16;   /* RIU通信接收计数 */
extern Uint16 s_ledCount_u16;      /* 心跳灯闪烁计数      */
extern Uint16 s_SovConCnt_u16;     /* 电磁阀控制计数      */
extern Uint16 s_CarbinConCnt_u16;  /* 舱门控制计数      */
extern Uint16 s_WDogCnt_u16;       /* 喂狗计数      */

/* ******************************************************************************** */
/* Main.c 内部函数原型 */

extern void TimeCountInit(void);

#endif /* end of include guard: MAIN_H_ */

/* ===================================================================================== */
/* END OF FILE */
/* ===================================================================================== */
