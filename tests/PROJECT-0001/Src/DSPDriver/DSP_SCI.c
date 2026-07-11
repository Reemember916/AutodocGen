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
 *文件名称:    DSP_SCI.c
 *
 *功能说明:   文件功能说明
 *
 *
 *文件日期:   REDACTED
 *
 *
 *程序版本:   V1.02
 *
 *********************************************************************************/

#include "Global.h"
#include "DSP_SCI.h"

/* ***************************************************************** */
/* 本地数据定义 */

/* SCI端口 */
SCIPort_t mySciPorts[3U];

/* SCI端口配置 */
sciConf_t mySciConfs[3U] = {SCI_A_CONF_TAB,SCI_B_CONF_TAB,SCI_C_CONF_TAB};

/* ***************************************************************** */
/**
 * 【说明】:SciDelayGet
 *
 * 依据SCI口的波特率，计算发送单个字节数据的最大等待时间
 *
 * 【参数】:baudRate ---- SCI口波特率
 *
 * 【返回】:发送单个字节数据的最大延时，单位为微妙
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciDelayGet
 *
 * 【功能描述】依据SCI口波特率计算发送单个字节数据的最大等待延时
 *
 * 【输入参数说明】baudRate ---- SCI口波特率
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】发送单个字节数据的最大延时，单位为微秒
 */
/* ***************************************************************** */
Uint16 SciDelayGet(Uint32 baudRate)
{
    Uint16 delay = 0U;

    if(baudRate < SCI_BAUDRATE_MIN)
    {
        baudRate = SCI_BAUDRATE_MIN;
    }
    /* 默认以12个BIT进行计算 */
    delay = 12000000ul / baudRate;

    return delay;
}

/* ***************************************************************** */
/**
 * 【说明】:BaudRateSet
 *
 * SCI通信波特率设置，波特率的可选择范围为【2400,115200】
 *
 * 【参数】:sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【参数】:baud  ---- SCI口待配置波特率
 *
 * 【返回】:波特率分频系数
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:BaudRateSet
 *
 * 【功能描述】SCI通信波特率设置，并计算发送单字节最大等待延时
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输入参数说明】baud   ---- SCI口待配置波特率，可选范围[2400,115200]
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】波特率分频系数
 */
/* ***************************************************************** */
Uint16 BaudRateSet(Uint16 sciID,Uint32 baud)
{
    Uint16 temp = 0U;
    Uint32 bRate = 0UL;

    if(sciID < SCI_PORT_NUM)
    {
        /* 波特率参数限幅 */
        if( baud > SCI_BAUDRATE_MAX )
        {
            bRate = SCI_BAUDRATE_MAX;
        }
        else if( baud < SCI_BAUDRATE_MIN )
        {
            bRate = SCI_BAUDRATE_MIN;
        }
        else
        {
            bRate = baud;
        }

        /* 计算波特率分频系数并赋值 */
        temp = (((1000000ul * DSP_LSPCLK) / 8U) / bRate) - 1U;

        mySciPorts[sciID].pSci->SCIHBAUD = (temp >> 8U) & 0xFFU;
        mySciPorts[sciID].pSci->SCILBAUD = temp & 0xFFU;

        /* 计数发送单个数最长延时 */
        mySciPorts[sciID].delay = SciDelayGet(bRate);
    }

    return temp;
}

/* ***************************************************************** */
/**
 * 【说明】:SciIntEnable
 *
 *  注册SCI中断向量，并使能CPU中断
 *
 * 【参数】:sciID ---- SCI口ID，可取值为：SCI_A_ID、SCI_B_ID、SCI_C_ID
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciIntEnable
 *
 * 【功能描述】注册SCI中断向量，并使能CPU中断
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID、SCI_B_ID、SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciIntEnable(Uint8 sciID)
{
    EALLOW;

    switch(sciID)
    {
        case(SCI_A_ID):
            {
                PieVectTable.SCIRXINTA = &ISR_SCIA_RXINT;   /* 注册SCIA中断向量 */

                PieCtrlRegs.PIEIER9.bit.INTx1 = 1U;          /* 使能中断 */
                IER |= M_INT9;
            }
            break;

        case(SCI_B_ID):
            {
                PieVectTable.SCIRXINTB = &ISR_SCIB_RXINT;   /* 注册SCIB中断向量 */

                PieCtrlRegs.PIEIER9.bit.INTx3 = 1U;          /* 使能中断 */
                IER |= M_INT9;
            }
            break;

        case(SCI_C_ID):
            {
                PieVectTable.SCIRXINTC = &ISR_SCIC_RXINT;   /* 注册SCIC中断向量 */

                PieCtrlRegs.PIEIER8.bit.INTx5 = 1U;          /* 使能中断 */
                IER |= M_INT8;
            }
            break;

        default:
            break;
    }

    EDIS;
}

/* ***************************************************************** */
/**
 * 【说明】:SciPinConfig
 *
 * 该函数用来实现对SCI口的接收、发送引脚进行配置。
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 * 【参数】:txpin ---- 发送引脚序号
 * 【参数】:rxpin ---- 接收引脚序号
 *
 * SCI口发送、接收引脚可能的配置如下：
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
/* ***************************************************************** */
/**
 * 【函数名】:SciPinConfig
 *
 * 【功能描述】配置SCI口的接收、发送引脚复用
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输入参数说明】txpinNum ---- 发送引脚序号
 * 【输入参数说明】rxpinNum ---- 接收引脚序号
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciPinConfig(Uint8 sciID,Uint8 txpinNum,Uint8 rxpinNum)
{
    EALLOW;

    switch(sciID)
    {
        case SCI_A_ID:
            {
                if( txpinNum == GPIO_NUM_29 )
                {
                    GpioCtrlRegs.GPAMUX2.bit.GPIO29 = 1U;
                }
                else if(txpinNum == GPIO_NUM_35)
                {
                    GpioCtrlRegs.GPBMUX1.bit.GPIO35 = 1U;
                }
                else
                {
                    /* 无操作 */
                }

                if( rxpinNum == GPIO_NUM_28 )
                {
                    GpioCtrlRegs.GPAMUX2.bit.GPIO28 = 1U;
                }
                else if(rxpinNum == GPIO_NUM_36)
                {
                    GpioCtrlRegs.GPBMUX1.bit.GPIO36 = 1U;
                }
                else
                {
                    /* 无操作 */
                }
            }
            break;

        case SCI_B_ID:
            {
                switch(txpinNum)
                {
                    case GPIO_NUM_9:
                        GpioCtrlRegs.GPAMUX1.bit.GPIO9 = 2U;
                        break;

                    case GPIO_NUM_14:
                        GpioCtrlRegs.GPAMUX1.bit.GPIO14 = 2U;
                        break;

                    case GPIO_NUM_18:
                        GpioCtrlRegs.GPAMUX2.bit.GPIO18 = 2U;
                        break;

                    case GPIO_NUM_22:
                        GpioCtrlRegs.GPAMUX2.bit.GPIO22 = 3U;
                        break;

                    default:
                        break;
                }

                switch(rxpinNum)
                {
                    case GPIO_NUM_11:
                        GpioCtrlRegs.GPAMUX1.bit.GPIO11 = 2U;
                        break;

                    case GPIO_NUM_15:
                        GpioCtrlRegs.GPAMUX1.bit.GPIO15 = 2U;
                        break;

                    case GPIO_NUM_19:
                        GpioCtrlRegs.GPAMUX2.bit.GPIO19 = 2U;
                        break;

                    case GPIO_NUM_23:
                        GpioCtrlRegs.GPAMUX2.bit.GPIO23 = 3U;
                        break;

                    default:
                        break;
                }
            }
            break;

        case SCI_C_ID:
            {
                if( txpinNum == GPIO_NUM_63 )
                {
                    GpioCtrlRegs.GPBMUX2.bit.GPIO63 = 1U;
                }

                /* 忽略非法发送管脚设置 */

                if( rxpinNum == GPIO_NUM_62 )
                {
                    GpioCtrlRegs.GPBMUX2.bit.GPIO62 = 1U;
                }

                /* 忽略非法接收管脚设置 */
            }
            break;
        default:
            break;
    }

    EDIS;
}

/* ***************************************************************** */
/**
 * 【说明】:SciRxStatusGet
 *
 * 获取SCI口接收状态。
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【返回】:SCI接收状态，可能的取值如下：
 *          SCI_RX_FIFO_OVFL ---- 接收FIFO溢出
 *          SCI_RX_FIFO_INT  ---- 接收FIFO中断
 *          SCI_RX_ERR       ---- 接收错误
 *          SCI_RX_RDY       ---- 接收数据就位（非FIFO模式）
 *          SCI_RX_BRKDT     ---- 检测到接收 break
 *          SCI_RX_FE_ERR    ---- 接收报文错误
 *          SCI_RX_OE_ERR    ---- 接收 overrunn 错误
 *          SCI_RX_PE_ERR    ---- 接收校验错误
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciRxStatusGet
 *
 * 【功能描述】获取SCI口接收状态标志
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】SCI接收状态标志，可能的取值包括SCI_RX_FIFO_OVFL、SCI_RX_FIFO_INT、SCI_RX_ERR、SCI_RX_RDY、SCI_RX_BRKDT、SCI_RX_FE_ERR、SCI_RX_OE_ERR、SCI_RX_PE_ERR
 */
/* ***************************************************************** */
Uint16 SciRxStatusGet(Uint16 sciID)
{
    Uint16 temp = 0;

    /* 参数合法性检查 */
    if( sciID < SCI_PORT_NUM )
    {
        temp =   mySciPorts[sciID].pSci->SCIRXST.all;
        temp |= (mySciPorts[sciID].pSci->SCIFFRX.bit.RXFFINT << 8U);
        temp |= (mySciPorts[sciID].pSci->SCIFFRX.bit.RXFFOVF << 9U);
    }

    /* 非法端口操作返回默认值 */

    return temp;
}

/* ***************************************************************** */
/**
 * 【说明】:SciRxFFOVClear
 *
 * 清除接收FIFO溢出标志位
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciRxFFOVClear
 *
 * 【功能描述】清除接收FIFO溢出标志位
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciRxFFOVClear(Uint16 sciID)
{
    /* 参数合法性检查 */
    if( sciID < SCI_PORT_NUM )
    {
        mySciPorts[sciID].pSci->SCIFFRX.bit.RXFFOVRCLR = 1U;
    }

    /* 忽略掉非法端口操作 */
}

/* ***************************************************************** */
/**
 * 【说明】:SciReset
 *
 * 复位SCI接口，清除状态标志位，复位FIFO状态机，配置信息不受影响。
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciReset
 *
 * 【功能描述】复位SCI接口，清除状态标志位，复位FIFO状态机，配置信息不受影响
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciReset(Uint16 sciID)
{
    /* 参数合法性检查 */
    if( sciID < SCI_PORT_NUM )
    {
        /* 复位SCI */
        mySciPorts[sciID].pSci->SCICTL1.bit.SWRESET = 0U;
        mySciPorts[sciID].pSci->SCIFFTX.bit.SCIRST  = 0U;

        NOP; NOP; NOP; NOP;
        NOP; NOP; NOP; NOP;

        /* 从复位中恢复 */
        mySciPorts[sciID].pSci->SCICTL1.bit.SWRESET = 1U;
        mySciPorts[sciID].pSci->SCIFFTX.bit.SCIRST  = 1U;
    }

    /* 忽略掉非法端口操作 */
}

/* ***************************************************************** */
/**
 * 【说明】:SciTxRxEnable
 *
 * 该函数实现SCI端口接收、发送的使能和关闭功能。
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【参数】:opCode ：操作码，可选择的参数如下：
 *                 SCI_TX_EN    使能SCI发送
 *                 SCI_RX_EN    使能SCI接收
 *                 SCI_TXRX_EN  使能SCI接收和发送
 *                 SCI_TX_DIS   禁止SCI发送
 *                 SCI_RX_DIS   禁止SCI接收
 *                 SCI_TXRX_DIS 禁止SCI发送和接收
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciTxRxEnable
 *
 * 【功能描述】SCI端口接收、发送的使能和关闭
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输入参数说明】opCode ---- 操作码，可取值：SCI_TX_EN、SCI_RX_EN、SCI_TXRX_EN、SCI_TX_DIS、SCI_RX_DIS、SCI_TXRX_DIS
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciTxRxEnable(Uint16 sciID,Uint16 opCode)
{
    switch(opCode)
    {
        case SCI_TX_EN:
            {
                mySciPorts[sciID].pSci->SCICTL1.bit.TXENA = 1U;
            }
            break;

        case SCI_RX_EN:
            {
                mySciPorts[sciID]. pSci->SCICTL1.bit.RXENA = 1U;
            }
            break;

        case SCI_TXRX_EN:
            {
                mySciPorts[sciID].pSci->SCICTL1.bit.TXENA = 1U;
                mySciPorts[sciID].pSci->SCICTL1.bit.RXENA = 1U;
            }
            break;

        case SCI_TX_DIS:
            {
                mySciPorts[sciID].pSci->SCICTL1.bit.TXENA = 0U;
            }
            break;

        case SCI_RX_DIS:
            {
                mySciPorts[sciID].pSci->SCICTL1.bit.RXENA = 0U;
            }
            break;

        case SCI_TXRX_DIS:
            {
                mySciPorts[sciID].pSci->SCICTL1.bit.TXENA = 0U;
                mySciPorts[sciID].pSci->SCICTL1.bit.RXENA = 0U;
            }
            break;
        default:
            break;
    }
}

/* ***************************************************************** */
/**
 * 【说明】:SciLoopBackEn
 *
 * 该函数实现SCI口的回环模式使能和禁止。
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【参数】:opCode ：操作码，可选择参数如下：
 *          SCI_LOOPB_DIS ---- SCI口回环模式禁止
 *          SCI_LOOPB_EN  ---- SCI回环模式开启
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciLoopBackEn
 *
 * 【功能描述】SCI口回环模式使能或禁止
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输入参数说明】opCode ---- 操作码，可取值：SCI_LOOPB_EN、SCI_LOOPB_DIS
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciLoopBackEn(Uint16 sciID, Uint16 opCode)
{
    /* 参数合法性检查 */
    if( sciID < SCI_PORT_NUM )
    {
        /* 回环模式设置 */
        if( SCI_LOOPB_EN == opCode )
        {
            mySciPorts[sciID].pSci->SCICCR.bit.LOOPBKENA = 1U;
        }
        else
        {
            mySciPorts[sciID].pSci->SCICCR.bit.LOOPBKENA = 0U;
        }
    }

    /* 忽略非法端口操作 */
}

/* ***************************************************************** */
/**
 * 【说明】:SciDataBitsSet
 *
 * SCI通信数据位数设置。
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【参数】:databits ---- 拟设置数据位数，可能取值如下：
 *          SCI_DATABITS_1 -- SCI_DATABITS_8 ，数据位数位一位到八位
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciDataBitsSet
 *
 * 【功能描述】SCI通信数据位数设置
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输入参数说明】databits ---- 拟设置数据位数，取值范围：SCI_DATABITS_1 ~ SCI_DATABITS_8
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciDataBitsSet(Uint16 sciID,Uint16 databits)
{
    Uint16 temp = 0U;

    /* 参数合法性检查 */
    if( sciID < SCI_PORT_NUM )
    {
        if( databits > SCI_DATABITS_8 )
        {
            temp = SCI_DATABITS_8;
        }
        else
        {
            temp = databits;
        }

        /* 设置数据位数 */
        mySciPorts[sciID].pSci->SCICCR.bit.SCICHAR = temp;
    }

    /* 忽略非法端口操作 */
}

/* ***************************************************************** */
/**
 * 【说明】:SciStopBitsSet
 *
 * SCI通信停止位设置。
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【参数】:stopbits ---- 拟设置停止位位数，可能取值如下：
 *          SCI_STOPBITS_ONE ---- 一位停止位
 *          SCI_STOPBITS_TWO ---- 两位停止位
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciStopBitsSet
 *
 * 【功能描述】SCI通信停止位位数设置
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输入参数说明】stopbits ---- 拟设置停止位位数，可取值：SCI_STOPBITS_ONE、SCI_STOPBITS_TWO
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciStopBitsSet(Uint16 sciID,Uint16 stopbits)
{
    /* 参数合法性检查 */
    if( sciID < SCI_PORT_NUM )
    {
        /* 两位停止位 */
        if( SCI_STOPBITS_TWO == stopbits )
        {
            mySciPorts[sciID].pSci->SCICCR.bit.STOPBITS = 1U;
        }
        else    /* 一位停止位 */
        {
            mySciPorts[sciID].pSci->SCICCR.bit.STOPBITS = 0U;
        }
    }

    /* 忽略非法端口操作 */
}

/* ***************************************************************** */
/**
 * 【说明】:SciParitySet
 *
 * SCI通信奇偶校验设置。
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【参数】:parityMode ---- 拟设置奇偶校验模式，可能取值如下：
 *          SCI_PARITY_NONE ---- 无校验
 *          SCI_PARITY_EVEN ---- 偶校验
 *          SCI_PARITY_ODD  ---- 奇校验
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciParitySet
 *
 * 【功能描述】SCI通信奇偶校验设置
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输入参数说明】parityMode ---- 拟设置奇偶校验模式，可取值：SCI_PARITY_NONE、SCI_PARITY_EVEN、SCI_PARITY_ODD
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciParitySet(Uint16 sciID,Uint16 parityMode)
{
    /* 参数合法性检查 */
    if( sciID < SCI_PORT_NUM )
    {
        switch(parityMode)
        {
            case SCI_PARITY_EVEN:   /* 偶校验 */
                {
                    mySciPorts[sciID].pSci->SCICCR.bit.PARITYENA = 1U;
                    mySciPorts[sciID].pSci->SCICCR.bit.PARITY    = 1U;
                }
                break;

            case SCI_PARITY_ODD:    /* 奇校验 */
                {
                    mySciPorts[sciID].pSci->SCICCR.bit.PARITYENA = 1U;
                    mySciPorts[sciID].pSci->SCICCR.bit.PARITY    = 0U;
                }
                break;

            default:                /* 无校验 */
                {
                    mySciPorts[sciID].pSci->SCICCR.bit.PARITYENA = 0U;
                }
                break;
        }
    }

    /* 忽略非法端口操作 */
}

/* ***************************************************************** */
/**
 * 【说明】:SciConfig
 *
 * 依据SCI端口的配置信息，完成对SCI端口的配置
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciConfig
 *
 * 【功能描述】依据SCI端口的配置信息完成对SCI端口的引脚、回环、数据位、停止位、校验、波特率、FIFO等配置
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciConfig(Uint16 sciID)
{
    /* 输入参数合法性检查 */
    if( sciID < SCI_PORT_NUM)
    {
        /* 进入复位状态 */
        mySciPorts[sciID].pSci->SCICTL1.bit.SWRESET = 0U;
        mySciPorts[sciID].pSci->SCIFFTX.bit.SCIRST  = 0U;

        /* 禁止接收和发送 */
        SciTxRxEnable(sciID,SCI_TXRX_DIS);

        /* SCI 引脚配置 */
        SciPinConfig(sciID,mySciConfs[sciID].txpin,mySciConfs[sciID].rxpin);

        /* 回环模式设置 */
        SciLoopBackEn(sciID,mySciConfs[sciID].loopEn);

        /* 数据位数设置 */
        SciDataBitsSet(sciID,mySciConfs[sciID].databits);

        /* 停止位设置 */
        SciStopBitsSet(sciID,mySciConfs[sciID].stopbits);

        /* 校验方式设置 */
        SciParitySet(sciID,mySciConfs[sciID].parity);

        /* 不论是否使能FIFO功能，均配置RXERR中断功能 */
        mySciPorts[sciID].pSci->SCICTL1.bit.RXERRINTENA = mySciConfs[sciID].rxinten;

        /* 禁用SLEEP和TXWAKE */
        mySciPorts[sciID].pSci->SCICTL1.bit.TXWAKE      = 0U;
        mySciPorts[sciID].pSci->SCICTL1.bit.SLEEP       = 0U;

        /* SCI通信波特率计算 */
        BaudRateSet(sciID,mySciConfs[sciID].baud);

        /* 禁用发送中断 */
        mySciPorts[sciID].pSci->SCICTL2.bit.TXINTENA = 0U;

#if SCI_FIFO_EN
        /* 使能SCI FIFO功能 */
        mySciPorts[sciID].pSci->SCIFFTX.bit.SCIFFENA = 1U;

        /* 禁用SCI FIFO发送中断功能 */
        mySciPorts[sciID].pSci->SCIFFTX.bit.TXFFIENA     = 0U;
        mySciPorts[sciID].pSci->SCIFFTX.bit.TXFIFOXRESET = 1U;

        /* 清除SCI FIFO接收溢出标志 */
        mySciPorts[sciID].pSci->SCIFFRX.bit.RXFFOVRCLR  = 1U;
        mySciPorts[sciID].pSci->SCIFFRX.bit.RXFIFORESET = 1U;

        /* 清除SCI FIFO接收中断标志位 */
        mySciPorts[sciID].pSci->SCIFFRX.bit.RXFFINTCLR  = 1U;

        /* 配置SCI FIFO接收中断 */
        mySciPorts[sciID].pSci->SCIFFRX.bit.RXFFIENA    = mySciConfs[sciID].rxinten;

        /* 配置SCI FIFO接收中断触发数 */
        mySciPorts[sciID].pSci->SCIFFRX.bit.RXFFIL      = mySciConfs[sciID].fifolevel;

        /* 禁用 RXRDY 以及 RRKDT 中断 */
        mySciPorts[sciID].pSci->SCICTL2.bit.RXBKINTENA = 0U;
#else
        /* 禁用SCI FIFO功能 */
        mySciPorts[sciID].pSci->SCIFFTX.bit.SCIFFENA   = 0U;

        /* 配置 RXRDY 以及 RRKDT 中断 */
        mySciPorts[sciID].pSci->SCICTL2.bit.RXBKINTENA = mySciConfs[sciID].rxinten;
#endif
        /* 若中断使能，则注册中断向量 */
        if( SCI_RX_INT_EN == mySciConfs[sciID].rxinten)
        {
            SciIntEnable(sciID);
        }

        /* 使能接收和发送 */
        SciTxRxEnable(sciID,SCI_TXRX_EN);

        /* 退出复位状态 */
        mySciPorts[sciID].pSci->SCICTL1.bit.SWRESET = 1U;
        mySciPorts[sciID].pSci->SCIFFTX.bit.SCIRST  = 1U;
    }

    /* 忽略非法端口操作 */
}

/* ***************************************************************** */
/**
 * 【说明】:sciDataInit
 *
 * SCI模块数据初始化
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciDataInit
 *
 * 【功能描述】SCI模块数据初始化，将三个SCI端口寄存器起始地址映射到全局变量
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciDataInit(void)
{
    /* 三个SCI端口寄存器起始地址初始化 */
    mySciPorts[SCI_A_ID].pSci  = &SciaRegs;
    mySciPorts[SCI_A_ID].delay = 0U;

    mySciPorts[SCI_B_ID].pSci = &ScibRegs;
    mySciPorts[SCI_B_ID].delay = 0U;

    mySciPorts[SCI_C_ID].pSci = &ScicRegs;
    mySciPorts[SCI_C_ID].delay = 0U;
}

/* ***************************************************************** */
/**
 * 【说明】:sciInit
 *
 * 对SCI口进行初始化
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciInit
 *
 * 【功能描述】对SCI模块进行初始化，包括数据初始化和各使能端口的配置
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciInit(void)
{
    /* SCI模块数据初始化 */
    SciDataInit();

#if DSP_SCI_A
    SciConfig(SCI_A_ID);
#endif

#if DSP_SCI_B
    SciConfig(SCI_B_ID);
#endif

#if DSP_SCI_C
    SciConfig(SCI_C_ID);
#endif
}

/* ***************************************************************** */
/**
 * 【说明】:SciIsTxReady
 *
 * 判断发送缓冲区是否准备就绪
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【返回】:发送缓冲区就绪状态
 *          OK    ---- SCI发送缓冲区就绪
 *          ERROR ---- SCI发送缓冲区未就绪
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciIsTxReady
 *
 * 【功能描述】判断发送缓冲区是否准备就绪（FIFO或非FIFO模式均支持）
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】发送缓冲区就绪状态：OK-就绪，ERROR-未就绪
 */
/* ***************************************************************** */
Uint8 SciIsTxReady(Uint16 sciID)
{
    Uint8 temp = ERROR;

    if( sciID < SCI_PORT_NUM )
    {
#if SCI_FIFO_EN

        if(mySciPorts[sciID].pSci->SCIFFTX.bit.TXFFST < SCI_FIFO_MAX)
        {
            temp = OK;
        }
        else
        {
            temp = ERROR;
        }
#else
        if(mySciPorts[sciID].pSci->SCICTL2.bit.TXRDY == 1U)
        {
            temp = OK;
        }
        else
        {
            temp = ERROR;
        }
#endif
    }
    else
    {
        /* 忽略非法端口操作 */
        temp = ERROR;
    }


    return temp;
}

/* ***************************************************************** */
/**
 * 【说明】:SciIsRxReady
 *
 * 判断接收缓冲区数据是否就绪
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【返回】:接收缓冲区就绪状态
 *          OK    ---- SCI接收缓冲区就绪
 *          ERROR ---- SCI接收缓冲区未就绪
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciIsRxReady
 *
 * 【功能描述】判断接收缓冲区数据是否就绪（FIFO或非FIFO模式均支持）
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】接收缓冲区就绪状态：OK-就绪，ERROR-未就绪
 */
/* ***************************************************************** */
Uint8 SciIsRxReady(Uint16 sciID)
{
    Uint8 temp  = ERROR;

    if( sciID < SCI_PORT_NUM )
    {
#if SCI_FIFO_EN

        if(mySciPorts[sciID].pSci->SCIFFRX.bit.RXFFST > 0U)
        {
            temp = OK;
        }
        else
        {
            temp = ERROR;
        }
#else
        if(mySciPorts[sciID].pSci->SCIRXST.bit.RXRDY == 1U)
        {
            temp = OK;
        }
        else
        {
            temp = ERROR;
        }
#endif
    }
    else
    {
        temp = ERROR;
    }

    return temp;
}

/* ***************************************************************** */
/**
 * 【说明】:SciRxFIFOCount
 *
 * 获取接收FIFO缓冲区中的字节数
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【返回】:接收FIFO缓冲区中的字节数
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciRxFIFOCount
 *
 * 【功能描述】获取接收FIFO缓冲区中已存在的字节数
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】接收FIFO缓冲区中的字节数
 */
/* ***************************************************************** */
Uint8 SciRxFIFOCount(Uint16 sciID)
{
    Uint8 temp = 0U;

    if( sciID < SCI_PORT_NUM )
    {
        temp = mySciPorts[sciID].pSci->SCIFFRX.bit.RXFFST;
    }
    else
    {
        temp = 0U;
    }

    return temp;
}

/* ***************************************************************** */
/**
 * 【说明】:SciTxFIFOCount
 *
 * 获取发送FIFO缓冲区字节数
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【返回】:发送FIFO缓冲区中的字节数
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciTxFIFOCount
 *
 * 【功能描述】获取发送FIFO缓冲区中已存在的字节数
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】发送FIFO缓冲区中的字节数
 */
/* ***************************************************************** */
Uint8 SciTxFIFOCount(Uint16 sciID)
{
    Uint8 temp = 0U;

    if( sciID < SCI_PORT_NUM )
    {
        temp = mySciPorts[sciID].pSci->SCIFFTX.bit.TXFFST;
    }
    else
    {
        temp = 0U;
    }

    return temp;
}

/* ***************************************************************** */
/**
 * 【说明】:SciGetChar
 *
 * 从SCI口获取一个字节
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 *
 * 【返回】:从SCI口获得的字节
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciGetChar
 *
 * 【功能描述】从SCI口接收缓冲区读取一个字节
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】从SCI口获得的字节
 */
/* ***************************************************************** */
Uint16 SciGetChar(Uint16 sciID)
{
    Uint16 temp = 0U;

    if(sciID < SCI_PORT_NUM)
    {
        temp = mySciPorts[sciID].pSci->SCIRXBUF.all;
    }
    else
    {
        temp = 0U;
    }

    return temp;
}

/* ***************************************************************** */
/**
 * 【说明】:SciReadBuff
 *
 * 从SCI口接收缓存读取数据到数组中。
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 * 【参数】:buff  ---- 接收数据保存数组首地址
 * 【参数】:len   ---- 从接收缓冲区读取的字节数
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciReadBuff
 *
 * 【功能描述】从SCI口接收缓存读取指定字节数到目标数组
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输入参数说明】buff  ---- 接收数据保存数组首地址
 * 【输入参数说明】len   ---- 从接收缓冲区读取的字节数
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciReadBuff(Uint16 sciID,Uint16 *buff,Uint8 len)
{
    Uint8 ii = 0U;

    if( ( sciID < SCI_PORT_NUM ) && ( NULL != buff ))
    {
        for( ii = 0U; ii < len ; ii++)
        {
            buff[ii] = mySciPorts[sciID].pSci->SCIRXBUF.all;
        }
    }
    else
    {
        /* no deal with */
    }
}

/* ***************************************************************** */
/**
 * 【说明】:SciSendChar
 *
 * 从SCI口发送一个字节
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 * 【参数】:data  ---- 待发送字节
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciSendChar
 *
 * 【功能描述】从SCI口发送一个字节，发送前判断发送缓冲区是否就绪
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输入参数说明】data  ---- 待发送字节
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciSendChar(Uint16 sciID,Uint8 data)
{
    if( sciID < SCI_PORT_NUM )
    {
        if(OK == SciIsTxReady(sciID))
        {
            mySciPorts[sciID].pSci->SCITXBUF = data;
        }
    }
}

/* ***************************************************************** */
/**
 * 【说明】:SciSendBuff
 *
 * 从SCI口发送一组数据，注意该函数会引入延时，具体时间由波特率和数据长度确定
 *
 * 【参数】:sciID ---- SCI口ID，可取值:SCI_A_ID SCI_B_ID SCI_C_ID
 * 【参数】:buff  ---- 待发送数据的数组首地址
 * 【参数】:len   ---- 待发送数组长度
 *
 * 【返回】:返回成功发送的字节数
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciSendBuff
 *
 * 【功能描述】从SCI口发送一组数据，等待发送缓冲区就绪，超时则跳过该字节
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输入参数说明】buff  ---- 待发送数据的数组首地址
 * 【输入参数说明】len   ---- 待发送数组长度
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】成功发送的字节数
 */
/* ***************************************************************** */
Uint8 SciSendBuff(Uint16 sciID,Uint8 *buff, Uint8 len)
{
    Uint8 ii = 0U,jj = 0U,flag = 0U;
    Uint8 delayCount = 0U,rData = 0U;

    /* 输入参数合法性判断 */
    if( (sciID >= SCI_PORT_NUM) || ( NULL == buff ) )
    {
        return rData;
    }

    /* 获取最大等待延时 */
    delayCount = mySciPorts[sciID].delay;

    for( ii = 0U; ii < len; ii++)
    {
        jj    = 0U;   /* 延时计数 */
        flag = 0U;   /* 发送标志 */

        while( (jj < delayCount) && ( 0U == flag) )
        {
            if( OK == SciIsTxReady(sciID))
            {
                mySciPorts[sciID].pSci->SCITXBUF = buff[ii];

                flag = 1U;

                rData = rData + 1U;
            }
            else
            {
                jj = jj + 1U;

                delayUs(1UL);
            }
        }
    }

    return rData;
}

/* ***************************************************************** */
/**
 * 【说明】:SciISRAck
 *
 * 清除SCI接口的接收中断应答标志
 *
 * 【参数】:sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SciISRAck
 *
 * 【功能描述】清除SCI接口的接收中断应答标志，包括FIFO中断信号和CPU PIE应答信号
 *
 * 【输入参数说明】sciID ---- SCI口ID，可取值：SCI_A_ID SCI_B_ID SCI_C_ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void SciISRAck(Uint8 sciID)
{
    if( sciID < SCI_PORT_NUM )
    {
        /* 清除FIFO中断信号 */
#if SCI_FIFO_EN
        mySciPorts[sciID].pSci->SCIFFRX.bit.RXFFINTCLR = 1U;
#endif

        /* 清除CPU中断应答信号 */
        if( (SCI_A_ID == sciID) || (SCI_B_ID == sciID) )
        {
            PieCtrlRegs.PIEACK.all = PIEACK_GROUP9;
        }
        else if( SCI_C_ID == sciID )
        {
            PieCtrlRegs.PIEACK.all = PIEACK_GROUP8;
        }
        else
        {
            /* 无操作 */
        }
    }
}

interrupt void ISR_SCIA_RXINT(void)
{
    static Uint16 IsrSciARxCount =0U;
    IsrSciARxCount++;
    PieCtrlRegs.PIEACK.all = PIEACK_GROUP9;
}
interrupt void ISR_SCIB_RXINT(void)
{
    static Uint16 IsrSciBRxCount =0U;
    IsrSciBRxCount++;
    PieCtrlRegs.PIEACK.all = PIEACK_GROUP9;
}
interrupt void ISR_SCIC_RXINT(void)
{
    static Uint16 IsrSciCRxCount =0U;
    IsrSciCRxCount++;
    PieCtrlRegs.PIEACK.all = PIEACK_GROUP8;
}
//====================================================
// END OF FILE
//====================================================
