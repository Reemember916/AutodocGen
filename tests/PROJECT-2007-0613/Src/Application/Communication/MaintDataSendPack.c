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
 * 文件名称:    MaintDataSendPack.c
 *
 * 文件日期：       REDACTED
 *
 *
 * 程序版本:
 *
 **********************************************************************************
 *
 * 功能说明:   维护数据发送打包
 *
 *
 *
 *********************************************************************************/

#include "Global.h"

/* ***************************************************************** */
/**
 *  本地变量声明
 */
/* ***************************************************************** */

Uint8  s_MaintTxBuff_u8[COMM_MAINT_TX_PACK_NUM][COMM_MAINT_TX_FRAME_LEN];  /* 维护通信发送数据临时缓存 */
//
Uint16 s_commMaintTxFlag_u16 = RS422_COMM_TX_FLAG_OFF;  /* 维护通信发送标志          */
Uint16 s_commMaintTxPackValidNum_u16 = 1U;       /* 本轮已打包有效帧数量      */

static void CommMaintTxDataPackID1(Uint16 v_SendID_u16);
static void CommMaintTxDataPackID2(Uint16 v_SendID_u16);
static void CommMaintTxDataPackID3(Uint16 v_SendID_u16);
static void CommMaintTxDataPackID4(Uint16 v_SendID_u16);
static void CommMaintTxDataPackID5(Uint16 v_SendID_u16);

/* ***************************************************************** */
/**
 * 【函数名】:CommMaintTxDataPackID0
 *
 * 【功能描述】维护通信发送ID0数据打包
 * 【输入参数说明】v_SendID_u16 ---- 发送报文ID号
 * 【输出参数说明】NONE
 * 【其他说明】	   仅在当前拍输出授权有效时保持维护发送
 * 【返回】	   NONE
 */
/* ***************************************************************** */
void CommMaintTxDataPackID0(Uint16 v_SendID_u16)
{
    static Uint16 l_s_txFrmCnt_u16 = 0U;  /* 发送帧计数  */
    Uint16 l_temp_1_u16    = 0U;  /* 临时数据 1  */
    Uint16 l_ii_u16        = 0U;  /* 循环计数         */
    Uint16 l_sum_u16       = 0U;  /* 数据和             */
    Uint32 l_lTime_u32     = 0UL; /* 系统时间计数  */
    const ConData_t *lc_p_conData_t;      /* 系统控制数据指针  */

    /* 发送报文ID号小于发送报文数  */
    if(v_SendID_u16 < COMM_MAINT_TX_PACK_NUM)
    {
        /* 获取系统控制参数 */
        lc_p_conData_t = ConDataGet();

        /* 发送帧头一、帧头二 */
        s_MaintTxBuff_u8[v_SendID_u16][0] = RS422_COMM_TX_FRAME_HEAD_1;
        s_MaintTxBuff_u8[v_SendID_u16][1] = RS422_COMM_TX_FRAME_HEAD_2;

        /* 发送包号 */
        s_MaintTxBuff_u8[v_SendID_u16][2] = COMM_MAINT_TX_PACK_FRAME_ID_0;

        /* 发送帧计数 */
        s_MaintTxBuff_u8[v_SendID_u16][3] = (l_s_txFrmCnt_u16 & 0xFFU);

        /*****************************/
        /* 系统时间计数  */
        l_lTime_u32 = sysTime();

        /* 字节从低到高填充 */
        s_MaintTxBuff_u8[v_SendID_u16][4] = (l_lTime_u32 & 0xFFUL);
        s_MaintTxBuff_u8[v_SendID_u16][5] = ((l_lTime_u32 >>  8UL) & 0xFFUL);
        s_MaintTxBuff_u8[v_SendID_u16][6] = ((l_lTime_u32 >> 16UL) & 0xFFUL);
        s_MaintTxBuff_u8[v_SendID_u16][7] = ((l_lTime_u32 >> 24UL) & 0xFFUL);

        /*****************************/
        /* 获取当前和上一拍系统状态数据 */
        l_temp_1_u16 = (lc_p_conData_t->sysState_u16 & 0x0FU) + ((lc_p_conData_t->sysStateLast_u16 & 0x0FU) << 4U);

        /* 系统状态数据填充  */
        s_MaintTxBuff_u8[v_SendID_u16][8] = l_temp_1_u16 & 0xFFU;

        /*****************************/
        /* 获取当前和上一拍控制功能码数据 */
        l_temp_1_u16 = (lc_p_conData_t->workMode_u16 & 0x0FU) + ((lc_p_conData_t->workModeLast_u16 & 0x0FU) << 4U);

        /* 控制功能码数据填充  */
        s_MaintTxBuff_u8[v_SendID_u16][9] = l_temp_1_u16 & 0xFFU;

        /*****************************/
        /* 获取当前控制权归属和静态主备身份 */
        l_temp_1_u16 = (lc_p_conData_t->runtimeRole_u16 & 0x0FU) + ((lc_p_conData_t->ChType_u16 & 0x0FU) << 4U);

        /* 低4位为控制权归属，高4位为静态主备身份 */
        s_MaintTxBuff_u8[v_SendID_u16][10] = l_temp_1_u16 & 0xFFU;

        /*****************************/
        l_temp_1_u16 = 0U;  /* 临时数据清零 */

        /* 控制输出状态有效时bit0填1  */
        if(CON_OUT_STATE_VALID == lc_p_conData_t->ConOutData_t.conOutState_u16)
        {
            l_temp_1_u16 = l_temp_1_u16 | (0x01U << 0U); /* BIT0置为1 */
        }

        /* 本端CHV资格允许有效时bit1填1 */
        if(CHV_VALID == lc_p_conData_t->ConOutData_t.localChvPermit_u16)
        {
            /* BIT1置为1 */
            l_temp_1_u16 = l_temp_1_u16 | (0x01U << 1U);
        }

        /* 通道2时bit3填1，其他默认通道1 */
        if(SYS_CH_ID_2 == lc_p_conData_t->myChID_u16)
        {
            /* BIT3置为1 */
            l_temp_1_u16 = l_temp_1_u16 | (0x01U << 3U);
        }

        /* 状态信息和空中加油模式数据填充  */
        /* Byte11布局：
         * bit0=控制输出有效，bit1=本端CHV资格，bit3=本端通道号(通道2=1)；
         * 高4bit透传OilMode，便于维护口联查“资格-角色-模式”一致性。 */
        s_MaintTxBuff_u8[v_SendID_u16][11] = l_temp_1_u16 + (lc_p_conData_t->OilMode_u16 << 4U);

        /*****************************/
        /* 控制功能码值和上一拍控制功能码值填充  */
        /* Byte12布局：低4bit=conFunc，高4bit=conFuncLast，用于直接观察状态机跳转轨迹。 */
        s_MaintTxBuff_u8[v_SendID_u16][12] =(lc_p_conData_t->conFunc_u16 & 0x0FU) + ((lc_p_conData_t->conFuncLast_u16 & 0x0FU) << 4U);

        /*****************************/
        /* CHV回采信号填充  */
        /* Byte13保留CHV输入快照原值，供主备仲裁问题定位时和Byte10角色信息对照分析。 */
        s_MaintTxBuff_u8[v_SendID_u16][13] = lc_p_conData_t->CHVIn_un16.all & 0xFFU;

        /* 空中加油结束状态 */
        /* Byte14透传空中加油结束状态机输出，便于维护口快速区分正常结束/故障结束。 */
        s_MaintTxBuff_u8[v_SendID_u16][14] = lc_p_conData_t->airOilEndState_u16 & 0xFFU;

        /*****************************/
        /* 求数据和 */
        for( l_ii_u16 = 0U; l_ii_u16 < (COMM_MAINT_TX_FRAME_LEN - 1U); l_ii_u16++)
        {
            l_sum_u16 = l_sum_u16 + s_MaintTxBuff_u8[v_SendID_u16][l_ii_u16];
        }

        /*取反加1*/
        l_sum_u16 = (((~l_sum_u16) + 1U) & 0xFFU);

        /* 数据和填充  */
        s_MaintTxBuff_u8[v_SendID_u16][COMM_MAINT_TX_FRAME_LEN - 1U] = l_sum_u16;

        /* 发送帧计数加1 */
        l_s_txFrmCnt_u16 = ( l_s_txFrmCnt_u16 + 1U ) % 0x100U;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:CommMaintTxDataPackID1
 *
 * 【功能描述】维护通信发送ID1数据打包
 *             上报冷启动轮值诊断量，便于维护口直接观察本地/对端轮值值及本次仲裁主通道。
 * 【输入参数说明】v_SendID_u16 ---- 发送报文ID号
 * 【输出参数说明】NONE
 * 【其他说明】     ID1当前只承载主备轮值诊断，未使用字节全部清零
 * 【返回】         NONE
 */
/* ***************************************************************** */
static void CommMaintTxDataPackID1(Uint16 v_SendID_u16)
{
    Uint16 l_ii_u16 = 0U;
    Uint16 l_sum_u16 = 0U;
    const ConData_t *lc_p_conData_t = NULL;

    if (v_SendID_u16 >= COMM_MAINT_TX_PACK_NUM)
    {
        return;
    }

    lc_p_conData_t = ConDataGet();
    if (NULL == lc_p_conData_t)
    {
        return;
    }

    memset(s_MaintTxBuff_u8[v_SendID_u16], 0, COMM_MAINT_TX_FRAME_LEN);
    s_MaintTxBuff_u8[v_SendID_u16][0] = RS422_COMM_TX_FRAME_HEAD_1;
    s_MaintTxBuff_u8[v_SendID_u16][1] = RS422_COMM_TX_FRAME_HEAD_2;
    s_MaintTxBuff_u8[v_SendID_u16][2] = COMM_MAINT_TX_PACK_FRAME_ID_1;
    s_MaintTxBuff_u8[v_SendID_u16][3] = 0U;
    s_MaintTxBuff_u8[v_SendID_u16][4] = lc_p_conData_t->localPreferredMasterChId_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][5] = lc_p_conData_t->peerPreferredMasterChId_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][6] = lc_p_conData_t->arbMasterChId_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][7] = lc_p_conData_t->ChTypeCode_u16 & 0xFFU;

    for (l_ii_u16 = 0U; l_ii_u16 < (COMM_MAINT_TX_FRAME_LEN - 1U); l_ii_u16++)
    {
        l_sum_u16 = l_sum_u16 + s_MaintTxBuff_u8[v_SendID_u16][l_ii_u16];
    }

    l_sum_u16 = (((~l_sum_u16) + 1U) & 0xFFU);
    s_MaintTxBuff_u8[v_SendID_u16][COMM_MAINT_TX_FRAME_LEN - 1U] = l_sum_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommMaintTxDataPackID2
 *
 * 【功能描述】维护通信发送ID2数据打包
 *             上报输出授权诊断量，用于定位“本端为何不发/为何不是主控/为何CHV无效”。
 * 【输入参数说明】v_SendID_u16 ---- 发送报文ID号
 * 【输出参数说明】NONE
 * 【其他说明】     Byte14为输出授权条件位图，便于上位机直接给出未满足条件
 * 【返回】         NONE
 */
/* ***************************************************************** */
static void CommMaintTxDataPackID2(Uint16 v_SendID_u16)
{
    static Uint16 l_s_txFrmCnt_u16 = 0U;
    Uint16 l_ii_u16 = 0U;
    Uint16 l_sum_u16 = 0U;
    Uint16 l_condMask_u16 = 0U;
    const ConData_t *lc_p_conData_t = NULL;

    if (v_SendID_u16 >= COMM_MAINT_TX_PACK_NUM)
    {
        return;
    }

    lc_p_conData_t = ConDataGet();
    if (NULL == lc_p_conData_t)
    {
        return;
    }

    memset(s_MaintTxBuff_u8[v_SendID_u16], 0, COMM_MAINT_TX_FRAME_LEN);
    s_MaintTxBuff_u8[v_SendID_u16][0] = RS422_COMM_TX_FRAME_HEAD_1;
    s_MaintTxBuff_u8[v_SendID_u16][1] = RS422_COMM_TX_FRAME_HEAD_2;
    s_MaintTxBuff_u8[v_SendID_u16][2] = COMM_MAINT_TX_PACK_FRAME_ID_2;
    s_MaintTxBuff_u8[v_SendID_u16][3] = l_s_txFrmCnt_u16 & 0xFFU;

    /* Byte4: 低4bit=运行期控制权，高4bit=静态主备身份。 */
    s_MaintTxBuff_u8[v_SendID_u16][4] =
        (lc_p_conData_t->runtimeRole_u16 & 0x0FU) + ((lc_p_conData_t->ChType_u16 & 0x0FU) << 4U);

    /* Byte5: 低4bit=本通道ID，高4bit=启动判型结果码。 */
    s_MaintTxBuff_u8[v_SendID_u16][5] =
        (lc_p_conData_t->myChID_u16 & 0x0FU) + ((lc_p_conData_t->ChTypeCode_u16 & 0x0FU) << 4U);

    s_MaintTxBuff_u8[v_SendID_u16][6] = lc_p_conData_t->ConOutData_t.localChvPermit_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][7] = lc_p_conData_t->ConOutData_t.conOutState_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][8] = lc_p_conData_t->CHVIn_un16.all & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][9] = (lc_p_conData_t->CHVIn_un16.all >> 8U) & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][10] = lc_p_conData_t->peerAlive_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][11] = lc_p_conData_t->peerCtrlSeen_u16 & 0xFFU;

    /* Byte12: 低4bit=系统状态，高4bit=工作模式。 */
    s_MaintTxBuff_u8[v_SendID_u16][12] =
        (lc_p_conData_t->sysState_u16 & 0x0FU) + ((lc_p_conData_t->workMode_u16 & 0x0FU) << 4U);

    /* Byte13: 低4bit=控制功能，高4bit=维护功能。 */
    s_MaintTxBuff_u8[v_SendID_u16][13] =
        (lc_p_conData_t->conFunc_u16 & 0x0FU) + ((lc_p_conData_t->maintFunc_u16 & 0x0FU) << 4U);

    if (ROLE_MASTER == lc_p_conData_t->runtimeRole_u16)
    {
        l_condMask_u16 = l_condMask_u16 | (0x01U << 0U);
    }
    if (CHV_VALID == lc_p_conData_t->ConOutData_t.localChvPermit_u16)
    {
        l_condMask_u16 = l_condMask_u16 | (0x01U << 1U);
    }
    if (CHV_VALID == lc_p_conData_t->CHVIn_un16.bit.myCHV_u16)
    {
        l_condMask_u16 = l_condMask_u16 | (0x01U << 2U);
    }
    if (CON_OUT_STATE_VALID == lc_p_conData_t->ConOutData_t.conOutState_u16)
    {
        l_condMask_u16 = l_condMask_u16 | (0x01U << 3U);
    }
    if (VALID == lc_p_conData_t->peerAlive_u16)
    {
        l_condMask_u16 = l_condMask_u16 | (0x01U << 4U);
    }
    if (VALID == lc_p_conData_t->peerCtrlSeen_u16)
    {
        l_condMask_u16 = l_condMask_u16 | (0x01U << 5U);
    }
    s_MaintTxBuff_u8[v_SendID_u16][14] = l_condMask_u16 & 0xFFU;

    for (l_ii_u16 = 0U; l_ii_u16 < (COMM_MAINT_TX_FRAME_LEN - 1U); l_ii_u16++)
    {
        l_sum_u16 = l_sum_u16 + s_MaintTxBuff_u8[v_SendID_u16][l_ii_u16];
    }

    l_sum_u16 = (((~l_sum_u16) + 1U) & 0xFFU);
    s_MaintTxBuff_u8[v_SendID_u16][COMM_MAINT_TX_FRAME_LEN - 1U] = l_sum_u16;
    l_s_txFrmCnt_u16 = (l_s_txFrmCnt_u16 + 1U) % 0x100U;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommMaintTxDataPackID3
 *
 * 【功能描述】维护通信发送ID3数据打包
 *             上报BIT与控制故障摘要，用于定位“为何进安全/为何输出被故障抑制”。
 * 【输入参数说明】v_SendID_u16 ---- 发送报文ID号
 * 【输出参数说明】NONE
 * 【其他说明】     Byte7为控制故障位图，Byte9-12为IFBIT低32位签名
 * 【返回】         NONE
 */
/* ***************************************************************** */
static void CommMaintTxDataPackID3(Uint16 v_SendID_u16)
{
    static Uint16 l_s_txFrmCnt_u16 = 0U;
    Uint16 l_ii_u16 = 0U;
    Uint16 l_sum_u16 = 0U;
    Uint16 l_puBitStatus_u16 = 0U;
    Uint16 l_controlFaultMask_u16 = 0U;
    Uint32 l_ifBitResult_u32 = 0UL;
    Uint32 l_mBitResult_u32 = 0UL;
    ControlFaultEval_t l_faultEval_t;

    if (v_SendID_u16 >= COMM_MAINT_TX_PACK_NUM)
    {
        return;
    }

    memset(s_MaintTxBuff_u8[v_SendID_u16], 0, COMM_MAINT_TX_FRAME_LEN);
    s_MaintTxBuff_u8[v_SendID_u16][0] = RS422_COMM_TX_FRAME_HEAD_1;
    s_MaintTxBuff_u8[v_SendID_u16][1] = RS422_COMM_TX_FRAME_HEAD_2;
    s_MaintTxBuff_u8[v_SendID_u16][2] = COMM_MAINT_TX_PACK_FRAME_ID_3;
    s_MaintTxBuff_u8[v_SendID_u16][3] = l_s_txFrmCnt_u16 & 0xFFU;

    l_puBitStatus_u16 = PuBITDataGet();
    l_faultEval_t = ControlFaultEvalGet();
    l_ifBitResult_u32 = IFBITResultGet(IFBIT_DINDEX_RESULTS_BIT32_1);
    l_mBitResult_u32 = MBITResultGet(MBIT_DINDEX_RESULTS_BIT32_1);

    /* Byte4: PuBIT关键故障标志，0=无关键故障，1=存在关键故障。 */
    if (PUBIT_TEST_OK != (l_puBitStatus_u16 & PUBIT_KEY_FAULT_CODE))
    {
        s_MaintTxBuff_u8[v_SendID_u16][4] = 1U;
    }
    else
    {
        s_MaintTxBuff_u8[v_SendID_u16][4] = 0U;
    }

    s_MaintTxBuff_u8[v_SendID_u16][5] = IFBITResultGet(IFBIT_DINDEX_FLEVEL) & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][6] = MBITResultGet(MBIT_DINDEX_FLEVEL) & 0xFFU;

    if (VALID == l_faultEval_t.commFault_u16)
    {
        l_controlFaultMask_u16 = l_controlFaultMask_u16 | (0x01U << 0U);
    }
    if (VALID == l_faultEval_t.measureFault_u16)
    {
        l_controlFaultMask_u16 = l_controlFaultMask_u16 | (0x01U << 1U);
    }
    if (VALID == l_faultEval_t.imbalanceFault_u16)
    {
        l_controlFaultMask_u16 = l_controlFaultMask_u16 | (0x01U << 2U);
    }
    if (VALID == l_faultEval_t.hasFault_u16)
    {
        l_controlFaultMask_u16 = l_controlFaultMask_u16 | (0x01U << 3U);
    }

    s_MaintTxBuff_u8[v_SendID_u16][7] = l_controlFaultMask_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][8] = l_faultEval_t.reason_u16 & 0xFFU;

    s_MaintTxBuff_u8[v_SendID_u16][9] = l_ifBitResult_u32 & 0xFFUL;
    s_MaintTxBuff_u8[v_SendID_u16][10] = (l_ifBitResult_u32 >> 8UL) & 0xFFUL;
    s_MaintTxBuff_u8[v_SendID_u16][11] = (l_ifBitResult_u32 >> 16UL) & 0xFFUL;
    s_MaintTxBuff_u8[v_SendID_u16][12] = (l_ifBitResult_u32 >> 24UL) & 0xFFUL;

    /* Byte13-14: MBIT低16位签名，完整低32位可后续扩展到新ID。 */
    s_MaintTxBuff_u8[v_SendID_u16][13] = l_mBitResult_u32 & 0xFFUL;
    s_MaintTxBuff_u8[v_SendID_u16][14] = (l_mBitResult_u32 >> 8UL) & 0xFFUL;

    for (l_ii_u16 = 0U; l_ii_u16 < (COMM_MAINT_TX_FRAME_LEN - 1U); l_ii_u16++)
    {
        l_sum_u16 = l_sum_u16 + s_MaintTxBuff_u8[v_SendID_u16][l_ii_u16];
    }

    l_sum_u16 = (((~l_sum_u16) + 1U) & 0xFFU);
    s_MaintTxBuff_u8[v_SendID_u16][COMM_MAINT_TX_FRAME_LEN - 1U] = l_sum_u16;
    l_s_txFrmCnt_u16 = (l_s_txFrmCnt_u16 + 1U) % 0x100U;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommMaintTxDataPackID4
 *
 * 【功能描述】维护通信发送ID4数据打包
 *             上报通信选源与关键余度池状态，用于定位“当前控制链到底采用哪一路数据”。
 * 【输入参数说明】v_SendID_u16 ---- 发送报文ID号
 * 【输出参数说明】NONE
 * 【其他说明】     Byte14为关键来源有效位图
 * 【返回】         NONE
 */
/* ***************************************************************** */
static void CommMaintTxDataPackID4(Uint16 v_SendID_u16)
{
    static Uint16 l_s_txFrmCnt_u16 = 0U;
    Uint16 l_ii_u16 = 0U;
    Uint16 l_sum_u16 = 0U;
    Uint16 l_validMask_u16 = 0U;
    const ConData_t *lc_p_conData_t = NULL;
    RedunData_t l_riuHeart_t;
    RedunData_t l_kzzzLeft_t;
    RedunData_t l_kzzzRight_t;
    RedunData_t l_ccdlSysState_t;
    RedunData_t l_ccdlChType_t;
    RedunData_t l_ccdlPreferredMaster_t;

    if (v_SendID_u16 >= COMM_MAINT_TX_PACK_NUM)
    {
        return;
    }

    lc_p_conData_t = ConDataGet();
    if (NULL == lc_p_conData_t)
    {
        return;
    }

    l_riuHeart_t = RedunDataGet(REDUN_INDEX_RIU_HEART);
    l_kzzzLeft_t = RedunDataGet(REDUN_INDEX_KZZZ_L_CURR_TIME_REQ);
    l_kzzzRight_t = RedunDataGet(REDUN_INDEX_KZZZ_R_CURR_TIME_REQ);
    l_ccdlSysState_t = RedunDataGet(REDUN_INDEX_CCDL_SYSST);
    l_ccdlChType_t = RedunDataGet(REDUN_INDEX_CCDL_CHTYPE);
    l_ccdlPreferredMaster_t = RedunDataGet(REDUN_INDEX_CCDL_CHNVM);

    memset(s_MaintTxBuff_u8[v_SendID_u16], 0, COMM_MAINT_TX_FRAME_LEN);
    s_MaintTxBuff_u8[v_SendID_u16][0] = RS422_COMM_TX_FRAME_HEAD_1;
    s_MaintTxBuff_u8[v_SendID_u16][1] = RS422_COMM_TX_FRAME_HEAD_2;
    s_MaintTxBuff_u8[v_SendID_u16][2] = COMM_MAINT_TX_PACK_FRAME_ID_4;
    s_MaintTxBuff_u8[v_SendID_u16][3] = l_s_txFrmCnt_u16 & 0xFFU;

    /* Byte4: 低2bit=RIU来源，bit2-3=CCDL来源，bit4-5=KZZZ来源。 */
    s_MaintTxBuff_u8[v_SendID_u16][4] = lc_p_conData_t->commDataSourse_un16.all & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][5] = l_riuHeart_t.dataState_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][6] = l_kzzzLeft_t.dataState_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][7] = l_kzzzRight_t.dataState_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][8] = l_ccdlSysState_t.dataState_u16 & 0xFFU;

    /* Byte9-13: 关键来源快照，便于判断选源状态是否匹配业务数据。 */
    s_MaintTxBuff_u8[v_SendID_u16][9] = l_riuHeart_t.dataU_u32 & 0xFFUL;
    s_MaintTxBuff_u8[v_SendID_u16][10] = l_kzzzLeft_t.dataU_u32 & 0xFFUL;
    s_MaintTxBuff_u8[v_SendID_u16][11] = l_kzzzRight_t.dataU_u32 & 0xFFUL;
    s_MaintTxBuff_u8[v_SendID_u16][12] = l_ccdlSysState_t.dataU_u32 & 0xFFUL;
    s_MaintTxBuff_u8[v_SendID_u16][13] =
        (l_ccdlChType_t.dataU_u32 & 0x0FUL) + ((l_ccdlPreferredMaster_t.dataU_u32 & 0x0FUL) << 4UL);

    if (REDUN_DATA_STATE_ERR != l_riuHeart_t.dataState_u16)
    {
        l_validMask_u16 = l_validMask_u16 | (0x01U << 0U);
    }
    if (REDUN_DATA_STATE_ERR != l_kzzzLeft_t.dataState_u16)
    {
        l_validMask_u16 = l_validMask_u16 | (0x01U << 1U);
    }
    if (REDUN_DATA_STATE_ERR != l_kzzzRight_t.dataState_u16)
    {
        l_validMask_u16 = l_validMask_u16 | (0x01U << 2U);
    }
    if (REDUN_DATA_STATE_ERR != l_ccdlSysState_t.dataState_u16)
    {
        l_validMask_u16 = l_validMask_u16 | (0x01U << 3U);
    }
    if (COMM_SOURCE_INVALID == lc_p_conData_t->commDataSourse_un16.bit.RIU)
    {
        l_validMask_u16 = l_validMask_u16 | (0x01U << 4U);
    }
    if (COMM_SOURCE_INVALID == lc_p_conData_t->commDataSourse_un16.bit.CCDL)
    {
        l_validMask_u16 = l_validMask_u16 | (0x01U << 5U);
    }
    if (COMM_SOURCE_INVALID == lc_p_conData_t->commDataSourse_un16.bit.KZZZ)
    {
        l_validMask_u16 = l_validMask_u16 | (0x01U << 6U);
    }
    s_MaintTxBuff_u8[v_SendID_u16][14] = l_validMask_u16 & 0xFFU;

    for (l_ii_u16 = 0U; l_ii_u16 < (COMM_MAINT_TX_FRAME_LEN - 1U); l_ii_u16++)
    {
        l_sum_u16 = l_sum_u16 + s_MaintTxBuff_u8[v_SendID_u16][l_ii_u16];
    }

    l_sum_u16 = (((~l_sum_u16) + 1U) & 0xFFU);
    s_MaintTxBuff_u8[v_SendID_u16][COMM_MAINT_TX_FRAME_LEN - 1U] = l_sum_u16;
    l_s_txFrmCnt_u16 = (l_s_txFrmCnt_u16 + 1U) % 0x100U;
}
/* ***************************************************************** */
/**
 * 【函数名】:CommMaintTxDataPackID5
 *
 * 【功能描述】维护通信发送ID5数据打包
 *             上报软件版本、硬件版本和应用/加载软件CRC，供上位机校验与版本核对。
 * 【输入参数说明】v_SendID_u16 ---- 发送报文ID号
 * 【输出参数说明】NONE
 * 【其他说明】     Byte4~5=软件版本, Byte6=硬件版本, Byte7~8=应用CRC, Byte9~10=加载CRC
 * 【返回】         NONE
 */
/* ***************************************************************** */
static void CommMaintTxDataPackID5(Uint16 v_SendID_u16)
{
    static Uint16 l_s_txFrmCnt_u16 = 0U;
    Uint16 l_ii_u16 = 0U;
    Uint16 l_sum_u16 = 0U;
    union SoftwVData l_softv_un16;
    SpeData_t l_hardwVer_t;
    Uint16 l_maintFunc_u16 = 0U;
    Uint16 l_exeResult_u16 = 0U;
    const RsMaintDataInfo_t *lc_p_maintData_t = NULL;

    if (v_SendID_u16 >= COMM_MAINT_TX_PACK_NUM)
    {
        return;
    }

    memset(s_MaintTxBuff_u8[v_SendID_u16], 0, COMM_MAINT_TX_FRAME_LEN);
    s_MaintTxBuff_u8[v_SendID_u16][0] = RS422_COMM_TX_FRAME_HEAD_1;
    s_MaintTxBuff_u8[v_SendID_u16][1] = RS422_COMM_TX_FRAME_HEAD_2;
    s_MaintTxBuff_u8[v_SendID_u16][2] = COMM_MAINT_TX_PACK_FRAME_ID_5;
    s_MaintTxBuff_u8[v_SendID_u16][3] = l_s_txFrmCnt_u16 & 0xFFU;

    /* Byte4~5: 软件版本(小端), 例如0.0.1.0编码为16bit字段。 */
    l_softv_un16 = SoftwVDataGet();
    s_MaintTxBuff_u8[v_SendID_u16][4] = l_softv_un16.all & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][5] = (l_softv_un16.all >> 8U) & 0xFFU;

    /* Byte6: 硬件版本, 编码100=1.00。 */
    memset(&l_hardwVer_t, 0, sizeof(l_hardwVer_t));
    SpeDataGet(SPE_DATA_DINDEX_HARDW_VER, &l_hardwVer_t);
    s_MaintTxBuff_u8[v_SendID_u16][6] = l_hardwVer_t.dataU_u16 & 0xFFU;

    /* Byte7~8: 应用软件CRC(小端)。 */
    s_MaintTxBuff_u8[v_SendID_u16][7] = s_softwCRC_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][8] = (s_softwCRC_u16 >> 8U) & 0xFFU;

    /* Byte9~10: 加载软件CRC(小端)。 */
    s_MaintTxBuff_u8[v_SendID_u16][9] = s_softwCRC_Update_u16 & 0xFFU;
    s_MaintTxBuff_u8[v_SendID_u16][10] = (s_softwCRC_Update_u16 >> 8U) & 0xFFU;

    /* Byte11~12: 最近维护功能码与执行结果, 便于上位机确认CRC/下载指令是否被接收执行。 */
    lc_p_maintData_t = CommMaintDataGet();
    if (NULL != lc_p_maintData_t)
    {
        l_maintFunc_u16 = lc_p_maintData_t->MaintFuncCode_u16 & 0xFFU;
        l_exeResult_u16 = lc_p_maintData_t->MaintFuncExeResult_u16 & 0xFFU;
    }
    s_MaintTxBuff_u8[v_SendID_u16][11] = l_maintFunc_u16;
    s_MaintTxBuff_u8[v_SendID_u16][12] = l_exeResult_u16;

    /* Byte13~14: 保留(0)。 */

    for (l_ii_u16 = 0U; l_ii_u16 < (COMM_MAINT_TX_FRAME_LEN - 1U); l_ii_u16++)
    {
        l_sum_u16 = l_sum_u16 + s_MaintTxBuff_u8[v_SendID_u16][l_ii_u16];
    }

    l_sum_u16 = (((~l_sum_u16) + 1U) & 0xFFU);
    s_MaintTxBuff_u8[v_SendID_u16][COMM_MAINT_TX_FRAME_LEN - 1U] = l_sum_u16;
    l_s_txFrmCnt_u16 = (l_s_txFrmCnt_u16 + 1U) % 0x100U;
}



/* ***************************************************************** */
/**
 * 【函数名】:CommMaintTxDataPack
 *
 * 【功能描述】维护通信发送数据打包
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】	   NONE
 * 【返回】               NONE
 */
/* ***************************************************************** */
void CommMaintTxDataPack(void)
{
    const ConData_t *lc_p_conData_t = ConDataGet();

    if ((NULL == lc_p_conData_t) ||
        (CON_OUT_STATE_VALID != lc_p_conData_t->ConOutData_t.conOutState_u16))
    {
        s_commMaintTxFlag_u16 = RS422_COMM_TX_FLAG_OFF;
        s_commMaintTxPackValidNum_u16 = 1U;
        return;
    }

    /* 按任务书0041：进入周期工作后，维护422通道应保持发送状态。 */
    s_commMaintTxFlag_u16 = RS422_COMM_TX_FLAG_ON;

    /* 当前版本发送ID0基础状态 + ID1主备轮值诊断 + ID2输出授权诊断 + ID3 BIT/故障摘要 + ID4余度来源 + ID5软件版本与CRC。 */
    s_commMaintTxPackValidNum_u16 = 6U;

    /* 维护通信发送报文分包数据打包 */
    CommMaintTxDataPackID0(COMM_MAINT_TX_PACK_FRAME_ID_0);
    CommMaintTxDataPackID1(COMM_MAINT_TX_PACK_FRAME_ID_1);
    CommMaintTxDataPackID2(COMM_MAINT_TX_PACK_FRAME_ID_2);
    CommMaintTxDataPackID3(COMM_MAINT_TX_PACK_FRAME_ID_3);
    CommMaintTxDataPackID4(COMM_MAINT_TX_PACK_FRAME_ID_4);
    CommMaintTxDataPackID5(COMM_MAINT_TX_PACK_FRAME_ID_5);
}

/* ***************************************************************** */
/**
 * 【函数名】:CommMaintCommSend
 *
 * 【功能描述】维护报文通信发送
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】仅在当前拍输出授权有效时发送
 * 【返回】	   NONE
 */
/* ***************************************************************** */
void CommMaintCommSend(void)
{
    static Uint16 l_s_sendIndex_u16 = 0U;  /* 发送包号索引  */
    const ConData_t *lc_p_conData_t = ConDataGet();
    Uint16 l_txPackNum_u16 = s_commMaintTxPackValidNum_u16; /* 有效发送包数 */

    if ((NULL == lc_p_conData_t) ||
        (CON_OUT_STATE_VALID != lc_p_conData_t->ConOutData_t.conOutState_u16))
    {
        s_commMaintTxFlag_u16 = RS422_COMM_TX_FLAG_OFF;
        l_s_sendIndex_u16 = 0U;
        return;
    }

    /* 防护：有效发送包数必须落在[1, COMM_MAINT_TX_PACK_NUM] */
    if((0U == l_txPackNum_u16) || (l_txPackNum_u16 > COMM_MAINT_TX_PACK_NUM))
    {
        l_txPackNum_u16 = 1U;
    }

    /* 通信发送标志有效时  */
    if(RS422_COMM_TX_FLAG_ON ==  s_commMaintTxFlag_u16)
    {
        /* SCI数组数据发送  */
        SciSendBuff(SCI_A_ID,s_MaintTxBuff_u8[l_s_sendIndex_u16],16U);

        /* 发送包号索引加1 */
        l_s_sendIndex_u16 = l_s_sendIndex_u16 + 1U;

        /* 发送包号索引大于等于发送包号数时，通信发送完成  */
        if(l_s_sendIndex_u16 >= l_txPackNum_u16)
        {
            /* 发送标志置为无效 */
            s_commMaintTxFlag_u16 = RS422_COMM_TX_FLAG_OFF;

            /* 发送包号索引清零 */
            l_s_sendIndex_u16 = 0U;
        }
    }
}


///* ========================================================================== */
///* END OF FILE */
///* ========================================================================== */
