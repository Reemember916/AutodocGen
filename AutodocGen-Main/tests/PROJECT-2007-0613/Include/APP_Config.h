/*
 * [函数中文名] 加油控制主流程
 * [功能描述] 根据加油指令启动或停止加油泵，监控油量变化率，超时或异常时自动切断燃油供给并上报故障码。
 * [输入参数说明]
 * - Valve_Status: [业务含义] 主副阀门的物理开关状态
 * [输出参数说明]
 * - p_Fuel_Rate: [业务含义] 燃油流量变化率输出指针
 */
extern uint16_t Control_Refuel_Process(uint16_t Valve_Status, uint16_t * p_Fuel_Rate);

/* USER CODE BEGIN: Control_Refuel_Process */
// 旧的死区算法: return 0;
static uint16_t OLD_DEAD_ZONE(uint16_t input) {
    if (input < 10) return 0;
    return input;
}
/* USER CODE END: Control_Refuel_Process */
