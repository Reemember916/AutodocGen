/* 应用层主控模块 — 系统初始化与任务调度 */

#include "APP_Config.h"
#include "Common/Common.h"

/*
 * [函数名] InitSystem
 * [功能说明] 系统上电初始化：配置时钟、外设、全局变量，完成后进入主循环。
 * [输入参数说明] 无
 * [输出参数说明] 无
 * [返回说明] 无
 */
void InitSystem(void)
{
    Uint16 l_index_u16 = 0U;
    
    /* 系统时钟配置 */
    SysCtrlRegs.PLLCR.bit.DIV = 0x000AU;
    
    /* 初始化全局变量 */
    for (l_index_u16 = 0U; l_index_u16 < MAX_SENSOR_COUNT; l_index_u16++)
    {
        g_sensor_data[l_index_u16].status = 0U;
        g_sensor_data[l_index_u16].error_code = 0U;
    }
    
    /* 初始化通信接口 */
    SciInit();
    SpiInit();
}

/*
 * [函数名] TimeCountInit
 * [功能说明] 初始化任务时间计数器，清零所有计时变量。
 * [输入参数说明] 无
 * [输出参数说明] 无
 * [返回说明] 无
 */
void TimeCountInit(void)
{
    Uint16 l_index_u16 = 0U;
    
    /* 清零所有任务计数器 */
    for (l_index_u16 = 0U; l_index_u16 < MAX_SENSOR_COUNT; l_index_u16++)
    {
        g_task_time[l_index_u16] = (Uint32)0U;
    }
    
    g_sync_time = (Uint32)(TASK_PERIOD_MS * 1000U);
}