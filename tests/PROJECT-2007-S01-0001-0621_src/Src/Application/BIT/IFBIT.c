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
* 文件名称:   IFBIT
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
* 本模块实现周期BIT检测
*
*********************************************************************************/

#include "Global.h"

/***********************************************/
/* 周期BIT本地变量 */

IFBITData_t s_IFBITDataBuff_t[IFBIT_NUM]; 		 /* 周期自检信息结构体    */
Uint16 s_IFBITFaultLevel_u16;                 /* 周期BIT故障处理等级 */
Uint32 s_IFBITDataBit00To31_u32;              /* 周期BIT总检测结果低32位 */

/***********************************************/
/* 周期BIT配置表 */
IFBITDataConf_t s_IFBITDataConfBuff_t[IFBIT_NUM] =
   {
        /*   是否可恢复      | 报故次数 | 恢复次数 | 故障处理等级   */
        {  IFBIT_UN_RECOABLE     ,    60U   ,    1U    , IFBIT_FLEVEL_1  }, /* 0周期自检  +5V电源检测          (600ms) */
        {  IFBIT_UN_RECOABLE     ,    60U   ,    1U    , IFBIT_FLEVEL_1  }, /* 1周期自检  3.3V电源检测         (600ms) */
        {  IFBIT_UN_RECOABLE     ,    60U   ,    1U    , IFBIT_FLEVEL_1  }, /* 2周期自检  2.5V电源检测         (600ms) */
        {  IFBIT_UN_RECOABLE     ,    60U   ,    1U    , IFBIT_FLEVEL_1  }, /* 3周期自检  1.2V电源检测         (600ms) */
        {  IFBIT_UN_RECOABLE     ,    1U    ,    1U    , IFBIT_FLEVEL_1  }, /* 4周期自检  二次电源检测 */
        {  IFBIT_UN_RECOABLE     ,    1U    ,    1U    , IFBIT_FLEVEL_1  }, /* 5周期自检  三次电源检测 */
        {  IFBIT_UN_RECOABLE     ,    10U   ,    1U    , IFBIT_FLEVEL_1  }, /* 6周期自检 CPLD心跳检测 */
        {  IFBIT_RECOABLE        ,    40U   ,    2U    , IFBIT_FLEVEL_0  }, /* 7周期自检 板间SCI通信检测       (400ms, 连续2次恢复) */
        {  IFBIT_RECOABLE        ,    40U   ,    2U    , IFBIT_FLEVEL_0  }, /* 8周期自检 板间心跳检测          (400ms, 连续2次恢复) */
        {  IFBIT_RECOABLE        ,    20U   ,    2U    , IFBIT_FLEVEL_0  }, /* 9周期自检 与CPLD的CCDL检测      (200ms, 连续2次恢复) */
        {  IFBIT_RECOABLE        ,    40U   ,    1U    , IFBIT_FLEVEL_0  }, /* 10周期自检 帧同步检测           (400ms) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 11周期自检 RIU通道1检测         (1s, 60ms恢复) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 12周期自检 RIU通道2检测         (1s, 60ms恢复) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 13周期自检 RIU通道3检测         (1s, 60ms恢复) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 14周期自检 RIU综合检测          (1s, 60ms恢复) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 15周期自检 左吊舱接收检测       (1s, 60ms恢复) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 16周期自检 右吊舱接收检测       (1s, 60ms恢复) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 17周期自检 KZZZ接收综合检测     (1s, 60ms恢复) */
        {  IFBIT_UN_RECOABLE     ,    60U   ,    1U    , IFBIT_FLEVEL_1  }, /* 18周期自检 片上AD通道检测       (600ms) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 19周期自检 RIU发送回绕检测      (1s, 60ms恢复) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 20周期自检 左吊舱发送回绕检测   (1s, 60ms恢复) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 21周期自检 右吊舱发送回绕检测   (1s, 60ms恢复) */
        {  IFBIT_RECOABLE        ,   100U   ,    6U    , IFBIT_FLEVEL_0  }, /* 22周期自检 429发送综合检测      (1s, 60ms恢复) */
   };

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
Uint32 IFBITInfoGet(Uint16 v_index_u16)
{
    return BITCommonInfoGet(s_IFBITDataBuff_t, IFBIT_NUM, v_index_u16);
}

/* ***************************************************************** */
/**
 *    [函数名]	IFBITResultGet
 *
 *    [功能描述]	周期BIT检测结果获取
 *
 *    [输入参数说明] v_index_u16 ---- 拟获取数据索引，可能取值如下：
 *                IFBIT_DINDEX_FLEVEL ---- 周期BIT综合故障处理等级
 *                IFBIT_DINDEX_RESULTS_BIT32_L ---- 周期BIT结果数据低32位
 *                IFBIT_DINDEX_RESULTS_BIT32_H ---- 周期BIT结果数据高32位
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  周期BIT检测结果
 */
/* ***************************************************************** */
Uint32 IFBITResultGet(Uint16 v_index_u16)
{
    Uint32 l_rData_u32 = 0UL;  /* 结果数据 */

    /* 获取周期BIT故障等级 */
    if( IFBIT_DINDEX_FLEVEL == v_index_u16 )
    {
        l_rData_u32 = s_IFBITFaultLevel_u16 & 0x07U;
    }

    /* 获取周期BIT前32BIT结果 */
    else if( IFBIT_DINDEX_RESULTS_BIT32_1 == v_index_u16 )
    {
        l_rData_u32 = s_IFBITDataBit00To31_u32;
    }
    else
    {
        /* no deal to do */
    }

    /* 返回结果 */
    return l_rData_u32;
}

/* ***************************************************************** */
/**
 *    [函数名]	IFBITStateUpdate
 *
 *    [功能描述]	更新IFBIT检测项状态信息
 *    			当故障计数达到故障阈值时，更新该检测项状态为故障；
 *    			若该故障为可恢复故障时，且故障恢复计数达到阈值时，更新该检测项状态为正常。故障计数或故障恢复计数均为连续计数。
 *    [输入参数说明] v_index_u16 ---- 周期自检项索引
 *    			  v_newState_u16 ---- 该检测项的新的检测状态，可能取值为：
 *                         IFBIT_TEST_OK ---- 检测项检测结果为通过
 *                         IFBIT_TEST_ERR ---- 检测项检测结果为未通过
 *                v_info_u32 ---- 该检测项与检测相关的信息
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void IFBITStateUpdate(Uint16 v_index_u16, Uint16 v_newState_u16, Uint32 v_info_u32)
{
    BITCommonCtxInit(&s_IFBITDataBit00To31_u32,
                     &s_IFBITFaultLevel_u16);

    BITCommonStateUpdate(s_IFBITDataBuff_t,
                         IFBIT_NUM,
                         v_index_u16,
                         v_newState_u16,
                         v_info_u32);
}


/* ***************************************************************** */
/**
 *    [函数名]	IFBITComm429RIUTest
 *
 *    [功能描述]	周期远程接口单元429通讯检测
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		 NONE
 */
/* ***************************************************************** */
static void IFBITComm429RIUTest(void)
{
     Uint16 l_index_u16    = 0U;  /* 索引         */
     Uint16 l_temp_u16     = 0U;  /* 临时数据 */
     Uint16 l_okCnt_u16    = 0U;  /* 正常计数  */
     Uint16 l_results_u16  = IFBIT_TEST_OK;  /* 检测结果  */
     A429Info_t l_RIU429Info_t;  /* 远程接口单元429通讯信息 */

     /**********远程接口单元1通讯检测***********/
     /* 获取远程接口单元1通讯状态 */
     l_RIU429Info_t = Comm429RIURxStateGet(COMM429_RIU_1);

     /* 通信接收状态异常时  */
     if(RX429_STATE_OK != (l_RIU429Info_t.rxState_u16 | l_RIU429Info_t.rxDataState_u16))
     {
         l_results_u16 = IFBIT_TEST_ERR; /* 检测异常 */
     }

     /* 更新IFBIT数据结构体信息 */
     IFBITStateUpdate(IFBIT_INDEX_COMM_429RIU_1,l_results_u16,0UL);

     /**********远程接口单元2通讯检测***********/
     l_results_u16 = IFBIT_TEST_OK; /* 检测初始正常 */

     /* 获取远程接口单元2通讯状态 */
     l_RIU429Info_t = Comm429RIURxStateGet(COMM429_RIU_2);

     /* 通信接收状态异常时  */
     if(RX429_STATE_OK != (l_RIU429Info_t.rxState_u16 | l_RIU429Info_t.rxDataState_u16))
     {
         l_results_u16 = IFBIT_TEST_ERR; /* 检测异常 */
     }

     /* 更新IFBIT数据结构体信息 */
     IFBITStateUpdate(IFBIT_INDEX_COMM_429RIU_2,l_results_u16,0UL);

     /**********远程接口单元3通讯检测***********/
     l_results_u16 = IFBIT_TEST_OK; /* 检测初始正常 */

     /* 获取远程接口单元2通讯状态 */
     l_RIU429Info_t = Comm429RIURxStateGet(COMM429_RIU_3);

     /* 通信接收状态异常时  */
     if(RX429_STATE_OK != (l_RIU429Info_t.rxState_u16 | l_RIU429Info_t.rxDataState_u16))
     {
         l_results_u16 = IFBIT_TEST_ERR; /* 检测异常 */
     }

     /* 更新IFBIT数据结构体信息 */
     IFBITStateUpdate(IFBIT_INDEX_COMM_429RIU_3,l_results_u16,0UL);

     /**********远程接口单元综合通讯检测***********/
     l_results_u16 = IFBIT_TEST_OK; /* 检测初始正常 */

     /* 查询通信检查故障几路 */
     for(l_index_u16 = 0U;l_index_u16 < COMM429_RIU_NUM;l_index_u16++)
     {
         /* 获取检测结果 */
         l_temp_u16 = IFBITInfoGet(IFBIT_INDEX_COMM_429RIU_1 + l_index_u16);

         /* 检测结果为正常 */
         if(IFBIT_TEST_OK == l_temp_u16)
         {
             l_okCnt_u16 = l_okCnt_u16 + 1U; /* 计数加1 */
         }
     }

     /* 任一路通信故障时，综合通讯故障。 */
     if(l_okCnt_u16 < COMM429_RIU_NUM)
     {
         l_results_u16 = IFBIT_TEST_ERR; /* 检测异常 */
     }

     /* 更新IFBIT数据结构体信息 */
     IFBITStateUpdate(IFBIT_INDEX_COMM_429RIU,l_results_u16,0UL);
}

/* ***************************************************************** */
/**
 * 【函数名】:IFBITComm429KZZZTest
 * 【功能描述】IFBIT 429 KZZZ 通信检测,通过KZZZ通道收发数据进行周期自检
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static void IFBITComm429KZZZTest(void)
{
     Uint16 l_results_u16 = IFBIT_TEST_OK;
     Uint16 l_okCnt_u16 = 0U;
     Uint16 l_temp_u16 = 0U;
     A429Info_t l_kzzzInfo_t;
     memset(&l_kzzzInfo_t, 0, sizeof(l_kzzzInfo_t));

     l_kzzzInfo_t = Comm429KZZZRxStateGet(COMM429_KZZZ_1);
     if(RX429_STATE_OK != (l_kzzzInfo_t.rxState_u16 | l_kzzzInfo_t.rxDataState_u16))
     {
         l_results_u16 = IFBIT_TEST_ERR;
     }
     IFBITStateUpdate(IFBIT_INDEX_COMM_429LEFT_RX, l_results_u16, 0UL);

     l_results_u16 = IFBIT_TEST_OK;
     l_kzzzInfo_t = Comm429KZZZRxStateGet(COMM429_KZZZ_2);
     if(RX429_STATE_OK != (l_kzzzInfo_t.rxState_u16 | l_kzzzInfo_t.rxDataState_u16))
     {
         l_results_u16 = IFBIT_TEST_ERR;
     }
     IFBITStateUpdate(IFBIT_INDEX_COMM_429RIGHT_RX, l_results_u16, 0UL);

     l_results_u16 = IFBIT_TEST_OK;
     for(l_temp_u16 = 0U; l_temp_u16 < COMM429_KZZZ_NUM; l_temp_u16++)
     {
         if(IFBIT_TEST_OK == IFBITInfoGet(IFBIT_INDEX_COMM_429LEFT_RX + l_temp_u16))
         {
             l_okCnt_u16 += 1U;
         }
     }
     if(l_okCnt_u16 < COMM429_KZZZ_NUM)
     {
         l_results_u16 = IFBIT_TEST_ERR;
     }
     IFBITStateUpdate(IFBIT_INDEX_COMM_429KZZZ, l_results_u16, 0UL);
}



/* ***************************************************************** */
/**
 *    [函数名]	IFBITCommCCDLTest
 *
 *    [功能描述]	周期CCDL通信检测
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
static void IFBITCommSCICCDLTest(void)
{
     Uint16 l_results_u16    = IFBIT_TEST_OK;  /* 检测结果     */
     Uint16 l_heart_u16 = 0U;  /* 对方通道DSP心跳 */
     static Uint16 l_heartPre_u16 = 0U;  /* 对方通道DSP前一拍心跳 */

     /* 获取CCDL通信数据  */
     /* CCDL通信基础帧本拍未推进时判异常。 */
    if( VALID != CommCCDLPeerBaseAdvancedGet(COMM_CCDL_SCI) )
    {
        l_results_u16 = IFBIT_TEST_ERR; /* 检测异常 */
    }

    IFBITStateUpdate(IFBIT_INDEX_COMM_CCDL_SCI,l_results_u16,0UL);

    l_results_u16 = IFBIT_TEST_OK;
    l_heart_u16 = GPIOReadBitNum(GPIO_IN_DSP_HEART);

    if(l_heart_u16 == l_heartPre_u16)
    {
        l_results_u16 = IFBIT_TEST_ERR; /* 检测异常 */
    }

    IFBITStateUpdate(IFBIT_INDEX_COMM_DPV_HEART,l_results_u16,0UL);

    l_heartPre_u16 = l_heart_u16;

}

/* ***************************************************************** */
/**
 *    [函数名]	IFBITSyncTest
 *
 *    [功能描述]	周期同步检测
 *    			检测帧同步结果是否正常
 *
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
static void IFBITSyncTest(void)
{
    Uint16 l_results_u16 = IFBIT_TEST_OK;        /* 检测结果      */
    SynWholeInform_TypeDef l_SynWholeInform_t; /* 帧同步数据  */

    /* 获取帧同步结果  */
    l_SynWholeInform_t = SynWholeInfGet(SYNC_FRAME_ID);

    /* 帧同步结果异常时 */
    if(SYNC_NORM != l_SynWholeInform_t.faltCod_un16.bit.synRelRslt)
    {
        /* 帧同步结果异常时，检测异常 */
        l_results_u16 = IFBIT_TEST_ERR;
    }

    /* 更新IFBIT数据结构体信息 */
    IFBITStateUpdate(IFBIT_INDEX_FRAME_SYNC ,l_results_u16,0UL);
}

/* ***************************************************************** */
/**
 *    [函数名]	CPLDHeartTest
 *
 *    [功能描述]	CPLD心跳检测
 *
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
static void IFBITCPLDHeartTest(void)
{
    Uint16 l_results_u16 = IFBIT_TEST_OK;   /* 检测结果   */
    static Uint16 l_s_heartLast_u16 = 0U;  /* 上一CPLDA心跳    */
    Uint16 l_heart_u16 = 0U;  /* CPLD心跳 */

    /* 读取CPLD心跳 */
    l_heart_u16 = HardXintUint16Read(CPLD_ADDR_R_CPLD_HEART);

    /* 前后两拍心跳相等，心跳未更新  */
    if(l_s_heartLast_u16 == l_heart_u16)
    {
        l_results_u16 = IFBIT_TEST_ERR; /* 检测结果异常 */
    }

    /* 更新上一CPLDA心跳  */
    l_s_heartLast_u16 = l_heart_u16;

    /* 更新IFBIT数据结构体信息 */
    IFBITStateUpdate(IFBIT_INDEX_CPLD_HEART,l_results_u16,0UL);
}

/* ***************************************************************** */
/**
 *    [函数名]	IFBITCPLDCCDLTest
 *
 *    [功能描述]	CPLD心跳检测
 *
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
static void IFBITCPLDCCDLTest(void)
{
    Uint16 l_results_u16 = IFBIT_TEST_OK;   /* 检测结果   */
    static Uint16 l_s_heartLast_u16 = 0U;  /* 上一拍CCDL的CPLD心跳    */
    Uint16 l_heart_u16 = 0U;  /* CCDL的CPLD心跳 */
    PeerBaseStatus_t l_peerBase_t; /* 对端基础帧快照 */

    l_peerBase_t = CommCCDLPeerBaseGet(COMM_CCDL_CPLD);
    /* 读取CCDL的CPLD心跳 */
    l_heart_u16 = l_peerBase_t.cpldHeart_u16;

    /* 前后两拍心跳相等，心跳未更新  */
    if(l_s_heartLast_u16 == l_heart_u16)
    {
        l_results_u16 = IFBIT_TEST_ERR; /* 检测结果异常 */
    }

    /* 更新上一CPLDA心跳  */
    l_s_heartLast_u16 = l_heart_u16;

    /* 更新IFBIT数据结构体信息 */
    IFBITStateUpdate(IFBIT_INDEX_COMM_CCDL_CPLD,l_results_u16,0UL);
}



/* ***************************************************************** */
/**
 *    [函数名]	IFBITComm429RIUTxTest
 *
 *    [功能描述]	RIU 429发送回绕检测
 *               通过CPLD硬件回绕FIFO读取发送数据，与最近一次发送值比对。
 *
 *    [输入参数说明] NONE
 *    [输出参数说明] NONE
 *    [其他说明]    可恢复故障，任务书3.2-0020 ARINC429发送检测
 *    [返回]		 NONE
 */
/* ***************************************************************** */
static void IFBITComm429RIUTxTest(void)
{
    Uint16 l_results_u16 = IFBIT_TEST_OK;  /* 检测结果 */

    l_results_u16 = BITCommon429LoopbackResultGet(Comm429RIUTxLastWordGet(),
                                                  COMM429_9_REG_LOOPBACK_EN,
                                                  COMM429_9_REG_LOOPBACK_CNT,
                                                  COMM429_9_REG_LOOPBACK_L,
                                                  COMM429_9_REG_LOOPBACK_H);

    /* 更新IFBIT数据结构体信息 */
    IFBITStateUpdate(IFBIT_INDEX_COMM_429TX_RIU, l_results_u16, 0UL);
}
/* ***************************************************************** */
/**
 *    [函数名]	IFBITComm429KZZZTxTest
 *
 *    [功能描述]	左/右吊舱429发送回绕检测及429发送综合检测
 *
 *    [输入参数说明] NONE
 *    [输出参数说明] NONE
 *    [其他说明]    左右吊舱回绕寄存器地址待补充，当前默认正常
 *    [返回]		 NONE
 */
/* ***************************************************************** */
static void IFBITComm429KZZZTxTest(void)
{
    Uint16 l_results_u16 = IFBIT_TEST_OK;  /* 检测结果 */
    Uint16 l_okCnt_u16 = 0U;               /* 正常计数 */
    Uint16 l_txResult_u16 = IFBIT_TEST_OK; /* 单路检测结果 */

    /* 左吊舱发送回绕检测 (通道0) */
    l_txResult_u16 = BITCommon429LoopbackResultGet(Comm429KZZZTxLastWordGet(0U),
                                                   COMM429_10_REG_LOOPBACK_EN,
                                                   COMM429_10_REG_LOOPBACK_CNT,
                                                   COMM429_10_REG_LOOPBACK_L,
                                                   COMM429_10_REG_LOOPBACK_H);
    IFBITStateUpdate(IFBIT_INDEX_COMM_429TX_LEFT, l_txResult_u16, 0UL);

    /* 右吊舱发送回绕检测 (通道1) */
    l_txResult_u16 = BITCommon429LoopbackResultGet(Comm429KZZZTxLastWordGet(1U),
                                                   COMM429_11_REG_LOOPBACK_EN,
                                                   COMM429_11_REG_LOOPBACK_CNT,
                                                   COMM429_11_REG_LOOPBACK_L,
                                                   COMM429_11_REG_LOOPBACK_H);
    IFBITStateUpdate(IFBIT_INDEX_COMM_429TX_RIGHT, l_txResult_u16, 0UL);

    /* 429发送综合检测：任一路发送故障则综合故障 */
    l_okCnt_u16 = BITCommonOkCountGet(s_IFBITDataBuff_t,
                                      IFBIT_NUM,
                                      IFBIT_INDEX_COMM_429TX_RIU,
                                      3U);
    if(l_okCnt_u16 < 3U)
    {
        l_results_u16 = IFBIT_TEST_ERR;
    }
    /* 更新IFBIT数据结构体信息 */
    IFBITStateUpdate(IFBIT_INDEX_COMM_429TX, l_results_u16, 0UL);
}
/* ***************************************************************** */
/**
 *    [函数名]	IFBITTest
 *
 *    [功能描述]	周期自检
 *
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		 NONE
 */
/* ***************************************************************** */
void IFBITTest(void)
{
    const ConData_t *lc_p_conData_t = NULL; /* 系统控制数据指针      */
    Uint16 l_ii_u16 = 0U;  /* 索引  */

    BITCommonCtxInit(&s_IFBITDataBit00To31_u32,
                     &s_IFBITFaultLevel_u16);

    /* 获取系统控制数据 */
    lc_p_conData_t = ConDataGet();

    /* 周期BIT仅在工作/安全状态执行，维护状态由MBIT承担 */
    if( ( SYS_STATE_1WORK == lc_p_conData_t->sysState_u16) \
     || ( SYS_STATE_2SAFETY     == lc_p_conData_t->sysState_u16))
    {
        /* 周期电源检测 */
        BITCommonPowerTest(s_IFBITDataBuff_t,
                           IFBIT_NUM,
                           IFBIT_INDEX_P5V);

        /* 周期CPLD心跳检测  */
        IFBITCPLDHeartTest();

        /* 周期与CPLD的CCDL检测  */
        IFBITCPLDCCDLTest();

        /* 429通信属于周期BIT常规监控项，进入周期工作后立即检测。 */
        IFBITComm429RIUTest();   /* 周期远程接口单元429通讯检测   */
        IFBITComm429KZZZTest();  /* 周期KZZZ429通讯检测 */

        /* 周期板间SCI通信检测   */
        IFBITCommSCICCDLTest();

        /* 周期同步检测 */
        IFBITSyncTest();

        /* 周期片上AD通道检测 */
        IFBITStateUpdate(IFBIT_INDEX_AD,
                         BITCommonADResultGet(),
                         0UL);

        /* 周期429发送回绕检测 */
        IFBITComm429RIUTxTest();
        IFBITComm429KZZZTxTest();
//
//        /* CPLD组合故障判定：CPLD心跳故障 + CPLD CCDL故障同时出现 → 强制FLEVEL_1 */
//        if((IFBIT_TEST_ERR == IFBITInfoGet(IFBIT_INDEX_CPLD_HEART)) \
//         && (IFBIT_TEST_ERR == IFBITInfoGet(IFBIT_INDEX_COMM_CCDL_CPLD)))
//        {
//            s_IFBITFaultLevel_u16 = IFBIT_FLEVEL_1;
//        }
//
//        /* 板间通信组合故障判定：板间CCDL故障 + 板间心跳故障同时出现 → 强制FLEVEL_1 */
//        if((IFBIT_TEST_ERR == IFBITInfoGet(IFBIT_INDEX_COMM_CCDL_SCI)) \
//         && (IFBIT_TEST_ERR == IFBITInfoGet(IFBIT_INDEX_COMM_DPV_HEART)))
//        {
//            s_IFBITFaultLevel_u16 = IFBIT_FLEVEL_1;
//        }
    }
    else /* 在不进行检测的系统状态中，需将连续计数清零 */
    {
        for( l_ii_u16 = 0U; l_ii_u16 < IFBIT_NUM; l_ii_u16++ )
        {
            s_IFBITDataBuff_t[l_ii_u16].faultCount_u16 = 0U; /* 故障计数清零                 */
            s_IFBITDataBuff_t[l_ii_u16].recoCount_u16  = 0U;	/* 恢复计数清零                 */
        }
    }

}

/* ***************************************************************** */
/**
 *    [函数名]	IFBITDataInit
 *
 *    [功能描述]	周期BIT信息初始化
 *
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void IFBITDataInit(void)
{
    BITCommonCtxInit(&s_IFBITDataBit00To31_u32,
                     &s_IFBITFaultLevel_u16);

       Uint16 l_ii_u16 = 0U;  /* 索引  */

       for( l_ii_u16 = 0U; l_ii_u16 < IFBIT_NUM; l_ii_u16++ )
       {
           s_IFBITDataBuff_t[l_ii_u16].currState_u16  = IFBIT_TEST_OK;  /* 当前状态初始化为正常  */
           s_IFBITDataBuff_t[l_ii_u16].errInfo_u32    = 0UL;           /* 故障信息清零                 */
           s_IFBITDataBuff_t[l_ii_u16].faultCount_u16 = 0U;            /* 故障计数清零                 */
           s_IFBITDataBuff_t[l_ii_u16].recoCount_u16  = 0U;			  /* 恢复计数清零                 */

           /* 获取故障等级配置信息   */
           s_IFBITDataBuff_t[l_ii_u16].faultLevel_u16 = s_IFBITDataConfBuff_t[l_ii_u16].faultLevel_u16;

           /* 获取故障恢复配置信息   */
           s_IFBITDataBuff_t[l_ii_u16].recoAble_u16   = s_IFBITDataConfBuff_t[l_ii_u16].recoAble_u16;

           /* 获取故障报故计数  */
           s_IFBITDataBuff_t[l_ii_u16].faultValidCount_u16 = s_IFBITDataConfBuff_t[l_ii_u16].faultValidCount_u16;

           /* 获取故障恢复计数  */
           s_IFBITDataBuff_t[l_ii_u16].recoValidCount_u16  = s_IFBITDataConfBuff_t[l_ii_u16].recoValidCount_u16;
       }

       s_IFBITFaultLevel_u16 = IFBIT_FLEVEL_0;          /* 周期BIT故障处理等级清零 */
       s_IFBITDataBit00To31_u32 = IFBIT_TEST_OK;        /* 周期BIT总检测结果低32位清零 */
}

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
