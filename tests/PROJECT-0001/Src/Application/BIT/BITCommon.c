/**********************************************************************************
 *
 * 文件名称:   BITCommon
 *
 * 功能说明:   IFBIT/MBIT共用状态查询与状态更新逻辑
 *
 *********************************************************************************/

#include "Global.h"
#include "BITCommon.h"

/* BITCommon 模块当前激活上下文的模块全局指针(由 IFBIT/MBIT 初始化时通过 BITCommonCtxInit 设置) */
static Uint32 *s_ctx_pResultBits_u32  = NULL;
static Uint16 *s_ctx_pFaultLevel_u16  = NULL;
static const Uint16 sc_BITPowerTestConBuff[BIT_COMMON_POWER_TEST_NUM] =
{
    ANA_DINDEX_V28,
    ANA_DINDEX_V5,
    ANA_DINDEX_3V3,
    ANA_DINDEX_2V5,
    ANA_DINDEX_1V2
};

/* ***************************************************************** */
/**
 *    [函数名]    BITCommonCtxInit
 *
 *    [功能描述]  设置当前 BIT 上下文(由 IFBIT/MBIT 初始化时调用一次)
 */
/* ***************************************************************** */
void BITCommonCtxInit(Uint32 *vp_resultBits_u32,
                     Uint16 *vp_faultLevel_u16)
{
    s_ctx_pResultBits_u32  = vp_resultBits_u32;
    s_ctx_pFaultLevel_u16  = vp_faultLevel_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]    BITCommonInfoGet
 *
 *    [功能描述]  获取BIT检测项当前状态
 *
 *    [输入参数说明] vp_data_t ---- BIT检测项数据表
 *                  v_num_u16 ---- BIT检测项数量
 *                  v_index_u16 ---- 检测项索引
 *    [返回]        BIT检测项状态
 */
/* ***************************************************************** */
Uint32 BITCommonInfoGet(const BITCommonData_t *vp_data_t,
                        Uint16 v_num_u16,
                        Uint16 v_index_u16)
{
    Uint32 l_rData_u32 = BIT_TEST_OK;

    if((NULL != vp_data_t) && (v_index_u16 < v_num_u16))
    {
        l_rData_u32 = vp_data_t[v_index_u16].currState_u16;
    }

    return l_rData_u32;
}

/* ***************************************************************** */
/**
 *    [函数名]    BITCommonStateUpdate
 *
 *    [功能描述]  更新BIT检测项状态信息
 *
 *    [输入参数说明] vp_data_t ---- BIT检测项数据表
 *                  v_num_u16 ---- BIT检测项数量
 *                  v_index_u16 ---- 检测项索引
 *                  v_newState_u16 ---- 检测项新的检测状态
 *                  v_info_u32 ---- 检测相关故障信息
 *                  v_okState_u16 ---- 正常状态值
 *                  v_errState_u16 ---- 故障状态值
 *                  v_recoAble_u16 ---- 可恢复故障标识
 *                  vp_resultBits_u32 ---- BIT结果位图
 *                  vp_faultLevel_u16 ---- BIT综合故障等级
 *    [返回]        NONE
 */
/* ***************************************************************** */
void BITCommonStateUpdate(BITCommonData_t *vp_data_t,
                          Uint16 v_num_u16,
                          Uint16 v_index_u16,
                          Uint16 v_newState_u16,
                          Uint32 v_info_u32)
{
    BITCommonData_t *lp_item_t;

    if((NULL == vp_data_t) || (NULL == s_ctx_pResultBits_u32) || (NULL == s_ctx_pFaultLevel_u16))
    {
        return;
    }

    if(v_index_u16 >= v_num_u16)
    {
        return;
    }

    lp_item_t = &vp_data_t[v_index_u16];

    if(BIT_TEST_ERR == lp_item_t->currState_u16)
    {
        if(BIT_RECOABLE == lp_item_t->recoAble_u16)
        {
            if(BIT_TEST_OK == v_newState_u16)
            {
                lp_item_t->recoCount_u16 = lp_item_t->recoCount_u16 + 1U;

                if(lp_item_t->recoCount_u16 >= lp_item_t->recoValidCount_u16)
                {
                    lp_item_t->currState_u16  = BIT_TEST_OK;
                    lp_item_t->faultCount_u16 = 0U;
                    lp_item_t->recoCount_u16  = 0U;

                    if(v_index_u16 < 32U)
                    {
                        *s_ctx_pResultBits_u32 = *s_ctx_pResultBits_u32 & (~(0x01UL << v_index_u16));
                    }
                }
            }
            else
            {
                lp_item_t->recoCount_u16 = 0U;
            }
        }
    }
    else
    {
        if(BIT_TEST_OK == v_newState_u16)
        {
            lp_item_t->faultCount_u16 = 0U;
        }
        else
        {
            lp_item_t->faultCount_u16 = lp_item_t->faultCount_u16 + 1U;

            if(lp_item_t->faultCount_u16 >= lp_item_t->faultValidCount_u16)
            {
                lp_item_t->currState_u16  = BIT_TEST_ERR;
                lp_item_t->faultCount_u16 = 0U;
                lp_item_t->recoCount_u16  = 0U;
                lp_item_t->errInfo_u32    = v_info_u32;

                if(v_index_u16 < 32U)
                {
                    *s_ctx_pResultBits_u32 = *s_ctx_pResultBits_u32 | (0x01UL << v_index_u16);
                }

                if(lp_item_t->faultLevel_u16 > *s_ctx_pFaultLevel_u16)
                {
                    *s_ctx_pFaultLevel_u16 = lp_item_t->faultLevel_u16;
                }
            }
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]    BITCommonPowerTest
 *
 *    [功能描述]  IFBIT/MBIT共用电源检测
 *
 *    [返回]      NONE
 */
/* ***************************************************************** */
void BITCommonPowerTest(BITCommonData_t *vp_data_t,
                        Uint16 v_num_u16,
                        Uint16 v_bitStartIndex_u16)
{
    Uint16 l_index_u16 = 0U;
    Uint16 l_results_u16 = BIT_TEST_OK;

    for(l_index_u16 = 1U; l_index_u16 < BIT_COMMON_POWER_TEST_NUM; l_index_u16++)
    {
        l_results_u16 = BIT_TEST_OK;

        if(ANA_DATA_STATE_OK != AnaDataStateGet(sc_BITPowerTestConBuff[l_index_u16]))
        {
            l_results_u16 = BIT_TEST_ERR;
        }

        BITCommonStateUpdate(vp_data_t,
                             v_num_u16,
                             v_bitStartIndex_u16 + l_index_u16 - 1U,
                             l_results_u16,
                             0UL);
    }
}

/* ***************************************************************** */
/**
 *    [函数名]    BITCommonADResultGet
 *
 *    [功能描述]  片上AD通道检测结果获取
 *
 *    [返回]      BIT检测状态
 */
/* ***************************************************************** */
Uint16 BITCommonADResultGet(void)
{
    Uint16 l_results_u16 = BIT_TEST_OK;

    if(ANA_DATA_STATE_OK != AnaDataStateGet(ANA_DINDEX_3V3))
    {
        l_results_u16 = BIT_TEST_ERR;
    }

    return l_results_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]    BITCommon429LoopbackResultGet
 *
 *    [功能描述]  429发送硬件回绕比对结果获取
 *                先向 EN 地址写 1 触发一次回绕读使能，
 *                硬件回环完成后从 FIFO 读出回绕数据与最近发送值比对。
 *
 *    [输入参数说明]v_lastTxData_u32    ---- 最近一次发送的429原始数据
 *                v_loopbackEnAddr_u16  ---- 回绕读使能寄存器地址(DSP 写 1 触发)
 *                v_loopbackCntAddr_u16 ---- 回绕FIFO可读计数寄存器地址
 *                v_loopbackLAddr_u16   ---- 回绕低2字节寄存器地址
 *                v_loopbackHAddr_u16   ---- 回绕高2字节寄存器地址
 *    [返回]      BIT检测状态
 */
/* ***************************************************************** */
Uint16 BITCommon429LoopbackResultGet(Uint32 v_lastTxData_u32,
                                     Uint16 v_loopbackEnAddr_u16,
                                     Uint16 v_loopbackCntAddr_u16,
                                     Uint16 v_loopbackLAddr_u16,
                                     Uint16 v_loopbackHAddr_u16)
{
    Uint16 l_results_u16 = BIT_TEST_OK;
    Uint16 l_loopbackCnt_u16 = 0U;
    Uint16 l_dataL_u16 = 0U;
    Uint16 l_dataH_u16 = 0U;
    Uint32 l_loopbackData_u32 = 0UL;

    if(0UL != v_lastTxData_u32)
    {
        /* DSP 向 EN 地址写 1 触发一次硬件回绕读 */
        *(volatile Uint16 *)(v_loopbackEnAddr_u16) = 0x01U;

        l_loopbackCnt_u16 = *(volatile Uint16 *)(v_loopbackCntAddr_u16);
        if(l_loopbackCnt_u16 > 0U)
        {
            l_dataL_u16 = *(volatile Uint16 *)(v_loopbackLAddr_u16);
            l_dataH_u16 = *(volatile Uint16 *)(v_loopbackHAddr_u16);
            l_loopbackData_u32 = ((Uint32)l_dataH_u16 << 16U) | (Uint32)l_dataL_u16;

            if(l_loopbackData_u32 != v_lastTxData_u32)
            {
                l_results_u16 = BIT_TEST_ERR;
            }
        }
        else
        {
            l_results_u16 = BIT_TEST_ERR;
        }
    }

    return l_results_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]    BITCommonOkCountGet
 *
 *    [功能描述]  获取连续BIT检测项中正常项数量
 *
 *    [返回]      正常项数量
 */
/* ***************************************************************** */
Uint16 BITCommonOkCountGet(const BITCommonData_t *vp_data_t,
                           Uint16 v_num_u16,
                           Uint16 v_startIndex_u16,
                           Uint16 v_count_u16)
{
    Uint16 l_index_u16 = 0U;
    Uint16 l_okCnt_u16 = 0U;

    for(l_index_u16 = 0U; l_index_u16 < v_count_u16; l_index_u16++)
    {
        if(BIT_TEST_OK == BITCommonInfoGet(vp_data_t,
                                                 v_num_u16,
                                                 v_startIndex_u16 + l_index_u16))
        {
            l_okCnt_u16 = l_okCnt_u16 + 1U;
        }
    }

    return l_okCnt_u16;
}

/* =============================================================================== */
/* END OF FILE */
/* =============================================================================== */
