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
 * 文件名称:   DSP_SPI.c
 *
 * 功能说明:
 * --------
 *
 * 本程序用以实现对TMS320F28335 SPI接口进行配置、操作。
 *
 * 当前版本程序支持：
 * 1. 支持主工作模式
 * 2. 支持波特率可配置
 * 3. 支持引脚配置
 * 4. 支持中断、查询模式配置
 * 5. 支持FIFO模式
 * 6. 支持时钟极性、相位配置
 * 7. 支持数据位配置
 * 8. 支持回环模式配置
 *
 * 当前版本程序不支持：
 * 1. 不支持延时发送；
 * 2. 不支持中断发送；
 * 3. 不支持从工作模式；
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V1.03
 *
 *********************************************************************************/

#include "Global.h"

/* ***************************************************************** */
/**
 * 【说明】:本地宏定义
 */
/* ***************************************************************** */

#if DSP_SPI

#define BAUDRATE_DIVIDE_MIN (4U)
#define BAUDRATE_DIVIDE_MAX (128U)

#define SPI_FIFO_MAX     (16U)        //SPI FIFO最大缓存字节数
#define SPI_MAX_DBITS    (16U)        //SPI 最大的数据BIT数

//SPI配置

struct g_SpiConf_t s_MySpiConf_t = SPI_CONF_TAB;
/* 写数据时，左移位数 */
Uint16 s_SpiShiftBits_u16 = 0;

/* 单个数据传输最大延时 */
Uint16 s_SpiDelayCount_u16 = 0;

Uint16 s_SpiErrCount_u16 = 0;

/* ***************************************************************** */
/**
 *    [函数名]			SpiBaudRateSet
 *
 *    [功能描述]			计算SPI通信波特率。波特率计算公式如下：
 *                      波特率 = DSP低速时钟 / 分频系数;
 *    [输入参数说明]		l_DspLspClk_u8--DSP低速时钟，单位：MHZ
 *                      l_BaudRate_u16--SPI波特率，单位：KHZ
 *    [输出参数说明]		分频系数值减1
 *    [其他说明]
 *    [返回]				分频系数值减1
 */
/* ***************************************************************** */
Uint16 SpiBaudRateSet(Uint8 l_DspLspClk_u8,Uint16 l_BaudRate_u16)
{
    Uint16 l_divide_u16 = 0U;

    /* 计算分频系数 */
    if(l_BaudRate_u16 > 0U)
    {
    l_divide_u16 = 1000U * l_DspLspClk_u8 / l_BaudRate_u16;
	}

    /* 判断分频系数是否超限 */
    if( l_divide_u16 <= BAUDRATE_DIVIDE_MIN)
    {
    	l_divide_u16 = BAUDRATE_DIVIDE_MIN;
    }
    else if(l_divide_u16 >= BAUDRATE_DIVIDE_MAX)
    {
    	l_divide_u16 = BAUDRATE_DIVIDE_MAX;
    }
    else
    {
    	/* no deal with */;
    }

    /* 计算寄存器值 */
    l_divide_u16 = l_divide_u16 - 1U;

    /* 设置波特率寄存器 */
    SpiaRegs.SPIBRR = l_divide_u16;

    return l_divide_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiGpioConf
 *
 *    [功能描述]			SPI引脚配置，只配置SPISIMO,SPISOMI,SPICLK三个引脚，不包含SPISTE。
 *                      可能的引脚配置如下：
 *                         SPISIMO ---- GPIO_NUM_16 或 GPIO_NUM_54
 *                         SPISOMI ---- GPIO_NUM_17 或 GPIO_NUM_55
 *                         SPICLK  ---- GPIO_NUM_18 或 GPIO_NUM_56
 *                         SPISTE  ---- GPIO_NUM_19 或 GPIO_NUM_57
 *    [输入参数说明]		l_SimoGpio_u8 ----  SPISIMO引脚
 *                      l_SomiGpio_u8 ----  SPISOMI引脚
 *                      l_ClkGpio_u8  ----  SPICLK引脚
 *                      l_SpisteGpio_u8---- SPISTE引脚
 *    [输出参数说明]		分频系数值减1
 *    [其他说明]
 *    [返回]				分频系数值减1
 */
/* ***************************************************************** */
void SpiGpioConf( Uint8 l_SimoGpio_u8,Uint8 l_SomiGpio_u8,Uint8 l_ClkGpio_u8,Uint8 l_SpisteGpio_u8 )
{
    EALLOW;

    /* SPISIMO引脚配置 */
    if( GPIO_NUM_16 == l_SimoGpio_u8 )
    {
       GpioCtrlRegs.GPAMUX2.bit.GPIO16 = 1U;
    }
    else if( GPIO_NUM_54 == l_SimoGpio_u8 )
    {
       GpioCtrlRegs.GPBMUX2.bit.GPIO54 = 1U;
    }
    else
    {
    	/* no deal with */;
    }

    /* SPISOMI引脚配置 */
    if( GPIO_NUM_17 == l_SomiGpio_u8 )
    {
       GpioCtrlRegs.GPAMUX2.bit.GPIO17 = 1U;
    }
    else if( GPIO_NUM_55 == l_SomiGpio_u8 )
    {
       GpioCtrlRegs.GPBMUX2.bit.GPIO55 = 1U;
    }
    else
    {
    	/* no deal with */;
    }

    /* SPICLK引脚配置 */
    if( GPIO_NUM_18 == l_ClkGpio_u8 )
    {
       GpioCtrlRegs.GPAMUX2.bit.GPIO18 = 1U;
    }
    else if( GPIO_NUM_56 == l_ClkGpio_u8 )
    {
       GpioCtrlRegs.GPBMUX2.bit.GPIO56 = 1U;
    }
    else
    {
    	/* no deal with */;
    }

    /* SPISTE引脚配置 */
    if( GPIO_NUM_19 == l_SpisteGpio_u8 )
    {
        GpioCtrlRegs.GPAMUX2.bit.GPIO19 = 1U;
    }
    else if( GPIO_NUM_57 == l_SpisteGpio_u8 )
    {
        GpioCtrlRegs.GPBMUX2.bit.GPIO57 = 1U;
    }
    else
    {
    	/* no deal with */;
    }

    EDIS;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiIntEnable
 *
 *    [功能描述]			注册SPI RXINT中断向量，并使能CPU中断。
 *    [输入参数说明]		NONE
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiIntEnable(void)
{
    /* 注册中断向量 */
    EALLOW;
    PieVectTable.SPIRXINTA = &ISR_SPIRXINT;
    EDIS;

    /* 使能CPU中断 */
    PieCtrlRegs.PIEIER6.bit.INTx1 = 1U;
    IER |= M_INT6;
    PieCtrlRegs.PIEACK.all = PIEACK_GROUP6;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiIntConf
 *
 *    [功能描述]			SPI中断配置，当中断使能时，同时实现中断向量注册和CPU中断使能。
 *    [输入参数说明]		l_IntEnable_u8 ---- 中断使能配置，可能取值如下：
 *                      	SPI_INT_EN  ---- SPI中断使能
 *                      	SPI_INT_DIS ---- SPI中断禁止
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiIntConf(Uint8 l_IntEnable_u8)
{
    /* 使能接收中断和OVERRUN中断 */
    SpiaRegs.SPICTL.bit.OVERRUNINTENA = l_IntEnable_u8;
    SpiaRegs.SPICTL.bit.SPIINTENA = l_IntEnable_u8;

    /* 使能接收FIFO中断 */
    SpiaRegs.SPIFFRX.bit.RXFFIENA = l_IntEnable_u8;

    /* 禁止发送中断 */
    SpiaRegs.SPIFFTX.bit.TXFFIENA = 0U;

    /* 当中断使能时，完成中断向量注册及CPU中断使能 */
    if( SPI_INT_EN == l_IntEnable_u8 )
    {
        SpiIntEnable();
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiStatusGet
 *
 *    [功能描述]			SPI中断状态标志位获取。
 *    [输入参数说明]		NONE
 *    [输出参数说明]		SPI中断状态标志
 *    [其他说明]
 *    [返回]				SPI中断状态标志，包含如下标志位：
 *                  		SPI_RXFFINT  ---- SPI FIFO接收中断标志
 *                  		SPI_OVERRUN  ---- SPI OVERRUN标志
 *                  		SPI_INTFLAG  ---- SPI 接收中断标志
 */
/* ***************************************************************** */
Uint16 SpiStatusGet(void)
{
    Uint16 l_temp_u16 = 0U;

    l_temp_u16  = SpiaRegs.SPISTS.all;
    l_temp_u16 |= (SpiaRegs.SPIFFRX.bit.RXFFINT << 8U);

    return l_temp_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiIntAck
 *
 *    [功能描述]			SPI 中断应答。
 *    [输入参数说明]		l_IntFlag_u8----SPI FIFO接收中断标志，可能的取值如下：
								SPI_INT_RXFFINT ---- SPI FIFO接收中断标志
								SPI_INT_INTFLAG ---- SPI OVERRUN标志
								SPI_INT_OVERRUN ---- SPI 接收中断标志
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiIntAck(Uint8 l_IntFlag_u8)
{
    switch(l_IntFlag_u8)
    {
        /* SPI FIFO 接收中断 */
        case SPI_INT_RXFFINT:
            SpiaRegs.SPIFFRX.bit.RXFFINTCLR = 1U;
          break;

        /* SPI_INT_INTFLAG 通过读SPIRXBUF寄存器自动清除 */

        /* SPI OVERRUN中断 */
        case SPI_INT_OVERRUN:
            SpiaRegs.SPISTS.bit.OVERRUN_FLAG = 1U;
          break;

        default:
            break;
    }

    /* 清除组中断标志位 */
    PieCtrlRegs.PIEACK.all = PIEACK_GROUP6;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiRxFifoCount
 *
 *    [功能描述]			SPI接收缓冲区中数据个数
 *    [输入参数说明]		NONE
 *    [输出参数说明]		接收缓冲区中数据个数
 *    [其他说明]
 *    [返回]				接收缓冲区中数据个数
 */
/* ***************************************************************** */
Uint16 SpiRxFifoCount(void)
{
    return SpiaRegs.SPIFFRX.bit.RXFFST;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiTxFifoCount
 *
 *    [功能描述]			SPI发送缓冲区中数据个数
 *    [输入参数说明]		NONE
 *    [输出参数说明]		发送缓冲区中数据个数
 *    [其他说明]
 *    [返回]				发送缓冲区中数据个数
 */
/* ***************************************************************** */
Uint16 SpiTxFifoCount(void)
{
    return SpiaRegs.SPIFFTX.bit.TXFFST;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiIsRxReady
 *
 *    [功能描述]			判断SPI接收是否就绪。
 *    [输入参数说明]		NONE
 *    [输出参数说明]		SPI接收就绪状态
 *    [其他说明]
 *    [返回]				SPI接收就绪状态，可能值如下：
 *                  		SPI_RX_READY     ---- SPI接收就绪
 *                  		SPI_RX_NOT_READY ---- SPI接收未就绪
 */
/* ***************************************************************** */
Uint16 SpiIsRxReady(void)
{
    Uint16 l_temp_u16 = SPI_RX_NOT_READY;

#if SPI_FIFO_EN

    /* 判断接收缓冲区数据个数是否大于零 */
    if( SpiaRegs.SPIFFRX.bit.RXFFST > 0U)
    {
    	l_temp_u16 = SPI_RX_READY;
    }
#else

    /* 判断是否有接收数据中断标志 */
    if( 1 == SpiaRegs.SPISTS.bit.INT_FLAG )
    {
    	l_temp_u16 = SPI_RX_READY;
    }
#endif

    return l_temp_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiIsTxReady
 *
 *    [功能描述]			判断SPI发送是否就绪。
 *    [输入参数说明]		NONE
 *    [输出参数说明]		SPI发送就绪状态
 *    [其他说明]
 *    [返回]				SPI发送就绪状态，可能值如下：
 *                  		SPI_TX_READY     ---- SPI发送就绪
 *              			SPI_TX_NOT_READY ---- SPI未发送就绪
 */
/* ***************************************************************** */
Uint16 SpiIsTxReady(void)
{
    Uint16 l_temp_u16 = SPI_TX_NOT_READY;

#if SPI_FIFO_EN
    /* 判断发送FIFO是否满 */
    if( SpiaRegs.SPIFFTX.bit.TXFFST < SPI_FIFO_MAX )
    {
    	l_temp_u16 = SPI_TX_READY;
    }
#else
    /* 判断TXBUFF满标志 */
    if( 0 == SpiaRegs.SPISTS.bit.BUFFULL_FLAG )
    {
    	l_temp_u16 = SPI_TX_READY;
    }
#endif

    return l_temp_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiDelayCacu
 *
 *    [功能描述]			依据SPI通信波特率以及数据位数，计数单个数据传输需要的时间。
 *    [输入参数说明]		l_BaudRate_u16----通信波特率，单位：K
 *                      l_DataBits_u8 ----数据位数
 *    [输出参数说明]		单个数据传输所需要的时间
 *    [其他说明]
 *    [返回]				单个数据传输所需要的时间，单位：微妙(us)
 */
/* ***************************************************************** */
Uint16 SpiDelayCacu(Uint16 l_BaudRate_u16,Uint8 l_DataBits_u8)
{
    Uint16 l_temp_u16 = 0U;

    if( 0 != l_BaudRate_u16 )
    {
    	l_temp_u16 = (Uint16)((1000.0 / l_BaudRate_u16) * l_DataBits_u8) + 1U;
    }

    return l_temp_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiWrite
 *
 *    [功能描述]			通过SPI口发送一个数据，该函数内部完成数据的左对齐移位操作。
 *    [输入参数说明]		l_data_u16----SPI拟发送数据
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiWrite(Uint16 l_data_u16)
{
    SpiaRegs.SPITXBUF = l_data_u16 << (s_SpiShiftBits_u16 & 0x0F);
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiWriteBuff
 *
 *    [功能描述]			通过SPI口发送一组数据，该函数仅关心数据的发送，不管SPI数据接收，适用
 *                      于中断接收的场合。
 *    [输入参数说明]		l_buff_u16----待发送数据缓冲区首地址
 *                      l_len_u16 ----待发送数据长度
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiWriteBuff(Uint16 *l_buff_u16, Uint16 l_len_u16)
{
    Uint8 l_ii_u8 = 0U;
    Uint16 l_DelayCount_u16 = 0U;

    for( l_ii_u8 = 0U; l_ii_u8 < l_len_u16; )
    {
        /* 等待发送缓冲区就绪 */
        if( SPI_TX_READY == SpiIsTxReady() )
        {
            SpiWrite(l_buff_u16[l_ii_u8]);
            l_ii_u8++;

            /* 清除延时计数 */
            l_DelayCount_u16 = 0U;
        }
        else
        {
            /* 等待延时计数 */
        	l_DelayCount_u16++;
            delayUs(1UL);

            /* 判断等待是否超时，若超时舍弃当前数据 */
            if( l_DelayCount_u16 > s_SpiDelayCount_u16 )
            {
            	l_DelayCount_u16 = 0U;
                l_ii_u8++;

                //错误计数
                s_SpiErrCount_u16++;
            }
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiRead
 *
 *    [功能描述]			从SPI接口读取一个数据。
 *    [输入参数说明]		NONE
 *    [输出参数说明]		所读取数据
 *    [其他说明]
 *    [返回]				所读取数据
 */
/* ***************************************************************** */
Uint16 SpiRead(void)
{
    return SpiaRegs.SPIRXBUF;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiReadBuff
 *
 *    [功能描述]			从SPI接收缓冲区连续读取数据，适用于启用FIFO场合。
 *    [输入参数说明]		l_buff_u16---- 拟接收数据缓冲区首地址
 *                      l_len_u16 ---- 拟接收数据长度
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiReadBuff(Uint16 *l_buff_u16, Uint16 l_len_u16)
{
    Uint8 l_ii_u8 = 0U;

    for( l_ii_u8 = 0U; l_ii_u8 < l_len_u16; l_ii_u8++)
    {
        if( SPI_RX_READY == SpiIsRxReady() )
        {
        	l_buff_u16[l_ii_u8] = SpiaRegs.SPIRXBUF;
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiDataTrans
 *
 *    [功能描述]			SPI数据传输，当不使用中断接收时，该函数同时实现数据的发送和接收。
 *                      若使用中断接收时，该函数仅实现数据的发送，不处理数据的接收。
 *    [输入参数说明]		l_DataBuff_u16---- 待发送（拟接收）数据缓冲区首地址
 *                      l_len_u8 ---- 发送(接收)数据长度
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiDataTrans(Uint16 * l_DataBuff_u16, Uint8 l_len_u8)
{
    Uint8 l_TxCount_u8 = 0U;          //发送计数
    Uint8 l_RxCount_u8 = 0U;          //接收计数
    Uint16 l_DelayCount_u16 = 0U;      //延时计数

    while( l_RxCount_u8 < l_len_u8)
    {
        /* 判断是否需要发送数据 */
        if( ( l_TxCount_u8 < l_len_u8 ) && ( SPI_TX_READY == SpiIsTxReady() ))
        {
            SpiWrite(l_DataBuff_u16[l_TxCount_u8]);
            /* dataBuff[txCount] = 0; */
            l_TxCount_u8++;
        }

        /* 判断数据接收是否就绪 */
        if( SPI_RX_READY == SpiIsRxReady())
        {
        	l_DataBuff_u16[l_RxCount_u8] = SpiaRegs.SPIRXBUF;
        	l_RxCount_u8++;

        	l_DelayCount_u16 = 0U;
        }
        else
        {
            /* 接收未就绪时，延时并计数 */
        	l_DelayCount_u16++;

            delayUs(1);

            /* 判断接收延时是否超时，若超时则跳过当前数据接收 */
            if( l_DelayCount_u16 > s_SpiDelayCount_u16 )
            {
            	l_DelayCount_u16 = 0U;
                l_RxCount_u8++;

                //错误计数
                s_SpiErrCount_u16++;
            }
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiReset
 *
 *    [功能描述]			复位SPI状态，包括FIFO部分，所有的配置信息不受影响。
 *    [输入参数说明]		NONE
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiReset(void)
{
    /* 进入复位状态 */
    SpiaRegs.SPICCR.bit.SPISWRESET = 0U;
    SpiaRegs.SPIFFTX.bit.SPIRST = 0U;

    NOP;
    NOP;

    /* 退出复位状态 */
    SpiaRegs.SPICCR.bit.SPISWRESET = 1U;
    SpiaRegs.SPIFFTX.bit.SPIRST = 1U;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiClkModeSet
 *
 *    [功能描述]			SPI时钟模式极性、相位设置，只有(0,0),(0,1),(1,0),(1,1)四种模式
 *    [输入参数说明]		l_polarity_u8---- SPI时钟的极性，可能取值如下：
 *    						0 ---- 数据在上升沿输出，下降沿输入
 *                  		1 ---- 数据在下降沿输出，上升沿输入
 *                  	l_phase_u8---- SPI时钟的相位，可能取值如下：
 *                  		0 ---- 正常时钟输出
 *                  		1 ---- 延时半个时钟周期输出
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiClkModeSet(Uint8 l_polarity_u8, Uint8 l_phase_u8)
{
    SpiaRegs.SPICCR.bit.CLKPOLARITY = l_polarity_u8;
    SpiaRegs.SPICTL.bit.CLK_PHASE = l_phase_u8;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiLoopBackModeSet
 *
 *    [功能描述]			SPI回环模式设置
 *    [输入参数说明]		l_LbMode_u8---- SPI回环模式，可能取值如下：
 *    						SPI_LOOP_EN  ---- SPI回环模式使能
 *                  		SPI_LOOP_DIS ---- SPI回环模式禁止
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiLoopBackModeSet(Uint8 l_LbMode_u8)
{
    SpiaRegs.SPICCR.bit.SPILBK = l_LbMode_u8;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiMasterSlaveSet
 *
 *    [功能描述]			SPI主从工作模式设置
 *    [输入参数说明]		l_mode_u8 ---- SPI主从工作模式，可能取值如下：
 *    							SPI_MASTER ---- SPI工作于主模式
 *                  			SPI_SLAVE  ---- SPI工作于从模式
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiMasterSlaveSet(Uint8 l_mode_u8)
{
    SpiaRegs.SPICTL.bit.MASTER_SLAVE = l_mode_u8;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiDataBitsSet
 *
 *    [功能描述]			SPI数据位数设定，取值范围为【1,16】
 *    [输入参数说明]		l_DataBits_u8 ---- SPI数据位数
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiDataBitsSet(Uint8 l_DataBits_u8)
{
    /* 设置左移位数 */
	s_SpiShiftBits_u16 = SPI_MAX_DBITS - l_DataBits_u8;

    if( l_DataBits_u8 > 0U )
    {
    	l_DataBits_u8 = l_DataBits_u8 - 1U;
    }

    SpiaRegs.SPICCR.bit.SPICHAR = l_DataBits_u8;
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiFIFOSet
 *
 *    [功能描述]			SPI FIFO模式以及接收FIFO触发数设置。
 *    [输入参数说明]		l_FifoLevel_u8 ---- SPI 接收FIFO触发数设置，取值范围为：【0,16】
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiFIFOSet(Uint8 l_FifoLevel_u8)
{
#if SPI_FIFO_EN

    /* 使能 SPI FIFO模式 */
    SpiaRegs.SPIFFTX.bit.SPIFFENA = 1U;

    /* 接收FIFO触发数设置 */
    SpiaRegs.SPIFFRX.bit.RXFFIL = l_FifoLevel_u8;
#else

    /* 关闭 SPI FIFO模式 */
    SpiaRegs.SPIFFTX.bit.SPIFFENA = 0;
#endif
}

/* ***************************************************************** */
/**
 *    [函数名]			SpiInit
 *
 *    [功能描述]			SPI接口初始化配置。
 *    [输入参数说明]		NONE
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void SpiInit(void)
{
    Uint16 l_temp_u16 = 0;

    /* 进入复位状态 */
    SpiaRegs.SPICCR.bit.SPISWRESET = 0U;
    SpiaRegs.SPIFFTX.bit.SPIRST = 0U;

    /* 时钟极性、相位模式设置 */
    SpiClkModeSet(s_MySpiConf_t.g_ClkPolarity_u8,s_MySpiConf_t.g_ClkPhase_u8);

    /* 主从模式设置 */
    SpiMasterSlaveSet(s_MySpiConf_t.g_SpiMode_u8);

    /* SPI引脚配置 */
    SpiGpioConf(s_MySpiConf_t.g_SimoGpio_u8,s_MySpiConf_t.g_SomiGpio_u8,s_MySpiConf_t.g_ClkGpio_u8,s_MySpiConf_t.g_SpisteGpio_u8);

    /* 回环模式设置 */
    SpiLoopBackModeSet(s_MySpiConf_t.g_LoopBackMode_u8);

    /* 数据位数设置 */
    SpiDataBitsSet(s_MySpiConf_t.g_DataBits_u8);

    /* 当仿真器暂停程序时，SPI继续正常运行 */
    SpiaRegs.SPIPRI.bit.SOFT = 0U;
    SpiaRegs.SPIPRI.bit.FREE = 0U;

    /* SPI FIFO设置 */
    SpiFIFOSet(s_MySpiConf_t.g_FifoLevel_u8);

    /* NO Delay */

    /* 波特率设置 */
    l_temp_u16 = SpiBaudRateSet(DSP_LSPCLK,s_MySpiConf_t.g_BaudRate_u16);

    /* 单个数据传输最大延时计算 */
    s_SpiDelayCount_u16 = SpiDelayCacu(s_MySpiConf_t.g_BaudRate_u16,s_MySpiConf_t.g_DataBits_u8);

    /* 中断配置 */
    SpiIntConf(s_MySpiConf_t.g_IntMode_u8);

    /* 使能SPI发送 */
    SpiaRegs.SPICTL.bit.TALK = 1U;

    /* 退出复位状态 */
    SpiaRegs.SPICCR.bit.SPISWRESET = 1U;
    SpiaRegs.SPIFFTX.bit.SPIRST = 1U;

    l_temp_u16 = l_temp_u16;
}

#endif
//================================================================================
// END OF FILE
//================================================================================
