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
* 文件名称:   PuBIT
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
* 本模块实现上电BIT检测功能
*
*********************************************************************************/

#include "Global.h"

/* ***************************************************************** */
/* 定义本地变量 */

Uint16 s_puBITInfo_u16[PUBIT_INDEX_NUM];   /* 上电BIT检测项信息    */
Uint16 s_puBITData_u16;    /* 上电BIT自检数据        */
Uint16 s_puBITPowerTestCon_u16[POWER_BIT_NUM] = {
        ANA_DINDEX_V28,
        ANA_DINDEX_V5,
        ANA_DINDEX_3V3,
        ANA_DINDEX_2V5,
        ANA_DINDEX_1V2,
};

/* ***************************************************************** */
/**
 *    [函数名]：    PuBITDataRebuild
 *    [功能描述]：  根据各上电BIT单项结果重建汇总位图
 *    [输入参数说明]：NONE
 *    [输出参数说明]：NONE
 *    [其他说明]：  供上电自检结束和外部补充注入关键故障时统一调用
 *    [返回]：      NONE
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:PuBITDataRebuild
 *
 * 【功能描述】PuBIT数据重建, 上电自检后重建模块状态
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static void PuBITDataRebuild(void)
{
    Uint16 l_index_u16 = 0U;

    s_puBITData_u16 = PUBIT_TEST_OK;

    for (l_index_u16 = 0U; l_index_u16 < PUBIT_INDEX_NUM; l_index_u16++)
    {
        if (PUBIT_TEST_OK != s_puBITInfo_u16[l_index_u16])
        {
            s_puBITData_u16 |= (Uint16)(0x01U << l_index_u16);
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	IFBITInfoGet
 *
 *    [功能描述]	周期BIT检测信息获取
 *
 *    [输入参数说明] v_index_u16 ---- 检测项索引
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  周期BIT检测结果
 */
/* ***************************************************************** */
Uint16 PUBITInfoGet(Uint16 v_index_u16)
{
    Uint16 l_rData_u16 = PUBIT_TEST_OK;  /* 结果数据 */

    /* 输入索引小于索引数量 */
    if(v_index_u16 < PUBIT_INDEX_NUM)
    {
        /* 获取自检自检结果 */
        l_rData_u16 = s_puBITInfo_u16[v_index_u16];
    }

    /* 返回结果 */
    return l_rData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]：    PuBITForceResultUpdate
 *    [功能描述]：  供启动后续流程补充修正单项上电BIT结果
 *    [输入参数说明]：v_index_u16 --- 检测项索引
 *                    v_result_u16 -- 检测结果
 *    [输出参数说明]：NONE
 *    [其他说明]：  主要用于启动判型结束后把“主备状态识别故障”并入上电关键故障链
 *    [返回]：      NONE
 */
/* ***************************************************************** */
void PuBITForceResultUpdate(Uint16 v_index_u16, Uint16 v_result_u16)
{
    if (v_index_u16 < PUBIT_INDEX_NUM)
    {
        if (PUBIT_TEST_OK == v_result_u16)
        {
            s_puBITInfo_u16[v_index_u16] = PUBIT_TEST_OK;
        }
        else
        {
            s_puBITInfo_u16[v_index_u16] = PUBIT_TEST_ERR;
        }
        PuBITDataRebuild();
    }
}
/* ***************************************************************** */
/**
 *    [函数名]	PuBITDataGet
 *
 *    [功能描述]	上电BIT结果获取
 *
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		 上电BIT检测结果，可能取值如下：
 *          PUBIT_TEST_OK  ---- 检测结果正常
 *          PUBIT_TEST_ERR ---- 检测结果异常
 */
/* ***************************************************************** */
Uint16 PuBITDataGet(void)
{
    /* 返回上电BIT结果数据  */
    return s_puBITData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]：    PuBITHotResetBypassInit
 *    [功能描述]：  热复位路径下的PuBIT初始化
 *    [输入参数说明]：NONE
 *    [输出参数说明]：NONE
 *    [其他说明]：  热复位不再重跑上电BIT，统一将PuBIT通道静默为“正常”；
 *                  本次热重连的CCDL/CPLD/同步诊断改由InitStatus和runtimerole承担。
 *    [返回]：      NONE
 */
/* ***************************************************************** */
void PuBITHotResetBypassInit(void)
{
    Uint16 l_index_u16 = 0U;

    s_puBITData_u16 = PUBIT_TEST_OK;

    for(l_index_u16 = 0U; l_index_u16 < PUBIT_INDEX_NUM; l_index_u16++)
    {
        s_puBITInfo_u16[l_index_u16] = PUBIT_TEST_OK;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]：		PuBITCPUTest
 *    [功能描述]：		上电CPU检测
 *    [输入参数说明]：	NONE
 *	  [输出参数说明]：	NONE
 *    [其他说明]：		NONE
 *    [返回]：		NONE
 */
/* ***************************************************************** */
void PuBITCPUTest(void)
{
    Uint16 l_temp_u16 = 0U;   /* 临时数据   */
    Uint16 l_passCnt_u16 = 0U; /* 通过次数 */
    Uint16 l_tryCnt_u16 = 0U;  /* 尝试次数 */

    /* 连续测试3次，至少2次通过判定上电CPU检测正常 */
    for(l_tryCnt_u16 = 0U; l_tryCnt_u16 < PUBIT_TEST_RETRY_MAX; l_tryCnt_u16++)
    {
        /* 执行CPU测试，返回测试结果 */
        l_temp_u16 = cpuTest();

        if(CPUTEST_OK == l_temp_u16)
        {
            l_passCnt_u16 = l_passCnt_u16 + 1U;
        }

        /* 周期喂狗，避免上电自检阶段误触发看门狗 */
        CycleDogFeed();
    }

    if(l_passCnt_u16 < PUBIT_TEST_PASS_MIN)
    {
        s_puBITInfo_u16[PUBIT_INDEX_CPU] = PUBIT_TEST_ERR;
    }
}


/* ***************************************************************** */
/**
 *    [函数名]：	  PuBITCCDLTxTest
 *    [功能描述]：	     上电CCDL检测
 *    [输入参数说明]：  NONE
 *	  [输出参数说明]： NONE
 *    [其他说明]：	   NONE
 *    [返回]：	   NONE
 */
/* ***************************************************************** */
void PuBITCCDLTest(void)
{
    InitStatus_t l_initStatus_t = {0};

    /* 已在初始化阶段完成通道间握手；PuBIT 直接复用初始化结果，避免重复检测引入时序性误报。 */
    InitStatusGet(&l_initStatus_t);

    if(VALID != l_initStatus_t.interChHandshakeOk_u16)
    {
        s_puBITInfo_u16[PUBIT_INDEX_CCDL_TX] = PUBIT_TEST_ERR; /* 检测故障 */
    }
}

/* ***************************************************************** */
/**
 *    [函数名]：	  PuBITCPLDTest
 *    [功能描述]：上电CPLD检测+与CPLD的CCDL检测
 *    [输入参数说明]：  NONE
 *	  [输出参数说明]：  NONE
 *    [其他说明]：	   NONE
 *    [返回]：	   NONE
 */
/* ***************************************************************** */
void PuBITCPLDTest(void)
{
    InitStatus_t l_initStatus_t = {0};

    /* 初始化已完成通道内寄存器握手和与CPLD的CCDL心跳检测；PuBIT 直接映射这两项结果。 */
    InitStatusGet(&l_initStatus_t);

    if(VALID != l_initStatus_t.cpldBusHandshakeOk_u16)
    {
        s_puBITInfo_u16[PUBIT_INDEX_CPLD] = PUBIT_TEST_ERR; /* 记录CPLD检测故障 */
    }
    if(VALID != l_initStatus_t.cpldCcdlHeartOk_u16)
    {
        s_puBITInfo_u16[PUBIT_INDEX_CCDL_CPLD] = PUBIT_TEST_ERR;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]：	  PuBITSyncTest
 *    [功能描述]：上电通道同步检测（复用长同步结果）
 *    [输入参数说明]：  NONE
 *	  [输出参数说明]：  NONE
 *    [其他说明]：	   NONE
 *    [返回]：	   NONE
 */
/* ***************************************************************** */
void PuBITSyncTest(void)
{
    SynWholeInform_TypeDef l_syncInfo_t;  /* 同步结果 */

    /* 上电阶段以长同步结果作为通道同步检测判据 */
    l_syncInfo_t = SynWholeInfGet(SYNC_LONG_ID);
    if(SYNC_NORM != l_syncInfo_t.faltCod_un16.bit.synRelRslt)
    {
        s_puBITInfo_u16[PUBIT_INDEX_SYNC] = PUBIT_TEST_ERR;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]：	  PuBITADTest
 *    [功能描述]：上电片上AD检测（3次中至少2次正常）
 *    [输入参数说明]：  NONE
 *	  [输出参数说明]：  NONE
 *    [其他说明]：	   NONE
 *    [返回]：	   NONE
 */
/* ***************************************************************** */
void PuBITADTest(void)
{
    Uint16 l_tryCnt_u16 = 0U;   /* 尝试次数 */
    Uint16 l_passCnt_u16 = 0U;  /* 通过次数 */

    /* 复用3.3V采样状态判断片上AD通道是否可用 */
    for(l_tryCnt_u16 = 0U; l_tryCnt_u16 < PUBIT_TEST_RETRY_MAX; l_tryCnt_u16++)
    {
        if(ANA_DATA_STATE_OK == AnaDataStateGet(ANA_DINDEX_3V3))
        {
            l_passCnt_u16 = l_passCnt_u16 + 1U;
        }

        /* 每次采样间隔1ms并喂狗 */
        delayUs(333U);
        CycleDogFeed();
    }

    if(l_passCnt_u16 < PUBIT_TEST_PASS_MIN)
    {
        s_puBITInfo_u16[PUBIT_INDEX_AD] = PUBIT_TEST_ERR;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]：	  PuBITPowerSingleTest
 *    [功能描述]：上电单路电源检测（最多3次，任意一次正常则通过）
 *    [输入参数说明]：  v_index_u16  ---- 上电BIT检测索引
 *                    v_anaIndex_u16---- 模拟量索引
 *	  [输出参数说明]：  NONE
 *    [其他说明]：	   NONE
 *    [返回]：	   NONE
 */
/* ***************************************************************** */
void PuBITPowerSingleTest(Uint16 v_index_u16, Uint16 v_anaIndex_u16)
{
    Uint16 l_tryCnt_u16 = 0U;  /* 尝试次数 */
    Uint16 l_isOk_u16 = PUBIT_TEST_ERR; /* 单路电源检测结果 */

    for(l_tryCnt_u16 = 0U; l_tryCnt_u16 < PUBIT_TEST_RETRY_MAX; l_tryCnt_u16++)
    {
        if(ANA_DATA_STATE_OK == AnaDataStateGet(v_anaIndex_u16))
        {
            l_isOk_u16 = PUBIT_TEST_OK;
            break;
        }

        /* 异常时延时1ms后重试 */
        delayUs(333U);
        CycleDogFeed();
    }

    if((v_index_u16 < PUBIT_INDEX_NUM) && (PUBIT_TEST_OK != l_isOk_u16))
    {
        s_puBITInfo_u16[v_index_u16] = PUBIT_TEST_ERR;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]：	  PuBITPowerTest
 *    [功能描述]：上电电源检测（5V/3.3V/2.5V/1.2V）
 *    [输入参数说明]：  NONE
 *	  [输出参数说明]：  NONE
 *    [其他说明]：	   若上电AD检测故障，则按任务书约束跳过电源检测
 *    [返回]：	   NONE
 */
/* ***************************************************************** */
void PuBITPowerTest(void)
{
    /* AD通道异常时，不继续进行各路电源检测 */
    if(PUBIT_TEST_OK != s_puBITInfo_u16[PUBIT_INDEX_AD])
    {
        return;
    }

    PuBITPowerSingleTest(PUBIT_INDEX_P5V, s_puBITPowerTestCon_u16[1U]);
    PuBITPowerSingleTest(PUBIT_INDEX_3V3, s_puBITPowerTestCon_u16[2U]);
    PuBITPowerSingleTest(PUBIT_INDEX_2V5, s_puBITPowerTestCon_u16[3U]);
    PuBITPowerSingleTest(PUBIT_INDEX_1V2, s_puBITPowerTestCon_u16[4U]);
}

/* ***************************************************************** */
/**
 *    [函数名]：	  PuBITFlashTest
 *    [功能描述]：上电FLASH检测
 *    [输入参数说明]：  NONE
 *	  [输出参数说明]：  NONE
 *    [其他说明]：	   NONE
 *    [返回]：	   NONE
 */
/* ***************************************************************** */
void PuBITFlashTest(void)
{
    Uint16 l_ii_u16       = 0U;  /* 循环计数 */
    Uint16 l_readBuff_u16[3] = {0U,0U,0U};  /* 读取数据 */

    /* 最多读取3次，成功后跳出 */
    for(l_ii_u16 = 0U; l_ii_u16 < PUBIT_TEST_RETRY_MAX; l_ii_u16++)
    {
        /* 延时 */
        delayUs(10UL);

        /* 获取FLASH设备ID数据 */
        SpiFlashReadID(l_readBuff_u16,3U);

        /* FLASH设备ID不正确时  */
        if(FLASH_DEVICE_ID == l_readBuff_u16[0])
        {
            /* 跳出FOR */
            break;
        }
    }

    /* 超时未读取正确数据 */
    if(l_ii_u16 >= PUBIT_TEST_RETRY_MAX)
    {
        /* 记录FLASH测试故障信息 */
        s_puBITInfo_u16[PUBIT_INDEX_FLASH] = PUBIT_TEST_ERR;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]：	  PuBITTest
 *    [功能描述]：	     上电自检
 *    [输入参数说明]：  NONE
 *	  [输出参数说明]： NONE
 *    [其他说明]：	  仅冷启动路径调用；热复位路径使用PuBITHotResetBypassInit()做静默初始化
 *    [返回]：	  上电BIT检测结果，可能取值如下：
 *          PUBIT_TEST_OK  ---- 检测结果正常
 *          PUBIT_TEST_ERR ---- 检测结果异常
 */
/* ***************************************************************** */
Uint16 PuBITTest(void)
{
    Uint16 l_index_u16 = 0U;  /* 索引 */

    /* 上电BIT信息数据初始化为检测正常  */
    for( l_index_u16 = 0U; l_index_u16 < PUBIT_INDEX_NUM; l_index_u16++)
    {
        s_puBITInfo_u16[l_index_u16] = PUBIT_TEST_OK;
    }

    /******************************/
    /* CPU检测 */
    PuBITCPUTest();

    /* 上电FLASH检测  */
    PuBITFlashTest();

    /* 上电CPLD检测  */
    PuBITCPLDTest();

    /* 上电CCDL检测  */
    PuBITCCDLTest();

    /* 上电通道同步检测 */
    PuBITSyncTest();

    /* 上电AD通道检测 */
    PuBITADTest();

    /* 上电电源检测 */
    PuBITPowerTest();


    /* 记录PUBIT检测结果 */
    PuBITDataRebuild();

    /* 返回上电BIT结果 */
    return s_puBITData_u16;
}

/* ========================================================================== */
/* END OF FILE */
/* ========================================================================== */
