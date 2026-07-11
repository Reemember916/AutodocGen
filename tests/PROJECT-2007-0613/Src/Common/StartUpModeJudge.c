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
 *        文件名称:    StartaUpModeJudge.c
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
 *********************************************************************************
 * 功能说明:
 * 本功能模块用以实现“冷启动先软件复位一次，再由CPLD维持热启动标志”的启动模式判别，实现原则如下：
 *
 * 1.首次加电后，NOINIT RAM为空，软件先记录PENDING态并立即执行一次软件看门狗复位。
 * 2.软件复位返回后，若检测到“WDFlag有效 + RAM处于PENDING态”，则本次启动对外仍按上电冷启动处理，并将RAM切到READY。
 * 3.冷启动闭环完成后，软件再向CPLD写入“热启动标志”并回读校验；后续不掉电复位时，由CPLD热启动标志配合WDFlag区分内狗/外狗热启动。
 * 4.看门狗寄存器复位标志和NOINIT RAM只承担冷启动一次复位闭环，不再负责长期冷热启动记忆。
 * 5.头文件中模块提供外部调用的API函数接口如下：
 *    StartUpEarlyColdResetOnce ---- 早期冷启动一次复位闭环
 *    StartUpModeJudge          ---- XINTF和CPLD总线握手完成后基于CPLD确认冷热启动模式
 *    StartUpModeGet            ---- 冷热启动模式获取
 *
 * 6.NOTE:
 *    `StartUpEarlyColdResetOnce()` 需要放在初始化最前端，在系统时钟初始化之前执行；
 *    `StartUpModeJudge()` 需要放在XINTF初始化且CPLD握手成功之后执行。
 *
 *********************************************************************************/

#include "Global.h"
#include "StartUpModeJudge.h"

/*********************************************************************/


/* 上电启动模式 */
Uint16 s_startUpMode_u16  = COLD_POW_STARTUP_MODE;

#pragma DATA_SECTION(s_startUpJudgeState_u32, "startup_judge")
volatile Uint32 s_startUpJudgeState_u32;
static Uint16 s_startUpColdResetReturned_u16 = INVALID; /* 本次启动是否刚完成冷启动软件复位返回 */

/* ***************************************************************** */
/**
 * 【函数名】:StartUpFlagHotWriteVerify
 *
 * 【功能描述】向CPLD写入热启动标志，并执行回读校验与重试。
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       仅在XINTF和CPLD握手完成后调用。
 * 【返回】VALID-写入并校验成功 / INVALID-多次重试仍失败
 *
 ****************************************************************** */
static Uint16 StartUpFlagHotWriteVerify(void)
{
    Uint16 l_retry_u16 = 0U;
    Uint16 l_readFlag_u16 = CPLD_STARTUP_FLAG_COLD;

    for(l_retry_u16 = 0U; l_retry_u16 < STARTUP_FLAG_VERIFY_RETRY_MAX; l_retry_u16++)
    {
        HARD_XINT_UINT16(CPLD_ADDR_W_STARTUP_FLAG) = CPLD_STARTUP_FLAG_HOT;
        delayUs(STARTUP_FLAG_VERIFY_RETRY_DELAY_US);
        l_readFlag_u16 = HARD_XINT_UINT16(CPLD_ADDR_R_STARTUP_FLAG);

        if(CPLD_STARTUP_FLAG_HOT == l_readFlag_u16)
        {
             return VALID;
        }
    }

    return INVALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:StartUpEarlyColdResetOnce
 *
 * 【功能描述】早期冷启动一次复位闭环
 *             1. RAM无有效标记时，认为当前是加电首拍，先写PENDING并触发一次软件看门狗复位。
 *             2. 软件复位返回后，若检测到PENDING + WDFlag有效，则标记“本次启动刚完成冷启动复位返回”，并把RAM切到READY。
 *             3. 本函数运行在XINTF初始化前，不访问任何CPLD寄存器。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】
 * 1. `s_startUpJudgeState_u32` 位于 `startup_judge` NOINIT段，掉电清零、复位保持。
 * 2. 状态机取值：
 *   `STARTUP_JUDGE_PHASE_PENDING`：已识别到冷启动首拍，等待看门狗复位返回。
 *   `STARTUP_JUDGE_PHASE_READY`：冷启动恢复已完成，系统进入正常运行，可区分外狗/内狗热启动。
 * 3. 本函数只做“是否需要立刻再复位一次”的早期判断；真正冷热启动模式由 `StartUpModeJudge()` 在XINTF初始化后确认。
 *
 * 【返回】NONE
 *
 ****************************************************************** */
void StartUpEarlyColdResetOnce(void)
{
    Uint16 l_WDFlag_u16 = 0U;      /* 喂狗复位标志 */
    Uint16 l_markerReady_u16 = INVALID;   /* RAM标志处于READY态 */
    Uint16 l_markerPending_u16 = INVALID; /* RAM标志处于冷启动复位待确认态 */

    /* 先读取看门狗来源，再查看RAM是否已经完成过冷启动一次复位闭环。 */
    l_WDFlag_u16 = WDogWDFlagGet();
    s_startUpColdResetReturned_u16 = INVALID;
    if (STARTUP_JUDGE_PHASE_READY == s_startUpJudgeState_u32)
    {
        l_markerReady_u16 = VALID;
    }
    else
    {
        l_markerReady_u16 = INVALID;
    }
    if (STARTUP_JUDGE_PHASE_PENDING == s_startUpJudgeState_u32)
    {
        l_markerPending_u16 = VALID;
    }
    else
    {
        l_markerPending_u16 = INVALID;
    }

    /* PENDING + WDFlag有效表示这是冷启动首拍触发的软件复位返回路径。 */
    if((WDOG_WDFLAG_VALID == l_WDFlag_u16) && (VALID == l_markerPending_u16))
    {
        s_startUpJudgeState_u32 = STARTUP_JUDGE_PHASE_READY;
        s_startUpColdResetReturned_u16 = VALID;
    }
    else if(INVALID == l_markerReady_u16)
    {
        /* RAM中既没有READY也没有PENDING，说明这是掉电后的第一拍，需先执行一次软件复位闭环。 */
        s_startUpJudgeState_u32 = STARTUP_JUDGE_PHASE_PENDING;
        WDogReset();
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:StartUpModeJudge
 *
 * 【功能描述】在XINTF初始化后基于CPLD冷热启动标志确认本次启动模式
 *             1. 若本次启动刚完成冷启动软件复位返回，则直接上报冷启动，并向CPLD写入热启动标志。
 *             2. 其余情况下，从CPLD读取冷热启动标志；读到热启动值时，再由WDFlag区分内狗/外狗热启动。
 *             3. 若CPLD标志为冷启动或异常值，则保守按冷启动上报，并重新把CPLD标志写成热启动供后续复位使用。
 *             4. 对热启动标志写入执行回读校验，避免CPLD未锁存时 silently fail。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       本函数要求在XINTF初始化且CPLD握手成功后调用。
 * 【返回】上电冷热启动模式 ，可能取值如下：
 * 		COLD_POW_STARTUP_MODE ---- 上电冷启动
 *		HOT_EXT_STARTUP_MODE  ---- 外狗热启动（外部电路（如FPGA）将DSP的XRS复位管脚拉低）
 *		HOT_INN_STARTUP_MODE  ---- 内狗热启动
 *
 ****************************************************************** */
void StartUpModeJudge(void)
{
    Uint16 l_WDFlag_u16 = 0U;      /* 喂狗复位标志 */
    Uint16 l_startupFlag_u16 = 0U; /* CPLD冷热启动标志 */

    l_WDFlag_u16 = WDogWDFlagGet();
    s_startUpMode_u16 = COLD_POW_STARTUP_MODE;

    if(VALID == s_startUpColdResetReturned_u16)
    {
        /* 刚完成冷启动软件复位返回，本次启动仍对外报告为冷启动。 */
        (void)StartUpFlagHotWriteVerify();
        return;
    }

    /* 冷启动闭环已经完成后，后续冷热启动来源由CPLD标志提供。 */
    l_startupFlag_u16 = HARD_XINT_UINT16(CPLD_ADDR_R_STARTUP_FLAG);
    if(CPLD_STARTUP_FLAG_HOT == l_startupFlag_u16)
    {
        if (WDOG_WDFLAG_VALID == l_WDFlag_u16)
        {
            s_startUpMode_u16 = HOT_INN_STARTUP_MODE;
        }
        else
        {
            s_startUpMode_u16 = HOT_EXT_STARTUP_MODE;
        }
    }
    else
    {
        /* CPLD标志为冷启动或异常值时，保守按冷启动处理，并为后续复位补写热启动标志。 */
        (void)StartUpFlagHotWriteVerify();
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:StartUpModeGet
 *
 * 【功能描述】冷热启动模式获取
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】上电启动模式 ，可能取值如下：
 * 		COLD_POW_STARTUP_MODE ---- 上电冷启动
 *		HOT_EXT_STARTUP_MODE  ---- 外狗热启动
 *		HOT_INN_STARTUP_MODE  ---- 内狗热启动
 *
 ****************************************************************** */
Uint16 StartUpModeGet(void)
{
    /* 返回上电启动模式数据 */
    return s_startUpMode_u16;
}

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
