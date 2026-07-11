#ifndef DSP_WDOG_

#define DSP_WDOG_

#include "Global.h"

/* 看门狗模式配置 */
#define WDOG_MODE_RESET     (0U)     //看门狗超时将复位
#define WDOG_MODE_WDINT     (1U)     //看门狗超时将产生WDINT中断，不复位

#define WDOG_WDCHK_RESET        (0x00U << 3U)     /* 历史兼容非法WDCHK写值，当前不再用于软件复位 */
#define WDOG_WDFLAG_RESET_BIT   (0x01U << 7U)     /* 看门狗状态复位标志BIT位  */

#define WDOG_WDFLAG_VALID       (0x01U)           /* 喂狗复位标志有效  */
#define WDOG_WDFLAG_INVALID     (0x00U)           /* 喂狗复位标志无效  */

/* 看门狗超时时间配置信息 */
#define WDOG_TIME_4_MS      (1U)    //4ms没喂狗时，狗叫
#define WDOG_TIME_9_MS      (2U)    //9ms没喂狗时，狗叫
#define WDOG_TIME_17_MS     (3U)    //17ms没喂狗时，狗叫
#define WDOG_TIME_35_MS     (4U)    //35ms没喂狗时，狗叫
#define WDOG_TIME_70_MS     (5U)    //70ms没喂狗时，狗叫
#define WDOG_TIME_139_MS    (6U)    //139ms没喂狗时，狗叫
#define WDOG_TIME_279_MS    (7U)    //279ms没喂狗时，狗叫

/*外部接口*/
extern void wDogFeed(void);  //软件喂狗函数

extern void wDogDisable(void); //看门狗失能

extern void wDogEnable(Uint8 time,Uint8 mode); //看门狗使能

extern void WDogResetTrigger(void); /* 配置最短超时看门狗复位，不等待 */

extern void WDogReset(void);        /* 看门狗复位           */

extern Uint16 WDogWDFlagGet(void);  /* 喂狗复位标志获取 */

/* ***************************************************************** */
/* DSP_WDog.c 私有宏定义 */
/* ***************************************************************** */
#define WDOG_KEY_1          (0x0055)        /* 看门狗喂狗参数1 */
#define WDOG_KEY_2          (0x00AA)        /* 看门狗喂狗参数2 */
#define WDOG_WDCR_CHECK     (0x05U << 3)     /* 写WDCR寄存器校验值 */
#define WDOG_WDCR_DISAB     (0x01U << 6)     /* 看门狗禁止 */
#define WDOG_WDCR_ENAB      (0x00U << 6)     /* 看门狗使能 */

#endif /* end of include guard: DSP_WDOG_ */
