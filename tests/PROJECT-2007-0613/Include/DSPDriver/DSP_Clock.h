#ifndef DSP_CLOCK_

#define DSP_CLOCK_
/**外部接口**/
extern void initPLL(Uint16 dspClock,Uint16 exClock);/* 系统时钟初始化 */

extern void periClkEnable(void);/* 外设时钟使能 */
extern Uint16 ClockLimpModeGet(void);          /* 获取LIMP模式状态 */
extern Uint16 ClockPllLockTimeoutGet(void);    /* 获取PLL锁定超时状态 */

/* ***************************************************************** */
/* DSP_Clock.c 私有宏定义 */
/* ***************************************************************** */
#define PLL_MULMAX  (10)

#endif /* end of include guard: DSP_CLOCK_ */
