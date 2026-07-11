/* DSP GPIO 驱动 — 芯片引脚初始化与读写 */

#include "APP_Config.h"
#include "Common/Common.h"

/*
 * [函数名] GPIO_Init
 * [功能说明] 初始化 GPIO 引脚方向与初始电平，配置所有数字 I/O 通道。
 * [输入参数说明] 无
 * [输出参数说明] 无
 * [返回说明] 无
 */
void GPIO_Init(void)
{
    Uint16 l_index_u16 = 0U;
    
    /* 配置所有 GPIO 为输出模式 */
    for (l_index_u16 = 0U; l_index_u16 < 8U; l_index_u16++)
    {
        GpioCtrlRegs.GPADIR.bit.GPIO0 = 1U;
    }
    
    /* 初始化输出电平为低 */
    for (l_index_u16 = 0U; l_index_u16 < 8U; l_index_u16++)
    {
        GpioDataRegs.GPACLEAR.bit.GPIO0 = 1U;
    }
}

/*
 * [函数名] GPIO_ReadChannel
 * [功能说明] 读取指定 GPIO 通道的输入电平状态。
 * [输入参数说明] channel: 通道号（0-7）
 * [输出参数说明] 无
 * [返回说明] 通道电平状态（0=低电平，1=高电平）
 */
Uint16 GPIO_ReadChannel(Uint16 channel)
{
    Uint16 l_status_u16 = 0U;
    
    if (channel > 7U)
    {
        return 0U;
    }
    
    l_status_u16 = (Uint16)(GpioDataRegs.GPADAT.bit.GPIO0 & 0x01U);
    
    return l_status_u16;
}

/*
 * [函数名] GPIO_WriteChannel
 * [功能说明] 设置指定 GPIO 通道的输出电平。
 * [输入参数说明] channel: 通道号（0-7）; level: 输出电平（0或1）
 * [输出参数说明] 无
 * [返回说明] 操作结果（0=成功，1=失败）
 */
Uint16 GPIO_WriteChannel(Uint16 channel, Uint16 level)
{
    if (channel > 7U)
    {
        return 1U;
    }
    
    if (level == 0U)
    {
        GpioDataRegs.GPACLEAR.bit.GPIO0 = 1U;
    }
    else if (level == 1U)
    {
        GpioDataRegs.GPASET.bit.GPIO0 = 1U;
    }
    else
    {
        /* 无效电平值 */
        return 1U;
    }
    
    return 0U;
}