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
 * 文件名称:   CommDRI_CAN.c
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V1.00
 *
 **********************************************************************************
 *
 * 功能说明:    本功能模块，实现基于CCDL的CAN通信底层接口
 *
 *********************************************************************************/

#include "Global.h"

/* ***************************************************************** */
/* 本地数据定义 */

/* CCDLCAN通信ID号设置  */
RegCanConf_t s_CCDLCanRegConfs_t[COMMDRI_CAN_NUM] =
      { COMMCAN_0_REG_CONF_TAB,
        COMMCAN_1_REG_CONF_TAB,
        COMMCAN_2_REG_CONF_TAB,
        COMMCAN_3_REG_CONF_TAB,
        COMMCAN_4_REG_CONF_TAB,
        COMMCAN_5_REG_CONF_TAB,
        COMMCAN_6_REG_CONF_TAB,
        COMMCAN_7_REG_CONF_TAB,
        COMMCAN_8_REG_CONF_TAB,
        COMMCAN_9_REG_CONF_TAB,
        COMMCAN_10_REG_CONF_TAB,
        COMMCAN_11_REG_CONF_TAB
       };

/* ***************************************************************** */
/*
 *【函数名】 CcdlCanMboxSendFix
 *【功能描述】CCDLCan指定邮箱发送
 *【输入参数说明】v_mboxNum_u16 --- 发送邮箱号
 *		     vp_wBuff_u16  --- 发送数据指针
 *【输出参数说明】NONE
 *【其他说明】       按“数组前字节在高位”的口径打包：
 *                  buff[0]->bit15~8，buff[1]->bit7~0，依次写入4个U16邮箱数据寄存器。
 *【返回】              NONE
***************************************************************** */
void CcdlCanMboxSendFix(Uint16 v_mboxNum_u16,Uint16 *vp_wBuff_u16)
{
    Uint16 l_wData_u16 = 0U;   /* 发送数据，用于拼接2个字节   */
    Uint16 l_ii_u16    = 0U;   /* 循环计数    */
    Uint16 l_index_u16 = 0U;   /* 索引    */

    /* 邮箱号小于邮箱数 且 发送数组不为空 */
    if( (v_mboxNum_u16 < COMMDRI_CAN_NUM) && (NULL != vp_wBuff_u16) )
    {
        /* 将CAN发送8个字节数组数据高低拼接成4个U16数据发送  */
        for(l_ii_u16 = 0U; l_ii_u16 < COMMCAN_DATA_ADR_NUM;l_ii_u16++)
        {
            /* 获取数据索引 */
            l_index_u16 = l_ii_u16 * 2U;

            /* 字节序约定：索引偶数字节映射高8bit，奇数字节映射低8bit。 */
            l_wData_u16 = (vp_wBuff_u16[l_index_u16 + 1U] & 0xFFU) + ((vp_wBuff_u16[l_index_u16] & 0xFFU) << 8U);

            /* 发送寄存器写数据 */
            *(volatile Uint16 *)(s_CCDLCanRegConfs_t[v_mboxNum_u16].WReg_FiFo_Start_u16 + l_ii_u16) = l_wData_u16;
        }
    }
}

/* ***************************************************************** */
/*
 *【函数名】 CcdlCanMboxRx
 *【功能描述】CCDLCan指定邮箱接收
 *【输入参数说明】v_mboxNum_u16 --- 接收邮箱号
 *		     vp_wBuff_u16  --- 接收数据指针
 *【输出参数说明】NONE
 *【其他说明】       与发送函数保持同一字节序口径：
 *                  bit15~8回填到buff[偶数索引]，bit7~0回填到buff[奇数索引]。
 *【返回】              NONE
***************************************************************** */
void CcdlCanMboxRx(Uint16 v_rboxNum_u16,Uint16 *vp_rBuff_u16)
{
    Uint16 l_rData_u16 = 0U;   /* 接收数据   */
    Uint16 l_ii_u16    = 0U;   /* 循环计数    */
    Uint16 l_index_u16 = 0U;   /* 索引    */

    /* 邮箱号小于邮箱数 */
    if(v_rboxNum_u16 < COMMDRI_CAN_NUM)
    {
        /* 将CAN发送8个字节数组数据高低拼接成4个U16数据发送  */
        for(l_ii_u16 = 0U; l_ii_u16 < COMMCAN_DATA_ADR_NUM;l_ii_u16++)
        {
            /* 获取数据索引 */
            l_index_u16 = l_ii_u16 * 2U;

            /* 读取邮箱数据 */
            l_rData_u16 = *(volatile Uint16 *)(s_CCDLCanRegConfs_t[v_rboxNum_u16].RReg_FiFo_Start_u16 + l_ii_u16);

            /* 与发送打包规则镜像拆分，避免上层出现大小端错位。 */
            vp_rBuff_u16[l_index_u16 + 1U] = l_rData_u16 & 0xFFU;
            vp_rBuff_u16[l_index_u16] = (l_rData_u16 >> 8U) & 0xFFU;
        }
    }
}

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
