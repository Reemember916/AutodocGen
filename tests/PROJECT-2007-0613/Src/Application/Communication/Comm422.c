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
 * 文件名称:    comm422.c
 *
 * 文件日期：       REDACTED
 *
 *
 * 程序版本:
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 * 1. 实现422通信功能，其中包括维护通信
 *
 *********************************************************************************/

#include "Global.h"

/* ***************************************************************** */
/**
 *  本地变量声明
 */
/* ***************************************************************** */
/* 422通信ID配置表 */
static Uint16  s_422CommIDConf_u16[COMM422_ID_NUM] =
            {
                SCI_A_ID,
                SCI_B_ID
            };

/* 422通信长度信息配置 */
static Rs422CommLenConf_t s_Rs422CommLenConfBuff_t[COMM422_ID_NUM] =
                                            {
                                                { COMM_MAINT_RX_FRAME_LEN   ,COMM_MAINT_RX_BUFF_LEN    },  /* 维护通信接收长度配置         */
                                                { COMM_CCDL_FRAME_LEN_MAX   ,COMM_CCDL_RX_BUFF_LEN    }  /* CCDL通信接收长度配置         */
                                            };

Rs422CommBuff_t s_rs422CommBuff_t[COMM422_ID_NUM];    /* 通信缓冲区          */
Rs422CommInfo_t s_rs422CommInfo_t[COMM422_ID_NUM];    /* 通信状态信息      */
RsMaintDataInfo_t   s_rsMaintData_t;  /* 维护通信接收数据             */
union SoftwVData s_mySoftwVData_un16;   /* 软件版本数据            */

Uint16 s_tempRxBuff_u16[COMM_CCDL_RX_BUFF_LEN]; /* 通信接收数据临时缓存 */
Uint16 s_softwCRC_u16; /* 软件CRC校验码     */
Uint16 s_softwCRC_Update_u16; /* 加载软件CRC校验码     */

/* ***************************************************************** */
/**
 * 【函数名】:CommMaintDataGet
 *
 * 【功能描述】维护通信数据获取
 * 【输入参数说明】v_pRxMaintPData_t  ---- 维护通信数据结构体指针
 * 【输出参数说明】NONE
 * 【其他说明】	  NONE
 * 【返回】	  维护通信接收数据
 */
/* ***************************************************************** */
const RsMaintDataInfo_t * CommMaintDataGet(void)
{
    return &s_rsMaintData_t;
}

/* ***************************************************************** */
/**
 * 【函数名】:CommMaintExecStatusUpdate
 *
 * 【功能描述】更新最近一次维护功能执行状态
 * 【输入参数说明】v_func_u16   ---- 执行的维护功能码
 *              v_result_u16 ---- 执行结果
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】           NONE
 */
/* ***************************************************************** */
void CommMaintExecStatusUpdate(Uint16 v_func_u16, Uint16 v_result_u16)
{
    s_rsMaintData_t.MaintFuncLastExe_u16 = v_func_u16;
    s_rsMaintData_t.MaintFuncExeResult_u16 = v_result_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:SoftwVDataGet
 *
 * 【功能描述】软件版本数据获取
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】	   版本信息数据
 */
/* ***************************************************************** */
union SoftwVData SoftwVDataGet(void)
{
    /* 返回版本信息数据 */
    return s_mySoftwVData_un16;
}

/* ***************************************************************** */
/**
 * 【函数名】:MaintCommInfoProcess
 *
 * 【功能描述】维护通信状态数据处理
 *
 * 【输入参数】:v_commID_u16  ---- RS422通道ID，可能取值为:
 *              	SCI_A_ID ---- SCIA接口
 *              	SCI_B_ID ---- SCIB接口
 *              	SCI_C_ID ---- SCIC接口
 *          v_sIndex_u16  ---- 缓存区数据基索引
 *
 * 【输出参数】NONE
 * 【其他说明】NONE
 * 【返回】        NONE
 *
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:MaintCommInfoProcess
 *
 * 【功能描述】维护通信信息处理
 *
 * 【输入参数说明】v_commID_u16 ---- 通道ID
 *             v_sIndex_u16 ---- 起始索引
 * 【输出参数说明】NONE
 * 【其他说明】处理维护报文头部的通信信息
 * 【返回】NONE
 */
/* ***************************************************************** */
static void MaintCommInfoProcess(Uint16 v_commID_u16,Uint16 v_sIndex_u16)
{
    Uint16 l_temp_u16;  /* 临时数据      */
    Uint16 l_temp_2_u16;  /* 临时数据      */
    Uint16 l_ii_u16 = 0U;
    Uint32 l_Addr_u32  = 0UL; /* 读取地址     */

    /* 输入通道ID小于数量 且 基索引小于接收数据长度时 */
    if( (v_commID_u16 < COMM422_ID_NUM) && (v_sIndex_u16 < COMM_MAINT_RX_FRAME_LEN))
    {
        /* 获取索引4接收数据 */
        l_temp_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 4U] & 0xFFU;

        /* 低4位数据为429通信信息ID号   */
        l_temp_2_u16 = l_temp_u16 & 0x0FU;

        /* 小于通信数量时 */
        if(l_temp_2_u16 < COMM_MAINT_TX_COMM429_INFO_NUM)
        {
            s_rsMaintData_t.A429InfoID_u16 = l_temp_2_u16;
        }

        /* 高4位数据为流量测量盒422通信信息ID号   */
        l_temp_2_u16 = (l_temp_u16 >> 4U) & 0x0FU;

        /* 小于通信数量时 */
        if(l_temp_2_u16 < COMM_MAINT_TX_COMMFLOWB_INFO_NUM)
        {
            s_rsMaintData_t.FlowB422InfoID_u16 = l_temp_2_u16;
        }

        /* 获取索引5接收数据 */
        l_temp_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 5U] & 0xFFU;

        s_rsMaintData_t.A429RxLabel_u16 = l_temp_u16;

        /*******************************************/
        /* 对读取起始地址3个字节数据从低到高进行拼接 */
        for(l_ii_u16 = 0U; l_ii_u16 < 3U; l_ii_u16++)
        {
            l_Addr_u32 = l_Addr_u32 << 8U;
            l_Addr_u32 = l_Addr_u32 +  (s_rs422CommBuff_t[v_commID_u16].commBuff_u16[(v_sIndex_u16 + 8U) - l_ii_u16] & 0xFFU);
        }

        /* 获取读取数据地址 */
        s_rsMaintData_t.readAddr_u32 = l_Addr_u32;

        /*******************************************/
        /* 获取索引9接收数据 */
        l_temp_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 9U] & 0xFFU;

        /* 获取余度数据索引   */
        s_rsMaintData_t.RudunInfoID_u16 = l_temp_u16;

        /*******************************************/
        /* 获取索引10接收数据 */
        l_temp_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 10U] & 0xFFU;

        /* 获取软件版本信息索引   */
        s_rsMaintData_t.SoftVInfoID_u16 = l_temp_u16;

        /*******************************************/
        /* 获取索引11接收数据 */
        l_temp_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 11U] & 0xFFU;

        /* 模拟量信息索引小于数量时更新索引   */
        if(l_temp_u16 < ANA_DATA_NUM_TOTAL)
        {
            s_rsMaintData_t.AnaInfoID_u16 = l_temp_u16;
        }

        /*******************************************/
        /* 获取索引12接收数据 */
        l_temp_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 12U] & 0xFFU;

        /* 泵控制器信息索引小于数量时更新索引   */
        if(l_temp_u16 < COMM429_JYB_NUM)
        {
            s_rsMaintData_t.BengInfoID_u16 = l_temp_u16;
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:MaintConDataProcess
 *
 * 【功能描述】维护地面控制数据处理
 *
 * 【输入参数】:v_commID_u16  ---- RS422通道ID，可能取值为:
 *              	SCI_A_ID ---- SCIA接口
 *              	SCI_B_ID ---- SCIB接口
 *              	SCI_C_ID ---- SCIC接口
 *          v_sIndex_u16  ---- 缓存区数据基索引
 *
 * 【输出参数】NONE
 * 【其他说明】NONE
 * 【返回】        NONE
 *
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:MaintConDataProcess
 *
 * 【功能描述】维护控制数据处理
 *
 * 【输入参数说明】v_commID_u16 ---- 通道ID
 *             v_sIndex_u16 ---- 起始索引
 * 【输出参数说明】NONE
 * 【其他说明】解析维护报文中的控制数据
 * 【返回】NONE
 */
/* ***************************************************************** */
static void MaintConDataProcess(Uint16 v_commID_u16,Uint16 v_sIndex_u16)
{
    Uint16 l_temp_u16;  /* 临时数据      */
    Uint16 l_dataH_u16 = 0U;  /* 高字节数据  */
    Uint16 l_dataL_u16 = 0U;  /* 低字节数据  */

    /* 输入通道ID小于数量 且 基索引小于接收数据长度时 */
    if( (v_commID_u16 < COMM422_ID_NUM) && (v_sIndex_u16 < COMM_MAINT_RX_FRAME_LEN))
    {
        /* 获取索引4接收数据，指令更新标志 */
        s_rsMaintData_t.cmdUpdateflag_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 4U] & 0xFFU;

        /* 获取索引5接收数据，维护指令ID号  */
        s_rsMaintData_t.cmdInfoID_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 5U] & 0xFFU;

        /* 根据维护指令ID号进行数据解析 */
        if(s_rsMaintData_t.cmdInfoID_u16 <= COMM_MAINT_R_CON_CMD_JYB_2) /* 泵指令 */
        {
            /* 当前版本仅透传泵/阀指令索引与更新标志，具体泵指令位定义待任务书补充。 */
        }
        else if(s_rsMaintData_t.cmdInfoID_u16 <= COMM_MAINT_R_CON_CMD_SOV) /* 阀指令 */
        {
            /* 当前版本仅透传泵/阀指令索引与更新标志，具体阀指令位定义待任务书补充。 */
        }
        else /* 控制装置指令 */
        {
            /* 当前版本已清退KZZZ控制指令镜像，控制装置维护指令不再落入control输出结构。 */
            l_dataL_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 6U] & 0xFFU;
            l_dataH_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 7U] & 0xFFU;
            l_temp_u16  = l_dataL_u16 + (l_dataH_u16 << 8U);
            (void)l_temp_u16;
        }
    }
}

/* ***************************************************************** */

/* ***************************************************************** */

/* ***************************************************************** */
/**
 * 【函数名】:Comm422FrameBufferGet
 * 【功能描述】获取RS422帧缓冲区指针,返回指定通道的接收数据缓存
 * 【输入参数说明】v_commID_u16 ---- 通信通道ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】指向帧缓冲区的指针
 */
/* ***************************************************************** */
Uint16 * Comm422FrameBufferGet(Uint16 v_commID_u16)
{
    Uint16 * l_pCommBuff_u16 = NULL;

    if( v_commID_u16 < COMM422_ID_NUM )
    {
        l_pCommBuff_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16;
    }

    return l_pCommBuff_u16;
}

/* ***************************************************************** */
/**
 * [函数名]	Comm422RxBufferIndexGet
 * [功能描述]	获取指定RS422通道的接收缓存当前写入索引
 * [输入参数说明]v_commID_u16 ---- 通道ID
 * [输出参数说明]NONE
 * [其他说明]	通道ID越界时返回0
 * [返回]	当前写入索引
 */
/* ***************************************************************** */
Uint16 Comm422RxBufferIndexGet(Uint16 v_commID_u16)
{
    Uint16 l_index_u16 = 0U;

    if(v_commID_u16 < COMM422_ID_NUM)
    {
        l_index_u16 = s_rs422CommBuff_t[v_commID_u16].index_u16;
    }

    return l_index_u16;
}

Rs422CommInfo_t Comm422CommInfoGet(Uint16 v_commID_u16)
{
    Rs422CommInfo_t l_info_t;
    memset(&l_info_t, 0, sizeof(l_info_t));

    if(v_commID_u16 < COMM422_ID_NUM)
    {
        l_info_t = s_rs422CommInfo_t[v_commID_u16];
    }

    return l_info_t;
}

/* ***************************************************************** */
/**
 * [函数名]	Comm422RxBufferCompact
 * [功能描述]	压缩RS422接收缓存，保留未消费尾帧
 * [输入参数说明]v_commID_u16      ---- 通道ID
 *             v_consumedLen_u16 ---- 已消费的前缀长度
 * [输出参数说明]NONE
 * [其他说明]	已消费长度大于等于已写入长度时整体清零
 * [返回]	NONE
 */
/* ***************************************************************** */
void Comm422RxBufferCompact(Uint16 v_commID_u16, Uint16 v_consumedLen_u16)
{
    Uint16 l_index_u16 = 0U;
    Uint16 l_remain_u16 = 0U;
    Uint16 l_ii_u16 = 0U;

    if(v_commID_u16 < COMM422_ID_NUM)
    {
        l_index_u16 = s_rs422CommBuff_t[v_commID_u16].index_u16;

        if(v_consumedLen_u16 >= l_index_u16)
        {
            s_rs422CommBuff_t[v_commID_u16].index_u16 = 0U;

            for(l_ii_u16 = 0U; l_ii_u16 < s_Rs422CommLenConfBuff_t[v_commID_u16].rxBuffLen_u16; l_ii_u16++)
            {
                s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16] = 0U;
            }
        }
        else
        {
            l_remain_u16 = l_index_u16 - v_consumedLen_u16;

            for(l_ii_u16 = 0U; l_ii_u16 < l_remain_u16; l_ii_u16++)
            {
                s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16] =
                    s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_consumedLen_u16 + l_ii_u16];
            }

            for(l_ii_u16 = l_remain_u16; l_ii_u16 < s_Rs422CommLenConfBuff_t[v_commID_u16].rxBuffLen_u16; l_ii_u16++)
            {
                s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16] = 0U;
            }

            s_rs422CommBuff_t[v_commID_u16].index_u16 = l_remain_u16;
        }
    }
}

/* ***************************************************************** */
/**
 * [函数名]	Comm422RxBufferClear
 * [功能描述]	清空指定RS422通道的接收缓存
 * [输入参数说明]v_commID_u16 ---- 通道ID
 * [输出参数说明]NONE
 * [其他说明]	   static，仅本文件使用
 * [返回]	NONE
 */
/* ***************************************************************** */
static void Comm422RxBufferClear(Uint16 v_commID_u16)
{
    Uint16 l_ii_u16 = 0U;

    if(v_commID_u16 < COMM422_ID_NUM)
    {
        s_rs422CommBuff_t[v_commID_u16].index_u16 = 0U;

        for(l_ii_u16 = 0U; l_ii_u16 < s_Rs422CommLenConfBuff_t[v_commID_u16].rxBuffLen_u16; l_ii_u16++)
        {
            s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16] = 0U;
        }
    }
}
/* ***************************************************************** */
/**
 * 【函数名】:MaintFuncDataProcess
 *
 * 【功能描述】地面维护功能数据处理
 *
 * 【输入参数】:v_commID_u16  ---- RS422通道ID，可能取值为:
 *              	SCI_A_ID ---- SCIA接口
 *              	SCI_B_ID ---- SCIB接口
 *              	SCI_C_ID ---- SCIC接口
 *          v_sIndex_u16  ---- 缓存区数据基索引
 *
 * 【输出参数】NONE
 * 【其他说明】NONE
 * 【返回】        NONE
 */
/* ***************************************************************** */
void MaintFuncDataProcess(Uint16 v_commID_u16,Uint16 v_sIndex_u16)
{
    Uint16 l_ii_u16        = 0U;  /* 循环索引            */
    Uint32 l_startAddr_u32 = 0UL; /* 下载起始地址     */
    Uint32 l_addrLen_u32   = 0UL; /* 下载地址长度     */
    Uint16 l_MaintFunc_u16 = GROUND_MAINT_FUNC_INVALID;  /* 维护功能    */
    Uint16 l_funcChanged_u16 = INVALID; /* 维护功能是否变化 */
    Uint16 l_downloadParaChanged_u16 = INVALID; /* 下载参数是否变化 */

    /* 输入通道ID小于数量 且 基索引小于接收数据长度时 */
    if( (v_commID_u16 < COMM422_ID_NUM) && (v_sIndex_u16 < COMM_MAINT_RX_FRAME_LEN))
    {
        /* 获取维护功能码 */
        l_MaintFunc_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16+4U] & 0xFFU;

        /* 维护功能指令发生切换 */
        if(l_MaintFunc_u16 != s_rsMaintData_t.MaintFuncCode_u16)
        {
            l_funcChanged_u16 = VALID;
        }

        /* 维护功能码为数据下载时，解析参数并检查是否变化 */
        if(GROUND_MAINT_FUNC_DATA_DOWNLOAD == l_MaintFunc_u16)
        {
            /* 对下载起始地址4个字节数据从低到高进行拼接 */
            for(l_ii_u16 = 0U; l_ii_u16 < 4U; l_ii_u16++)
            {
                l_startAddr_u32 = l_startAddr_u32 << 8U;
                l_startAddr_u32 = l_startAddr_u32 +  (s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 8U - l_ii_u16] & 0xFFU);
            }

            /*******************************************/
            /* 对下载地址长度4个数据从低到高进行拼接 */
            for(l_ii_u16 = 0U; l_ii_u16 < 4U; l_ii_u16++)
            {
                l_addrLen_u32 = l_addrLen_u32 << 8U;
                l_addrLen_u32 = l_addrLen_u32 +  (s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 12U - l_ii_u16] & 0xFFU);
            }

            /* 下载参数变化检查 */
            if((l_startAddr_u32 != s_rsMaintData_t.downLoadStartAddr_u32) ||
               (l_addrLen_u32 != s_rsMaintData_t.downLoadAddrLen_u32))
            {
                l_downloadParaChanged_u16 = VALID;
            }
        }

        /* 功能变化或下载参数变化时刷新执行触发 */
        if((VALID == l_funcChanged_u16) || (VALID == l_downloadParaChanged_u16))
        {
            /* 更新维护功能指令  */
            s_rsMaintData_t.MaintFuncCode_u16 = l_MaintFunc_u16;

            /* 维护功能码为数据下载时更新下载参数，否则清零防止旧参数残留 */
            if(GROUND_MAINT_FUNC_DATA_DOWNLOAD == s_rsMaintData_t.MaintFuncCode_u16)
            {
                s_rsMaintData_t.downLoadStartAddr_u32 = l_startAddr_u32;
                s_rsMaintData_t.downLoadAddrLen_u32 = l_addrLen_u32;
            }
            else
            {
                s_rsMaintData_t.downLoadStartAddr_u32 = 0UL;
                s_rsMaintData_t.downLoadAddrLen_u32 = 0UL;
            }

            /* 接收到有效指令时更新维护指令执行状态 */
            if(GROUND_MAINT_FUNC_INVALID != s_rsMaintData_t.MaintFuncCode_u16)
            {
                /* 维护功能指令执行状态置为新指令 */
                MaintCMDExeStateClear(MAINT_CMD_EXE_NEW);
            }
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:MaintRxDataProcess
 *
 * 【功能描述】维护通信接收数据处理
 *
 * 【输入参数】:v_commID_u16  ---- RS422通道ID，可能取值为:
 *              	SCI_A_ID ---- SCIA接口
 *              	SCI_B_ID ---- SCIB接口
 *              	SCI_C_ID ---- SCIC接口
 *          vp_rxBuff_u16   ---- 待解析接收数组指针
 *
 * 【输出参数】NONE
 * 【其他说明】NONE
 * 【返回】        NONE
 *
 */
/* ***************************************************************** */
void MaintRxDataProcess(Uint16 v_commID_u16,Uint16 v_sIndex_u16)
{

    /* 输入通道ID小于数量 且 基索引小于接收数据长度时 */
    if( (v_commID_u16 < COMM422_ID_NUM) && (v_sIndex_u16 < COMM_MAINT_RX_FRAME_LEN))
    {
        /* 维护帧关键字节布局（相对帧起始）：
         * [2]=帧计数，[3]=维护指令码，[13]=维护状态码。
         * 各指令的业务载荷从[4]开始，由子处理函数按指令类型继续解析。 */
        /* 接收帧计数 */
        s_rsMaintData_t.rxFrameCnt_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 2U];

        /* 获取维护状态码 */
        s_rsMaintData_t.MaintStateCode_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 13U] & 0xFFU;

        /*******************************************/
        /* 获取维护指令码  */
        s_rsMaintData_t.MaintCMDCode_u16 = s_rs422CommBuff_t[v_commID_u16].commBuff_u16[v_sIndex_u16 + 3U] & 0xFFU;

        /* 根据维护指令码进行处理  */
        switch(s_rsMaintData_t.MaintCMDCode_u16)
        {
            case MAINT_CODE_COMM_INFO :  /* 维护指令为通信状态信息时 */
                {
                    /* 维护通信状态数据处理   */
                    MaintCommInfoProcess(v_commID_u16,v_sIndex_u16);
                }
            break;

            case MAINT_CODE_GROUND_CON :  /* 维护指令为地面控制时 */
                {
                    /* 维护地面控制数据处理   */
                    MaintConDataProcess(v_commID_u16,v_sIndex_u16);
                }
                break;

            case MAINT_CODE_MAINT_FUNC :  /* 维护指令为地面维护功能时 */
                {
                    /* 维护功能指令数据处理    */
                    MaintFuncDataProcess(v_commID_u16,v_sIndex_u16);
                }
                break;



            default :  /* 默认无效，不做数据处理 */
                break;
        }
    }
}


/* ***************************************************************** */
/**
 * 【函数名】:DownLoadDataCommSend
 *
 * 【功能描述】下载数据通信发送
 * 		   1.根据维护通信接收到的下载起始地址和地址长度，将地址区域内数据通过422通信发送；
 * 		   2.按照每2ms发送16个数据通信发送；
 * 		   3.若数据下载中途发生28V掉电（28V掉电标志有效），提前结束数据下载；
 * 		   4.周期进行喂狗。
 * 【输入参数说明】v_startAddr_u32 ---- 下载起始地址
 * 			   v_addrLen_u32   ---- 下载地址长度
 * 【输出参数说明】NONE
 * 【其他说明】	  NONE
 * 【返回】               NONE
 */
/* ***************************************************************** */
void DownLoadDataCommSend(Uint32 v_startAddr_u32,Uint32 v_addrLen_u32)
{
    Uint32 l_startAddr_u32     = 0UL;  /* 开始下载地址  */
    Uint32 l_currAddr_u32      = 0UL;  /* 当前下载地址  */
    Uint32 l_endAddr_u32       = 0UL;  /* 结束地址（开区间） */
    Uint32 l_remainLen_u32     = 0UL;  /* 剩余发送长度 */
    Uint32 l_flashWinLen_u32   = 0UL;  /* 下载窗口长度 */
    Uint16 l_sendLen_u16       = 0U;   /* 当前帧发送长度 */
    Uint16 l_buff_u16[16U];             /* 数据缓存区       */
    Uint16 l_powerDownFlag_u16 = 0U;   /* 掉电标志           */
    memset(l_buff_u16, 0, sizeof(l_buff_u16));

    if(0UL == v_addrLen_u32)
    {
        return;
    }

    /* 周期喂狗  */
    CycleDogFeed();

    /* 延时2ms */
    delayUs(666U);

    l_flashWinLen_u32 = ((FLASH_SECTOR_LAST - FLASH_SECTOR_FIRST) + 1UL) * FLASH_SECTOR_LEN;
    /* NOTE:因输入开始地址为相对地址，需要获取绝对地址进行数据下载 */
    /* 下载窗口固定限制在应用区FLASH范围：
     * 起始地址采用“窗口内取模 + 应用区基址”折算，长度超窗时按窗口末端截断。 */
    l_startAddr_u32 = (v_startAddr_u32 % l_flashWinLen_u32) + (FLASH_BASE_ADDR + (FLASH_SECTOR_FIRST * FLASH_SECTOR_LEN));

    if(v_addrLen_u32 > (l_flashWinLen_u32 - (v_startAddr_u32 % l_flashWinLen_u32)))
    {
        l_endAddr_u32 = FLASH_BASE_ADDR + (FLASH_SECTOR_FIRST * FLASH_SECTOR_LEN) + l_flashWinLen_u32;
    }
    else
    {
        l_endAddr_u32 = l_startAddr_u32 + v_addrLen_u32;
    }

    /* 当前下载地址初始化为起始地址 */
    l_currAddr_u32 = l_startAddr_u32;

    /* 通信发送地址数据，2ms发送16个字节 */
    while(l_currAddr_u32 < l_endAddr_u32)
    {
        /* 周期喂狗  */
        CycleDogFeed();

        /* 延时2ms */
        delayUs(666U);

        l_remainLen_u32 = l_endAddr_u32 - l_currAddr_u32;
        if(l_remainLen_u32 > 16UL)
        {
            l_sendLen_u16 = 16U;
        }
        else
        {
            l_sendLen_u16 = (Uint16)l_remainLen_u32;
        }

        if(0U == l_sendLen_u16)
        {
            break;
        }

        /* 从内存中读取数据 */
        STORE_DATAREAD_DRI(l_currAddr_u32,l_buff_u16,l_sendLen_u16);

        /* 调用SCI发送函数 */
        /* 维护下载按2ms/16Byte节拍发送，保持与地面维护口既有吞吐约定一致。 */
        SciSendBuff(s_422CommIDConf_u16[COMM422_MAINT_ID],(Uint8 *)(l_buff_u16),l_sendLen_u16);

        /* 更新数据下载地址 */
        l_currAddr_u32 = l_currAddr_u32 + l_sendLen_u16;

        /* 获取28V掉电标志 */
        l_powerDownFlag_u16 = PowerDownFlagGet();

        /* 掉电标志有效时 */
        if(POWERDOWN_FLAG_VALID == l_powerDownFlag_u16)
        {
            /* 提前结束数据下载 */
            break;
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:GroundMaintProcessDataDownLoad
 *
 * 【功能描述】地面维护数据下载功能处理
 * 		   1.根据维护通信接收到的下载起始地址和地址长度，将地址区域内数据通过422通信发送
 * 		   2.若数据下载中途发生28V掉电（28V掉电标志有效），提前结束数据下载
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】	NONE
 * 【返回】               NONE
 */
/* ***************************************************************** */
void GroundMaintProcessDataDownLoad(void)
{
    const RsMaintDataInfo_t * l_pMaintData_t = CommMaintDataGet();

    if((NULL != l_pMaintData_t) && (l_pMaintData_t->downLoadAddrLen_u32 > 0UL))
    {
        DownLoadDataCommSend(l_pMaintData_t->downLoadStartAddr_u32,l_pMaintData_t->downLoadAddrLen_u32);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:GroundMaintSoftwCRCProcess
 *
 * 【功能描述】地面维护软件CRC处理
 * 		   进行软件CRC计算
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】               NONE
 */
/* ***************************************************************** */
void GroundMaintProcessSoftwCRC(void)
{
    /* 周期喂狗 */
    CycleDogFeed();

    /* 软件CRC计算  */
    s_softwCRC_u16 = calCRC16Prog(0x328000UL,0x18000UL);
}

/* ***************************************************************** */
/**
 * 【函数名】:GroundMaintProcessDataErase
 *
 * 【功能描述】地面维护信息擦除功能处理
 * 		   1.将用于FLASH擦除;
 * 		   2.周期喂狗。
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】        NONE
 * 【返回】               NONE
 */
/* ***************************************************************** */
void GroundMaintProcessDataErase(void)
{
    /* 周期喂狗  */
    CycleDogFeed();

    /* 擦除FLASH芯片 */
    SpiFlashBulkErase();
}

/* ***************************************************************** */
/**
 *    [函数名]	 WriteToRs422Buff
 *
 *    [功能描述]	 422通信接收数据写入缓冲区
 *    			  将接收到的数据写入通信缓冲区，写入缓冲区时对报文帧头一、帧头二进行过滤。
 *    [输入参数说明] v_commID_u16  ---- RS422通道ID，可能取值为:
 *              	SCI_A_ID ---- SCIA接口
 *              	SCI_B_ID ---- SCIB接口
 *              	SCI_C_ID ---- SCIC接口
 *              v_pBuff_u8  ---- 通信缓存区数组指针
 *              v_buffLen_u16---- 写入缓存区数据长度
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		 NONE
 */
/* ***************************************************************** */
void WriteToRs422Buff(Uint16 v_commID_u16, Uint16 *v_pBuff_u8, Uint16 v_buffLen_u16)
{
    Uint16 l_len_u16        = 0U;  /* 数据长度        */
    Uint16 l_ii_u16         = 0U;  /* 循环索引        */
    Uint16 l_headErrCnt_u16 = 0U;  /* 帧头错误计数 */

    /* 通道ID小于端口数 且 输入数组指针不为空 且 缓存区数据长度不等于0 */
    if((v_commID_u16 < COMM422_ID_NUM) && (NULL != v_pBuff_u8) && ( 0U != v_buffLen_u16))
    {
        /* 更新通信状态信息 */
        s_rs422CommInfo_t[v_commID_u16].rxBytesCount_u16 = s_rs422CommInfo_t[v_commID_u16].rxBytesCount_u16 + v_buffLen_u16;
        s_rs422CommInfo_t[v_commID_u16].rxBytesTime_u32  = sysTime();

        /* 将数据写入缓冲区 */
        for( l_ii_u16 = 0U; l_ii_u16 < v_buffLen_u16; l_ii_u16++)
        {
            /* 获取当前通道缓冲区数据索引 */
            l_len_u16 = s_rs422CommBuff_t[v_commID_u16].index_u16;

            /* 数据长度小于通信缓存区数据长度 */
            if( l_len_u16 < s_Rs422CommLenConfBuff_t[v_commID_u16].rxBuffLen_u16 )
            {
                l_headErrCnt_u16 = 0U; /* 帧头校验异常计数清零  */

                /* 对帧头一进行过滤 */
                if( (0U == l_len_u16) && ( RS422_COMM_FRAME_HEAD_1 != (v_pBuff_u8[l_ii_u16] & 0xFFU)) )
                {
                    /* 帧头校验异常计数加1 */
                    l_headErrCnt_u16 = l_headErrCnt_u16 + 1U;
                }

                /* 对帧头二进行过滤 */
                if( (1U == l_len_u16) && ( RS422_COMM_FRAME_HEAD_2 != (v_pBuff_u8[l_ii_u16] & 0xFFU)) )
                {
                    l_len_u16 = 0U ;
                    s_rs422CommBuff_t[v_commID_u16].index_u16 = 0U;

                    /* 当帧头二错误时，继续检测帧头一合法性 */
                    if( RS422_COMM_FRAME_HEAD_1 != (v_pBuff_u8[l_ii_u16] & 0xFFU) )
                    {
                        /* 帧头校验异常计数加1 */
                        l_headErrCnt_u16 = l_headErrCnt_u16 + 1U;
                    }
                }

                /* 无帧头校验异常为0时 */
                if(0U == l_headErrCnt_u16)
                {
                    /* 将新接收数据存入通信缓冲区数据 */
                    s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_len_u16] = v_pBuff_u8[l_ii_u16] & 0xFFU;
                    s_rs422CommBuff_t[v_commID_u16].index_u16 = s_rs422CommBuff_t[v_commID_u16].index_u16 + 1U;
                }
            }
            else
            {
                /* 更新缓冲区溢出计数 */
                s_rs422CommBuff_t[v_commID_u16].overCount_u16 = s_rs422CommBuff_t[v_commID_u16].overCount_u16 + v_buffLen_u16 - l_ii_u16;

                /* 当缓冲区满时，不再往缓冲区中写数 */
                break;
            }
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	 Comm422BuffCheckTimeGet
 *
 *    [功能描述]	 422通信报文检索次数获取
 *    			  依据缓冲区中数据个数，确定报文的检索次数
 *    [输入参数说明] v_commID_u16  ---- RS422通道ID，可能取值为:
 *              	SCI_A_ID ---- SCIA接口
 *              	SCI_B_ID ---- SCIB接口
 *              	SCI_C_ID ---- SCIC接口
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		 当前缓冲区中报文的检索次数
 */
/* ***************************************************************** */
Uint16 Comm422BuffCheckTimeGet(Uint16 v_commID_u16)
{
    Uint16 l_rData_u16 = 0U;  /* 检索次数，默认返回0 */

    /* 通道号ID小于通道数时  */
    if( v_commID_u16 < COMM422_ID_NUM )
    {
        /* 缓存区数据个数在有效范围内 */
        if( ( s_rs422CommBuff_t[v_commID_u16].index_u16 >= s_Rs422CommLenConfBuff_t[v_commID_u16].rxFrameLen_u16 ) &&
            ( s_rs422CommBuff_t[v_commID_u16].index_u16 <  s_Rs422CommLenConfBuff_t[v_commID_u16].rxBuffLen_u16  ) )
        {
            /* 获取缓冲区中报文的检索次数  */
            l_rData_u16 = s_rs422CommBuff_t[v_commID_u16].index_u16 - s_Rs422CommLenConfBuff_t[v_commID_u16].rxFrameLen_u16 + 1U;
        }

        /* 缓存区数据个数超出缓存数据长度 */
        else if( s_rs422CommBuff_t[v_commID_u16].index_u16 >= s_Rs422CommLenConfBuff_t[v_commID_u16].rxBuffLen_u16)
        {
            /* 获取缓冲区中报文的检索次数  */
            l_rData_u16 = s_Rs422CommLenConfBuff_t[v_commID_u16].rxBuffLen_u16 - s_Rs422CommLenConfBuff_t[v_commID_u16].rxFrameLen_u16 + 1U;
        }
        else
        {
            /* 缓冲区中报文的检索次数清零  */
            l_rData_u16 = 0U;
        }
    }

    /* 返回检索次数  */
    return l_rData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]	 Comm422FrameCheck
 *
 *    [功能描述]	 422通信有效报文检测
 *    			  检测对应通道接收缓冲区是否存在有效报文。
 *    [输入参数说明] v_commID_u16  ---- RS422通道ID，可能取值为:
 *              	SCI_A_ID ---- SCIA接口
 *              	SCI_B_ID ---- SCIB接口
 *              	SCI_C_ID ---- SCIC接口
 *	  [输出参数说明] NONE
 *    [其他说明]	    NONE
 *    [返回]		 返回有效报文首数据在缓冲区中索引，无有效报文时，返回:RS422_COMM_FRAM_NOT_EXIST
 */
/* ***************************************************************** */
Uint16 Comm422FrameCheck(Uint16 v_commID_u16)
{
    Uint16 l_ii_u16         = 0U;  /* 循环索引ii  */
    Uint16 l_jj_u16         = 0U;  /* 循环索引jj  */
    Uint16 l_count_u16      = 0U;  /* 计数                  */
    Uint16 l_sum_u16        = 0U;  /* 数据和               */
    Uint16 l_headErrCnt_u16 = 0U;  /* 帧头错误计数   */
    Uint16 l_rData_u16      = RS422_COMM_FRAM_NOT_EXIST;  /* 检测结果，默认没有合法报文 */

    /* 通道号ID小于通道数时  */
    if( v_commID_u16 < COMM422_ID_NUM )
    {
        /* 获取缓冲区中报文数据检索次数 */
        l_count_u16 = Comm422BuffCheckTimeGet(v_commID_u16);

        for( l_ii_u16 = 0U; l_ii_u16 < l_count_u16; l_ii_u16++)
        {
            l_headErrCnt_u16 = 0U;  /* 帧头错误计数清零  */

            /* 报文帧头一是否合法 */
            if(RS422_COMM_FRAME_HEAD_1 != (s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16] & 0xFFU))
            {
                /* 帧头校验异常计数加1 */
                l_headErrCnt_u16 = l_headErrCnt_u16 + 1U;
            }

            /* 报文帧头二是否合法 */
            if(RS422_COMM_FRAME_HEAD_2 != (s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16 + 1U] & 0xFFU))
            {
                /* 帧头校验异常计数加1 */
                l_headErrCnt_u16 = l_headErrCnt_u16 + 1U;
            }

            /* 无帧头校验异常时进行数据和校验 */
            if( 0U == l_headErrCnt_u16)
            {
                /* 计算报文累加和 */
                l_sum_u16 = 0U;
                for( l_jj_u16 = 0U; l_jj_u16 <(s_Rs422CommLenConfBuff_t[v_commID_u16].rxFrameLen_u16 - 1U) ; l_jj_u16++)
                {
                    l_sum_u16 = l_sum_u16 + (s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_jj_u16+l_ii_u16] & 0xFFU);
                }

                /*取反加1*/
                l_sum_u16 = (((~l_sum_u16) + 1U) & 0xFFU);

                /* 判断累加和低八位与通信接收缓冲区数组最后一位数据是否相等 */
                if(s_rs422CommBuff_t[v_commID_u16].commBuff_u16[s_Rs422CommLenConfBuff_t[v_commID_u16].rxFrameLen_u16 - 1U+l_ii_u16] == l_sum_u16)
                {
                    /* 返回有效报文首数据索引 */
                    l_rData_u16 = l_ii_u16;

                    /* 记录通信接收报文状态信息 */
                    s_rs422CommInfo_t[v_commID_u16].rxFrameCount_u16 = s_rs422CommInfo_t[v_commID_u16].rxFrameCount_u16 + 1U;
                    s_rs422CommInfo_t[v_commID_u16].rxFrameTime_u32  = sysTime();

                    /* 跳出FOR循环 */
                    break;
                }
            }
        }
    }

    /* 返回检测结果 */
    return l_rData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]	 Comm422FrameProcess
 *
 *    [功能描述]	 422通信报文处理
 *
 *    [输入参数说明] v_commID_u16  ---- RS422通道ID，可能取值为:
 *              	SCI_A_ID ---- SCIA接口
 *              	SCI_B_ID ---- SCIB接口
 *              	SCI_C_ID ---- SCIC接口
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
Uint16 Comm422FrameProcess(Uint16 v_commID_u16)
{
    Uint16 l_frameIndex_u16 = RS422_COMM_FRAM_NOT_EXIST;  /* 有效帧起始索引 */

    if( (v_commID_u16 < COMM422_ID_NUM) &&
        (s_rs422CommBuff_t[v_commID_u16].index_u16 >= s_Rs422CommLenConfBuff_t[v_commID_u16].rxFrameLen_u16) )
    {
        l_frameIndex_u16 = Comm422FrameCheck(v_commID_u16);

        /* 计数与时间戳在Comm422FrameCheck()内更新，这里仅返回有效帧索引。 */
    }

    return l_frameIndex_u16;
}



/* ***************************************************************** */
/**
 * 【函数名】:Comm422SciErrProcess
 *
 * 【功能描述】422底层SCI通信错误处理
 * 【输入参数说明】v_commID_u16  ---- RS422通道ID，可能取值为:
 *              SCI_A_ID ---- SCIA接口
 *              SCI_B_ID ---- SCIB接口
 *              SCI_C_ID ---- SCIC接口
 * 【输出参数说明】NONE
 * 【其他说明】	  NONE
 * 【返回】		  返回底层SCI通信状态
 *          SCI_COMM_OK  ---- SCI底层通信正常
 *          SCI_COMM_ERR ---- SCI底层通信存在错误
 *          SCI_COMM_OVF ---- SCI底层通信接收FIFO溢出
 */
/* ***************************************************************** */
Uint16 Comm422SciErrProcess(Uint16 v_commID_u16)
{
    Uint16 l_tempStatus_u16 = 0U;           /* 数据状态                                   */
    Uint16 l_rData_u16      = SCI_COMM_OK;  /* 底层SCI通信状态，函数返回 */

    /* 获取SCI接口接收状态标志 */
    l_tempStatus_u16 = SciRxStatusGet(s_422CommIDConf_u16[v_commID_u16]);

    /* SCI接收底层接收错误时 */
    if( 0U != (SCI_RX_ERR & l_tempStatus_u16) )
    {
        /* SCI接口复位 */
        SciReset(s_422CommIDConf_u16[v_commID_u16]);

        /* 返回SCI底层通信错误 */
        l_rData_u16 = SCI_COMM_ERR;
    }
    /* SCI发生FIFO接收溢出时 */
    else if( 0U != (SCI_RX_FIFO_OVFL & l_tempStatus_u16))
    {
        /* 清除接收FIFO溢出标志位 */
        SciRxFFOVClear(s_422CommIDConf_u16[v_commID_u16]);

        /* 返回FIFO接收溢出 */
        l_rData_u16 = SCI_COMM_OVF;
    }
    else
    {
         /* 返回SCI底层通信正常 */
        l_rData_u16 = SCI_COMM_OK;
    }

    /* 返回底层SCI通信状态 */
    return l_rData_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:Comm422DataBuffRead
 *
 * 【功能描述】422通信硬件缓冲区数据获取
 * 【输入参数说明】v_commID_u16  ---- RS422通道ID，可能取值为:
 *              SCI_A_ID ---- SCIA接口
 *              SCI_B_ID ---- SCIB接口
 *              SCI_C_ID ---- SCIC接口
 * 【输出参数说明】NONE
 * 【其他说明】	   NONE
 * 【返回】	   NONE
 */
/* ***************************************************************** */
void Comm422DataBuffRead(Uint16 v_commID_u16)
{
    Uint16 l_tempCount_u16  = 0U;           /* 临时计数  */
    Uint16 l_tempStatus_u16 = SCI_COMM_OK;  /* 数据状态  */

    /* 通道号小于通道数时 */
    if( v_commID_u16 < COMM422_ID_NUM )
    {
        /* SCI接口底层接收错误处理 */
        l_tempStatus_u16 = Comm422SciErrProcess(v_commID_u16);

        if(SCI_COMM_OVF == l_tempStatus_u16)
        {
            /* FIFO 溢出后，软件缓存中的半帧已经失去连续性，必须一并清场。 */
            s_rs422CommBuff_t[v_commID_u16].overCount_u16 += 1U;
            Comm422RxBufferClear(v_commID_u16);
        }

        /* SCI接收正常或仅有溢出错误时  */
        if( SCI_COMM_ERR != l_tempStatus_u16 )
        {
            /* SCI接收FIFO字节个数获取 */
            l_tempCount_u16 = SciRxFIFOCount(s_422CommIDConf_u16[v_commID_u16]);

            /* SCI数组数据读取   */
            SciReadBuff(s_422CommIDConf_u16[v_commID_u16],s_tempRxBuff_u16,l_tempCount_u16);

            /* 接收字节个数大于0时  */
            if( l_tempCount_u16 > 0U)
            {
                /* 将数据写入接收缓冲区 */
                WriteToRs422Buff(v_commID_u16,s_tempRxBuff_u16,l_tempCount_u16);
            }
        }
        else
        {
            /* 错误计数加1 */
            s_rs422CommInfo_t[v_commID_u16].sciErrCount_u16 = s_rs422CommInfo_t[v_commID_u16].sciErrCount_u16 + 1U;
        }
    }
}



/* ***************************************************************** */
/**
 * 【函数名】:Comm422RxStateCheck
 *
 * 【功能描述】422通信接收状态检测
 * 【输入参数说明】v_commID_u16  ---- RS422通道ID，可能取值为:
 *              SCI_A_ID ---- SCIA接口
 *              SCI_B_ID ---- SCIB接口
 *              SCI_C_ID ---- SCIC接口
 * 【输出参数说明】NONE
 * 【其他说明】	   NONE
 * 【返回】	   NONE
 */
/* ***************************************************************** */
void Comm422RxStateCheck(Uint16 v_commID_u16)
{
    Uint16 l_rData_u16 = RS422_COMM_RX_OK;   /* 通信接收状态，默认通信接收正常  */

    /* 通道号小于通道数 */
    if( v_commID_u16 < COMM422_ID_NUM )
    {
        /* 接收检查数据时间更新为系统时间计数  */
        s_rs422CommInfo_t[v_commID_u16].checkRxTime_u32 = sysTime();

        /* 超时2个周期数据接收时间没更新时  */
        if( s_rs422CommInfo_t[v_commID_u16].checkRxTime_u32 > (s_rs422CommInfo_t[v_commID_u16].rxBytesTime_u32 + (2UL * COMM422_MAINT_PRIOD)) )
        {
            /* 422接收无数状态异常 */
            l_rData_u16 = l_rData_u16 | RS422_COMM_RX_NO_BYTES_ERR;
        }
        else /*RS422数据接收正常*/
        {
            /* 超时2个周期有效报文接收时间没更新时  */
            if( s_rs422CommInfo_t[v_commID_u16].checkRxTime_u32 > (s_rs422CommInfo_t[v_commID_u16].rxFrameTime_u32 + (2UL * COMM422_MAINT_PRIOD)) )
            {
                /* 422接收有效报文状态异常 */
                l_rData_u16 = l_rData_u16 | RS422_COMM_RX_NO_FRAMES_ERR;
            }
        }

        /* 更新接收状态 */
        s_rs422CommInfo_t[v_commID_u16].rxState_u16 = l_rData_u16;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:Comm422FrameCleanup
 * 【功能描述】RS422帧缓存清理,清空指定通道的接收缓冲区及状态
 * 【输入参数说明】v_commID_u16 ---- 通信通道ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void Comm422FrameCleanup(Uint16 v_commID_u16)
{
    Uint16 l_ii_u16;

    if( v_commID_u16  < COMM422_ID_NUM )
    {
        if( s_rs422CommBuff_t[v_commID_u16].index_u16 >= s_Rs422CommLenConfBuff_t[v_commID_u16].rxFrameLen_u16 )
        {
            s_rs422CommBuff_t[v_commID_u16].index_u16 = 0U;

            for( l_ii_u16 = 0U; l_ii_u16 < s_Rs422CommLenConfBuff_t[v_commID_u16].rxBuffLen_u16; l_ii_u16++)
            {
                s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16] = 0U;
            }
        }

        Comm422RxStateCheck(v_commID_u16);
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	 Comm422Init
 *
 *    [功能描述]	 422通信数据初始化
 *    			  对RS422通信数据、通信状态数据、错误计数进行初始化。
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void Comm422Init(void)
{
    Uint16 l_ii_u16 = 0U;   /* 循环索引ii */
    Uint16 l_jj_u16 = 0U;   /* 循环索引jj */

    for( l_ii_u16 = 0U; l_ii_u16 < COMM422_ID_NUM; l_ii_u16++)
    {
        /* 422通信接收缓冲区初始化 */
        s_rs422CommBuff_t[l_ii_u16].index_u16        = 0U;     /* 422通信缓冲区数据索引清零        */
        s_rs422CommBuff_t[l_ii_u16].overCount_u16    = 0U;     /* 422通信缓冲区数据溢出计数清零 */
        s_rs422CommBuff_t[l_ii_u16].timeOutCount_u16 = 0U;     /* 422通信缓冲区数据超时计数 清零 */
        s_rs422CommBuff_t[l_ii_u16].headErrCount_u16 = 0U;     /* 422通信缓冲区帧头错误计数清零  */

        /* 422通信缓冲区数据清零 */
        for( l_jj_u16 = 0U; l_jj_u16 < COMM_MAINT_RX_BUFF_LEN; l_jj_u16++)
        {
            s_rs422CommBuff_t[l_ii_u16].commBuff_u16[l_jj_u16] = 0U;
        }

        /* 通信状态信息初始化 */
        s_rs422CommInfo_t[l_ii_u16].rxBytesCount_u16 = 0U;                /* 接收数据计数清零         */
        s_rs422CommInfo_t[l_ii_u16].rxBytesTime_u32  = 0UL;               /* 接收数据时间清零          */
        s_rs422CommInfo_t[l_ii_u16].checkRxTime_u32  = 0U;                /* 接收检查数据时间清零  */
        s_rs422CommInfo_t[l_ii_u16].rxFrameCount_u16 = 0U;                /* 接收报文计数清零          */
        s_rs422CommInfo_t[l_ii_u16].rxFrameTime_u32  = 0UL;               /* 最新接收报文时间清零  */
        s_rs422CommInfo_t[l_ii_u16].sciErrCount_u16  = 0U;                /* SCI底层错误计数清零   */
        s_rs422CommInfo_t[l_ii_u16].rxState_u16      = RS422_COMM_RX_OK;  /* 通信接收状态正常           */
    }

    /* 通信接收数据临时缓存数组初始化 */
    memset(s_tempRxBuff_u16,0U,sizeof(s_tempRxBuff_u16));

    /***********************************************************************/
    /* 初始化软件版本信息 */
    s_mySoftwVData_un16.bit.soft_version1 = DSP_SOFT_VERSION1;
    s_mySoftwVData_un16.bit.soft_version2 = DSP_SOFT_VERSION2;
    s_mySoftwVData_un16.bit.soft_version3 = DSP_SOFT_VERSION3;
    s_mySoftwVData_un16.bit.soft_version4 = DSP_SOFT_VERSION4;

    /* 软件CRC计算  */
    s_softwCRC_u16 = calCRC16Prog(0x320000UL,0x18000UL);
    s_softwCRC_Update_u16 = calCRC16Prog(0x338000UL,0x7FF8UL);

    /*****************************************/
    /* 维护通信接收信息初始化 */
    s_rsMaintData_t.rxFrameCnt_u16        = 0U;                         /* 维护通信接收帧计数清零   */
    s_rsMaintData_t.MaintStateCode_u16    = MAINT_CODE_STATE_INVALID;         /* 维护状态码无效                  */
    s_rsMaintData_t.MaintCMDCode_u16      = MAINT_CODE_CMD_INVALID;         /* 维护指令码无效                  */
    s_rsMaintData_t.MaintFuncCode_u16     = GROUND_MAINT_FUNC_INVALID;  /* 地面维护功能码无效           */
    s_rsMaintData_t.A429InfoID_u16        = COMM_MAINT_TX_COMM429_INFO_RMC_1; /* 通信信息ID号初始化为RMC1   */
    s_rsMaintData_t.FlowB422InfoID_u16    = COMM_MAINT_TX_COMMFLOWB_INFO_1;   /* 422通信信息ID号初始化为流量测量盒1   */
    s_rsMaintData_t.readAddr_u32          = 0U; /* 读取数据地址初始化为0 */
    s_rsMaintData_t.RudunInfoID_u16       = 0U; /* 余度数据索引初始化为0 */
    s_rsMaintData_t.SoftVInfoID_u16       = 0U; /* 软件版本信息ID号初始化为0 */
    s_rsMaintData_t.AnaInfoID_u16         = 0U; /* 模拟量信息ID号初始化为0   */
    s_rsMaintData_t.BengInfoID_u16        = 0U; /* 泵控制器信息ID号初始化为0   */
    s_rsMaintData_t.A429RxLabel_u16       = 0U; /* 429通信接收标号初始化为0   */

    s_rsMaintData_t.cmdUpdateflag_u16     = COMM_MAINT_R_CMD_FLAG_INVALID; /* 指令更新标志无效  */
    s_rsMaintData_t.cmdInfoID_u16         = COMM_MAINT_R_CON_CMD_JYB_1;    /* 维护指令索引-加油泵1指令  */

    s_rsMaintData_t.downLoadStartAddr_u32 = 0UL;  /* 数据下载起始地址清零   */
    s_rsMaintData_t.downLoadAddrLen_u32   = 0UL;  /* 数据下载地址长度清零    */
    s_rsMaintData_t.MaintFuncLastExe_u16  = GROUND_MAINT_FUNC_INVALID;  /* 最近执行功能码初始化 */
    s_rsMaintData_t.MaintFuncExeResult_u16 = MAINT_FUNC_EXE_RESULT_NONE; /* 最近执行结果初始化 */
}

/* ========================================================================== */
/* END OF FILE */
/* ========================================================================== */
