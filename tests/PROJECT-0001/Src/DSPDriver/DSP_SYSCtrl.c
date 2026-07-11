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
 * 文件名称:    DSP_SYSCtrl
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V1.00
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 *
 *********************************************************************************/

#include "Global.h"

#pragma CODE_SECTION(InitFlash,"ramfuncs")
void InitFlash(void)
{
   EALLOW;
   //Enable Flash Pipeline mode to improve performance
   //of code executed from Flash.
   FlashRegs.FOPT.bit.ENPIPE = 1;

   //                CAUTION
   //Minimum waitstates required for the flash operating
   //at a given CPU rate must be characterized by TI.
   //Refer to the datasheet for the latest information.

   /* #if DSP_SYSCLK == 120.0 */
   //Set the Paged Waitstate for the Flash
   FlashRegs.FBANKWAIT.bit.PAGEWAIT = 5;

   //Set the Random Waitstate for the Flash
   FlashRegs.FBANKWAIT.bit.RANDWAIT = 5;

   //Set the Waitstate for the OTP
   FlashRegs.FOTPWAIT.bit.OTPWAIT = 8;
/* #endif */

/*
 * #if DSP_SYSCLK == 100.0
 *    //Set the Paged Waitstate for the Flash
 *    FlashRegs.FBANKWAIT.bit.PAGEWAIT = 3;
 * 
 *    //Set the Random Waitstate for the Flash
 *    FlashRegs.FBANKWAIT.bit.RANDWAIT = 3;
 * 
 *    //Set the Waitstate for the OTP
 *    FlashRegs.FOTPWAIT.bit.OTPWAIT = 5;
 * #endif
 */
   //                CAUTION
   //ONLY THE DEFAULT VALUE FOR THESE 2 REGISTERS SHOULD BE USED
   FlashRegs.FSTDBYWAIT.bit.STDBYWAIT = 0x01FF;
   FlashRegs.FACTIVEWAIT.bit.ACTIVEWAIT = 0x01FF;
   EDIS;

   //Force a pipeline flush to ensure that the write to
   //the last register configured occurs before returning.

   asm(" RPT #7 || NOP");
}

/* ***************************************************************** */
/**
 * 【函数名】:MemCopy
 * 【功能描述】内存复制,从源地址复制到目标地址
 * 【输入参数说明】SourceAddr ---- 源起始地址
 * 【输入参数说明】SourceEndAddr ---- 源结束地址(不含)
 * 【输入参数说明】DestAddr ---- 目标起始地址
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void MemCopy(Uint16 *SourceAddr, Uint16* SourceEndAddr, Uint16* DestAddr)
{
    while (SourceAddr < SourceEndAddr)
    {
        *DestAddr = *SourceAddr;
        DestAddr++;
        SourceAddr++;
    }

    return;
}

//==================================================================
//END OF FILE
//==================================================================
