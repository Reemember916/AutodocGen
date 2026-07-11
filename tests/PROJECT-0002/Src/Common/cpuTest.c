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
 * 文件名称:    cpuTest.c
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V1.00
 *
 **********************************************************************************
 *
 * 功能说明:
 *
 *  本功能模块为独立的CPU检测模块，实现对主CPU（TMS320F28335）的检测，具体检测功能如下：
 *
 *  1. 算术运算检测
 *  2. 浮点数运算检测
 *  3. 条件运算符检测
 *  4. 逻辑位运算检测
 *  5. 地址访问检测
 *
 *********************************************************************************/

//#include <math.h>
#include "cpuTest.h"

/* ***************************************************************** */
/**
 * 【说明】:arithMeticOpTest
 *
 * CPU算术运算测试，进行加、减、乘、除操作测试。
 *
 * 【返回】:
 *          测试通过 ==> CPUTEST_ARITH_OP_OK
 *        测试未通过 ==> CPUTEST_ARITH_OP_ERR
 */
/* ***************************************************************** */
unsigned int arithMeticOpTest(void)
{
    unsigned int tdata = ARITHMETIC_TEST_VALUE ;

    tdata++;
    tdata = tdata * 5;
    tdata = tdata + 0x1234;
    tdata = tdata - 0x1234;
    tdata = tdata / 5;
    tdata--;

    if( tdata != ARITHMETIC_TEST_VALUE )
    {
        return CPUTEST_ARITH_OP_ERR;
    }
    else
    {
        return CPUTEST_ARITH_OP_OK;
    }
}
/* ***************************************************************** */
/**
 * 【说明】:floatOpTest
 *
 * CPU浮点数运算操作，对浮点数进行加、减、乘、除操作测试。
 *
 * 【返回】:
 *        测试通过 ==> CPUTEST_FLOAT_OP_OK
 *      测试未通过 ==> CPUTEST_FLOAT_OP_ERR
 */
/* ***************************************************************** */
unsigned int floatOpTest(void)
{
    float tfdata = FLOAT_OP_VALUE;

    tfdata += 6.7532F;
    tfdata *= 1.82F;
    tfdata /= 1.82F;
    tfdata -= 6.7532F;

    if( fabs(tfdata - FLOAT_OP_VALUE ) > FLOAT_THREASH_VALUE)
    {
        return CPUTEST_FLOAT_OP_ERR;
    }
    else
    {
        return CPUTEST_CON_LOGIC_OP_OK;
    }
}
/* ***************************************************************** */
/**
 * 【说明】:conditionOpTest
 *
 * CPU测试条件运算符操作,具体操作包括：条件或、条件与、条件非。
 *
 * 【返回】:
 *        测试通过 ==> CPUTEST_CON_LOGIC_OP_OK
 *      测试未通过 ==> CPUTEST_CON_LOGIC_OP_ERR
 */
/* ***************************************************************** */
unsigned int conditionOpTest(void)
{
    unsigned int tcdata = CONDITION_ERROR;
    unsigned int count = 0;

    /* 逻辑或操作 */
    if( tcdata || CONDITION_OK )
    {
        count++;
    }

    /* 条件与操作 */
    if( ( CONDITION_OK && tcdata ) == CONDITION_ERROR )
    {
        count++;
    }

    /* 条件非操作 */
    if( !tcdata )
    {
        count++;
    }

    if( 3 != count )
    {
        return CPUTEST_CON_LOGIC_OP_ERR;
    }
    else
    {
        return CPUTEST_CON_LOGIC_OP_OK;
    }
}

/* ***************************************************************** */
/**
 * 【说明】:bitLogicOpTest
 *
 * CPU位操作符功能测试，具体操作如下：位或、位与、位取反、位异或、左移、
 * 右移操作。
 *
 * 【返回】:
 *        测试通过 ==> CPUTEST_BIT_LOGIC_OP_OK
 *      测试未通过 ==> CPUTEST_BIT_LOGIC_OP_ERR
 */
/* ***************************************************************** */
unsigned int bitLogicOpTest(void)
{
    unsigned int tldata = 0x55AA;
    unsigned long tdata = 0;

    /* 位操作符与、或、异或、取反操作 */
    tldata |= 0xAA55;
    tldata &= 0xAAAA;
    tldata = ~tldata;
    tldata ^= 0x00FF;

    /* 左移、右移操作 */
    tdata = ((unsigned long)tldata) << 8;
    tdata = tdata >> 8;

    /* 检测结果判断 */
    if( (tdata & 0xFFFF) == tldata)
    {
        return CPUTEST_BIT_LOGIC_OP_OK;
    }
    else
    {
        return CPUTEST_BIT_LOGIC_OP_ERR;
    }
}

/* ***************************************************************** */
/**
 * 【说明】:addrOpTest
 *
 * CPU地址访问功能测试。
 *
 * 【返回】:
 *        测试通过 ==> CPUTEST_ADDR_OP_OK
 *      测试未通过 ==> CPUTEST_ADDR_OP_ERR
 */
/* ***************************************************************** */
unsigned int addrOpTest(void)
{
    unsigned int a[3][4] = {{1,2,3,4},{5,6,7,8},{9,10,11,12}};
    unsigned int b[4][3] = {{0}},i,j;
    unsigned int *pa,*pb;

    pa = a[0];
    pb = b[0];

    /* 数组赋值 */
    for( i = 0; i < 3; i++)
    {
        for( j = 0; j < 4; j++)
        {
            b[j][i] = a[i][j];
        }
    }

    /* 间接寻址访问 */
    for( i = 0; i < 12 ; i++ )
    {
        if( *( pb +  (3 * (i % 4)) + (i / 4) ) != *(pa + i))
        {
            break;
        }
    }

    /* 判断检测是否通过 */
    if( i == 12 )
    {
        return CPUTEST_ADDR_OP_OK;
    }
    else
    {
        return CPUTEST_ADDR_OP_ERR;
    }
}

/* ***************************************************************** */
/**
 * 【说明】:cpuTest
 *
 * 执行CPU测试，具体包括以下测试：
 * 1. 算术运算测试
 * 2. 浮点数运算测试
 * 3. 条件运算测试
 * 4. 位运算符操作测试
 * 5. 地址操作测试
 *
 * 【返回】:
 *        CPUTEST_OK ---- CPU测试通过
 *
 *  若测试未通过，则可能包含以下一个或多个结果：
 *
 *        CPUTEST_ARITH_OP_ERR ---- CPU测试算术运算测试错误
 *        CPUTEST_FLOAT_OP_ERR ---- CPU测试浮点数运算测试错误
 *    CPUTEST_CON_LOGIC_OP_ERR ---- CPU测试条件运算符测试错误
 *    CPUTEST_BIT_LOGIC_OP_ERR ---- CPU测试位运算符测试错误
 *         CPUTEST_ADDR_OP_ERR ---- CPU测试地址访问功能测试错误
 */
/* ***************************************************************** */
unsigned int cpuTest(void)
{
    unsigned int tdata = CPUTEST_OK;

    /* 算术运算测试 */
    tdata |= arithMeticOpTest();

    /* 浮点数运算测试 */
    tdata |= floatOpTest();

    /* 条件运算测试 */
    tdata |= conditionOpTest();

    /* 位运算操作测试 */
    tdata |= bitLogicOpTest();

    /* 地址访问测试 */
    tdata |= addrOpTest();

    return tdata;
}

//=====================================================================
//END OF FILE
//=====================================================================
