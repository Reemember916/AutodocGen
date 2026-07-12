/*
 * Control_Module.h — 控制模块接口头文件
 */

/*
 * [函数中文名] 控制处理流程
 * [功能描述] 根据输入标志位执行控制逻辑，并通过指针参数输出结果
 * [输入参数说明]
 * - flag: [业务含义] 控制标志位（低 4 位为指令编码，高 4 位为优先级）
 * [输出参数说明]
 * - p_New_Fault: [业务含义] 新增故障码输出指针
 */
extern uint16_t Control_Process(uint16_t flag, uint16_t * p_New_Fault);
