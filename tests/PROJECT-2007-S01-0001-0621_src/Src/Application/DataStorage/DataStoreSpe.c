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
* 文件名称:   DataStoreSpe.c
*
* 文件日期:   REDACTED
*
*
* 程序版本:
*
**********************************************************************************
*
* 功能说明:
*
* 本功能模块用以实现对特定数据的读取、写入和存储管理。
*
*     本模块初始化时，从FLASH中获取各数据的数值，并对数据合法性进行判断
*
*********************************************************************************/

#include "Global.h"
/* ***************************************************************** */
/* 本地函数声明 */
Uint16 SpeDataCrcCacu(Uint16 v_wData_u16);

/* 本地全局变量 */

SpeData_t s_SpeData_t[SPE_DATA_DINDEX_MAX];      /* 特定存储数据     */
static volatile Uint16 s_speDataPendingMask_u16 = 0U; /* 延迟落盘的特定数据掩码 */

/* ***************************************************************** */
/**
 *    [函数名]	 SpeDataMirrorUpdate
 *
 *    [功能描述]	 更新特定数据RAM镜像，不执行FLASH操作。
 *    [输入参数说明] v_index_u16 ---- 特定数据索引
 *    			 v_wData_u16 ---- 数据值
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		 NONE
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:SpeDataMirrorUpdate
 *
 * 【功能描述】掉电保留区镜像更新, 更新RAM中的掉电保留数据镜像
 *
 * 【输入参数说明】v_index_u16 ---- 数据索引
                 v_wData_u16 ---- 写入数据
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static void SpeDataMirrorUpdate(Uint16 v_index_u16, Uint16 v_wData_u16)
{
    if(v_index_u16 >= SPE_DATA_DINDEX_MAX)
    {
        return;
    }

    s_SpeData_t[v_index_u16].dataU_u16 = v_wData_u16;
    s_SpeData_t[v_index_u16].dataState_u16 = SPE_DATA_STATE_OK;

    if(SPE_DATA_DINDEX_HARDW_VER == v_index_u16)
    {
        s_SpeData_t[v_index_u16].dataF_f = ((float)v_wData_u16) / 100.0F;
    }
    else
    {
        s_SpeData_t[v_index_u16].dataF_f = (float)v_wData_u16;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	 SpeDataGet
 *
 *    [功能描述]	 特定数据获取
 *              通过数据索引获取数据。
 *    [输入参数说明] v_index_u16 ---- 特定数据获取索引
 *    			 v_pSpeData_t ---- 特定数据指针
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		 NONE
 */
/* ***************************************************************** */
void SpeDataGet(Uint16 v_index_u16,SpeData_t *v_pSpeData_t)
{
    /* 数据索引小于特定数据数量且数据指针不为空时  */
    if( ( v_index_u16 < SPE_DATA_DINDEX_MAX ) && ( NULL != v_pSpeData_t ))
    {
        /* 获取特定数据中浮点数据、整形数据、数据状态  */
        v_pSpeData_t->dataF_f       = s_SpeData_t[v_index_u16].dataF_f;
        v_pSpeData_t->dataU_u16     = s_SpeData_t[v_index_u16].dataU_u16;
        v_pSpeData_t->dataState_u16 = s_SpeData_t[v_index_u16].dataState_u16;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	 SpeDataCrcCacu
 *
 *    [功能描述]	 特定数据地址获取
 *    [输入参数说明] v_index_u16 ---- 特定数据索引
 *
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  地址数据
 */
/* ***************************************************************** */
Uint32 SpeDataAddrGet(Uint16 v_index_u16)
{
    Uint32 lo_addr_u32   = FLASH_BASE_ADDR;  /* 返回地址，函数返回值，默认为基地址 */

        /* 数据索引小于特定数据存储数量时  */
        if( v_index_u16 < SPE_DATA_DINDEX_MAX)
        {
            /* 特定数据地址策略：
             * 当前实现按“索引 -> 独立扇区”固定映射，方便掉电/异常场景下按项擦写与追溯，
             * 代价是空间利用率较低。维护工具与上电恢复逻辑都依赖该一一映射关系。 */
            /* 索引小于等于硬件版本时，每个数据单独占一个扇区 */
            if(v_index_u16 <= SPE_DATA_DINDEX_SYS_TIME_SUM)
            {
            /* 找到当前索引地址 */
            lo_addr_u32 = FLASH_BASE_ADDR + ( (SPE_DATA_START_SECTOR + v_index_u16) * FLASH_SECTOR_LEN);
        }

        else
        {
            ;/* no deal to do */
        }
    }

    /* 返回地址 */
    return lo_addr_u32;
}
/* ***************************************************************** */
/**
 *    [函数名]	SpeDataRead
 *
 *    [功能描述]	特定数据读取
 *    			依据索引获取FLASH中数据。
 *    [输入参数说明] v_index_u16 ---- 特定数据索引
 *
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		  返回数据，默认返回0
 */
/* ***************************************************************** */
Uint16 SpeDataRead(Uint16 v_index_u16)
{
    Uint16 l_ii_u16       = 0U;   /* 循环索引                      */
    Uint32 l_addr_u32 = 0UL;  /* 临时地址                      */
    Uint16 l_rData_u16    = 0U;	  /* 读取数据，函数返回  */
    Uint16 l_rBuff_u16[SPE_DATA_STUCT_NUM - 1U];  /* 读取数据数组 */
    memset(l_rBuff_u16, 0, sizeof(l_rBuff_u16));

        /* 数据索引小于特定数据存储数量时  */
        if( v_index_u16 < SPE_DATA_DINDEX_MAX)
        {
        /* 获取地址 */
        l_addr_u32 = SpeDataAddrGet(v_index_u16);

        /* 获取特定数据 */
        (void)SpiFlashDataRead(l_addr_u32, l_rBuff_u16, (SPE_DATA_STUCT_NUM - 1U));

            /* 字节拼装口径（历史兼容）：
             * FLASH里按“低字节在低地址”的方式逐字节保存；
             * 读取时按反向索引拼回16bit，保持与旧版本写入口径一致。 */
            /* 对数据字节从低到高进行拼接 */
            for( l_ii_u16 = 0U; l_ii_u16 < (SPE_DATA_STUCT_NUM - 1U); l_ii_u16++)
            {
                l_rData_u16 = (l_rData_u16 << 8U);
                l_rData_u16 = l_rData_u16 + (l_rBuff_u16[(SPE_DATA_STUCT_NUM - 2U) - l_ii_u16] & 0xFFU);
            }
    }

    /* 返回读取数据  */
    return l_rData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]	 SpeDataCrcCacu
 *
 *    [功能描述]	 特定数据校验码计算
 *    			校验码是八位的，计算方法为：将前高低4个字节相加，数据和取反然后取低8位。
 *    [输入参数说明] v_wData_u16 ---- 拟存入数据
 *
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  生成的校验码，默认返回0
 */
/* ***************************************************************** */
Uint16 SpeDataCrcCacu(Uint16 v_wData_u16)
{
    Uint16 l_ii_u16      = 0U;  /* 循环计数                 */
    Uint16 l_crcData_u16 = 0U;  /* 校验码 ，函数返回 */

        /* CRC口径（兼容旧维护协议）：
         * 对有效数据字节逐字节求和，再按8bit取反，作为单字节校验存储。
         * 该算法不是通用CRC16/CRC32，不能与其它模块的CRC函数混用。 */
        /* 数据高低字节相加*/
        for(l_ii_u16 = 0U;l_ii_u16 < (SPE_DATA_STUCT_NUM - 1U);l_ii_u16++)
        {
        l_crcData_u16 = l_crcData_u16 + ((v_wData_u16 >> (8U * l_ii_u16)) & 0xFFU);
    }

    /* 取反后取低8位 */
    l_crcData_u16 = (~l_crcData_u16) & 0xFFU;

    /* 返回校验码 */
    return l_crcData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]	 SpeDataCrcRead
 *
 *    [功能描述]	 特定数据CRC获取
 *    [输入参数说明] v_index_u16 ---- 数据索引
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  返回数据CRC，默认返回零
 */
/* ***************************************************************** */
Uint16 SpeDataCrcRead(Uint16 v_index_u16)
{
    Uint32 l_addr_u32 = 0UL;  /* 临时地址                 */
    Uint16 l_crcData_u16  = 0U;   /* 校验码 ，函数返回 */

    /* 数据索引小于特定数据存储数量时  */
    if( v_index_u16 < SPE_DATA_DINDEX_MAX)
    {
        /* 获取地址 */
        l_addr_u32 = SpeDataAddrGet(v_index_u16);

        /* 获取校验地址 */
        l_addr_u32 = l_addr_u32 + (SPE_DATA_STUCT_NUM - 1U);

        /* 获取特定数据 */
        (void)SpiFlashDataRead(l_addr_u32, &l_crcData_u16, 1U);

        /* 取数据低8位 */
        l_crcData_u16 = l_crcData_u16 & 0xFFU;
    }

    /* 返回校验码 */
    return l_crcData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]	 SpeDataWrite
 *
 *    [功能描述]	 特定数据写入
 *    		             将新的数据固化，在固化的同时更新本地数据。
 *    [输入参数说明] v_index_u16 ---- 数据索引
 *    			  v_wData_u16 ---- 写入数据
 *	  [输出参数说明] NONE
 *    [其他说明]	  只适用一个扇区记录一个数据的场景
 *    [返回]		  写入结果
 */
/* ***************************************************************** */
Uint16 SpeDataWrite(Uint16 v_index_u16,Uint16 v_wData_u16)
{
    Uint16 lo_rData_u16   = SPE_DATA_STATE_OK;   /* 结果数据，函数返回值，默认正常   */
    Uint16 l_ii_u16       = 0U;   /* 循环计数   */
    Uint16 l_delayCnt_1_u16 = 0U; /* 延时计数1   */
    Uint16 l_delayCnt_2_u16 = 0U; /* 延时计数2   */
    Uint16 l_busyState_u16= 0U;   /* 忙状态   */
    Uint32 l_addr_u32     = 0UL;  /* 写地址       */
    Uint16 l_crcData_u16  = 0U;  /* 校验数据   */
    Uint16 l_wBuff_1_u16[SPE_DATA_STUCT_NUM];  /* 写入数据数组1，用于调用SPI口写入，写入后数组数值被刷新 */
    Uint16 l_wBuff_2_u16[SPE_DATA_STUCT_NUM];  /* 写入数据数组2 */
    Uint16 l_rBuff_u16[SPE_DATA_STUCT_NUM];  /* 回读数据数组 */
    memset(l_wBuff_1_u16, 0, sizeof(l_wBuff_1_u16));
    memset(l_wBuff_2_u16, 0, sizeof(l_wBuff_2_u16));
    memset(l_rBuff_u16, 0, sizeof(l_rBuff_u16));

    /* 数据索引小于特定数据数量时  */
    if( v_index_u16 < SPE_DATA_DINDEX_MAX )
    {
        /* 获取地址 */
        l_addr_u32 = SpeDataAddrGet(v_index_u16);

        /* 擦除扇区 */
        SpiFlashSectorErase(l_addr_u32);

        /* 超时等待FLASH扇区擦除完成 */
        while(l_delayCnt_1_u16 < SPE_DATA_WRITE_OVER_TIME_MS)
        {
            /* 周期喂狗 */
            CycleDogFeed();

            /* 延时1ms */
            delayUs(332UL);

            /* 获取FLASH忙状态 */
            l_busyState_u16 = SpiFlashIsBusy();

            /* FLASH状态处于不忙时，擦除扇区完成 ，结束延时等待*/
            if( FLASH_NOT_BUSY == l_busyState_u16)
            {
                break;
            }
            else /*忙时等待扇区擦除  */
            {
                l_delayCnt_1_u16 = l_delayCnt_1_u16 + 1U; /* 延时计数加1 */
            }
        }

        /* 延时计数小于门限值时，扇区擦除完成 */
        if(l_delayCnt_1_u16 < SPE_DATA_WRITE_OVER_TIME_MS)
        {
            /* 计算当前写入数据的CRC */
            l_crcData_u16 = SpeDataCrcCacu(v_wData_u16);

            /* 将写入数据从低到高分成字节数组 */
            for(l_ii_u16 = 0U;l_ii_u16 < (SPE_DATA_STUCT_NUM - 1U);l_ii_u16++)
            {
                l_wBuff_1_u16[l_ii_u16] = ((v_wData_u16 >> (8U * l_ii_u16)) & 0xFFU);
                l_wBuff_2_u16[l_ii_u16] = ((v_wData_u16 >> (8U * l_ii_u16)) & 0xFFU);

            }

            /* 最后一个字节为校验码 */
            l_wBuff_1_u16[SPE_DATA_STUCT_NUM - 1U] = (l_crcData_u16 & 0xFFU);
            l_wBuff_2_u16[SPE_DATA_STUCT_NUM - 1U] = (l_crcData_u16 & 0xFFU);

            /* 将数据写入FLASH中 */
            SpiFlashPageProgram(l_addr_u32, l_wBuff_1_u16, SPE_DATA_STUCT_NUM);

            /* 超时等待FLASH写入完成 */
            while(l_delayCnt_2_u16 < SPE_DATA_WRITE_OVER_TIME_MS)
            {
                /* 周期喂狗 */
                CycleDogFeed();

                /* 延时1ms */
                delayUs(332UL);

                /* 获取FLASH忙状态 */
                l_busyState_u16 = SpiFlashIsBusy();

                /* FLASH状态处于不忙时，写入完成 ，结束延时等待*/
                if( FLASH_NOT_BUSY == l_busyState_u16)
                {
                    break;
                }
                else /*忙时等待扇区擦除  */
                {
                    l_delayCnt_2_u16 = l_delayCnt_2_u16 + 1U; /* 延时计数加1 */
                }
            }

            /* 延时计数小于门限值时，写入完成 */
            if(l_delayCnt_2_u16 < SPE_DATA_WRITE_OVER_TIME_MS)
            {
                /* 回读内存中数据 */
                (void)SpiFlashDataRead(l_addr_u32, l_rBuff_u16, SPE_DATA_STUCT_NUM);

                /* 对每个数据进行回读判断时 */
                for(l_ii_u16 = 0U;l_ii_u16 < SPE_DATA_STUCT_NUM;l_ii_u16++)
                {
                    /* 写入回读数据不相等时 */
                    if((l_rBuff_u16[l_ii_u16] & 0xFFU) != l_wBuff_2_u16[l_ii_u16])
                    {
                        break; /* 跳出 */
                    }
                }

                /* 回读计数小于数量时回读不通过 */
                if(l_ii_u16 < SPE_DATA_STUCT_NUM)
                {
                    lo_rData_u16   = SPE_DATA_STATE_ERR_WRITE_READ_BACK;  /* 数据状态写入回读异常 */
                }
                else /* 回读通过时，写入完成 */
                {
                    /* 更新本地数据 */
                    s_SpeData_t[v_index_u16].dataU_u16 = v_wData_u16;
                }
            }
            else /* 写入超时 */
            {
                lo_rData_u16   = SPE_DATA_STATE_ERR_WRITE_BUSY;   /* 数据状态写入超时异常(写入数据后超时异常) */
            }
        }
        else /* 擦除扇区超时 */
        {
            lo_rData_u16   = SPE_DATA_STATE_ERR_ERASE_BUSY;   /* 返回数据状态写入擦除扇区异常(擦除扇区超时异常)   */
        }

        /* 数据状态正常时更新浮点数据 */
        if(SPE_DATA_STATE_OK == lo_rData_u16)
        {
            /* 更新数据状态 */
            s_SpeData_t[v_index_u16].dataState_u16 = lo_rData_u16;

            /* 根据数据索引更新浮点镜像值，保证读接口`dataF_f`可用。 */
            if(SPE_DATA_DINDEX_HARDW_VER == v_index_u16)
            {
                /* 版本字段按百分比编码：100 -> 1.00。 */
                s_SpeData_t[v_index_u16].dataF_f = ((float)v_wData_u16) / 100.0F;
            }
            else
            {
                /* 其他计数类/码值类数据按数值镜像。 */
                s_SpeData_t[v_index_u16].dataF_f = (float)v_wData_u16;
            }
        }
    }

    /* 返回数据状态 */
    return lo_rData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]	 SpeDataWriteDefer
 *
 *    [功能描述]	 延迟写入特定数据。
 *    		             仅更新RAM镜像并置位待刷写标志，由主循环在非ISR上下文内落盘。
 *    [输入参数说明] v_index_u16 ---- 数据索引
 *    			  v_wData_u16 ---- 写入数据
 *	  [输出参数说明] NONE
 *    [其他说明]	  仅支持索引小于16的特定数据。
 *    [返回]		  写入结果
 */
/* ***************************************************************** */
Uint16 SpeDataWriteDefer(Uint16 v_index_u16,Uint16 v_wData_u16)
{
    if(v_index_u16 >= SPE_DATA_DINDEX_MAX)
    {
        return SPE_DATA_STATE_ERR;
    }

    SpeDataMirrorUpdate(v_index_u16, v_wData_u16);
    s_speDataPendingMask_u16 |= (Uint16)(1U << v_index_u16);

    return SPE_DATA_STATE_OK;
}

/* ***************************************************************** */
/**
 *    [函数名]	 SpeDataPendingExist
 *
 *    [功能描述]	 查询是否存在待刷写的特定数据。
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  VALID-存在待刷写项 / INVALID-无待刷写项
 */
/* ***************************************************************** */
Uint16 SpeDataPendingExist(void)
{
    if (0U != s_speDataPendingMask_u16)
    {
        return VALID;
    }

    return INVALID;
}

/* ***************************************************************** */
/**
 *    [函数名]	 SpeDataFlushPending
 *
 *    [功能描述]	 刷写待落盘的特定数据。
 *    		             每次按索引顺序尝试刷写，失败项保留到下一次重试。
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void SpeDataFlushPending(void)
{
    Uint16 l_index_u16 = 0U;
    /* 先锁存当前待刷写掩码，避免本轮扫描过程中反复读取共享标志。 */
    Uint16 l_pendingMask_u16 = s_speDataPendingMask_u16;

    if(0U == l_pendingMask_u16)
    {
        return;
    }

    for(l_index_u16 = 0U; l_index_u16 < SPE_DATA_DINDEX_MAX-1; l_index_u16++)
    {
        Uint16 l_bitMask_u16 = (Uint16)(1U << l_index_u16);

        /* 当前索引未挂起落盘请求时直接检查下一项。 */
        if(0U == (l_pendingMask_u16 & l_bitMask_u16))
        {
            continue;
        }

        if(SPE_DATA_STATE_OK == SpeDataWrite(l_index_u16, s_SpeData_t[l_index_u16].dataU_u16))
        {
            /* 仅在落盘成功后清除待刷写标志，失败项保留待后续重试。 */
            s_speDataPendingMask_u16 &= (Uint16)(~l_bitMask_u16);
        }
        else
        {
            /* 底层写FLASH失败时停止继续刷写，避免本轮继续放大时延。 */
            break;
        }
    }
}


/* ***************************************************************** */
/**
 *    [函数名]	SpeDataCheck
 *
 *    [功能描述]	特定数据合法性检测
 *    			检测特定数据校验是否正确。
 *    [输入参数说明] v_index_u16 ---- 数据索引
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  数据检测结果，可能的取值如下：
 *          SPE_DATA_STATE_ERR ---- 特定数据异常
 *          SPE_DATA_STATE_OK  ---- 特定数据正常
 */
/* ***************************************************************** */
Uint16 SpeDataCheck(Uint16 v_index_u16)
{
    Uint16 l_rData_u16     = SPE_DATA_STATE_ERR; /* 检测结果，函数返回 */
    Uint16 l_tempData_u16  = 0U;   /* 临时数据     */
    Uint16 l_crcData_1_u16 = 0U;   /* 校验数据1 */
    Uint16 l_crcData_2_u16 = 0U;   /* 校验数据2 */

    /* 数据索引小于特定数据数量时  */
    if( v_index_u16 < SPE_DATA_DINDEX_MAX )
    {
        /* 获取当前索引地址的数据 */
        l_tempData_u16 = SpeDataRead(v_index_u16);

        /* 计算当前数据的CRC */
        l_crcData_1_u16  = SpeDataCrcCacu(l_tempData_u16);

        /* 获取数据的CRC */
        l_crcData_2_u16  = SpeDataCrcRead(v_index_u16);

        /* 数据CRC校验一致时  */
        if( l_crcData_1_u16 == l_crcData_2_u16 )
        {
            /* 检查结果为数据正常 */
            l_rData_u16 = SPE_DATA_STATE_OK;
        }
    }

    /* 返回检查结果  */
    return l_rData_u16;
}


/* ***************************************************************** */
/**
 *    [函数名]	 SpeDataRecordInit
 *
 *    [功能描述]	 特定数据记录初始化
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		 NONE
 */
/* ***************************************************************** */
void SpeDataRecordInit(void)
{
    Uint16 l_index_u16      = 0U;  /* 数据索引               */
    Uint16 l_dataU_u16      = 0U;  /* 整形数据               */
    Uint16 l_startUpMode_u16= 0U;  /* 冷热启动模式        */
    Uint16 l_delayCnt_1_u16 = 0U;  /* 延时计数1   */
    Uint16 l_busyState_u16  = 0U;  /* 忙状态   */

    /* 获取FLASH忙状态 */
    l_busyState_u16 = SpiFlashIsBusy();

    /* 超时200ms等待FLASH非忙 */
    while((FLASH_BUSY == l_busyState_u16) && (l_delayCnt_1_u16 < 200U))
    {
        /* 周期喂狗 */
        CycleDogFeed();

        /* 延时1ms */
        delayUs(332UL);

        /* 获取FLASH忙状态 */
        l_busyState_u16 = SpiFlashIsBusy();

        l_delayCnt_1_u16 = l_delayCnt_1_u16 + 1U; /* 延时计数加1 */
    }

    /* 读取特定数据 */
    for(l_index_u16 = 0U;l_index_u16 < SPE_DATA_DINDEX_MAX;l_index_u16++)
    {
        /* 检查数据状态 */
        s_SpeData_t[l_index_u16].dataState_u16 = SpeDataCheck(l_index_u16);

        /* 数据状态异常时 */
        if( SPE_DATA_STATE_ERR == s_SpeData_t[l_index_u16].dataState_u16)
        {
            /* 浮点数清零 */
            s_SpeData_t[l_index_u16].dataF_f = 0.0F;

            /* 索引为硬件版本设置时，默认硬件版本为1.00 */
            if(SPE_DATA_DINDEX_HARDW_VER == l_index_u16)
            {
                /* 默认硬件版本为1.00 */
                s_SpeData_t[l_index_u16].dataU_u16 = 100U;
            }
            else /* 其他索引时  */
            {
                /* 整形数清零 */
                s_SpeData_t[l_index_u16].dataU_u16 = 0U;
            }
        }
        else  /* 数据状态正常时 */
        {
            /* 获取当前索引地址的数据 */
            l_dataU_u16 = SpeDataRead(l_index_u16);

            /* 更新浮点数据和整形数据 */
            s_SpeData_t[l_index_u16].dataU_u16 = l_dataU_u16;

            /* 根据数据索引更新浮点镜像值。 */
            if(SPE_DATA_DINDEX_HARDW_VER == l_index_u16)
            {
                /* 版本字段按百分比编码：100 -> 1.00。 */
                s_SpeData_t[l_index_u16].dataF_f = ((float)l_dataU_u16) / 100.0F;
            }
            else
            {
                /* 其他计数类/码值类数据按数值镜像。 */
                s_SpeData_t[l_index_u16].dataF_f = (float)l_dataU_u16;
            }
        }
    }

    /* 获取冷热启动模式数据 */
    l_startUpMode_u16 = StartUpModeGet();

    /* 启动模式等于上电冷启动时  */
    if(COLD_POW_STARTUP_MODE == l_startUpMode_u16)
    {
        /* 上电冷启动次数加1，更新特定数据 */
        (void)SpeDataWrite(SPE_DATA_DINDEX_COLD_STARTUP_NUM,(s_SpeData_t[SPE_DATA_DINDEX_COLD_STARTUP_NUM].dataU_u16 + 1U));
    }
    /* 启动模式等于外狗热启动时  */
    else if(HOT_EXT_STARTUP_MODE == l_startUpMode_u16)
    {
        /* 外狗热启动次数加1，更新特定数据 */
        (void)SpeDataWrite(SPE_DATA_DINDEX_HOT_EXT_STARTUP_NUM,(s_SpeData_t[SPE_DATA_DINDEX_HOT_EXT_STARTUP_NUM].dataU_u16 + 1U));
    }
    else /* 启动模式等于内狗热启动时  */
    {
        /* 内狗热启动次数加1，更新特定数据 */
        (void)SpeDataWrite(SPE_DATA_DINDEX_HOT_IN_STARTUP_NUM,(s_SpeData_t[SPE_DATA_DINDEX_HOT_IN_STARTUP_NUM].dataU_u16 + 1U));
    }
}

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
