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
 * 文件名称:    synchronous.c
 *
 * 文件日期:   REDACTED
 *
 *
 * 【程序版本】
 *
 * 【功能描述】实现软件通道同步功能
 * 【其他说明】无
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 *
 *********************************************************************************/

#include "Global.h"

 SynInform_TypeDef s_synchInf_t;       /* 一条同步通道的信息 */
 SynWholeInform_TypeDef s_synWhle_t[SYNC_STYL_NUM]; /* 同步整体的信息 */
static Uint16 s_syncFrameHealthy_u16 = INVALID;
/* 同步的配置表，只读 */
static const SynConf_TypeDef s_c_confTab_t = DEFAULT_SYNC_GPIO_CONFG;


/********************************************************************
 *1.
 *【函数名】 SynchroInit
 *       同步数据初始化
 *【功能描述】 将同步的相关数据初始化
 *【输入参数说明】NONE
 *【输出参数说明】 NONE
 *【其他说明】NONE
 *【返回】NONE
 *
 * *****************************************************************/
void SynchroInit(void)
{
    Uint16 l_ii_u16 = 0U,l_jj_u16 = 0U;

    /* 同步数据初始化 */
    /* 配置同步输入输出引脚 */
    s_synchInf_t.pinOut_u16 = s_c_confTab_t.confPinOut_u16;
    s_synchInf_t.pinInt_u16 = s_c_confTab_t.confPinInt_u16;

    /* 故障码初始化无故障 */
    s_synchInf_t.faltCod_un16.all = SYNC_NORM;

        s_synchInf_t.synFaltCnt_u16    = 0U; /* 同步连续错误次数 */
        s_synchInf_t.synFaltMaxCnt_u16 = 0U; /* 同步连续最大错误次数 */
        s_synchInf_t.synFaltSum_u16    = 0U; /* 同步错误总数 */
        s_syncFrameHealthy_u16         = INVALID;

    /* 同步整体的数据初始化 */
    for(l_ii_u16 = 0U; l_ii_u16 < SYNC_STYL_NUM; l_ii_u16++)
    {
        /* 高、低握手消耗时间初始为零 */
        for(l_jj_u16 = 0U; l_jj_u16 < SYNC_ID_NUM; l_jj_u16++)
        {
            s_synWhle_t[l_ii_u16].costTimHdSk_u32[l_jj_u16] = 0UL;
        }

        s_synWhle_t[l_ii_u16].cstTimSyn_u32    = 0UL;  /* 同步消耗的时间        */
        s_synWhle_t[l_ii_u16].cstMaxTimSyn_u32 = 0UL;  /* 同步消耗的最长时间 */

        s_synWhle_t[l_ii_u16].faltCod_un16.all = SYNC_NORM;  /* 同步结果故障码初始化为无故障  */
    }
}
/********************************************************************
 *2.
 *【函数名】 SynchroTx
 *       同步发送
 *【功能描述】 输出高电平 或 低电平
 *【输入参数说明】 l_handskID_u16 -- HANDSK_H_ID
 *                             HANDSK_L_ID
 *【输出参数说明】 NONE
 *【其他说明】NONE
 *【返回】NONE
 *
 * *****************************************************************/
/* ***************************************************************** */
/**
 * 【函数名】:SynchroTx
 *
 * 【功能描述】同步信号发送, 主控向备控发送同步帧
 *
 * 【输入参数说明】l_handskID_u16 ---- 握手ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static void SynchroTx(Uint16 l_handskID_u16)
{
    /* 参数合理性检测 */
    if(l_handskID_u16 < HANDSK_ID_NUM)
    {
        /* 高握手 */
        if(HANDSK_H_ID == l_handskID_u16)
        {
            /*高电平输出*/
            GPIOSetNum(s_synchInf_t.pinOut_u16);
        }
        /* 低握手 */
        else if(HANDSK_L_ID == l_handskID_u16)
        {
            /*低电平输出*/
            GPIOClearNum(s_synchInf_t.pinOut_u16);
        }
        else
        {
            /* no deal with  */
        }
    }
}

/********************************************************************************************************************
 *
 *【函数名】HandShakeProcess
 *
 *【功能描述】同步握手处理，只对未切除的通道做握手检测
 *
 *【输入参数说明】
 *      l_hadshkID_u16 -- HANDSK_H_ID   高握手
 *                        HANDSK_L_ID   低握手
 *      l_hadshkTime_u32 -- 握手允许的最大等待时间
 *【输出参数说明】 NONE
 *【其他说明】  握手时间过长时，注意 喂狗！
 *【返回】 握手消耗时间
 *********************************************************************************************************************/
/* ***************************************************************** */
/**
 * 【函数名】:HandShakeProcess
 *
 * 【功能描述】握手处理, 处理同步握手状态机
 *
 * 【输入参数说明】l_hadshkID_u16 ---- 握手ID
                 l_hadshkTime_u32 ---- 握手时间
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static Uint32 HandShakeProcess(Uint16 l_hadshkID_u16,const Uint32 l_hadshkTime_u32)
{
    Uint32 l_hadskeStrtTim_u32 = 0UL;/*握手起始时刻*/
    Uint16 l_handEnd_u16 = 0U;/**握手成功，结束标志**/
    Uint32 l_costTimHdSk_u32 = 0UL; /* 高、低握手消耗的时间 */

    /** 参数合理性检测 **/
    if(l_hadshkID_u16 < HANDSK_ID_NUM)
    {
        /*两两模块的硬线检测初始化为握手失败*/
        s_synchInf_t.faltCod_un16.all |= (HANDSK_FAULT<<l_hadshkID_u16);
            /* 输出电平 */
        SynchroTx(l_hadshkID_u16);

        /*握手起始时刻*/
        l_hadskeStrtTim_u32 = ReadCpuTimer1Counter();

        /*握手消耗的实时时间*/
        while((CpuTimer1DeltaGet(l_hadskeStrtTim_u32, ReadCpuTimer1Counter()) < l_hadshkTime_u32) && \
              (HANDSHAKE_END != l_handEnd_u16))
        {
            /* 周期喂狗 */
            CycleDogFeed();

            /*读取到正确的电平信号*/
            if(l_hadshkID_u16 == GPIOReadBitNum(s_synchInf_t.pinInt_u16))
            {
                /*置本轮握手成功，位 清零*/
                s_synchInf_t.faltCod_un16.all &= ~(1U<<l_hadshkID_u16);

                    /* 周期中的第一个握手成功了，需要延时，保持本模块输出引脚的状态一定时间。
                     * 这里仅在低握手成功后补 7us，是为了给对端在“先看到低沿再回读输入”的时序里留稳定窗口，
                     * 避免双方几乎同时翻转导致的竞态采样。该延时属于板级握手时序参数，不建议随意改小。 */
                    if(HANDSK_L_ID == l_hadshkID_u16)
                    {
                        /* 此处延时，非常重要！给对方读取自己引脚状态的机会。 */
                        delayUs(HANDSHAKE_L_HOLD_US);
                    }

                /**握手成功，置为握手结束**/
                l_handEnd_u16 = HANDSHAKE_END;
            }
            /*读取到错误的电平信号*/
            else
            {
                /*置本轮握手故障，位 置1*/
                s_synchInf_t.faltCod_un16.all |= (1U<<l_hadshkID_u16);
            }
        }

        /*高握手或低握手 消耗的时间*/
        l_costTimHdSk_u32 = CpuTimer1DeltaGet(l_hadskeStrtTim_u32, ReadCpuTimer1Counter());
    }

    return  l_costTimHdSk_u32; /* 返回握手消耗时间 */
}
/********************************************************************************************
 *
 *【函数名】SynMonitor
 *
 *【功能描述】模块间同步监控， 实现帧通道的通道故障状态监控
 *【输入参数说明】l_synStyleID_u16 - 同步类型，取值如下：
 *            SYNC_LONG_ID -- 长同步
 *            SYNC_SHORT_ID--短同步
 *            SYNC_FRAME_ID--帧同步
 *
 *【输出参数说明】
 *
 *【其他说明】NONE
 *【返回】NONE
 * *******************************************************************************************/
/* ***************************************************************** */
/**
 * 【函数名】:SynMonitor
 *
 * 【功能描述】同步状态监测, 监测同步状态是否健康
 *
 * 【输入参数说明】l_synStyleID_u16 ---- 同步样式ID
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static void SynMonitor(Uint16 l_synStyleID_u16)
{
    /* 同步消耗的时间 */
    s_synWhle_t[l_synStyleID_u16].cstTimSyn_u32 = \
    s_synWhle_t[l_synStyleID_u16].costTimHdSk_u32[HANDSK_L_ID] + s_synWhle_t[l_synStyleID_u16].costTimHdSk_u32[HANDSK_H_ID];

    /* 同步消耗的最大时间 */
    if(s_synWhle_t[l_synStyleID_u16].cstMaxTimSyn_u32 < s_synWhle_t[l_synStyleID_u16].cstTimSyn_u32)
    {
        s_synWhle_t[l_synStyleID_u16].cstMaxTimSyn_u32 = s_synWhle_t[l_synStyleID_u16].cstTimSyn_u32;
    }

        /****************    实时拍监控结果          **************
         * s_syncFrameHealthy_u16 是实时拍状态，本拍握手失败即立刻置INVALID，成功即立刻恢复VALID。
         * synFaltCnt/synFaltSum/synFaltMax 分别记录连续失败计数、累计失败计数、历史连续失败峰值。 */
            if((HANDSK_SUCC == s_synchInf_t.faltCod_un16.bit.handShakeL) && \
                    (HANDSK_SUCC == s_synchInf_t.faltCod_un16.bit.handShakeH))
            {
        /* 本通道同步正常 */
        s_synchInf_t.faltCod_un16.bit.synRelRslt = SYNC_NORM;
        s_syncFrameHealthy_u16 = VALID;

        /* 同步连续错误次数清零 */
        s_synchInf_t.synFaltCnt_u16 = 0U;
        }
        else
        {
            /* 本通道同步故障 */
            s_synchInf_t.faltCod_un16.bit.synRelRslt = SYNC_ERR;
            s_syncFrameHealthy_u16 = INVALID;

            /* 同步连续错误次数加加 */
            s_synchInf_t.synFaltCnt_u16 = ((s_synchInf_t.synFaltCnt_u16 + 1U) & 0xFFFFU);

        /* 同步错误总次数加加 */
        s_synchInf_t.synFaltSum_u16 = ((s_synchInf_t.synFaltSum_u16 + 1U) & 0xFFFFU);

        /* 最大连续错误次数 */
            if(s_synchInf_t.synFaltMaxCnt_u16 < s_synchInf_t.synFaltCnt_u16)
            {
                s_synchInf_t.synFaltMaxCnt_u16 = s_synchInf_t.synFaltCnt_u16;
            }
        }

    /* 记录帧同步结果数据 */
    s_synWhle_t[l_synStyleID_u16].faltCod_un16.all = s_synchInf_t.faltCod_un16.all;
}
/***********************************************************************************************************************
 *
 *【函数名】FrameSyn
 *
 *【功能描述】通道同步
 *
 *【输入参数说明】l_synStyleID_u16 - 同步类型，取值如下：
 *            SYNC_LONG_ID -- 长同步
 *            SYNC_SHORT_ID--短同步
 *            SYNC_FRAME_ID--帧同步
 *【输入参数说明】 l_frmSynTim_u32 -- 同步时间
 *
 *【输出参数说明】 NONE
 *
 *【其他说明】高低握手，得到同步结果
 *
 *【返回】 NONE
 **************************************************************************************************************************/
/* ***************************************************************** */
/**
 * 【函数名】:FrameSyn
 * 【功能描述】帧同步处理,根据同步通道信息完成握手与帧同步判定
 * 【输入参数说明】l_synStyleID_u16 ---- 同步方式ID
 * 【输入参数说明】l_frmSynTim_u32 ---- 帧同步时间
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
void FrameSyn(Uint16 l_synStyleID_u16,Uint32 l_frmSynTim_u32)
{
    Uint32 l_hadskTim_u32 = 0UL;          /*高、低握手时间*/

    /* 同步类型在数量内 且 同步时间大于0 */
    if((l_synStyleID_u16 < SYNC_STYL_NUM) && (l_frmSynTim_u32 > 0UL))
    {
        /*  高、低握手时间是帧同步时间的一半  */
        l_hadskTim_u32 = l_frmSynTim_u32 / 2UL;

        /* 低握手处理  */
        s_synWhle_t[l_synStyleID_u16].costTimHdSk_u32[HANDSK_L_ID] = HandShakeProcess(HANDSK_L_ID,l_hadskTim_u32);

        /* 高握手处理 */
        s_synWhle_t[l_synStyleID_u16].costTimHdSk_u32[HANDSK_H_ID] = HandShakeProcess(HANDSK_H_ID,l_hadskTim_u32);
    }

    /* 通道间 帧同步监控 , 不能放在 “紧挨着握手结束后” */
    SynMonitor(l_synStyleID_u16);
}

/****************************************************************************************
 *
 *【函数名】SynWholeInfGet
 *【功能描述】 同步类型数据获取
 *【输入参数说明】 l_synStyleID_u16 -- SYNC_LONG_ID   长同步
 *【输入参数说明】 					 SYNC_SHORT_ID  短同步
 *                               SYNC_FRAME_ID  帧同步
 *【输出参数说明】 NONE
 *【其他说明】        NONE
 *【返回】 l_rslt_t -- l_rslt_t.cstMaxTimSyn_u32 = 0xFFFFFFFFUL,表示输入参数故障
 ****************************************************************************************/
SynWholeInform_TypeDef SynWholeInfGet(Uint16 l_synStyleID_u16)
{
    SynWholeInform_TypeDef l_rslt_t; /* 同步整体信息 */
    memset(&l_rslt_t, 0, sizeof(l_rslt_t));

    /* 输入参数合理 */
    if(l_synStyleID_u16 < SYNC_STYL_NUM)
    {
        l_rslt_t = s_synWhle_t[l_synStyleID_u16];
    }
    else
    {
        l_rslt_t.cstMaxTimSyn_u32 = 0xFFFFFFFFUL;
    }

    return l_rslt_t; /* 返回同步整体信息 */
}

/****************************************************************************************
 *
 *【函数名】SyncFrameHealthyGet
 *【功能描述】获取当前帧同步健康状态
 *【返回】VALID/INVALID
 ****************************************************************************************/
Uint16 SyncFrameHealthyGet(void)
{
    return s_syncFrameHealthy_u16;
}

/* ========================================================================== */
/* END OF FILE */
/* ========================================================================== */
