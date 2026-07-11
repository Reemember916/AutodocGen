/* 应用层通信模块 — RS422 帧校验 */

#include "APP_Config.h"
#include "Common/Common.h"

/*
 * [函数名] Comm422FrameCheck
 * [功能说明] 校验 RS422 通信接收报文帧头，确认报文完整性。
 * 检测帧头1（低8位）和帧头2是否匹配，并计算校验和。
 * [输入参数说明] buf: 接收缓冲区指针; len: 缓冲区长度
 * [输出参数说明] 无
 * [返回说明] 校验结果（0=通过，1=帧头错误，2=校验和错误）
 */
Uint16 Comm422FrameCheck(Uint16 *buf, Uint16 len)
{
    Uint16 l_ii_u16         = 0U;
    Uint16 l_jj_u16         = 0U;
    Uint16 l_count_u16      = 0U;
    Uint16 l_sum_u16        = 0U;
    Uint16 l_headErrCnt_u16 = 0U;
    
    if (buf == NULL || len < 4U)
    {
        return 1U;
    }
    
    /* RS422通信接收报文帧头1 */
    if (COMM_RS422_HEAD_1 == (buf[0] & 0xFFU))
    {
        l_count_u16 = 1U;
    }
    else
    {
        l_headErrCnt_u16 = l_headErrCnt_u16 + 1U;
    }
    
    /* RS422通信接收报文帧头2 */
    if (COMM_RS422_HEAD_2 == (buf[1] & 0xFFU))
    {
        l_count_u16 = l_count_u16 + 1U;
    }
    else
    {
        l_headErrCnt_u16 = l_headErrCnt_u16 + 1U;
    }
    
    /* 计算校验和 */
    for (l_ii_u16 = 0U; l_ii_u16 < (len - 1U); l_ii_u16++)
    {
        l_sum_u16 = (l_sum_u16 + buf[l_ii_u16]) & 0xFFU;
    }
    
    /* 校验和验证 */
    l_sum_u16 = (~l_sum_u16 + 1U) & 0xFFU;
    
    if (l_sum_u16 != buf[len - 1U])
    {
        return 2U;
    }
    
    if (l_headErrCnt_u16 > 0U)
    {
        return 1U;
    }
    
    return 0U;
}