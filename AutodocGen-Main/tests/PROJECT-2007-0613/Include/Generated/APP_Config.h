#ifndef _APP_CONFIG_H_
#define _APP_CONFIG_H_

/* 应用层配置头文件 — 燃油控制系统顶层接口 */

/* 燃油泵通道数 */
#define FUEL_PUMP_CHANNEL_COUNT 4
/* 加油超时时间（毫秒） */
#define REFUEL_TIMEOUT_MS 30000

/*
 * [函数中文名] 加油控制主流程
 * [功能描述] 根据加油指令启动或停止加油泵，监控油量变化率，超时或异常时自动切断燃油供给并上报故障码。
 * [输入参数说明] u16_refuel_cmd: 加油指令字（0x01=启动加油，0x00=停止加油）; u16_current_fuel_qty: 当前燃油量（kg）; u16_target_fuel_qty: 目标加油量（kg）
 * [输出参数说明] p_error_code: 故障码输出指针（0=正常，非0=故障编码）
 */
extern Uint16 Control_Refuel_Process(Uint16 u16_refuel_cmd, Uint16 u16_current_fuel_qty, Uint16 u16_target_fuel_qty, Uint16 * p_error_code);

#endif /* _APP_CONFIG_H_ */
