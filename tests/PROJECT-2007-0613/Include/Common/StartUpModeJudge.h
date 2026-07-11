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
 *        文件名称:    StartaUpModeJudge.h
 *
 *        功能说明:   本程序用以实现冷热启动判别功能。
 *
 *        文件日期:   REDACTED
 *
 *
 *        程序版本:   V1.01
 *
 * 【功能描述】实现冷热启动判别
 *
 * 【其他说明】无
 *
 *********************************************************************************/

#ifndef STARTUP_MODEJUDGE_H_
#define STARTUP_MODEJUDGE_H_

/********************************************************************/

#define COLD_POW_STARTUP_MODE  	  (0x00U)        /* 上电冷启动               */
#define HOT_EXT_STARTUP_MODE      (0x11U)        /* 外狗热启动               */
#define HOT_INN_STARTUP_MODE      (0x22U)        /* 内狗热启动               */

#define CPLD_STARTUP_FLAG_COLD    (0x0000U)      /* CPLD冷启动标志值 */
#define CPLD_STARTUP_FLAG_HOT     (0x1234U)      /* CPLD热启动标志值 */

#define STARTUP_JUDGE_PHASE_PENDING   (0x12349089UL) /* 冷启动首拍已触发复位等待返回 */
#define STARTUP_JUDGE_PHASE_READY     (0x5678901UL) /* 冷启动一次复位已完成 */
/********************************************************************/
/* 提供函数接口外部声明 */
extern void   StartUpEarlyColdResetOnce(void);
extern void   StartUpModeJudge(void);
extern Uint16 StartUpModeGet(void);

/********************************************************************/
/* StartUpModeJudge.c 私有宏定义 */
#define STARTUP_FLAG_VERIFY_RETRY_MAX      (10U)  /* 启动标志写后回读最大重试次数 */
#define STARTUP_FLAG_VERIFY_RETRY_DELAY_US (100U) /* 启动标志写后回读间隔 */

#endif /* STARTUP_MODEJUDGE_H_ */

/**********************************************************************
 * END OF FILE
 *********************************************************************/
