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

/* CCDL429通信ID号设置  */
Reg429Conf_t s_CCDL429RegConfs_t[COMMDRI_429_NUM] =
      { COMM429_0_REG_CONF_TAB,
        COMM429_1_REG_CONF_TAB,
        COMM429_2_REG_CONF_TAB,
        COMM429_3_REG_CONF_TAB,
        COMM429_4_REG_CONF_TAB,
        COMM429_5_REG_CONF_TAB,
        COMM429_6_REG_CONF_TAB,
        COMM429_7_REG_CONF_TAB,
        COMM429_8_REG_CONF_TAB,
        COMM429_9_REG_CONF_TAB,
        COMM429_10_REG_CONF_TAB,
        COMM429_11_REG_CONF_TAB,
       };

/* ***************************************************************** */
/*
 *【函数名】 Ccdl429RxFifoStatusGet
 *【功能描述】429通信接收FIFO状态获取
 *【输入参数说明】v_ccdlID_u16 --- CCDL 端口号
 *【输出参数说明】NONE
 *【其他说明】       NONE
 *【返回】              CCDL通信FIFO接收状态,取值如下：
 *			CCDL_RX_FIFO_OK   ----  CCDL FIFO接收正常
 *			CCDL_RX_FIFO_OVFL ----  CCDL FIFO接收溢出
***************************************************************** */
Uint16 Ccdl429RxFifoStatusGet(Uint16 v_ccdlID_u16)
{
    Uint16 l_LSRData_u16 = 0U;               /* LSR寄存器数据  */
    Uint16 l_rData_u16   = DRI422_R_FIFO_OK;  /* FIFO接收状态，函数返回，默认FIFO接收正常  */

    /* 端口号小于端口数  */
    if( v_ccdlID_u16 < COMMDRI_429_NUM )
    {
        /* 获取接收FIFO可读个数 */
        l_LSRData_u16 = *(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].RReg_FiFo_Cnt_u16);

        /* 接收FIFO溢出时 */
        if(l_LSRData_u16 >= A429_RX_DATA_NUM_MAX)
        {
            /* FIFO接收状态置为接收FIFO溢出 */
            l_rData_u16 = DRI429_R_FIFO_OVFL;
        }
    }

    /* 返回FIFO接收状态 */
    return l_rData_u16;
}

/* ***************************************************************** */
/*
 *【函数名】 Ccdl429RFIFOReset
 *【功能描述】CCDL429接收FIFO复位
 *【输入参数说明】v_ccdlID_u16 --- CCDL 端口号
 *【输出参数说明】NONE
 *【其他说明】       NONE
 *【返回】             NONE
***************************************************************** */
void Ccdl429RFIFOReset(Uint16 v_ccdlID_u16)
{
    /* 端口号小于端口数  且 输入指针不为空  */
    if(  v_ccdlID_u16 < COMMDRI_429_NUM )
    {
        /* 接收FIFO复位使能 */
        *(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].WReg_resetRFifo_u16) = DRI429_RFIFO_RESET_EN_VALID;

        /* 接收FIFO复位关闭 */
        *(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].WReg_resetRFifo_u16) = DRI429_RFIFO_RESET_EN_INVALID;
    }
}

/* ***************************************************************** */
/*
 *【函数名】 Ccdl429ParityCalc
 *【功能描述】Ccdl429数据校验
 *		     计算前31位0、1个数填充校验位。
 *【输入参数说明】v_msgData_un  --- 输入429发送数据数据
 *【输出参数说明】NONE
 *【其他说明】       按ARINC429口径仅统计bit1~bit31数据位，再写bit32奇偶校验位；
 *                  调用方不应再重复改写parity位。
 *【返回】              填充校验位后429发送数据
***************************************************************** */
union arinc429Data Ccdl429ParityCalc(union arinc429Data v_msgData_un, Uint16 v_odd_u16)
{
    Uint16 l_index_u16 ;      /* 循环计数  */
    Uint16 l_sum_u16 = 0U;    /* 数据和    */
    Uint16 l_temp_u16 = 0U;   /* 临时数据  */

    /* 按ARINC429定义统计前31位“1”的个数，bit32保留给parity。 */
    v_msgData_un.bit.parity = 0U;
    for(l_index_u16 = 0U;l_index_u16 < 31U;l_index_u16++)
    {
        l_sum_u16 = l_sum_u16 + ((v_msgData_un.msgData >> l_index_u16) & 0x01U);
    }

    /* 获取前31位数据1个数奇偶状态  */
    l_temp_u16 = l_sum_u16 % 2U;

    if(PARITY_ODD == v_odd_u16)
    {
        /* 不满足校验状态  */
        if(1U != l_temp_u16)
        {
            /* 校验位填充1  */
            v_msgData_un.bit.parity = 1U;
        }
        else
        {
            /* 校验位填充0  */
            v_msgData_un.bit.parity = 0U;
        }
    }
    else
    {
        /* 不满足校验状态  */
        if(0U != l_temp_u16)
        {
            /* 校验位填充1  */
            v_msgData_un.bit.parity = 1U;
        }
        else
        {
            /* 校验位填充0  */
            v_msgData_un.bit.parity = 0U;
        }
    }

    /* 返回填充校验位后429发送数据 */
    return v_msgData_un;
}

/* ***************************************************************** */
/*
 *【函数名】 Ccdl429ParityCheck
 *【功能描述】检查429数据奇偶校验是否合法
 *【输入参数说明】v_msgData_un  --- 输入429数据
 *                v_odd_u16     --- PARITY_ODD/PARITY_EVEN
 *【输出参数说明】NONE
 *【其他说明】       按完整32位统计1的个数
 *【返回】              1-校验正确 / 0-校验错误
***************************************************************** */
Uint16 Ccdl429ParityCheck(union arinc429Data v_msgData_un, Uint16 v_odd_u16)
{
    Uint16 l_index_u16 = 0U;
    Uint16 l_sum_u16 = 0U;
    Uint16 l_oddState_u16 = 0U;
    Uint16 l_rData_u16 = 0U;

    for(l_index_u16 = 0U; l_index_u16 < 32U; l_index_u16++)
    {
        l_sum_u16 = l_sum_u16 + ((v_msgData_un.msgData >> l_index_u16) & 0x01U);
    }

    l_oddState_u16 = l_sum_u16 % 2U;

    if(PARITY_ODD == v_odd_u16)
    {
        if (1U == l_oddState_u16)
        {
            l_rData_u16 = 1U;
        }
        else
        {
            l_rData_u16 = 0U;
        }
    }
    else
    {
        if (0U == l_oddState_u16)
        {
            l_rData_u16 = 1U;
        }
        else
        {
            l_rData_u16 = 0U;
        }
    }

    return l_rData_u16;
}

/* ***************************************************************** */
/*
 *【函数名】 Ccdl429LabOrderRev
 *【功能描述】Ccdl429数据标号位序反转
 *		     将数据低8位标号数据位序反转。
 *【输入参数说明】v_label_u16  --- 输入标号数据
 *【输出参数说明】NONE
 *【其他说明】       NONE
 *【返回】              反转后标号
***************************************************************** */
Uint16 Ccdl429LabOrderRev(Uint16 v_label_u16)
{
    Uint16 lo_label_u16 = 0U;  /* 反转后标号,函数输出，默认为0 */
    Uint16 l_ii_u16     = 0U;  /* 循环计数  */
    Uint16 l_temp_u16   = 0U;  /* 临时数据  */

    /* 标号bit0-bit7位查询  */
    for(l_ii_u16 = 0U;l_ii_u16 < 8U;l_ii_u16++)
    {
        /* 获取数据位状态 */
        l_temp_u16 = ((0x01U << l_ii_u16) & v_label_u16);

        /* 位bit不为0时 */
        if(0U != l_temp_u16)
        {
            /* 标号反转位bit置为1 */
            lo_label_u16 = lo_label_u16 | (0x01U << (7U - l_ii_u16));
        }
    }

    /* 返回反转后标号 */
    return lo_label_u16;
}

/* ***************************************************************** */
/*
 *【函数名】 Ccdl429ReadBuff
 *【功能描述】Ccdl429数据读取
 *		     从CCDL双端口读取数据到缓存数组中。
 *【输入参数说明】v_ccdlID_u16 --- CCDL 端口号
 *		      v_pBuff_u8  --- 接收数据数组指针
 *【输出参数说明】NONE
 *【其他说明】       每读取1个429字都重新拉一次读使能脉冲，匹配CPLD FIFO“单拍出队”语义；
 *                  本实现默认底层已完成label位序口径统一，因此不再执行软件label反转。
 *【返回】              接收字个数
***************************************************************** */
Uint16 Ccdl429ReadBuff(Uint16 v_ccdlID_u16,union arinc429Data *v_pbuff_un)
{
    Uint16 l_index_u16 = 0U;  /* 索引    */
    Uint16 l_rxCnt_u16 = 0U;  /* 接收计数    */
    Uint32 l_dataL_u32 = 0UL;  /* 低2字节数据   */
    Uint32 l_dataH_u32 = 0UL;  /* 高2字节数据    */
    Uint32 l_data429_u32 = 0UL;  /*429数据    */

    /* 端口号小于端口数  且 输入指针不为空  */
    if( ( v_ccdlID_u16 < COMMDRI_429_NUM ) && ( NULL != v_pbuff_un ))
    {
        /* 获取接收FIFO可读计数 */
        l_rxCnt_u16 = *(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].RReg_FiFo_Cnt_u16);

        if(l_rxCnt_u16 > 0U)  /* 接收计数大于0时，FIFO有数据 */
        {
            /* 接收计数限幅 */
            if(l_rxCnt_u16 > A429_RX_DATA_NUM_MAX)
            {
                l_rxCnt_u16 = A429_RX_DATA_NUM_MAX;  /* 接收计数最大值限幅 */
            }

                /* FIFO读取数据 */
                for(l_index_u16 = 0U;l_index_u16 < l_rxCnt_u16;l_index_u16++)
                {
                    /* 每个字单独拉读使能，确保FIFO按“读一次弹一次”工作。 */
                    (*(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].WReg_rFifo_EN_u16)) = DRI429_R_EN_VALID;

                /* 双端口地址读取数据 */
                l_dataL_u32 = (*(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].RReg_FiFo_2Byte_L_u16));
                l_dataH_u32 = (*(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].RReg_FiFo_2Byte_H_u16));

                    /* 读使能拉回无效，形成完整脉冲，避免FIFO被持续触发出队。 */
                    (*(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].WReg_rFifo_EN_u16)) = DRI429_R_EN_INVALID;

                /* 高低字节拼接 */
                l_data429_u32 = (l_dataH_u32 << 16U) + l_dataL_u32;

                v_pbuff_un[l_index_u16].msgData = l_data429_u32;

                /*label号翻转*/
                v_pbuff_un[l_index_u16].bit.label = Ccdl429LabOrderRev(v_pbuff_un[l_index_u16].bit.label);

                }
            }
    }

    /* 返回接收计数 */
    return l_rxCnt_u16;
}

/* ***************************************************************** */
/*
 *【函数名】 Ccdl429DataSend
 *【功能描述】CCDL429数据发送
 *【输入参数说明】v_ccdlID_u16 --- CCDL 端口号
 *		      v_mydata_un  --- 429发送数据
 *【输出参数说明】NONE
 *【其他说明】       发送前统一在驱动层补奇校验，调用方只需填label/data/ssm；
 *                  若上层已填过parity，本函数会覆盖为当前口径结果。
 *【返回】              发送字个数，默认返回0
***************************************************************** */
void Ccdl429DataSend(Uint16 v_ccdlID_u16,union arinc429Data v_mydata_un)
{
    Uint32 l_dataL_u32 = 0UL;  /* 低2字节数据   */
    Uint32 l_dataH_u32 = 0UL;  /* 高2字节数据    */
    Uint16 l_waitCnt_u16 = 0U;

    /* 端口号小于端口数 */
    if( v_ccdlID_u16 < COMMDRI_429_NUM )
    {

        /* 校验位填充 */
        v_mydata_un = Ccdl429ParityCalc(v_mydata_un,PARITY_ODD);

        /* 获取高低字节数据 */
        l_dataL_u32 =  v_mydata_un.msgData & 0xFFFFU;
        l_dataH_u32 = (v_mydata_un.msgData >> 16U) & 0xFFFFU;

        if(0U != s_CCDL429RegConfs_t[v_ccdlID_u16].RReg_TFifo_Status_u16)
        {
            while((l_waitCnt_u16 < DRI429_TX_WAIT_MAX) &&
                  (0U != ((*(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].RReg_TFifo_Status_u16)) & DRI429_T_FIFO_FULL)))
            {
                l_waitCnt_u16 = l_waitCnt_u16 + 1U;
            }
        }

        if(l_waitCnt_u16 < DRI429_TX_WAIT_MAX)
        {
            /* 发送寄存器写数据 */
            *(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].WReg_FiFo_2Byte_L_u16) = l_dataL_u32 & 0xFFFFU;
            *(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].WReg_FiFo_2Byte_H_u16) = l_dataH_u32 & 0xFFFFU;

            if(0U != s_CCDL429RegConfs_t[v_ccdlID_u16].WReg_tFifo_EN_u16)
            {
                *(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].WReg_tFifo_EN_u16) = DRI429_T_EN_VALID;
                *(volatile Uint16 *)(s_CCDL429RegConfs_t[v_ccdlID_u16].WReg_tFifo_EN_u16) = DRI429_T_EN_INVALID;
            }
        }
    }
}

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
