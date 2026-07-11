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
* 文件名称:   DataObtainAI
*
* 文件日期:    REDACTED
*
*
* 程序版本:
*
**********************************************************************************
*
* 功能说明:
*
* 本模块实现模拟量数据采集
*
*
*********************************************************************************/

#include "Global.h"

/********************************************************************************/
/* 本地变量 */

AnaData_t s_anaDataBuff_t[ANA_DATA_NUM_TOTAL] ;        /* 模拟量数据缓冲区 */

/* ***************************************************************** */
/* 模拟量配置结构体数组 */
AnaDataConf_t s_anaDataConfBuff_t[ANA_DATA_NUM_DSP] =
                   {
                         /* 上限          |  下限        |  下限         |  系数k   | 系数b   | 地址占位        */
                           {  32.0F  ,  22.0F,   0.0F,     22.581F,   0.0F, 0U  }, 	 /* 0模拟量3.3V电源(片上AD采集)   */
                           {  6.0F  ,   4.0F,   0.0F,     3.226F,   0.0F, 0U  },   /* 1模拟量1.9V电源 (片上AD采集)      */
                           {  4.0F  ,   3.0F,   0.0F,     3.204F,   0.0F, 0U  },   /* 2模拟量2.5V电源(片上AD采集)	    */
                           {  3.0F  ,   2.0F,   0.0F,     3.218F,   0.0F, 0U  }, 	 /* 3模拟量1.8V电源(片上AD采集)  	 */
                           {  1.5F  ,   0.9F,   0.0F,     3.217F,   0.0F, 0U  },   /* 4模拟量 1.1V电源(片上AD采集)      */

                   };

/* ***************************************************************** */
/**
 * 【函数名】:AnaDataStateGet
 *
 * 【功能描述】模拟量数据检查状态获取。
 *
 * 【输入参数说明】v_index_u16 ---- 模拟量数据索引
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】:	   模拟量数据的检查状态，默认数据未知异常
 *      ANA_DATA_STATE_OK         ---- 数据检测正常
 *      ANA_DATA_STATE_LIMIT_ERR  ---- 数据超限
 *      ANA_DATA_STATE_CHANGE_ERR ---- 数据变化率超限
 *      ANA_DATA_STATE_UNKNOW_ERR ---- 数据未知异常
 */
/* ***************************************************************** */
Uint16 AnaDataStateGet(Uint16 v_index_u16)
{
    Uint16 l_rData_u16 = ANA_DATA_STATE_UNKNOW_ERR;  /* 状态数据   */

    /* 输入数据索引小于 数据个数时 */
    if( v_index_u16 < ANA_DATA_NUM_TOTAL )
    {
        l_rData_u16 = s_anaDataBuff_t[v_index_u16].checkState_u16;
    }

    return l_rData_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:AnaDataCheck
 *
 * 【功能描述】模拟量数据检查
 * 判别新增模拟量数据合理性，判据有以下两条：
 * 1. 数据是否超过上限或下限
 * 2. 数据变化率是否超限
 *
 * 【输入参数说明】v_index_u16 ---- 模拟量数据索引
 * 			   v_fData_f   ---- 模拟量数据
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】:	当数据合理性判别错误时，可能会包含一个或两个故障码，具体返回值如下：
 *          ANA_DATA_STATE_OK ---- 数据合理性判别通过
 *   ANA_DATA_STATE_LIMIT_ERR ---- 数据超过上限或下限
 *  ANA_DATA_STATE_CHANGE_ERR ---- 数据变化率超限
 */
/* ***************************************************************** */
Uint16 AnaDataCheck(Uint16 v_index_u16, float v_fData_f)
{
    Uint16 l_rData_u16 = ANA_DATA_STATE_OK; /* 检查状态  */

    /* 输入数据索引小于 数据个数时 */
    if(v_index_u16 < ANA_DATA_NUM_TOTAL)
    {
        /* 检查数据是否超过上限和下限 */
        if( (v_fData_f < s_anaDataConfBuff_t[v_index_u16].lowLimit_f ) || (v_fData_f > s_anaDataConfBuff_t[v_index_u16].hiLimit_f))
        {
            /* 若数据超限，则记录故障码 */
            l_rData_u16 = l_rData_u16 | ANA_DATA_STATE_LIMIT_ERR;
        }

        /* 检查数据是否超过未知状态下限 */
        if(v_fData_f <= s_anaDataConfBuff_t[v_index_u16].unknownlowLimit_f)
        {
            /* 若数据超限，则记录故障码 */
            l_rData_u16 = l_rData_u16 | ANA_DATA_STATE_UNKNOW_ERR;
        }
    }

    return l_rData_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:FdataAverage
 *
 * 【功能描述】浮点数求平均
 * 	 1、对一组浮点数，去除最大、最小值后，求平均值，当浮点数个数为零时，返回零；
 *   2、当浮点数个数大于零，小于三时，返回数组第一个数。
 *
 * 【输入参数说明】v_pBuff_f ---- 浮点数数组指针
 * 			   v_len_16  ---- 数据长度
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】:	数组中浮点数的平均值
 */
/* ***************************************************************** */
float FdataAverage(float *v_pBuff_f, Uint16 v_len_16)
{
    Uint16 l_ii_u16 = 0U; /* 循环索引 */
    float  l_min_f = 0.0,l_max_f = 0.0; /* 最小值，最大值 */
    double l_sum_f = 0.0; /* 数据和值 */
    float  l_fData_f = 0.0;  /* 平均值 */

    /* 输入数组不为空 且 数组长度大于3 */
    if(NULL != v_pBuff_f)
    {
        /* 输入数组长度大于3 */
        if( v_len_16 > 3U )
        {
            /* 最大、最小值、和值初始化为0索引数据 */
            l_min_f = v_pBuff_f[0];
            l_max_f = v_pBuff_f[0];
            l_sum_f = v_pBuff_f[0];

            /* 求数组和以及最大值和最小值 */
            for( l_ii_u16 = 1U; l_ii_u16 < v_len_16 ; l_ii_u16++)
            {
                /* 数据求和计算 */
                l_sum_f = l_sum_f + v_pBuff_f[l_ii_u16];

                /* 数据小于最小值时更新最小值 */
                if( v_pBuff_f[l_ii_u16] < l_min_f )
                {
                    l_min_f = v_pBuff_f[l_ii_u16];
                }

                /* 数据大于最小值时更新最大值 */
                else if ( v_pBuff_f[l_ii_u16] > l_max_f )
                {
                    l_max_f = v_pBuff_f[l_ii_u16];
                }
                else
                {
                    /* no deal to do */
                }
            }

            /* 去除最大值、最小值求平均值 */
            l_sum_f   = l_sum_f - l_min_f - l_max_f;/* 去除最大值、最小值 */
            l_fData_f = l_sum_f / ( v_len_16 - 2U); /* 剩余数据求平均值 */
        }
        else if ( v_len_16 > 0U )
        {
            /* 当浮点数个数大于零，小于三时，返回数组第一个值 */
            l_fData_f = v_pBuff_f[0];
        }
        else
        {
            /* no deal to do */
        }
    }

    return l_fData_f;
}

/* ***************************************************************** */
/**
 * 【函数名】:AnaDataUpdate
 *
 * 【功能描述】模拟量数据更新
 * 		模拟量数据依据缓存中的浮点数更新数据，同时对数据合理性进行判断，并记录判断失败数据。
 *
 * 【输入参数说明】v_index_u16 ---- 模拟量数据索引
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】:	 NONE
 */
/* ***************************************************************** */
void AnaDataUpdate(Uint16 v_index_u16)
{
    float l_fData_f = 0.0F; /* 滤波后数据 */
    Uint16 l_checkState_u16 = 0U;  /* 检查状态  */

    /* 输入数据索引小于 数据个数时 */
    if(v_index_u16 < ANA_DATA_NUM_TOTAL)
    {
        /* 去除最大值、最小值求平均值 */
        l_fData_f = FdataAverage(s_anaDataBuff_t[v_index_u16].fDataBuff_f, ANA_DATA_RECORD_NUM);

        /* 数据合理性判断 */
        l_checkState_u16 = AnaDataCheck(v_index_u16,l_fData_f);

        /* 记录数据有效性判别结果 */
        s_anaDataBuff_t[v_index_u16].checkState_u16 = l_checkState_u16;

        /* 更新模拟量数据 */
        s_anaDataBuff_t[v_index_u16].currData_f = l_fData_f;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:AnaDataBuffInsert
 *
 * 【功能描述】模拟量数据插入
 *
 * 【输入参数说明】v_index_u16 ---- 模拟量数据索引
 * 			     v_fData_f ---- 待插入浮点数
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】:	  NONE
 */
/* ***************************************************************** */
void AnaDataBuffInsert(Uint16 v_index_u16, float v_fData_f)
{
    Uint32 l_tempCount_u32 = 0UL;

    /* 输入数据索引小于 数据个数时 */
    if(v_index_u16 < ANA_DATA_NUM_TOTAL)
    {
        /* 获取缓存数组索引 */
        l_tempCount_u32 = s_anaDataBuff_t[v_index_u16].count_u32 % ANA_DATA_RECORD_NUM;

        /* 更新模拟量数据缓存 */
        s_anaDataBuff_t[v_index_u16].fDataBuff_f[l_tempCount_u32] = v_fData_f;

        /* 更新模拟量数据缓存计数 */
        s_anaDataBuff_t[v_index_u16].count_u32 = s_anaDataBuff_t[v_index_u16].count_u32 + 1UL ;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:AnaDataObtain
 *
 * 【功能描述】模拟量数据采集
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】:	  NONE
 */
/* ***************************************************************** */
void AnaDataObtain(void)
{
    float l_fBuff_f[ANA_DATA_NUM_TOTAL] = {0.0F}; /* 浮点数据缓存数组  */
    Uint16 l_index_u16    = 0U;   /* 循环索引   */

    /* 从ADC获取模拟量数据 */
    AdcDataGet(l_fBuff_f,ANA_DATA_NUM_DSP,ADC_SEQ1);

    /* 从片上获取模拟量数据 */
    for( l_index_u16 = 0U; l_index_u16 < ANA_DATA_NUM_DSP; l_index_u16++)
    {
        /* 乘以硬件比例获取数据 */
        l_fBuff_f[l_index_u16] = (s_anaDataConfBuff_t[l_index_u16].ratio_k_f * l_fBuff_f[l_index_u16]) + s_anaDataConfBuff_t[l_index_u16].ratio_b_f;
    }


    for( l_index_u16 = 0U; l_index_u16 < ANA_DATA_NUM_TOTAL; l_index_u16++)
    {
        /* 将获取的浮点数插入相应模拟量数据的缓存 */
        AnaDataBuffInsert(l_index_u16,l_fBuff_f[l_index_u16]);

        /* 依据模拟量数据缓存更新数据 */
        AnaDataUpdate(l_index_u16);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:AnaDataInit
 *
 * 【功能描述】模拟量数据初始化
 * 			依据模拟量配置信息对模拟量结构体参数进行初始化。
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】:	  NONE
 */
/* ***************************************************************** */
void AnaDataInit(void)
{
    Uint16 l_index_u16    = 0U;      /* 循环索引      */
    Uint16 l_ii_u16       = 0U;      /* 循环计数      */

    /* 依次对所有模拟量结构体数据进行初始化 */
    for( l_index_u16 = 0U; l_index_u16 < ANA_DATA_NUM_TOTAL; l_index_u16++)
    {
        s_anaDataBuff_t[l_index_u16].count_u32   = 0UL;
        s_anaDataBuff_t[l_index_u16].currData_f  = 0.0F;
        s_anaDataBuff_t[l_index_u16].lastData_f  = 0.0F;

        /* 数据有效性标识，初始化为全有效，避免最开始的报故误判 */
        s_anaDataBuff_t[l_index_u16].checkState_u16 = ANA_DATA_STATE_OK;

        /* 对模拟量结构体数据缓存进行初始化清零 */
        for( l_ii_u16 = 0U; l_ii_u16 < ANA_DATA_RECORD_NUM; l_ii_u16++)
        {
            s_anaDataBuff_t[l_index_u16].fDataBuff_f[l_ii_u16] = 0.0F;
        }
    }
}

/* =============================================================================== */
/* END OF FILE */
/* =============================================================================== */
