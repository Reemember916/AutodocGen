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
 * 文件名称:    DSP_Config.h
 *
 * 文件日期：       REDACTED
 *
 *
 * 程序版本:
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 * 1. DSP片上驱动配置
 *
 *********************************************************************************/

#ifndef DSP_CONFIG_

#define DSP_CONFIG_

#include "Global.h"

//============================================
//  系统时钟配置
//============================================

#define EXTERN_CLOCK        (30)        //外部时钟频率，单位MHZ

#define DSP_SYSCLK          (120.0)     //DSP工作主频，最高150MHZ

/***************************/

#define DSP_XCLKOUT         (OFF)       //使能系统时钟4分频输出，调试用

#define PLL_DIVIDE          (2)         //PLL分频系数，只能为：1,2,4其中一个

#define DSP_HSPCLK_FAC      (6)         //系统高速时钟因子，只能为 0 —14之间的偶数
#define DSP_LSPCLK_FAC      (2)         //系统低速时钟因子，只能为 0 —14之间的偶数

#define DSP_HSPCLK          (DSP_SYSCLK / DSP_HSPCLK_FAC)           //DSP内部高速时钟
#define DSP_LSPCLK          (DSP_SYSCLK / DSP_LSPCLK_FAC)           //DSP内部低速时钟

//============================================
//  DSP片上外设配置
//============================================

#define DSP_FLASH           ON         // DSP是否在FLASH中运行   【TESTED】
#define DSP_WDOG            ON          // DSP片上看门狗   【TESTED】

#define DSP_TIMER_0         ON          // DSP片上定时器，Timer0 【TESTED】
#define DSP_TIMER_1         ON          // DSP片上定时器，Timer1 【TESTED】
#define DSP_TIMER_2         OFF        // DSP片上定时器，Timer2 【TESTED】

#define DSP_SCI_A           ON        // SCIA口测试完毕 【TESTED】
#define DSP_SCI_B           ON        // SCIB口测试完毕 【TESTED】
#define DSP_SCI_C           OFF         // SCIC口测试完毕 【TESTED】

#define DSP_ADC             ON         // ADC口测试完毕  【TESTED】

#define DSP_I2C             OFF
#define DSP_SPI             ON           // SPI口测试完毕 【TESTED】

#define DSP_ECAN_A          OFF          //
#define DSP_ECAN_B          OFF         //

#define DSP_MCBSP_A         OFF          // McBsp A口测试完毕 【TESTED】
#define DSP_MCBSP_B         OFF         // McBsp B口测试完毕 【TESTED】

#define DSP_DMA             OFF

#define DSP_EQEP_1          OFF         //
#define DSP_EQEP_2          OFF         //

#define DSP_ECAP_1          OFF         //
#define DSP_ECAP_2          OFF         //
#define DSP_ECAP_3          OFF         //
#define DSP_ECAP_4          OFF         //
#define DSP_ECAP_5          OFF         //
#define DSP_ECAP_6          OFF         //

#define DSP_EPWM_1          OFF         //
#define DSP_EPWM_2          OFF         //
#define DSP_EPWM_3          OFF         //
#define DSP_EPWM_4          OFF         //
#define DSP_EPWM_5          OFF         //
#define DSP_EPWM_6          OFF         //

//============================================
/*
 * DSP片上看门狗配置
 *
 * 看门狗模式(WDOG_MODE)可以配置为如下两种方式：
 *
 * | WDOG_MODE_WDINT  |   中断模式，看门狗超时后，产生WAKEINT中断，不复位
 * | WDOG_MODE_RESET  |   复位模式，看门狗超时后产生复位
 *
 * 看门狗超时时间可能取值如下：
 *
 * WDOG_TIME_4_MS   ---- 看门狗超时时间为4ms
 * WDOG_TIME_9_MS   ---- 看门狗超时时间为9ms
 * WDOG_TIME_17_MS  ---- 看门狗超时时间为17ms
 * WDOG_TIME_35_MS  ---- 看门狗超时时间为35ms
 * WDOG_TIME_70_MS  ---- 看门狗超时时间为70ms
 * WDOG_TIME_139_MS ---- 看门狗超时时间为139ms
 * WDOG_TIME_279_MS ---- 看门狗超时时间为279ms
 */
//============================================

#if DSP_WDOG

#define WDOG_TIME       WDOG_TIME_279_MS

#define WDOG_MODE       (WDOG_MODE_RESET)

#endif

//============================================
//  定时器配置
//============================================

#if DSP_TIMER_0

#define DSP_TIMER_0_PERIOD  (1000UL)         // Timer0 定时周期，单位为us，微秒

#endif

#if DSP_TIMER_1

#define DSP_TIMER_1_PERIOD  (0xFFFFFFFFUL)         // Timer1 定时周期，单位为us，微秒

#endif

#if DSP_TIMER_2

#define DSP_TIMER_2_PERIOD  (300000)         // Timer2 定时周期，单位为us，微秒

#endif

/* ***************************************************************** */
/**
 * 【说明】:GPIO引脚输出配置
 *
 *  对GPIOA和GPIOB端口分别列出输出引脚序号和初值。
 *
 *  GPIOA端口的引脚序号范围为 GPIO_NUM_0  ---- GPIO_NUM_31
 *  GPIOB端口的引脚序号范围为 GPIO_NUM_32 ---- GPIO_NUM_63
 *
 *  引脚初值可以设置为：
 *  GPIO_SET   ---- 高电平
 *  GPIO_CLEAR ---- 低电平
 *
 *  NOTE:GPIO_NUM_NULL行用来标识数组结束行，不可删除。
 *
 *  示例：
 *  #define GPIO_OUT_TAB      {                                  \
 *                               { GPIO_NUM_32,  GPIO_CLEAR },   \
 *                               { GPIO_NUM_60,  GPIO_SET },     \
 *                               { GPIO_NUM_NULL,  GPIO_CLEAR }  \
 *                             }
 */
/* ***************************************************************** */

                               /* |  引脚序号   |    引脚初值  | */
/* GPIO输出引脚配置 */
#define GPIO_OUT_NUM    (10U)  /* GPIO输出引脚数量  */

#define GPIO_OUT_TAB            {{ GPIO_NUM_0,    GPIO_SET }, /* 同步输出 */\
                                 { GPIO_NUM_13,   GPIO_CLEAR }, /* 喂硬件狗 */\
                                 { GPIO_NUM_9,   GPIO_CLEAR   }, /* 呼吸灯*/\
                                 { GPIO_NUM_58,   GPIO_CLEAR   }, /* 本通道CHV*/\
                                 { GPIO_NUM_59,   GPIO_CLEAR   }, /* 本通道心跳*/\
                                 { GPIO_NUM_24,   GPIO_SET   },   /* DSP与CPLD间预留IO DSP_CPLD_YL1  */\
                                 { GPIO_NUM_25,   GPIO_SET   }, /* DSP与CPLD间预留IO DSP_CPLD_YL2  */\
                                 { GPIO_NUM_26,   GPIO_CLEAR   }, /* DSP与CPLD间预留IO DSP_CPLD_YL3 */\
                                 { GPIO_NUM_57,   GPIO_SET   }, /* SPI片选使能  */\
                                 { GPIO_NUM_NULL, GPIO_CLEAR }}
/* GPIO输入引脚配置 */
#define GPIO_IN_NUM     (8U)   /* GPIO输入引脚数量  */
#define GPIO_IN_TAB             {{ GPIO_NUM_1,  GPIO_PULL_UP_EN  }, /* 同步输入  */ \
	                             { GPIO_NUM_2,  GPIO_PULL_UP_EN  }, /* NMI中断 DSP_NMI  */ \
	                             { GPIO_NUM_60,  GPIO_PULL_UP_EN  }, /* 对方通道CHV  */\
	                             { GPIO_NUM_61,  GPIO_PULL_UP_EN  }, /* 对方通道心跳  */\
	                             { GPIO_NUM_27,  GPIO_PULL_UP_EN  }, /* DSP与CPLD间预留IO DSP_CPLD_YL4  */\
	                             { GPIO_NUM_32,  GPIO_PULL_UP_EN  }, /* DSP与CPLD间预留IO DSP_CPLD_YL5  */\
	                             { GPIO_NUM_33,  GPIO_PULL_UP_EN  }, /* DSP与CPLD间预留IO DSP_CPLD_YL6  */\
                                 { GPIO_NUM_NULL, GPIO_PULL_UP_EN }}

/* ***************************************************************** */
/**
 * 【说明】:GPIO引脚外部中断配置
 *
 * ********************************
 *
 *  GPIO引脚外部中断共八个，分别为：XNMI、XINT1----XINT7。
 *
 *  每一个中断都需要配置，使能状态、触发沿、引脚序号。
 *
 *  使能状态可以设为：
 *
 *  |  ON  |   中断使能     |
 *  |  OFF |   中断禁止     |
 *
 *  触发沿可以设为：
 *
 *  | GPIO_INT_POL_RISING |     上升沿触发      |
 *  | GPIO_INT_POL_FALLIN |     下降沿触发      |
 *  | GPIO_INT_POL_BOTH   | 上升沿、下降沿触发  |
 *
 *  引脚序号可以设为：
 *
 *  | XNMI、XINT1、XINT2  |   GPIO_NUM_0  ---- GPIO_NUM_31  |
 *  | XINT3  ---- XINT7   |   GPIO_NUM_32 ---- GPIO_NUM_63  |
 */
/* ***************************************************************** */
                                 /*  使能         触发沿         引脚号 */
#define GPIO_EXINT_CONF_TAB     {   { ON, GPIO_INT_POL_FALLIN, GPIO_NUM_2 }, /* XNMI中断配置，只能在GPIO0-GPIO31选择 */ \
                                    { OFF, GPIO_INT_POL_RISING, GPIO_NUM_11 },/* XINT1中断配置 */ \
                                    { OFF, GPIO_INT_POL_RISING, GPIO_NUM_13 },/* XINT2中断配置 */ \
                                    { OFF , GPIO_INT_POL_RISING, GPIO_NUM_59 },/* XINT3中断配置 */ \
                                    { OFF , GPIO_INT_POL_RISING, GPIO_NUM_48 },/* XINT4中断配置 */ \
                                    { OFF, GPIO_INT_POL_RISING, GPIO_NUM_53 },/* XINT5中断配置 */ \
                                    { OFF, GPIO_INT_POL_RISING, GPIO_NUM_48 },/* XINT6中断配置 */ \
                                    { OFF, GPIO_INT_POL_RISING, GPIO_NUM_46 } /* XINT7中断配置 */ \
                                }


/* ***************************************************************** */
/**
 * 【说明】:SCI接口配置 SCIA SCIB SCIC
 *
 * ******************************************
 *
 *   FIFO模式 ---- 可设为：
 *               SCI_FIFO_EN  ---- 使能SCI通信FIFO功能
 *               SCI_FIFO_DIS ---- 禁止SCI通信FIFO功能
 *
 * 需要配置的参数如下：
 *
 * 1 波特率 ---- 依据实际通信需要设置
 *
 * 2 数据位 ---- 取值范围为：SCI_DATABITS_1 ---- SCI_DATABITS_8
 *
 * 3 停止位 ---- 取值范围为：SCI_STOPBITS_ONE ---- SCI_STOPBITS_TWO
 *
 * 4 校验位 ---- 可设为：
 *               SCI_PARITY_ODD   ---- 奇校验
 *               SCI_PARITY_EVEN  ---- 偶校验
 *               SCI_PARITY_NONE  ---- 无校验
 *
 * 5 接收模式 ---- 可设为：
 *               SCI_RX_INT_DIS ---- SCI通信，接收不采用中断模式
 *               SCI_RX_INT_EN  ---- SCI通信，接收采用中断模式
 *
 * 6 回环模式 ---- 可设为：
 *              SCI_LOOPB_DIS ---- 禁用回环模式
 *              SCI_LOOPB_EN  ---- 使能回环模式
 *
 * 7 FIFO触发字节数 ---- 取值范围为[1,16]
 *
 * 8 SCI接收引脚
 * 9 SCI发送引脚，引脚配置如下：
 *
 *              SCIATXD : GPIO_NUM_29 或 GPIO_NUM_35
 *              SCIARXD : GPIO_NUM_28 或 GPIO_NUM_36
 *
 *              SCIBTXD : GPIO_NUM_14 或 GPIO_NUM_9  或 GPIO_NUM_22 或 GPIO_NUM_18
 *              SCIBRXD : GPIO_NUM_15 或 GPIO_NUM_11 或 GPIO_NUM_23 或 GPIO_NUM_19
 *
 *              SCICTXD : GPIO_NUM_63
 *              SCICRXD : GPIO_NUM_62
 */
/* ***************************************************************** */

#define SCI_FIFO_EN         ON                  /* SCI的FIFO使能 */

#define SCI_A_CONF_TAB    {                                     \
                              115200,           /* 波特率   */  \
                              SCI_DATABITS_8,   /* 数据位   */  \
                              SCI_STOPBITS_ONE, /* 停止位   */  \
                              SCI_PARITY_ODD,  /* 校验位   */  \
                              SCI_RX_INT_DIS,   /* 中断接收 */  \
                              SCI_LOOPB_DIS,     /* 回环模式 */  \
                                   10,           /* FIFO触发 */  \
                              GPIO_NUM_29,      /* SCIATXD  */  \
                              GPIO_NUM_28       /* SCIARXD  */  \
                          }

#define SCI_B_CONF_TAB    {                                     \
                              115200,           /* 波特率   */  \
                              SCI_DATABITS_8,   /* 数据位   */  \
                              SCI_STOPBITS_ONE, /* 停止位   */  \
                              SCI_PARITY_ODD,  /* 校验位   */  \
                              SCI_RX_INT_DIS,   /* 中断接收 */  \
                              SCI_LOOPB_DIS,    /* 回环模式 */  \
                                   10,          /* FIFO触发 */  \
                              GPIO_NUM_14,      /* SCIBTXD  */  \
                              GPIO_NUM_15       /* SCIBRXD  */  \
                          }

#define SCI_C_CONF_TAB    {                                     \
                              38400,           /* 波特率   */  \
                              SCI_DATABITS_8,   /* 数据位   */  \
                              SCI_STOPBITS_ONE, /* 停止位   */  \
                              SCI_PARITY_EVEN,  /* 校验位   */  \
                              SCI_RX_INT_DIS,   /* 中断接收 */  \
                              SCI_LOOPB_DIS,    /* 回环模式 */  \
                                   10,          /* FIFO触发 */  \
                              GPIO_NUM_63,      /* SCICTXD  */  \
                              GPIO_NUM_62       /* SCICRXD  */  \
                          }

/* ***************************************************************** */
/**
 * 【说明】:DSP_ADC 配置
 *
 * ADC的配置需要分别对ADC模块本身和转换通道进行配置。
 *
 * ADC模块的配置信息如下：
 *
 * 【ADC参考源设置】
 *          ADC_REF_IN       ----    ADC内部参考源
 *          ADC_REF_OUT_1024 ----    ADC外部1.024V参考电源
 *          ADC_REF_OUT_1500 ----    ADC外部1.500V参考电源
 *          ADC_REF_OUT_2048 ----    ADC外部2.048V参考电源
 *
 * 【ADC采样脉宽设置】
 *          ADC采样脉冲宽度，单位为ADCCLK，取值范围【1,16】
 *
 * 【ADC分频系数设置】
 *          ADC_CLK = DSP_HSPCLK / ADC分频系数，取值范围【0,30】偶数
 *          当分频系数为0时，实际分频系数为1
 *
 * 【ADC连续运行模式】
 *          ADC_CONTIN_RUN_ON  ---- ADC工作于连续运行模式
 *          ADC_CONTIN_RUN_OFF ---- ADC工作于Start-Stop模式
 *
 * 【ADC级联模式】
 *          ADC_CASCADE_ON  ---- ADC工作于级联模式，即：一个16通道的转换器
 *          ADC_CASCADE_OFF ---- ADC工作于非级联模式，即：两个8通道转换器
 *
 * 【ADC采样模式】
 *          ADC_SAMPLE_SEQUEN ---- ADC工作于顺序采样模式
 *          ADC_SAMPLE_SIMULT ---- ADC工作于并发采样模式
 *
 * 【ADC转换方式设置】
 *          ADC_CONV_POLL ---- 查询模式
 *          ADC_CONV_INT_EVERY ---- 每一次转换结束都产生中断
 *          ADC_CONV_INT_OTHER ---- 每间隔一次转换结束产生一次中断
 *
 * 【ADC转换触发方式设置】
 *          ADC_SOC_SOFT      ---- 软件触发
 *          ADC_SOC_EPWM_SOCA ---- EPWM SOCA触发
 *          ADC_SOC_EPWM_SOCB ---- EPWM SOCB触发
 *          ADC_SOC_EXT_GPIO  ---- 外部GPIO中断方式触发
 *
 *          其中SEQ1以上四种方式均支持，SEQ2只支持ADC_SOC_SOFT和ADC_SOC_EPWM_SOCB
 *
 */
/* ***************************************************************** */
#if DSP_ADC

#define ADC_CONF_TAB      {                                      \
                              ADC_REF_IN,         /* ADC参考电源  */ \
                                  6,              /* ADC采样脉宽  */ \
                                  6,              /* ADC分频系数  */ \
                              ADC_CONTIN_RUN_ON,  /* 连续运行模式 */  \
                              ADC_CASCADE_ON,     /* 级联模式     */   \
                              ADC_SAMPLE_SEQUEN,  /* 顺序采样模式 */  \
                              ADC_CONV_POLL,      /* SEQ1转换方式 */ \
                              ADC_SOC_SOFT,       /* SEQ1触发方式 */ \
                              ADC_CONV_POLL,      /* SEQ2转换方式 */ \
                              ADC_SOC_SOFT        /* SEQ2触发方式 */ \
                          }

/*ADC实际使用SEQ1通道数(级联模式下为总通道数)*/
#define ADCCHANNEL1NUM 	(6U)
/* ADC转换通道配置表 */
#define ADC_SEQ1_CHANNEL_TAB   {                   \
                                  ADC_CHANNEL_3,   \
                                  ADC_CHANNEL_8,   \
                                  ADC_CHANNEL_9,   \
                                  ADC_CHANNEL_10,   \
                                  ADC_CHANNEL_11,   \
                                  ADC_CHANNEL_NULL \
                               }

/*ADC实际使用SEQ2通道数*/
#define ADCCHANNEL2NUM 	(1U)
#define ADC_SEQ2_CHANNEL_TAB   {                    \
                                  ADC_CHANNEL_NULL  \
                               }

#endif

/* ***************************************************************** */
/**
 * 【说明】:DSP_I2C 配置
 */
/* ***************************************************************** */


/* ***************************************************************** */
/**
 * 【说明】:DSP_SPI 配置
 *
 * 【SPI主从模式】
 *          SPI_MASTER ---- SPI工作于主模式
 *          SPI_SLAVE  ---- SPI工作于从模式
 *
 *  【SPI时钟极性】只能取 0 或者 1
 *          0 ---- 数据在上升沿输出，下降沿输入
 *          1 ---- 数据在下降沿输出，上升沿输入
 *
 *  【SPI时钟相位】只能取 0 或者 1
 *          0 ---- 正常时钟输出
 *          1 ---- 延时半个时钟周期输出
 *
 *  【SPI波特率】
 *          单位为 K，取值范围为[DSP_LSPCLK * 1000 / 128 , DSP_LSPCLK * 1000 / 4]
 *
 *  【SPI数据长度】
 *          取值范围为[1,16]
 *
 *  【SPI回环模式】
 *          SPI_LOOP_EN  ---- SPI回环模式使能
 *          SPI_LOOP_DIS ---- SPI回环模式关闭
 *
 *  【SPI中断使能】
 *          SPI_INT_EN  ---- SPI中断使能
 *          SPI_INT_DIS ---- SPI中断关闭
 *
 *  【SPI FIFO中断触发】
 *          SPI FIFO触发数，取值范围为[1,16]
 *
 *  【SPI 引脚配置】
 *          SPISIMO ---- GPIO_NUM_16 或 GPIO_NUM_54
 *          SPISOMI ---- GPIO_NUM_17 或 GPIO_NUM_55
 *          SPICLK  ---- GPIO_NUM_18 或 GPIO_NUM_56
 *          SPISTE  ---- GPIO_NUM_19 或 GPIO_NUM_57
 */
/* ***************************************************************** */

#if DSP_SPI

#define    SPI_FIFO_EN    ON              //SPI FIFO 模式使能

#define    SPI_CONF_TAB {                                      \
                            SPI_MASTER,   /* SPI主从模式    */ \
                            1,            /* 时钟极性       */ \
                            0,            /* 时钟相位       */ \
                            2000,         /* 波特率，单位K  */ \
                            8,            /* 数据BIT数      */ \
                            SPI_LOOP_DIS, /* SPI回环模式    */ \
                            SPI_INT_DIS,  /* SPI中断使能    */ \
                            1,            /* SPI接收FIFO触发*/ \
                            GPIO_NUM_54,  /* SPISIMO引脚    */ \
                            GPIO_NUM_55,  /* SPISOMI引脚    */ \
                            GPIO_NUM_56,  /* SPICLK引脚     */ \
                            GPIO_NUM_NULL   /* SPISTE引脚     */ \
                        }

#endif

/* ***************************************************************** */
/**
 * 【说明】:DSP_ECAN_A
 *
 * 【波特率配置】
 *      设置CAN通信的波特率，单位为：K，可能的取值如下：
 *      ECAN_BAUD_25K   ---- 通信速率25K
 *      ECAN_BAUD_50K   ---- 通信速率50K
 *      ECAN_BAUD_100K  ---- 通信速率100K
 *      ECAN_BAUD_125K  ---- 通信速率125K
 *      ECAN_BAUD_200K  ---- 通信速率200K
 *      ECAN_BAUD_250K  ---- 通信速率250K
 *      ECAN_BAUD_500K  ---- 通信速率500K
 *      ECAN_BAUD_1000K ---- 通信速率1000K
 *
 * 【回环模式配置】
 *      设置CAN通信模块是否工作于回环模式，可能取值如下：
 *      ECAN_LOOPBACK_DIS ---- 回环模式关闭
 *      ECAN_LOOPBACK_EN  ---- 回环模式使能
 *
 * 【中断模式配置】
 *      设置CAN通信的中断模式，可能取值如下：
 *      ECAN_INT_EN  ---- CAN通信中断使能
 *      ECAN_INT_DIS ---- CAN通信中断禁用
 *
 * 【波特率TQ数】
 *      设置波特率设置时的，TQ数，可能取值如下：
 *      ECAN_TQNUM_10 ---- TQ数为10
 *      ECAN_TQNUM_12 ---- TQ数为12
 *      ECAN_TQNUM_15 ---- TQ数为15
 *      ECAN_TQNUM_20 ---- TQ数为20
 *
 * 【ID接收屏蔽位】
 *      与ID相同，相应的位设置为 1 时，标识该位被屏蔽，接收时，不进行比较，
 *      设置为 0 时，标识相应的位，在接收时，不可忽略，比如：
 *      0x000 --- 报文ID必须与接收邮箱完全一致，报文才会被接收
 *      0x7FF --- 接收邮箱接收任意ID的报文
 *
 * 【发送引脚配置】
 * 【接收引脚配置】
 *      引脚可能的配置如下：
 *      CANTXA ---- GPIO_NUM_19 或 GPIO_NUM_31
 *      CANRXA ---- GPIO_NUM_18 或 GPIO_NUM_30
 *
 *      CANTXB ---- GPIO_NUM_20 或 GPIO_NUM_16 或 GPIO_NUM_12 或 GPIO_NUM_8
 *      CANRXB ---- GPIO_NUM_21 或 GPIO_NUM_17 或 GPIO_NUM_13 或 GPIO_NUM_10
 *
 * 【邮箱及ID配置】
 *      最大可以配置16个邮箱，每个邮箱需要配置为发送或者接收，以及邮箱ID，
 *
 *      邮箱ID ---- 邮箱ID为11个BIT
 *
 *      邮箱发送接收的可能取值如下：
 *      ECAN_MBOX_RX ---- 接收邮箱
 *      ECAN_MBOX_TX ---- 发送邮箱
 *
 *  NOTE:在配置邮箱数组时，一定要保证所有的发送邮箱出现在接收邮箱之前，任意一个
 *       接收邮箱的后面都不应该再出现配置为发送邮箱的邮箱
 */
/* ***************************************************************** */

#if DSP_ECAN_A

#define ECAN_A_CONF      {\
                              ECAN_BAUD_500K,    /* 波特率，单位K  */ \
                              ECAN_LOOPBACK_DIS, /* 回环模式使能   */ \
                              ECAN_INT_DIS,      /* 中断使能       */ \
                              ECAN_TQNUM_12,     /* 波特率TQ数     */ \
                              0x7FF,             /* ID掩码 11BIT   */ \
                              GPIO_NUM_31,       /* CANTXA发送引脚 */ \
                              GPIO_NUM_30        /* CANRXA接收引脚 */ \
                         }

                            /*  发送/接收   | 邮箱ID  */
#define ECAN_A_MBOX_TAB  {\
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_NULL, 0x101 }  \
                         }

#endif

/* ***************************************************************** */
/**
 * 【说明】:DSP_ECAN_B
 */
/* ***************************************************************** */
#if DSP_ECAN_B

#define ECAN_B_CONF    {\
                            ECAN_BAUD_500K,    /* 波特率，单位K   */ \
                            ECAN_LOOPBACK_DIS, /* 回环模式        */ \
                            ECAN_INT_DIS,      /* 中断使能        */ \
                            ECAN_TQNUM_12,     /* 波特率TQ数      */ \
                            0x7FF,             /* ID掩码 11BIT    */ \
                            GPIO_NUM_16,       /* CANTXB 发送引脚 */ \
                            GPIO_NUM_17        /* CANRXB 接收引脚 */ \
                       }

#define ECAN_B_MBOX_TAB  {\
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_TX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_RX,   0x722 }, \
                            { ECAN_MBOX_NULL, 0x101 }  \
                         }
#endif

/* ***************************************************************** */
/**
 * 【说明】:DSP_MCBSP_A
 *
 * 【Mcbsp ID】
 *      Mcbsp接口标识ID，可能取值如下：
 *        MCBSP_A_ID ---- McBsp A 口
 *        MCBSP_B_ID ---- McBsp B 口
 *
 * 【Mcbsp 数据位数】
 *      Mcbsp通信WORD数据位数，可能取值如下：
 *        MCBSP_DATABITS_8
 *        MCBSP_DATABITS_16
 *        MCBSP_DATABITS_12
 *
 * 【Mcbsp 报文(FRAME)长度】
 *      Mcbsp通信单帧报文的WORD数，固定为1，不要修改
 *
 * 【Mcbsp 通信波特率】
 *      Mcbsp通信波特率，单位：K
 *
 * 【Mcbsp CLOCK STOP模式】
 *      Mcbsp Clock Stop模式，主要在配置为SPI模式时使用，可能取值如下：
 *        MCBSP_CLKSTP_DIS ---- 不启用CLOCK STOP模式
 *   MCBSP_CLKSTP_NO_DELAY ---- 启用CLOCK STOP模式，没有延时(SPI 模式)
 *      MCBSP_CLKSTP_DELAY ---- 启用CLOCK STOP模式，延时半个时钟(SPI 模式)
 *
 * 【Mcbsp 发送数据采样时钟沿】
 *      可能取值如下：
 *      MCBSP_CLK_TX_RISING_EDGE ---- 发送在时钟上升沿
 *        MCBSP_CLK_TX_FALL_EDGE ---- 发送在时钟下降沿
 *
 * 【Mcbsp 接收数据采样时钟沿】
 *      可能取值如下：
 *      MCBSP_CLK_RX_RISING_EDGE ---- 接收在时钟上升沿
 *        MCBSP_CLK_RX_FALL_EDGE ---- 接收在时钟下降沿
 *
 * 【Mcbsp 接收中断方式】
 *       MCBSP_INT_DISABLE ---- 禁止接收中断
 *      MCBSP_INT_ONE_WORD ---- 每接收到一个字符就产生中断
 *      MCBSP_INT_FRM_SYNC ---- 每一帧报文接收完毕产生中断
 *   MCBSP_INT_ONE_BLK_FRM ---- 每一个BLOCK发送完毕产生中断
 *      MCBSP_INT_RSYNCERR ---- 同步脉冲错误产生中断
 *
 * 【Mcbsp 回环模式】
 *      Mcbsp回环模式设置，可能取值如下：
 *        MCBSP_LOOPBACK_DIS ---- 禁用回环模式
 *        MCBSP_LOOPBACK_EN  ---- 使能回环模式
 *
 * 【Mcbsp SPI模式】
 *      Mcbsp启用SPI模式设置，可能取值如下：
 *        MCBSP_SPI_MODE_OFF ---- 不启用SPI模式
 *     MCBSP_SPI_MODE_MASTER ---- 启用SPI 主模式
 *      MCBSP_SPI_MODE_SLAVE ---- 启用SPI 从模式
 *
 * 【Mcbsp GPIO引脚】
 *
 *                  MFSXA   ---- GPIO_NUM_23
 *                  MCLKXA  ---- GPIO_NUM_22
 *                  MDXA    ---- GPIO_NUM_20
 *                  MDRA    ---- GPIO_NUM_21
 *                  MCLKRA  ---- GPIO_NUM_7  或 GPIO_NUM_58
 *                  MFSRA   ---- GPIO_NUM_5  或 GPIO_NUM_59
 *
 *                  MFSXB   ---- GPIO_NUM_15 或 GPIO_NUM_27
 *                  MCLKXB  ---- GPIO_NUM_14 或 GPIO_NUM_26
 *                  MDXB    ---- GPIO_NUM_12 或 GPIO_NUM_24
 *                  MDRB    ---- GPIO_NUM_13 或 GPIO_NUM_25
 *                  MCLKRB  ---- GPIO_NUM_3  或 GPIO_NUM_60
 *                  MFSRB   ---- GPIO_NUM_1  或 GPIO_NUM_61
 */
/* ***************************************************************** */
#if DSP_MCBSP_A

#define    MCBSP_A_CONF   {                                                  \
                            MCBSP_A_ID,              /* Mcbsp端口ID */        \
                            MCBSP_DATABITS_8,        /* 数据位长度  */        \
                            1,                       /* 报文长度    */        \
                            1000,                     /* 通信波特率  */        \
                            MCBSP_CLKSTP_DELAY,        /* CLOCK STOP模式     */ \
                            MCBSP_CLK_TX_RISING_EDGE,/* 发送数据采样时钟沿 */ \
                            MCBSP_CLK_RX_FALL_EDGE,  /* 接收数据采样时钟沿 */ \
                            MCBSP_INT_DISABLE,      /* 接收方式(中断)     */ \
                            MCBSP_LOOPBACK_DIS,       /* 回环模式    */        \
                            MCBSP_SPI_MODE_MASTER,      /* SPI模式    */        \
                            {                                                \
                                GPIO_NUM_NULL,         /* MFSXA 引脚  */        \
                                GPIO_NUM_22,         /* MCLKXA 引脚 */        \
                                GPIO_NUM_20,         /* MDXA 引脚   */        \
                                GPIO_NUM_21,         /* MDRA 引脚   */        \
                                GPIO_NUM_NULL,         /* MCLKRA 引脚 */        \
                                GPIO_NUM_NULL          /* MFSRA 引脚  */        \
                            }                                                \
                          }
#endif

/* ***************************************************************** */

#if DSP_MCBSP_B

#define    MCBSP_B_CONF   {                                                   \
                            MCBSP_B_ID,              /* Mcbsp端口ID */        \
                            MCBSP_DATABITS_8,        /* 数据位长度  */        \
                            1,                       /* 报文长度    */        \
                            1000,                    /* 通信波特率  */        \
                            MCBSP_CLKSTP_DIS,        /* CLOCK STOP模式     */ \
                            MCBSP_CLK_TX_RISING_EDGE,/* 发送数据采样时钟沿 */ \
                            MCBSP_CLK_RX_FALL_EDGE,  /* 接收数据采样时钟沿 */ \
                            MCBSP_INT_ONE_WORD,      /* 接收方式(中断)     */ \
                            MCBSP_LOOPBACK_DIS,      /* 回环模式    */        \
                            MCBSP_SPI_MODE_OFF,      /* SPI模式    */         \
                            {                                                 \
                                GPIO_NUM_15,         /* MFSXB 引脚  */        \
                                GPIO_NUM_14,         /* MCLKXB 引脚 */        \
                                GPIO_NUM_12,         /* MDXB 引脚   */        \
                                GPIO_NUM_13,         /* MDRB 引脚   */        \
                                GPIO_NUM_60,         /* MCLKRB 引脚 */        \
                                GPIO_NUM_61          /* MFSRB 引脚  */        \
                            }                                                \
                          }
#endif


#endif /* end of include guard: DSP_CONFIG_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
