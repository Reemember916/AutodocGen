/* 应用层控制模块 — 传感器检测与数据平均 */

#include "APP_Config.h"
#include "Common/Common.h"

/*
 * [函数名] CheckSensor
 * [功能说明] 检测指定传感器通道的状态，读取原始数据并校验有效范围。
 * [输入参数说明] sensor_id: 传感器通道号（0-7）; p_data: 传感器数据结构体指针
 * [输出参数说明] p_data: 更新后的传感器数据
 * [返回说明] 检测结果（0=正常，1=超范围，2=断线，3=通信超时）
 */
Uint16 CheckSensor(Uint16 sensor_id, SensorData_t *p_data)
{
    Uint16 l_status_u16 = 0U;
    Uint16 l_raw_value_u16 = 0U;
    
    if (sensor_id >= MAX_SENSOR_COUNT)
    {
        return 2U;
    }
    
    if (p_data == NULL)
    {
        return 2U;
    }
    
    /* 读取传感器原始值 */
    l_raw_value_u16 = ADC_ReadChannel(sensor_id);
    
    /* 检查传感器状态 */
    if (l_raw_value_u16 > 4000U)
    {
        l_status_u16 = 1U;
    }
    else if (l_raw_value_u16 < 100U)
    {
        l_status_u16 = 2U;
    }
    else
    {
        l_status_u16 = 0U;
    }
    
    p_data->status = l_status_u16;
    p_data->data[0] = l_raw_value_u16;
    
    return l_status_u16;
}

/*
 * [函数名] FdataAverage
 * [功能说明] 计算浮点数据缓冲区的平均值，支持可变长度。
 * [输入参数说明] p_buf: 浮点数据缓冲区; count: 数据个数
 * [输出参数说明] p_avg: 计算出的平均值
 * [返回说明] 无
 */
void FdataAverage(float32 *p_buf, Uint16 count, float32 *p_avg)
{
    Uint16 l_ii_u16 = 0U;
    float32 l_sum_f32 = 0.0f;
    float32 l_min_f32 = 0.0f;
    float32 l_max_f32 = 0.0f;
    
    if (p_buf == NULL || p_avg == NULL || count == 0U)
    {
        return;
    }
    
    l_min_f32 = p_buf[0];
    l_max_f32 = p_buf[0];
    
    for (l_ii_u16 = 0U; l_ii_u16 < count; l_ii_u16++)
    {
        l_sum_f32 = l_sum_f32 + p_buf[l_ii_u16];
        
        if (p_buf[l_ii_u16] < l_min_f32)
        {
            l_min_f32 = p_buf[l_ii_u16];
        }
        
        if (p_buf[l_ii_u16] > l_max_f32)
        {
            l_max_f32 = p_buf[l_ii_u16];
        }
    }
    
    *p_avg = l_sum_f32 / (float32)count;
}