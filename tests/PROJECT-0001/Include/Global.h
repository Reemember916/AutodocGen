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
 * 文件名称:    Global.h
 *
 * 文件日期：      REDACTED
 *
 *
 * 程序版本:
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 * 1.
 *
 *********************************************************************************/

#ifndef GLOBAL_

#define GLOBAL_

//===============================================
//
//  全局寄存器定义
//
//===============================================

extern cregister volatile unsigned int IFR;
extern cregister volatile unsigned int IER;

#define  EINT   asm(" clrc INTM")
#define  DINT   asm(" setc INTM")
#define  ERTM   asm(" clrc DBGM")
#define  DRTM   asm(" setc DBGM")
#define  EALLOW asm(" EALLOW")
#define  EDIS   asm(" EDIS")
#define  ESTOP0 asm(" ESTOP0")
#define  NOP    asm(" NOP")

#define M_INT1  0x0001   //宏定义命名
#define M_INT2  0x0002   //宏定义命名
#define M_INT3  0x0004   //宏定义命名
#define M_INT4  0x0008   //宏定义命名
#define M_INT5  0x0010   //宏定义命名
#define M_INT6  0x0020   //宏定义命名
#define M_INT7  0x0040   //宏定义命名
#define M_INT8  0x0080   //宏定义命名
#define M_INT9  0x0100   //宏定义命名
#define M_INT10 0x0200   //宏定义命名
#define M_INT11 0x0400   //宏定义命名
#define M_INT12 0x0800   //宏定义命名
#define M_INT13 0x1000   //宏定义命名
#define M_INT14 0x2000   //宏定义命名
#define M_DLOG  0x4000   //宏定义命名
#define M_RTOS  0x8000   //宏定义命名

#define BIT0    0x0001   //宏定义命名
#define BIT1    0x0002   //宏定义命名
#define BIT2    0x0004   //宏定义命名
#define BIT3    0x0008   //宏定义命名
#define BIT4    0x0010   //宏定义命名
#define BIT5    0x0020   //宏定义命名
#define BIT6    0x0040   //宏定义命名
#define BIT7    0x0080   //宏定义命名
#define BIT8    0x0100   //宏定义命名
#define BIT9    0x0200   //宏定义命名
#define BIT10   0x0400   //宏定义命名
#define BIT11   0x0800   //宏定义命名
#define BIT12   0x1000   //宏定义命名
#define BIT13   0x2000   //宏定义命名
#define BIT14   0x4000   //宏定义命名
#define BIT15   0x8000   //宏定义命名

//===============================================
//
//  类型定义
//
//===============================================

#define ON  (1)        //打开
#define OFF (0)        //关闭

#define ERROR   (1)        //错误
#define OK      (0)        //正确

#define NULL    (0)        //空

#define   STATIC     static    /* 定义静态变量类型宏定义，仿真调试时可将宏定义设为空格  */

//===============================================
//  类型定义
//===============================================

typedef unsigned char   uint8;  //重新定义数据类型
typedef signed char     int8;  //重新定义数据类型
typedef unsigned int    uint16;  //重新定义数据类型
typedef signed int      int16;  //重新定义数据类型
typedef unsigned long   uint32;  //重新定义数据类型
typedef signed long     int32;  //重新定义数据类型

typedef unsigned char   Uint8;  //重新定义数据类型
typedef signed char     Int8;  //重新定义数据类型
typedef unsigned int    Uint16;  //重新定义数据类型
typedef signed int      Int16;  //重新定义数据类型
typedef unsigned long   Uint32;  //重新定义数据类型
typedef signed long     Int32;  //重新定义数据类型

//===============================================
//  头文件
//===============================================
#include  "string.h"

#include "APP_Config.h"              //应用程序配置

#include "DSP_Config.h"              //DSP片上外设配置

#include "DSP_GPIO.h"
#include "DSP_Timer.h"
#include "DSP_Clock.h"
#include "DSP_XIntf.h"
#include "DSP_XIntrupt.h"
#include "DSP_DefaultIsr.h"
#include "DSP_PieCtrl.h"
#include "DSP_PieVect.h"
#include "DSP_ADC.h"
#include "DSP_SCI.h"
#include "DSP_SPI.h"
#include "DSP_WDog.h"
#include "DSP_SYSCtrl.h"

//=============================================================
//Application 头文件在此处添加
//=============================================================
#include "Comm429.h"
#include "IFBIT.h"
#include "PuBIT.h"
#include "Comm429RIU.h"
#include "Control.h"
#include "Control_Priv.h"
#include "MBIT.h"
#include "Comm422.h"
#include "Comm429KZZZ.h"
#include "CommCCDL.h"
#include "DataStoreSpe.h"
#include "DataStore.h"
#include "Init.h"
#include "Synchronous.h"
#include "DataObtainAI.h"
#include "DataObtainIO.h"


//=============================================================
//Common 头文件在此处添加
//=============================================================

#include "Common.h"
#include "cpuTest.h"
#include "CRC16.h"
#include "StartUpModeJudge.h"
//=============================================================
//otherDriver 头文件在此处添加
//=============================================================
#include "CommDRI_422.h"
#include "CommDRI_429.h"
#include "CommDRI_CAN.h"
#include "SM25QH256M_SpiFlash.h"

/*********************************************************************/
/* 函数外部声明  */

extern Uint32 sysTime(void);
extern void   NMIResetRequestClear(void);
extern Uint16 NMIResetRequestGet(void);
extern void   PowerDownFlagClear(void);
extern Uint16 PowerDownFlagGet(void);
extern void   PowerDownFlagSetValid(void);
extern void   CycleDogFeed(void);
extern A429Info_t Comm429KZZZRxStateGet(Uint16 v_ID_u16);

#endif /* end of include guard: GLOBAL_ */

/* ===================================================================================== */
/* END OF FILE */
/* ===================================================================================== */
