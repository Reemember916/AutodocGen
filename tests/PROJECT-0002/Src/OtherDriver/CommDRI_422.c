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
 * 文件名称:   CommDRI_422.c
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V1.00
 *
 **********************************************************************************
 *
 * 功能说明:    本功能模块，实现基于CCDL的RS422通信底层接口
 *
 *********************************************************************************/

#include "Global.h"

/* ***************************************************************** */
/* 本地数据定义 */

/* CCDL寄存器地址设置  */
Reg422Conf_t s_CCDL422RegConfs_t[COMMDRI_422_NUM] = {COMM422_0_REG_CONF_TAB};

/* ***************************************************************** */
/*
 *【函数名】 Ccdl422ReadBuff
 *【功能描述】CCDL422数据读取
 *		     从CCDL双端口读取数据到缓存数组中。
 *【输入参数说明】v_ccdlID_u16 --- CCDL 端口号
 *		      v_pBuff_u8  --- 接收数据数组指针
 *【输出参数说明】NONE
 *【其他说明】       读FIFO时每个数据字均单独写一次DRI422_R_EN_VALID，
 *                  与双端口“单拍出队”语义匹配；该接口按U16数组承载，实际有效载荷为低8bit。
 *【返回】              接收字个数
***************************************************************** */
Uint16 Ccdl422ReadBuff(Uint16 v_ccdlID_u16,Uint16 *v_pBuff_u8)
{
    Uint16 l_index_u16 = 0U;  /* 索引    */
    Uint16 l_rxCnt_u16 = 0U;  /* 接收计数    */

    /* 端口号小于端口数  且 输入指针不为空  */
    if( ( v_ccdlID_u16 < COMMDRI_422_NUM ) && ( NULL != v_pBuff_u8 ))
    {
        /* 获取接收FIFO可读计数 */
        l_rxCnt_u16 = *(volatile Uint16 *)(s_CCDL422RegConfs_t[v_ccdlID_u16].RReg_FiFo_Cnt_u16);

        if(l_rxCnt_u16 > 0U)  /* 接收计数大于0时，FIFO有数据 */
        {
            /* 接收计数限幅 */
            if(l_rxCnt_u16 > CCDL_RX_DATA_NUM_MAX)
            {
                l_rxCnt_u16 = CCDL_RX_DATA_NUM_MAX;  /* 接收计数最大值限幅 */
            }

            /* FIFO读取数据 */
            for(l_index_u16 = 0U;l_index_u16 < l_rxCnt_u16;l_index_u16++)
            {
                /* 每读取1字都打一次读使能脉冲，触发FIFO弹出当前字。 */
                (*(volatile Uint16 *)(s_CCDL422RegConfs_t[v_ccdlID_u16].WReg_rFifo_EN_u16)) = DRI422_R_EN_VALID;

                /* 双端口返回U16容器，协议数据位于低8bit。 */
                v_pBuff_u8[l_index_u16] = (*(volatile Uint16 *)(s_CCDL422RegConfs_t[v_ccdlID_u16].RReg_FiFo_Data_u16));

            }
        }
    }

    /* 返回接收计数 */
    return l_rxCnt_u16;
}


/* ***************************************************************** */
/*
 *【函数名】 Ccdl422RFIFOReset
 *【功能描述】CCDL422接收FIFO复位
 *		     从CCDL双端口读取数据到缓存数组中。
 *【输入参数说明】v_ccdlID_u16 --- CCDL 端口号
 *【输出参数说明】NONE
 *【其他说明】       复位采用“置位后清零”的脉冲式写法，避免保持复位电平导致后续接收被抑制。
 *【返回】             NONE
***************************************************************** */
void Ccdl422RFIFOReset(Uint16 v_ccdlID_u16)
{
    /* 端口号小于端口数  且 输入指针不为空  */
    if(  v_ccdlID_u16 < COMMDRI_422_NUM )
    {
        /* 拉高复位，触发FIFO清空。 */
        *(volatile Uint16 *)(s_CCDL422RegConfs_t[v_ccdlID_u16].WReg_resetRFifo_u16) = DRI422_RFIFO_RESET_EN_VALID;

        /* 立即拉低，形成有效复位脉冲并恢复正常工作。 */
        *(volatile Uint16 *)(s_CCDL422RegConfs_t[v_ccdlID_u16].WReg_resetRFifo_u16) = DRI422_RFIFO_RESET_EN_INVALID;
    }
}

/* ***************************************************************** */
/*
 *【函数名】 CcdlSendBuff
 *【功能描述】与CPLD的CCDL数组数据发送
 *【输入参数说明】v_ccdlID_u16 --- CCDL 端口号
 *		      v_pBuff_u8  --- 发送数据数组指针
 *		      v_len_u16    --- 发送数组长度
 *【输出参数说明】NONE
 *【其他说明】       常温下实测：2M波特率下发送1个字节（11bit）超时等待7us左右（包括程序运行执行时间）；
 *                  本函数不检查发送FIFO可写深度、不做超时等待，调用方需保证调用节拍与链路带宽匹配。
 *【返回】              发送字个数，默认返回0
***************************************************************** */
void Ccdl422SendBuff(Uint16 v_ccdlID_u16,Uint16 *v_pBuff_u16,Uint16 v_len_u16)
{
    Uint16 l_ii_u16 = 0U;  /* 循环计数    */

    /* 端口号小于端口数 且 输入数组指针不为空 且 发送长度大于0 */
    if( ( v_ccdlID_u16 < COMMDRI_422_NUM ) && ( NULL != v_pBuff_u16 ) && ( v_len_u16 > 0U))
    {
        /* 发送数据 */
        for(l_ii_u16 = 0U;l_ii_u16 < v_len_u16;l_ii_u16++)
        {
            /* 发送寄存器写数据 */
            *(volatile Uint16 *)(s_CCDL422RegConfs_t[v_ccdlID_u16].WReg_wData_u16) = v_pBuff_u16[l_ii_u16];
        }
    }
}

/* ***************************************************************** */
/*
 *【函数名】 Ccdl422RxFifoStatusGet
 *【功能描述】CCDL422接收FIFO状态获取
 *【输入参数说明】v_ccdlID_u16 --- 端口号
 *【输出参数说明】NONE
 *【其他说明】       NONE
 *【返回】              CCDL通信FIFO接收状态,取值如下：
 *			DRI422_R_FIFO_OK   ----  CCDL FIFO接收正常
 *			DRI422_R_FIFO_OVFL ----  CCDL FIFO接收溢出
***************************************************************** */
Uint16 Ccdl422RxFifoStatusGet(Uint16 v_ccdlID_u16)
{
    Uint16 l_LSRData_u16 = 0U;               /* 寄存器数据  */
    Uint16 l_rData_u16   = DRI422_R_FIFO_OK;  /* FIFO接收状态，函数返回，默认FIFO接收正常  */

    /* 端口号小于端口数  */
    if( v_ccdlID_u16 < COMMDRI_422_NUM )
    {
        /* 获取接收FIFO可读个数 */
        l_LSRData_u16 = *(volatile Uint16 *)(s_CCDL422RegConfs_t[v_ccdlID_u16].RReg_FiFo_Cnt_u16);

        /* 接收FIFO溢出时 */
        if(l_LSRData_u16 >= CCDL_RX_DATA_NUM_MAX)
        {
            /* FIFO接收状态置为接收FIFO溢出 */
            l_rData_u16 = DRI422_R_FIFO_OVFL;
        }
    }

    /* 返回FIFO接收状态 */
    return l_rData_u16;
}

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
