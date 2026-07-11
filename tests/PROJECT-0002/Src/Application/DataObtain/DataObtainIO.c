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
* 文件名称:   DataObtainIO.c
*
* 文件日期:    REDACTED
*
*
* 程序版本:   V2.00
*
**********************************************************************************
*
* 功能说明:
*
* 本文件完成离散量数字信号的采集
*
*********************************************************************************/

#include "Global.h"

/*******************************************************************************/
/* 本地数据 */

IoData_t  s_ioDataBuff_t[IO_DATA_NUM];   /* 离散量数据缓冲区     */

Uint16 s_tempIoBuff_u16[IO_DATA_NUM];    /* 离散量IO采集缓存数组 */

/* ***************************************************************** */
/* 离散量配置结构体数组 */
static IoDataConf_t s_IODataConfBuff_t[IO_DATA_NUM] =
                {
                    /* 初始状态     |        CPLD地址             |地址BIT位|滤波计数 */
                        { GPIO_CLEAR, CPLD_ADDR_R_HKA_DATA1, BIT0  , 5U },   /* 0离散量 吊舱加油阀开状态信号   */
                        { GPIO_CLEAR, CPLD_ADDR_R_HKA_DATA1, BIT1  , 5U },   /* 1离散量 吊舱回油阀开状态信号    */
                        { GPIO_CLEAR, CPLD_ADDR_R_HKA_DATA1, BIT2  , 5U },   /* 2离散量 吊舱在位信号           */
                        { GPIO_CLEAR, CPLD_ADDR_R_HKA_DATA1, BIT5  , 5U },   /* 3离散量 28V掉电检测信号       */
                        { GPIO_CLEAR, CPLD_ADDR_R_HKA_DATA1, BIT8  , 5U },   /* 4离散量 吊舱加油阀开状态信号   */
                        { GPIO_CLEAR, CPLD_ADDR_R_HKA_DATA1, BIT9  , 5U },   /* 5离散量 吊舱回油阀开状态信号    */
                        { GPIO_CLEAR, CPLD_ADDR_R_HKA_DATA1, BIT10  , 5U },     /* 6离散量 吊舱在位信号         */
                        { GPIO_CLEAR, CPLD_ADDR_R_HKA_DATA1, BIT4  , 5U },     /* 7离散量 地面维护开关信号  */
                        { GPIO_CLEAR, CPLD_ADDR_R_HKA_DATA1, BIT12  , 5U },     /* 离散量 通道号识别信号1 */
                        { GPIO_CLEAR, CPLD_ADDR_R_HKA_DATA1, BIT13 ,  5U },     /* 离散量 通道号识别信号2 */

                };

/* ***************************************************************** */
/**
 *    [函数名]	IoDataGet
 *
 *    [功能描述]	离散量数据获取
 *    [输入参数说明] v_index_u16 ---- 获取离散量数据的索引
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		  离散量数据状态
 */
/* ***************************************************************** */
Uint16 IoDataGet(Uint16 v_index_u16)
{
    Uint16 l_rData_u16 = 0U;  /* 结果数据，返回值 */

    /* 索引小于等于离散量个数 */
    if( v_index_u16 < IO_DATA_NUM )
    {
        /* 获取离散量状态 */
        l_rData_u16 = s_ioDataBuff_t[v_index_u16].validState_u16;
    }

    /* 返回结果数据 */
    return l_rData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]	IoDataStateUpdate
 *
 *    [功能描述]	离散量数据更新
 *    			通过离散量采集值，更新离散量数据状态。
 *    [输入参数说明] v_pIoDataBuff_u16 ---- 离散量数据存储数组首地址，顺序需与离散量配置数组一致
 *    			  v_len_u16         ---- 数组长度
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void IoDataStateUpdate(Uint16 *v_pIoDataBuff_u16,Uint16 v_len_u16)
{
    Uint16 l_index_u16  = 0U;  /* 循环索引  */
    Uint16 l_tempIO_u16 = GPIO_CLEAR;  /* 管脚状态 */

    /* 参数合法性判断 */
    if( (NULL != v_pIoDataBuff_u16) && ( v_len_u16 > 0U ) && ( v_len_u16 <= IO_DATA_NUM ) )
    {
        for( l_index_u16 = 0U; l_index_u16 < v_len_u16; l_index_u16++)
        {
            /* 采集当前IO引脚状态 */
            l_tempIO_u16 = v_pIoDataBuff_u16[l_index_u16];

            /* 当前采集IO引脚状态与最近的采集状态一致时 */
            if( l_tempIO_u16 == (s_ioDataBuff_t[l_index_u16].currState_u16) )
            {
                s_ioDataBuff_t[l_index_u16].count_u16 = s_ioDataBuff_t[l_index_u16].count_u16 + 1U;
            }
            else
            {
                /*
                 * 若当前采集IO引脚状态与最近的采集状态不一致，则更新
                 * 最近的采集状态，滤波计数从1开始重新计数
                 */
                s_ioDataBuff_t[l_index_u16].currState_u16 = l_tempIO_u16;
                s_ioDataBuff_t[l_index_u16].count_u16 = 1U;
            }

            /* 当前滤波计数满足滤波要求 */
            if( s_ioDataBuff_t[l_index_u16].count_u16 >= s_IODataConfBuff_t[l_index_u16].validCount_u16 )
            {
                /* 清除滤波计数 */
                s_ioDataBuff_t[l_index_u16].count_u16 = 0U;

                /* 若离散量有效状态与当前状态不一致，则更新离散量有效状态 */
                if( s_ioDataBuff_t[l_index_u16].validState_u16 != s_ioDataBuff_t[l_index_u16].currState_u16 )
                {
                    s_ioDataBuff_t[l_index_u16].validState_u16 = s_ioDataBuff_t[l_index_u16].currState_u16;
                }
            }
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	IoDataObtain
 *
 *    [功能描述]	离散量采集
 *    			从物理IO获取IO引脚的状态，并对IO引脚状态数据进行滤波处理。
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		 NONE
 */
/* ***************************************************************** */
void IoDataObtain(void)
{
    Uint16 l_index_u16  = 0U;  /* 循环索引 */
    Uint16 l_tempIO_u16  = GPIO_CLEAR;   /* 管脚状态 */

    /* 从CPLD获取离散量数据 */
    for( l_index_u16 = 0U; l_index_u16 < IO_DATA_NUM; l_index_u16++)
    {
        /* 采集当前IO引脚状态 */
        l_tempIO_u16 = HardXintUint16Read(s_IODataConfBuff_t[l_index_u16].CPLDAddr_u16) & s_IODataConfBuff_t[l_index_u16].dataBitNum_u16;

        /* IO电平状态不为低 */
        if(GPIO_CLEAR != l_tempIO_u16)
        {
            /* IO电平状态不为低时，更新IO状态 为高*/
            l_tempIO_u16 = GPIO_SET;
        }

        /* 更新IO缓存区电平状态 */
        s_tempIoBuff_u16[l_index_u16] = l_tempIO_u16;
    }

    /* 利用采集的数据更新IO数据的状态 */
    IoDataStateUpdate(s_tempIoBuff_u16,IO_DATA_NUM);
}

/* ***************************************************************** */
/**
 *    [函数名]	IoDataInit
 *
 *    [功能描述]	离散量数据初始化
 *    			依据离散量配置信息对离散量结构体参数进行初始化。
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void IoDataInit(void)
{
    Uint16 l_ii_u16 = 0U; /* 循环计数  */

    for( l_ii_u16 = 0U; l_ii_u16 < IO_DATA_NUM; l_ii_u16++)
    {
        /* 滤波计数器初始化为0 */
        s_ioDataBuff_t[l_ii_u16].count_u16 = 0U;

        /* 离散量初始状态初始化 */
        s_ioDataBuff_t[l_ii_u16].currState_u16  = s_IODataConfBuff_t[l_ii_u16].initState_u16;
        s_ioDataBuff_t[l_ii_u16].validState_u16 = s_IODataConfBuff_t[l_ii_u16].initState_u16;
    }
}

/* ========================================================================== */
/* END OF FILE */
/* ========================================================================== */
