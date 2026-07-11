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
 * [文件名称]			DSP_Timer.c
 *
 * [程序版本]			V1.02
 *
 * [文件日期]			REDACTED
 *
* [开发单位] TEST_ORG
 *
 * [功能描述]			定时器
 *
 * [其他说明]			软件根据软件编程规范Q/NZ 75-2020更新版本
 *
 *********************************************************************************/

#include "Global.h"

/* ***************************************************************** */
/**
 *    [函数名]			InitCpuTimers
 *    [功能描述]			本函数对Timer0,Timer1,Timer2三个定时器初始化，默认关闭所有三个定时器。
 *     					 定时器的使能状态(ENABLE)及定时周期(PERIOD)通过 DSP_Config.h 配置文件中的宏定义配置，
 *      				具体如下：
 *
 *      				|   ENABLE    |      PERIOD        |
 *      				| DSP_TIMER_0 | DSP_TIMER_0_PERIOD |
 *      				| DSP_TIMER_1 | DSP_TIMER_1_PERIOD |
 *      				| DSP_TIMER_2 | DSP_TIMER_2_PERIOD |
 *
 *      				对定时器的初始化操作主要实现如下操作：
 *     					 1. 配置定时器计数值，并加载
 *     					 2. 注册定时器中断向量
 *     					 3. 使能定时中断
 *    [输入参数说明]		NONE
 *    [输出参数说明]		NONE
 *    [其他说明]			NOTE:本函数并不启动定时器。
 *    [返回]				NONE
 */
/* ***************************************************************** */
void InitCpuTimers(void)
{
    /* 关闭所有定时器 */
    StopCpuTimer0();
    StopCpuTimer1();
    StopCpuTimer2();

#if DSP_TIMER_0

   /* 配置Timer0定时器 */
   ConfigCpuTimer(&CpuTimer0Regs,DSP_SYSCLK,DSP_TIMER_0_PERIOD);

   /* 设置Timer0中断向量 */
   EALLOW;
   PieVectTable.TINT0 = &ISR_Timer0;
   EDIS;

   /* 使能Timer0中断 */
   PieCtrlRegs.PIEIER1.bit.INTx7 = 1U;
   IER |= M_INT1;

#endif

#if DSP_TIMER_1

   /* 配置Timer1定时器 */
   ConfigCpuTimer(&CpuTimer1Regs,DSP_SYSCLK,DSP_TIMER_1_PERIOD);

   /* 设置Timer1中断向量 */
   EALLOW;
   PieVectTable.XINT13 = &ISR_Timer1;
   EDIS;

   /* 使能Timer1中断 */
   IER |= M_INT13;

#endif

#if DSP_TIMER_2

   /* 配置Timer2定时器 */
   ConfigCpuTimer(&CpuTimer2Regs,DSP_SYSCLK,DSP_TIMER_2_PERIOD);

   /* 设置Timer2中断向量 */
//   EALLOW;
//   PieVectTable.TINT2 = &ISR_Timer2;
//   EDIS;

   /* 不使能Timer2中断 */
//   IER |= M_INT14;

#endif

}

/* ***************************************************************** */
/**
 *    [函数名]			ConfigCpuTimer
 *    [功能描述]			配置定时器，依据系统时钟频率(单位:MHZ)，定时周期(单位:us)，实现对
 *     					定时器计数值的计算和设置，并重新加载计数器值，同时使能定时中断。
 *
 *    [输入参数说明]		timerReg     ---- 定时器指针，可以为 CpuTimer0Regs,CpuTimer1Regs,CpuTimer2Regs的地址
 *    					freq_u16     ---- 系统时钟频率，单位MHZ
 *    					period_u32   ---- 定时周期，单位us
 *    [输出参数说明]		NONE
 *    [其他说明]			定时器的计数值通过如下方式计算获得：
 *
 *      				定时器计数值 = 系统时钟频率 * 定时周期
 *
 *      				设置方式如下：
 *      				定时器预分频计数器值 =  系统时钟频率 - 1；
 *      				定时器周期计数器值     =  定时周期；
 *    [返回]				NONE
 */
/* ***************************************************************** */
void ConfigCpuTimer(volatile struct CPUTIMER_REGS  *timerReg, Uint16 freq_u16, Uint32 period_u32)
{
    Uint32 	l_temp_u32;

    /* 暂停定时器 */
    timerReg->TCR.bit.TSS = 1U;      // 1 = Stop timer, 0 = Start/Restart Timer

    /* 设置定时器预分频系数 */
    timerReg->TPR.all  = freq_u16 - 1U;
    timerReg->TPRH.all = 0U;

    /* 重新计算定时器计数值 */
    l_temp_u32 = period_u32 - 1U;   //重新加载定时器会消耗1个clock
    timerReg->PRD.all = l_temp_u32;

    /* 重新加载定时器计数值 */
    timerReg->TCR.bit.TRB = 1U;      // 1 = reload timer

    timerReg->TCR.bit.SOFT = 0U;
    timerReg->TCR.bit.FREE = 0U;     // Timer Free Run Disabled

    /* 使能定时器中断 */
    timerReg->TCR.bit.TIE = 1U;      // 0 = Disable/ 1 = Enable Timer Interrupt
}

//===========================================================================
// End of file.
//===========================================================================
