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
 *        文件名称:    DSP_GPIO.c
 *
 *        功能说明:   文件功能说明
 *
 *
 *        文件日期:   REDACTED
 *
 *
 *        程序版本:  V1.03
 *
 *********************************************************************************/

/**************************************************************/
/*
 * 全局变量
 */
/**************************************************************/

#include "Global.h"
#include "DSP_GPIO.h"


void GPIOIntConf(struct g_GPIOExIntConfData_t * l_ExIntConfTab_t);

void GpioOutConf(struct g_GPIOOut_t *l_GpioOutTab_t);
void GpioInConf(struct g_GPIOIn_t *l_GpioInTab_t);

/* GPIO输入输出配置 */
struct g_GPIOOut_t s_MyGPIOOutTab_t[] = GPIO_OUT_TAB;       //GPIO输出引脚配置数组
struct g_GPIOIn_t  s_MyGpioInTab_t[]  = GPIO_IN_TAB;        //GPIO输入引脚配置数组

//GPIO外部引脚中断配置数组
struct g_GPIOExIntConfData_t s_MyExIntConfTab_t[GPIO_EXINT_MAX] = GPIO_EXINT_CONF_TAB;

/* ***************************************************************** */
/**
 *    [函数名]			GpioIoFuncConf
 *
 *    [功能描述]			配置某引脚功能为普通IO口
 *    [输入参数说明]		l_GpioNum_u8--引脚序号，范围GPIO_NUM_0 到 GPIO_NUM_87
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GpioIoFuncConf(Uint8 l_GpioNum_u8)
{
    Uint8  l_PortNum_u8 = 0U;
    Uint8  l_BitNum_u8 = 0U;
    Uint32 l_TempData_u32 = 0x0UL;

    Uint32 l_BaseAddr_u32 = GPIO_MUX_REG_BASE;

    l_PortNum_u8 = l_GpioNum_u8 / GPIO_MAX;
    l_BitNum_u8 = l_GpioNum_u8 % GPIO_MAX;

    if( l_BitNum_u8 < 16U )
    {
        l_BaseAddr_u32 += (0x10UL * l_PortNum_u8);
        l_TempData_u32 = ~(0x03UL << (l_BitNum_u8 * 2U));
    }
    else
    {
        l_BaseAddr_u32 += (0x10UL * l_PortNum_u8) + 0x02UL;
        l_TempData_u32 = ~(0x03UL << ((l_BitNum_u8 - 16U) * 2U));
    }

    EALLOW;
    (*(volatile Uint32 *)(l_BaseAddr_u32)) &= l_TempData_u32;
    EDIS;
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOInit
 *
 *    [功能描述]			GPIO引脚初始化，主要实现GPIO引脚的输入、输出配置，以及地址数据总线的相关引脚的功能配置
 *    [输入参数说明]		NONE
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GPIOInit(void)
{
    EALLOW;

    /*
     * GPIOA --- GPIO0__GPIO15
     *
     * |  GPIO0  ---> GPIO   |   GPIO1  ---> GPIO |
     * |  GPIO2  ---> GPIO   |   GPIO3  ---> GPIO |
     * |  GPIO4  ---> GPIO   |   GPIO5  ---> GPIO |
     * |  GPIO6  ---> GPIO   |   GPIO7  ---> GPIO |
     * |  GPIO8  ---> GPIO   |   GPIO9  ---> GPIO |
     * |  GPIO10 ---> GPIO   |   GPIO11 ---> GPIO |
     * |  GPIO12 ---> GPIO   |   GPIO13 ---> GPIO |
     * |  GPIO14 ---> GPIO   |   GPIO15 ---> GPIO |
     */
    GpioCtrlRegs.GPAMUX1.all = 0UL;

    /*
     * GPIOA --- GPIO16__GPIO31
     *
     * |  GPIO16 ---> GPIO   |   GPIO17 ---> GPIO |
     * |  GPIO18 ---> GPIO   |   GPIO19 ---> GPIO |
     * |  GPIO20 ---> GPIO   |   GPIO21 ---> GPIO |
     * |  GPIO22 ---> GPIO   |   GPIO23 ---> GPIO |
     * |  GPIO24 ---> GPIO   |   GPIO25 ---> GPIO |
     * |  GPIO26 ---> GPIO   |   GPIO27 ---> GPIO |
     * |  GPIO28 ---> XZCS6  |   GPIO29 ---> XA19 |
     * |  GPIO30 ---> XA18   |   GPIO31 ---> XA17 |
     */
    GpioCtrlRegs.GPAMUX2.all = 0xFF000000UL;

    /*
     * GPIOB --- GPIO32__GPIO47
     *
     * |  GPIO32 ---> GPIO   |   GPIO33 ---> GPIO |
     * |  GPIO34 ---> XREADY |   GPIO35 ---> XR/W |
     * |  GPIO36 ---> XCS0   |   GPIO37 ---> XCS7 |
     * |  GPIO38 ---> XWE0   |   GPIO39 ---> XA16 |
     * |  GPIO40 ---> XA0    |   GPIO41 ---> XA1  |
     * |  GPIO42 ---> XA2    |   GPIO43 ---> XA3  |
     * |  GPIO44 ---> XA4    |   GPIO45 ---> XA5  |
     * |  GPIO46 ---> XA6    |   GPIO47 ---> XA7  |
     */
    GpioCtrlRegs.GPBMUX1.all = 0xFFFFFFF0UL;

    /*
     * GPIOB --- GPIO48__GPIO63
     *
     * |  GPIO48 ---> GPIO   |   GPIO49 ---> GPIO |
     * |  GPIO50 ---> GPIO   |   GPIO51 ---> GPIO |
     * |  GPIO52 ---> GPIO   |   GPIO53 ---> GPIO |
     * |  GPIO54 ---> GPIO   |   GPIO55 ---> GPIO |
     * |  GPIO56 ---> GPIO   |   GPIO57 ---> GPIO |
     * |  GPIO58 ---> GPIO   |   GPIO59 ---> GPIO |
     * |  GPIO60 ---> GPIO   |   GPIO61 ---> GPIO |
     * |  GPIO62 ---> GPIO   |   GPIO63 ---> GPIO |
     */
    GpioCtrlRegs.GPBMUX2.all = 0UL;

    /*
     * GPIOC --- GPIO64__GPIO79
     *
     * |  GPIO64 ---> XD15  |   GPIO65 ---> XD14 |
     * |  GPIO66 ---> XD13  |   GPIO67 ---> XD12 |
     * |  GPIO68 ---> XD11  |   GPIO69 ---> XD10 |
     * |  GPIO70 ---> XD9   |   GPIO71 ---> XD8  |
     * |  GPIO72 ---> XD7   |   GPIO73 ---> XD6  |
     * |  GPIO74 ---> XD5   |   GPIO75 ---> XD4  |
     * |  GPIO76 ---> XD3   |   GPIO77 ---> XD2  |
     * |  GPIO78 ---> XD1   |   GPIO79 ---> XD0  |
     */
    GpioCtrlRegs.GPCMUX1.all = 0xFFFFFFFFUL;

    /*
     * GPIOC --- GPIO80__GPIO87
     *
     * |  GPIO80 ---> XA8   |   GPIO81 ---> XA9  |
     * |  GPIO82 ---> XA10  |   GPIO83 ---> XA11 |
     * |  GPIO84 ---> XA12  |   GPIO85 ---> XA13 |
     * |  GPIO86 ---> XA14  |   GPIO87 ---> XA15 |
     */
    GpioCtrlRegs.GPCMUX2.all = 0x0000FFFFUL;

    /* 默认GPA口所有引脚的上拉使能 */
    GpioCtrlRegs.GPAPUD.all = 0UL;

    EDIS;

    /* 配置GPIO输出引脚 */
    GpioOutConf(s_MyGPIOOutTab_t);

    /* 配置GPIO输入引脚 */
    GpioInConf(s_MyGpioInTab_t);

    /* 外部引脚中断配置 */
    GPIOIntConf(s_MyExIntConfTab_t);
}

/* ***************************************************************** */
/**
 *    [函数名]			GpioOutConf
 *
 *    [功能描述]			GPIO输出引脚配置，所有引脚都是先设置初值，然后再配置为输出
 *    [输入参数说明]		l_GpioOutTab_t---- GPIO输出引脚配置数组
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GpioOutConf(struct g_GPIOOut_t *l_GpioOutTab_t)
{
    Uint8 l_ii_u8 = 0U;
    Uint8 l_PortNum_u8 = 0U;
    Uint8 l_BitNum_u8 = 0U;
    Uint32 l_TempData_u32 = 0UL;

    /* 遍历所有输出引脚配置数组 */
    while( GPIO_NUM_NULL != l_GpioOutTab_t[l_ii_u8].g_GPIONum_u32 )
    {
        /* 标识引脚端口号和位号 */
        l_PortNum_u8 = l_GpioOutTab_t[l_ii_u8].g_GPIONum_u32 / 32;
        l_BitNum_u8 = l_GpioOutTab_t[l_ii_u8].g_GPIONum_u32 % 32;

        l_TempData_u32 = (0x01UL << l_BitNum_u8);

        /* 配置为IO功能 */
        GpioIoFuncConf(l_GpioOutTab_t[l_ii_u8].g_GPIONum_u32);

        /* 先设置初值 */
        if( GPIO_SET == l_GpioOutTab_t[l_ii_u8].g_GPIOInitValue_u8)
        {
            *((volatile Uint32 *)(GPIO_SET_REG_BASE + (0x08 * l_PortNum_u8))) = l_TempData_u32;
        }
        else
        {
            *((volatile Uint32 *)(GPIO_CLEAR_REG_BASE + (0x08 * l_PortNum_u8))) = l_TempData_u32;
        }

        EALLOW;
        /* 配置为输出引脚 */
        *((volatile Uint32 *)(GPIO_DIR_REG_BASE + (0x10 * l_PortNum_u8))) |= l_TempData_u32;

        EDIS;

        l_ii_u8++;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			GpioInConf
 *
 *    [功能描述]			GPIO输入引脚配置，以及内部上拉配置
 *    [输入参数说明]		l_GpioInTab_t---- GPIO输入引脚配置数组
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GpioInConf(struct g_GPIOIn_t *l_GpioInTab_t)
{
    Uint8 l_ii_u8 = 0U;
    Uint8 l_PortNum_u8 = 0U;
    Uint8 l_BitNum_u8 = 0U;
    Uint32 l_TempData_u32 = 0UL;

    /* 遍历所有输入引脚数组 */
    while( GPIO_NUM_NULL != l_GpioInTab_t[l_ii_u8].g_GPIONum_u32 )
    {
        /* 标识引脚端口号和位号 */
        l_PortNum_u8 = l_GpioInTab_t[l_ii_u8].g_GPIONum_u32 / 32U;
        l_BitNum_u8 = l_GpioInTab_t[l_ii_u8].g_GPIONum_u32 % 32U;

        l_TempData_u32 = ~(0x01UL << l_BitNum_u8);

        EALLOW;

        /* 处理引脚复用功能 */
        GpioIoFuncConf(l_GpioInTab_t[l_ii_u8].g_GPIONum_u32);

        /* 配置引脚为输入 */
        *((volatile Uint32 *)(GPIO_DIR_REG_BASE + (0x10 * l_PortNum_u8))) &= l_TempData_u32;

        /* 配置引脚上拉电阻状态 */
        if( GPIO_PULL_UP_EN == l_GpioInTab_t[l_ii_u8].g_GPIOPullUpValue_u8 )
        {
            *((volatile Uint32 *)(GPIO_PUD_REG_BASE + (0x10 * l_PortNum_u8))) &= l_TempData_u32;
        }
        else
        {
            *((volatile Uint32 *)(GPIO_PUD_REG_BASE + (0x10 * l_PortNum_u8))) |= (~l_TempData_u32);
        }

        EDIS;

        l_ii_u8++;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOSetNum
 *
 *    [功能描述]			对单个GPIO引脚进行置位操作
 *    [输入参数说明]		l_GpioNum_u8---- 引脚序号，GPIO_NUM_0 到 GPIO_NUM_87
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GPIOSetNum(Uint8 l_GpioNum_u8)
{
    Uint8 l_GpioPort_u8 = 0U;
    Uint32 l_GpioBit_u32 = 0x01UL;

    /* 依据GPIO引脚序号，计算相应的引脚端口号和位号 */
    l_GpioPort_u8 = (l_GpioNum_u8 / GPIO_MAX);
    l_GpioBit_u32 = 0x01UL << (l_GpioNum_u8 % GPIO_MAX);

    GPIOSet(l_GpioPort_u8,l_GpioBit_u32);
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOSet
 *
 *    [功能描述]			对一个端口的一组引脚进行置位操作
 *    [输入参数说明]		l_GpioPort_u8---- GPIO端口，可以为GPIO_PortA，GPIO_PortA，GPIO_PortC
 *                      l_GpioBit_u32---- GPIO一组引脚
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GPIOSet(Uint8 l_GpioPort_u8, Uint32 l_GpioBit_u32)
{
    /* GPIO端口A操作 */
    if( GPIO_PortA == l_GpioPort_u8 )
    {
        GpioDataRegs.GPASET.all = l_GpioBit_u32;
    }

    /* GPIO端口B操作 */
    else if(GPIO_PortB == l_GpioPort_u8)
    {
        GpioDataRegs.GPBSET.all = l_GpioBit_u32;
    }

    /* GPIO端口C操作 */
    else if(GPIO_PortC == l_GpioPort_u8)
    {
        GpioDataRegs.GPCSET.all = l_GpioBit_u32;
    }
    else
    {
        /* no deal with */;
    }

}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOClearNum
 *
 *    [功能描述]			对单个引脚进行清零操作
 *    [输入参数说明]		l_GpioNum_u8---- 引脚序号，GPIO_NUM_0 到 GPIO_NUM_87
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GPIOClearNum(Uint8 l_GpioNum_u8)
{
    Uint8 l_GpioPort_u8 = 0U;
    Uint32 l_GpioBit_u32 = 0x01UL;

    /* 依据GPIO引脚序号，计算相应的引脚端口号和位号 */
    l_GpioPort_u8 = (l_GpioNum_u8 / GPIO_MAX);
    l_GpioBit_u32 = 0x01UL << (l_GpioNum_u8 % GPIO_MAX);

    GPIOClear(l_GpioPort_u8,l_GpioBit_u32);
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOClear
 *
 *    [功能描述]			对某个GPIO端口一组引脚进行清零操作
 *    [输入参数说明]		l_GpioPort_u8---- GPIO端口，可以为GPIO_PortA，GPIO_PortA，GPIO_PortC
 *                      l_GpioBit_u32---- GPIO一组引脚
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GPIOClear(Uint8 l_GpioPort_u8, Uint32 l_GpioBit_u32)
{
    if( GPIO_PortA == l_GpioPort_u8 )
    {
        GpioDataRegs.GPACLEAR.all = l_GpioBit_u32;
    }
    else if(GPIO_PortB == l_GpioPort_u8)
    {
        GpioDataRegs.GPBCLEAR.all = l_GpioBit_u32;
    }
    else if(GPIO_PortC == l_GpioPort_u8)
    {
        GpioDataRegs.GPCCLEAR.all = l_GpioBit_u32;
    }
    else
    {
        /* no deal with */;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOToggleNum
 *
 *    [功能描述]			实现单个引脚的翻转
 *    [输入参数说明]		l_GpioNum_u8---- 引脚序号，GPIO_NUM_0 到 GPIO_NUM_87
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GPIOToggleNum(Uint8 l_GpioNum_u8)
{
    Uint8 l_GpioPort_u8 = 0U;
    Uint32 l_GpioBit_u32 = 0x01UL;

    /* 依据GPIO引脚序号，计算相应的引脚端口号和位号 */
    l_GpioPort_u8 = (l_GpioNum_u8 / GPIO_MAX);
    l_GpioBit_u32 = 0x01UL << (l_GpioNum_u8 % GPIO_MAX);

    GPIOToggle(l_GpioPort_u8,l_GpioBit_u32);
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOToggle
 *
 *    [功能描述]			将端口内的引脚电平翻转，可以实现1--32个引脚电平同时翻转
 *    [输入参数说明]		l_GpioPort_u8---- GPIO端口，可以为GPIO_PortA，GPIO_PortA，GPIO_PortC
 *                      l_GpioBit_u32---- GPIO一组引脚，可以为：GPIO_BIT_0 ---- GPIO_BIT_31 之间一个或多个值的组合
 *    [输出参数说明]		NONE
 *    [其他说明]          NOTE:GpioBit不是引脚序号
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GPIOToggle(Uint8 l_GpioPort_u8, Uint32 l_GpioBit_u32)
{
    if( GPIO_PortA == l_GpioPort_u8)
    {
        GpioDataRegs.GPATOGGLE.all = l_GpioBit_u32;
    }
    else if(GPIO_PortB == l_GpioPort_u8)
    {
        GpioDataRegs.GPBTOGGLE.all = l_GpioBit_u32;
    }
    else if(GPIO_PortC == l_GpioPort_u8)
    {
        GpioDataRegs.GPCTOGGLE.all = l_GpioBit_u32;
    }
    else
    {
        /* no deal with */;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOWrite
 *
 *    [功能描述]			给指定端口所有引脚赋值
 *    [输入参数说明]		l_GpioPort_u8---- GPIO端口，可以为GPIO_PortA，GPIO_PortA，GPIO_PortC
 *                      l_data_u32---- 待赋值数据
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GPIOWrite(Uint8 l_GpioPort_u8, Uint32 l_data_u32)
{
    if( GPIO_PortA == l_GpioPort_u8)
    {
        GpioDataRegs.GPADAT.all = l_data_u32;
    }
    else if(GPIO_PortB == l_GpioPort_u8)
    {
        GpioDataRegs.GPBDAT.all = l_data_u32;
    }
    else if(GPIO_PortC == l_GpioPort_u8)
    {
        GpioDataRegs.GPCDAT.all = l_data_u32;
    }
    else
    {
        /* no deal with */;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIORead
 *
 *    [功能描述]			读取指定端口所有引脚的电平状态
 *    [输入参数说明]		l_GpioPort_u8---- GPIO端口，可以为GPIO_PortA，GPIO_PortA，GPIO_PortC
 *    [输出参数说明]		该端口32个引脚的电平状态
 *    [其他说明]
 *    [返回]				该端口32个引脚的电平状态
 */
/* ***************************************************************** */
Uint32 GPIORead(Uint8 l_GpioPort_u8)
{
    if( GPIO_PortA == l_GpioPort_u8)
    {
        return GpioDataRegs.GPADAT.all;
    }
    else if(GPIO_PortB == l_GpioPort_u8)
    {
        return GpioDataRegs.GPBDAT.all;
    }
    else if(GPIO_PortC == l_GpioPort_u8)
    {
        return GpioDataRegs.GPCDAT.all;
    }
    else
    {
        return 0;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOReadBitNum
 *
 *    [功能描述]			依据引脚序号，读取引脚上的电平状态
 *    [输入参数说明]		l_GpioPortNum_u8---- 引脚序号，可以为GPIO_NUM_0 ---- GPIO_NUM_87 中的任意一个值
 *    [输出参数说明]		GPIO_SET   ---- 引脚高电平
 *                      GPIO_CLEAR ---- 引脚低电平
 *    [其他说明]
 *    [返回]				GPIO_SET   ---- 引脚高电平
 *                      GPIO_CLEAR ---- 引脚低电平
 */
/* ***************************************************************** */
Uint8 GPIOReadBitNum(Uint8 l_GpioPortNum_u8)
{
    Uint8 l_GpioPort_u8 = 0U;
    Uint32 l_GpioBit_u32 = 0x01UL;

    /* 依据GPIO引脚序号，计算相应的引脚端口号和位号 */
    l_GpioPort_u8 = (l_GpioPortNum_u8 / GPIO_MAX);
    l_GpioBit_u32 = 0x01UL << (l_GpioPortNum_u8 % GPIO_MAX);

    return GPIOReadBit(l_GpioPort_u8,l_GpioBit_u32);
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOReadBit
 *
 *    [功能描述]			读取指定端口的某个引脚的电平状态，每次只能读取一个引脚
 *    [输入参数说明]		l_GpioPort_u8---- 引脚端口，可以为：GPIO_PortA 或 GPIO_PortB
 *                      l_GpioBit_u32---- 引脚，可以为：GPIO_BIT_0 ---- GPIO_BIT_31 之间任意一个值
 *    [输出参数说明]		GPIO_SET   ---- 引脚高电平
 *                      GPIO_CLEAR ---- 引脚低电平
 *    [其他说明]          NOTE:GpioBit不是引脚序号
 *    [返回]				GPIO_SET   ---- 引脚高电平
 *                      GPIO_CLEAR ---- 引脚低电平
 */
/* ***************************************************************** */
Uint8 GPIOReadBit(Uint8 l_GpioPort_u8,Uint32 l_GpioBit_u32)
{
    Uint32 l_data_u32 = 0U;

    /* 获取引脚端口数据 */
    if( GPIO_PortA == l_GpioPort_u8)
    {
        l_data_u32 = GpioDataRegs.GPADAT.all;
    }
    else if(GPIO_PortB == l_GpioPort_u8)
    {
        l_data_u32 = GpioDataRegs.GPBDAT.all;
    }
    else if(GPIO_PortC == l_GpioPort_u8)
    {
        l_data_u32 = GpioDataRegs.GPCDAT.all;
    }
    else
    {
        /* no deal with */;
    }

    /* 判断引脚电平状态 */
    if( (l_data_u32 & l_GpioBit_u32) != 0U)
    {
        return GPIO_SET;
    }
    else
    {
        return GPIO_CLEAR;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]			GPIOIntConf
 *
 *    [功能描述]			配置GPIO引脚外部中断
 *    [输入参数说明]		l_ExIntConfTab_t---- GPIO外部引脚中断配置信息表
 *    [输出参数说明]		NONE
 *    [其他说明]
 *    [返回]				NONE
 */
/* ***************************************************************** */
void GPIOIntConf(struct g_GPIOExIntConfData_t * l_ExIntConfTab_t)
{
    EALLOW;

    /* XNMI外部中断配置 */
    if( ON == l_ExIntConfTab_t[0].g_Enable_u8)
    {
        GpioIntRegs.GPIOXNMISEL.all = (l_ExIntConfTab_t[0U].g_GpioNum_u8 & 0x1F);
        XIntruptRegs.XNMICR.bit.ENABLE = ON;
        XIntruptRegs.XNMICR.bit.SELECT = 0U;     //不连接到XINT13
        XIntruptRegs.XNMICR.bit.POLARITY = (l_ExIntConfTab_t[0U].g_Polarity_u8 & 0x3U);

        //注册中断向量，NMI中断不需要使能
        PieVectTable.XNMI = &NMI_ISR;
    }
    else
    {
        XIntruptRegs.XNMICR.bit.ENABLE = OFF;
    }

    /* XINT1中断配置 */
    if( ON == l_ExIntConfTab_t[1].g_Enable_u8)
    {
        GpioIntRegs.GPIOXINT1SEL.all = (l_ExIntConfTab_t[1U].g_GpioNum_u8 & 0x1F);
        XIntruptRegs.XINT1CR.bit.ENABLE = ON;
        XIntruptRegs.XINT1CR.bit.POLARITY = (l_ExIntConfTab_t[1U].g_Polarity_u8 & 0x3U);

        /* 注册中断向量，并使能中断 */
        PieVectTable.XINT1 = &XINT1_ISR;
        PieCtrlRegs.PIEIER1.bit.INTx4 = 1U;
        IER |= M_INT1;
    }
    else
    {
        XIntruptRegs.XINT1CR.bit.ENABLE = OFF;
    }

    /* XINT2中断配置 */
    if( ON == l_ExIntConfTab_t[2].g_Enable_u8)
    {
        GpioIntRegs.GPIOXINT2SEL.all = (l_ExIntConfTab_t[2U].g_GpioNum_u8 & 0x1F);
        XIntruptRegs.XINT2CR.bit.ENABLE = ON;
        XIntruptRegs.XINT2CR.bit.POLARITY = (l_ExIntConfTab_t[2U].g_Polarity_u8 & 0x3U);

        /* 注册中断向量，并使能中断 */
        PieVectTable.XINT2 = &XINT2_ISR;
        PieCtrlRegs.PIEIER1.bit.INTx5 = 1U;
        IER |= M_INT1;
    }
    else
    {
        XIntruptRegs.XINT2CR.bit.ENABLE = OFF;
    }

    /* XINT3中断配置 */
    if( ON == l_ExIntConfTab_t[3].g_Enable_u8)
    {
        GpioIntRegs.GPIOXINT3SEL.all = (l_ExIntConfTab_t[3U].g_GpioNum_u8 & 0x1F);
        XIntruptRegs.XINT3CR.bit.ENABLE = ON;
        XIntruptRegs.XINT3CR.bit.POLARITY = (l_ExIntConfTab_t[3U].g_Polarity_u8 & 0x3U);

        /* 注册中断向量，并使能中断 */
        PieVectTable.XINT3 = &XINT3_ISR;
        PieCtrlRegs.PIEIER12.bit.INTx1 = 1U;
        IER |= M_INT12;
    }
    else
    {
        XIntruptRegs.XINT3CR.bit.ENABLE = OFF;
    }

    /* XINT4中断配置 */
    if( ON == l_ExIntConfTab_t[4].g_Enable_u8)
    {
        GpioIntRegs.GPIOXINT4SEL.all = (l_ExIntConfTab_t[4U].g_GpioNum_u8 & 0x1FU);
        XIntruptRegs.XINT4CR.bit.ENABLE = ON;
        XIntruptRegs.XINT4CR.bit.POLARITY = (l_ExIntConfTab_t[4U].g_Polarity_u8 & 0x3U);

        /* 注册中断向量，并使能中断 */
        PieVectTable.XINT4 = &XINT4_ISR;
        PieCtrlRegs.PIEIER12.bit.INTx2 = 1;
        IER |= M_INT12;
    }
    else
    {
        XIntruptRegs.XINT4CR.bit.ENABLE = OFF;
    }

    /* XINT5中断配置 */
    if( ON == l_ExIntConfTab_t[5].g_Enable_u8)
    {
        GpioIntRegs.GPIOXINT5SEL.all = (l_ExIntConfTab_t[5U].g_GpioNum_u8 & 0x1FU);
        XIntruptRegs.XINT5CR.bit.ENABLE = ON;
        XIntruptRegs.XINT5CR.bit.POLARITY = (l_ExIntConfTab_t[5U].g_Polarity_u8 & 0x3U);

        /* 注册中断向量，并使能中断 */
        PieVectTable.XINT5 = &XINT5_ISR;
        PieCtrlRegs.PIEIER12.bit.INTx3 = 1U;
        IER |= M_INT12;
    }
    else
    {
        XIntruptRegs.XINT5CR.bit.ENABLE = OFF;
    }

    /* XINT6中断配置 */
    if( ON == l_ExIntConfTab_t[6U].g_Enable_u8)
    {
        GpioIntRegs.GPIOXINT6SEL.all = (l_ExIntConfTab_t[6U].g_GpioNum_u8 & 0x1FU);
        XIntruptRegs.XINT6CR.bit.ENABLE = ON;
        XIntruptRegs.XINT6CR.bit.POLARITY = (l_ExIntConfTab_t[6U].g_Polarity_u8 & 0x3U);

        /* 注册中断向量，并使能中断 */
        PieVectTable.XINT6 = &XINT6_ISR;
        PieCtrlRegs.PIEIER12.bit.INTx4 = 1U;
        IER |= M_INT12;
    }
    else
    {
        XIntruptRegs.XINT6CR.bit.ENABLE = OFF;
    }

    /* XINT7中断配置 */
    if( ON == l_ExIntConfTab_t[7U].g_Enable_u8)
    {
        GpioIntRegs.GPIOXINT7SEL.all = (l_ExIntConfTab_t[7U].g_GpioNum_u8 & 0x1FU);
        XIntruptRegs.XINT7CR.bit.ENABLE = ON;
        XIntruptRegs.XINT7CR.bit.POLARITY = (l_ExIntConfTab_t[7U].g_Polarity_u8 & 0x3U);

        /* 注册中断向量，并使能中断 */
        PieVectTable.XINT7 = &XINT7_ISR;
        PieCtrlRegs.PIEIER12.bit.INTx5 = 1U;
        IER |= M_INT12;
    }
    else
    {
        XIntruptRegs.XINT7CR.bit.ENABLE = OFF;
    }

    EDIS;
}

//===============================================================
//文件结束
//===============================================================

