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
 * 文件名称:    cpuTest.h
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V1.00
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 *
 *********************************************************************************/
#ifndef CPUTEST_H

#define CPUTEST_H

#define CPUTEST_OK                  (0)           //CPU测试通过

#define CPUTEST_ARITH_OP_OK         (0U)           //CPU测试，算术运算操作通过
#define CPUTEST_ARITH_OP_ERR        (0x01U << 0)   //CPU测试，算术运算操作未通过

#define CPUTEST_FLOAT_OP_OK         (0)           //CPU测试，浮点数操作通过
#define CPUTEST_FLOAT_OP_ERR        (0x01U << 1)   //CPU测试，浮点数操作未通过

#define CPUTEST_CON_LOGIC_OP_OK     (0U)           //CPU测试，条件逻辑运算通过
#define CPUTEST_CON_LOGIC_OP_ERR    (0x01U << 2)   //CPU测试，条件逻辑运算未通过

#define CPUTEST_BIT_LOGIC_OP_OK     (0U)           //CPU测试，位运算符操作通过
#define CPUTEST_BIT_LOGIC_OP_ERR    (0x01U << 3)   //CPU测试，位运算符操作未通过

#define CPUTEST_ADDR_OP_OK          (0U)           //CPU测试，地址操作通过
#define CPUTEST_ADDR_OP_ERR         (0x01U << 4)   //CPU测试，地址操作未通过

#define CPUTEST_ABSOLUTE_OP_OK      (0U)           //CPU测试，绝对值测试通过
#define CPUTEST_ABSOLUTE_OP_ERR     (0x01U << 5)   //CPU测试，绝对值测试未通过

/* ***************************************************************** */
/**
 * 【说明】:外部调用接口声明
 */
/* ***************************************************************** */
extern unsigned int cpuTest(void);
//extern unsigned int arithMeticOpTest();
//extern unsigned int floatOpTest();
//extern unsigned int conditionOpTest();
//extern unsigned int bitLogicOpTest();
//extern unsigned int addrOpTest();

/* ***************************************************************** */
/* cpuTest.c 私有宏定义 */
/* ***************************************************************** */
#define CONDITION_OK            (1U)
#define CONDITION_ERROR         (0U)
#define FLOAT_OP_VALUE          (3.7684F)        /* 浮点数操作测试数据 */
#define FLOAT_THREASH_VALUE     (0.00001F)       /* 浮点数操作测试阀值 */
#define ARITHMETIC_TEST_VALUE   (100U)           /* 算术运算操作数 */

#endif /* end of include guard: CPUTEST_H */
