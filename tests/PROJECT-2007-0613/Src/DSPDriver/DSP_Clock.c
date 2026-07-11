
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
 *        文件名称:    DSP_Clock.c
 *
 *        功能说明:   文件功能说明
 *
 *
 *        文件日期:   REDACTED
 *
 *
 *        程序版本:   V1.00
 *
 *********************************************************************************/

#include "Global.h"
#include "DSP_Clock.h"
/* PLL 锁定超时保护阈值,假设每个 while 循环 ~50ns,1000000 次约 50ms */
#define PLL_LOCK_TIMEOUT_CNT    (1000000UL)

/* LIMP 模式(外部晶振丢失)状态标志 */
static Uint16 s_limpModeActive_u16 = INVALID;
/* PLL 锁定超时标志 */
static Uint16 s_pllLockTimeout_u16 = INVALID;


/* ***************************************************************** */
/**
 * 【说明】:getPLLMul
 *
 *      该函数用以计算PLL的倍频系数，即：PLL的DIV值，倍频系数最大值为10。
 *
 *      系统时钟计算公式为：
 *          DSP_Clock = EXTERN_CLOCK * PLL倍频系数 / PLL分频系数
 *
 *      NOTE: DSP_Clock不是EXTERN_CLOCK的整数倍时，可能产生配置误差。
 *
 * 【参数】:dspClock ---- 拟设定的DSP系统工作频率，单位MHZ
 * 【参数】:exClock ----  外部晶振的频率，单位MHZ
 *
 * 【返回】:PLL倍频系数
 */
/* ***************************************************************** */
Uint8 getPLLMul(Uint8 dspClock,Uint8 exClock)
{
    Uint8 mul = 0;

    /* 依据时钟频率计算公式计算PLL倍频系数 */
    mul = dspClock * PLL_DIVIDE / exClock;

    /* 检验PLL倍频系数是否超过最大值 */
    if( mul >= PLL_MULMAX )
    {
        mul = PLL_MULMAX;
    }

    return mul;
}

/* ***************************************************************** */
/**
 * 【说明】:getPLLDivSEL
 *
 *      该函数依据时钟分频系数(DIVIDE)计算分频系数选择值(DIVSEL)
 *
 * 【参数】:divide ---- 时钟分频系数
 *
 * 【返回】:时钟分频系数选择值(DIVSEL)
 */
/* ***************************************************************** */
Uint8 getPLLDivSEL(Uint8 divide)
{
    Uint8 divsel = 0;

    switch(divide)
    {
    case 1:
        divsel = 3;
        break;
    case 2:
        divsel = 2;
        break;
    case 4:
        divsel = 0;
        break;
    default:
        divsel = 2;         //默认DIVSEL值为 2
        break;
    }

    return divsel;
}

/* ***************************************************************** */
/**
 * 【说明】:initPLL
 *
 *      该函数用以实现对DSP系统时钟的配置。
 *
 *      系统时钟计算公式为：
 *          DSP_Clock = EXTERN_CLOCK * PLL倍频系数 / PLL分频系数
 *
 *      按照TI官方数据手册，对PLL初始化，需要遵循如下步骤：
 *
 *      1. 判断当前设备是否工作在LIMP模式(外部时钟丢失)，若是，则无法完成时钟配置，同时需让系统处于安全模式；
 *      2. 在设置PLLCR寄存器前，需要保证分频系数选择值(DIVSEL)为零
 *      3. 关闭时钟丢失检测功能
 *      4. 设置PLLCR寄存器值(PLL倍频系数)
 *      5. 等待PLL锁在新的工作频率
 *      6. 修改PLL分频系数
 *
 *      NOTE: DSP_Clock不是EXTERN_CLOCK的整数倍时，可能产生配置误差。
 *
 *      NOTE: PLL分频系数(PLL_DIVSEL)
 *
 * 【参数】:dspClock ---- 拟设定的DSP系统工作频率，单位MHZ
 * 【参数】:exClock ---- 外部晶振的频率，单位MHZ
 */
/* ***************************************************************** */
void initPLL(Uint16 dspClock,Uint16 exClock)
{
    Uint8 pllmul = 0;
    Uint8 plldivsel = 0;
    Uint32 l_waitCnt_u32 = 0U;

    /* 计算PLL倍频系数 */
    pllmul = getPLLMul(dspClock,exClock);

    /* 计算PLL分频系数选择值 */
    plldivsel = getPLLDivSEL(PLL_DIVIDE);

    /* 检测当前是否工作在 LIMP 模式 */
    if( SysCtrlRegs.PLLSTS.bit.MCLKSTS != 0 )
    {
        /* 当外部晶振丢失时,记录LIMP状态,持续喂狗避免复位,跳过后续PLL配置 */
        s_limpModeActive_u16 = VALID;
        CycleDogFeed();
        return;
    }

    /* 对PLLCR进行赋值时，需要先将DIVSEL设置为零 */
    if ( SysCtrlRegs.PLLSTS.bit.DIVSEL != 0 )
    {
        EALLOW;
        SysCtrlRegs.PLLSTS.bit.DIVSEL = 0;
        EDIS;
    }

    /* 设置新的PLLCR值(PLL倍频系数) */
    if ( SysCtrlRegs.PLLCR.bit.DIV != pllmul)
    {
        EALLOW;

        /* 关闭时钟丢失检测功能 */
        SysCtrlRegs.PLLSTS.bit.MCLKOFF = 1;

        /* 设置新的PLL倍频系数 */
        SysCtrlRegs.PLLCR.bit.DIV = pllmul;

        EDIS;

        /* 等待PLL锁在新的工作频率,期间喂狗避免看门狗复位,带超时保护 */
        l_waitCnt_u32 = 0U;
        while (SysCtrlRegs.PLLSTS.bit.PLLLOCKS != 1)
        {
            CycleDogFeed();
            if (++l_waitCnt_u32 > PLL_LOCK_TIMEOUT_CNT)
            {
                /* 锁定超时,标记PLL失锁,让主循环处理 */
                s_pllLockTimeout_u16 = VALID;
                break;
            }
        }

        /* PLL 未锁定时切分频会导致 SYSCLK 不稳定,直接返回不继续配置 */
        if (VALID == s_pllLockTimeout_u16)
        {
            return;
        }

        EALLOW;

        /* 重新打开时钟丢失检测功能 */
        SysCtrlRegs.PLLSTS.bit.MCLKOFF = 0;

        EDIS;
    }

    /* 设置PLL分频系数选择值 */
    EALLOW;
    SysCtrlRegs.PLLSTS.bit.DIVSEL = plldivsel;
    EDIS;
}

/* ***************************************************************** */
/**
 * 【说明】:periClkEnable
 *
 *      该函数依据DSP_Config.h文件中各功能模块的宏定义，使能相应的外
 *      时钟。其中，GPIO模块的输入时钟、 XINTF模块的时钟，始终默认打开。
 */
/* ***************************************************************** */
void periClkEnable(void)
{
    EALLOW;

    /* 配置DSP片上高速外设时钟、低速外设时钟 */
    SysCtrlRegs.HISPCP.all = ( DSP_HSPCLK_FAC / 2 ) & 0x07;
    SysCtrlRegs.LOSPCP.all = ( DSP_LSPCLK_FAC / 2 ) & 0x07;

#if DSP_ECAN_B
    SysCtrlRegs.PCLKCR0.bit.ECANBENCLK = 1;
#endif

#if DSP_ECAN_A
    SysCtrlRegs.PCLKCR0.bit.ECANAENCLK = 1;
#endif

#if DSP_MCBSP_B
    SysCtrlRegs.PCLKCR0.bit.MCBSPBENCLK = 1;
#endif

#if DSP_MCBSP_A
    SysCtrlRegs.PCLKCR0.bit.MCBSPAENCLK = 1;
#endif

#if DSP_SCI_B
    SysCtrlRegs.PCLKCR0.bit.SCIBENCLK = 1;
#endif

#if DSP_SCI_A
    SysCtrlRegs.PCLKCR0.bit.SCIAENCLK = 1;
#endif

#if DSP_SPI
    SysCtrlRegs.PCLKCR0.bit.SPIAENCLK = 1;
#endif

#if DSP_SCI_C
    SysCtrlRegs.PCLKCR0.bit.SCICENCLK = 1;
#endif

#if DSP_I2C
    SysCtrlRegs.PCLKCR0.bit.I2CAENCLK = 1;
#endif

#if DSP_ADC
    SysCtrlRegs.PCLKCR0.bit.ADCENCLK = 1;
#endif

#if DSP_EQEP_2
    SysCtrlRegs.PCLKCR1.bit.EQEP2ENCLK = 1;
#endif

#if DSP_EQEP_1
    SysCtrlRegs.PCLKCR1.bit.EQEP1ENCLK = 1;
#endif

#if DSP_ECAP_1
    SysCtrlRegs.PCLKCR1.bit.ECAP1ENCLK = 1;
#endif

#if DSP_ECAP_2
    SysCtrlRegs.PCLKCR1.bit.ECAP2ENCLK = 1;
#endif

#if DSP_ECAP_3
    SysCtrlRegs.PCLKCR1.bit.ECAP3ENCLK = 1;
#endif

#if DSP_ECAP_4
    SysCtrlRegs.PCLKCR1.bit.ECAP4ENCLK = 1;
#endif

#if DSP_ECAP_5
    SysCtrlRegs.PCLKCR1.bit.ECAP5ENCLK = 1;
#endif

#if DSP_ECAP_6
    SysCtrlRegs.PCLKCR1.bit.ECAP6ENCLK = 1;
#endif

#if DSP_EPWM_1
    SysCtrlRegs.PCLKCR1.bit.EPWM1ENCLK = 1;
#endif

#if DSP_EPWM_2
    SysCtrlRegs.PCLKCR1.bit.EPWM1ENCLK = 1;
#endif

#if DSP_EPWM_3
    SysCtrlRegs.PCLKCR1.bit.EPWM1ENCLK = 1;
#endif

#if DSP_EPWM_4
    SysCtrlRegs.PCLKCR1.bit.EPWM1ENCLK = 1;
#endif

#if DSP_EPWM_5
    SysCtrlRegs.PCLKCR1.bit.EPWM1ENCLK = 1;
#endif

#if DSP_EPWM_6
    SysCtrlRegs.PCLKCR1.bit.EPWM1ENCLK = 1;
#endif

#if DSP_DMA
    SysCtrlRegs.PCLKCR3.bit.DMAENCLK = 1;
#endif

#if DSP_TIMER_0
    SysCtrlRegs.PCLKCR3.bit.CPUTIMER0ENCLK = 1;
#endif

#if DSP_TIMER_1
    SysCtrlRegs.PCLKCR3.bit.CPUTIMER1ENCLK = 1;
#endif

#if DSP_TIMER_2
    SysCtrlRegs.PCLKCR3.bit.CPUTIMER2ENCLK = 1;
#endif

    /* GPIO模块和XINTF模块，默认时钟始终有效 */
    SysCtrlRegs.PCLKCR3.bit.GPIOINENCLK = 1;
    SysCtrlRegs.PCLKCR3.bit.XINTFENCLK  = 1;

    EDIS;
}


Uint16 ClockLimpModeGet(void)
{
    return s_limpModeActive_u16;
}

Uint16 ClockPllLockTimeoutGet(void)
{
    return s_pllLockTimeout_u16;
}


