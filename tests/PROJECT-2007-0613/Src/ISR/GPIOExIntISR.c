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
 * 文件名称:    GPIOExIntISR.c
 *
 * 文件日期:   REDACTED
 *
 *
 * 【功能描述】实现GPIO中断的相关功能
 * 【其他说明】无
 *
 *
 *********************************************************************************/

#include "Global.h"

Uint16 intcount[9] = {0U,0U,0U,0U,0U,0U,0U,0U,0U};

Uint16 s_NMISourseData_u16 = NMI_SOURCE_AB_NORMAL;     /* NMI中断源数据  */
Uint16 s_powerDownFlag_u16 = POWERDOWN_FLAG_INVALID;   /* 28V掉电标志      */
static volatile Uint16 s_nmiResetRequest_u16 = INVALID;/* NMI后待执行软件复位请求 */

/* ***************************************************************** */
/**
 * 【函数名】:NMISourceCheck
 *
 * 【功能描述】NMI中断源检查
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】	  NONE
 * 【返回】	  NMI中断源，取值如下：
 * 			  NMI_SOURCE_POWER_DOWN ---- 28V掉电
 * 			  NMI_SOURCE_WDOG_RESET ---- 看门狗复位
 * 			  NMI_SOURCE_AB_NORMAL  ---- 异常复位
 */
/* ***************************************************************** */
Uint16 NMISourceCheck(void)
{
    Uint16 l_rData_u16 = NMI_SOURCE_AB_NORMAL;  /* 检查结果，函数返回值，默认为异常复位 */
    Uint16 l_LowPowerState_u16 = 0U;  /* 电源低压状态      */
    Uint16 l_DogCallState_u16  = 0U;  /* 看门狗狗叫状态  */
    union CHVInInfo   l_CHVInfo_un16; /* CHV信号  */

     /* 获取CHV信号 */
     l_CHVInfo_un16.all = HARD_XINT_UINT16(CPLD_ADDR_W_CPUV_IN);

    /* 获取电源低压状态  */
    l_LowPowerState_u16 = HARD_XINT_UINT16(CPLD_ADDR_R_HKA_DATA1);
    l_LowPowerState_u16 = l_LowPowerState_u16 & 0x20;

    /* 获取看门狗狗叫状态  */
    l_DogCallState_u16 = l_CHVInfo_un16.bit.WDV_u16;

    /* 电源低压时  */
    if(CPLD_DATA_POWER_BIT_ERR == l_LowPowerState_u16)
    {
        /* NMI中断源为28V掉电 */
        l_rData_u16 = NMI_SOURCE_POWER_DOWN;
    }
    else  /* 电源电压正常  */
    {
        /* 狗叫时 */
        if(CPLD_DATA_WDV_ERR == l_DogCallState_u16)
        {
            /* NMI中断源为看门狗复位  */
            l_rData_u16 = NMI_SOURCE_WDOG_RESET;
        }
    }

    /* 返回检查结果 */
    return l_rData_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:PowerDownFlagGet
 *
 * 【功能描述】28V掉电标志获取
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】        NONE
 * 【返回】      28V掉电标志，取值如下：
 *		  POWERDOWN_FLAG_INVALID ---- 28V掉电标志无效
 *		  POWERDOWN_FLAG_VALID   ---- 28V掉电标志有效
 *
 ***************************************************************** */
Uint16 PowerDownFlagGet(void)
{
    /* 返回  28V掉电标志 */
    return s_powerDownFlag_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:PowerDownFlagClear
 *
 * 【功能描述】清除28V掉电标志
 *         28V掉电标志置为无效
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】        NONE
 * 【返回】               NONE
 *
 ***************************************************************** */
void PowerDownFlagClear(void)
{
    /* 28V掉电标志置为无效 */
    s_powerDownFlag_u16 = POWERDOWN_FLAG_INVALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:PowerDownFlagSetValid
 *
 * 【功能描述】确认28V掉电标志
 *         28V掉电标志置为有效
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】        NONE
 * 【返回】               NONE
 *
 ***************************************************************** */
void PowerDownFlagSetValid(void)
{
    s_powerDownFlag_u16 = POWERDOWN_FLAG_VALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:NMIResetRequestGet
 *
 * 【功能描述】获取NMI后待执行软件复位请求
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】      VALID-存在待执行复位请求 / INVALID-无请求
 *
 ***************************************************************** */
Uint16 NMIResetRequestGet(void)
{
    return s_nmiResetRequest_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:NMIResetRequestClear
 *
 * 【功能描述】清除NMI后待执行软件复位请求
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】      NONE
 *
 ***************************************************************** */
void NMIResetRequestClear(void)
{
    s_nmiResetRequest_u16 = INVALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:ISR_XNMIInt
 *
 * 【功能描述】XNMI中断响应程序
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】无
 * 【返回】NONE
 ***************************************************************** */
interrupt void ISR_XNMIInt(void)
{
    SpeData_t l_nvmData_t;    /* NVM数据  */
    Uint16 l_sysTimeSum_u16 =0U;
    Uint16 l_sector_u16=0xFFFF; /* 当前扇区 */

    /* 关闭NMI中断 */
    EALLOW;
    XIntruptRegs.XNMICR.bit.ENABLE = OFF;
    EDIS;

    /* 中断计数加1 */
    intcount[0] =  intcount[0] + 1U;

    /* 获取NMI中断源 */
    s_NMISourseData_u16 = NMISourceCheck();

    /* 更新工作时间镜像，并交由主循环在非ISR上下文内落盘。 */
    l_sysTimeSum_u16 = SysWorkTimeGet();
    (void)SpeDataWriteDefer(SPE_DATA_DINDEX_SYS_TIME_SUM,l_sysTimeSum_u16);

    /* NMI掉电分支只记录事件并置待确认标志，持续欠压确认移到主循环状态判定中。 */
    if(NMI_SOURCE_POWER_DOWN == s_NMISourseData_u16)
    {
        /* 获取掉电次数 */
        SpeDataGet(SPE_DATA_DINDEX_NMI_POWER_DOWN_NUM,&l_nvmData_t);

        /* 掉电次数加1后只更新镜像，实际FLASH落盘延后到主循环。 */
        (void)SpeDataWriteDefer(SPE_DATA_DINDEX_NMI_POWER_DOWN_NUM,(l_nvmData_t.dataU_u16 + 1U));

        /* 标记待确认，不在NMI内采样、延时或喂狗。 */
        s_powerDownFlag_u16 = POWERDOWN_FLAG_PENDING;

        /* 打开NMI中断  */
        EALLOW;
        XIntruptRegs.XNMICR.bit.ENABLE = ON;
        EDIS;
    }
    else if(NMI_SOURCE_WDOG_RESET == s_NMISourseData_u16)
    {
        /* NMI中断源等于看门狗复位时 */

        /* 获取看门狗复位次数 */
        SpeDataGet(SPE_DATA_DINDEX_NMI_WDOG_NUM,&l_nvmData_t);

        /* 看门狗复位次数加1后只更新镜像，实际FLASH落盘延后到主循环。 */
        (void)SpeDataWriteDefer(SPE_DATA_DINDEX_NMI_WDOG_NUM,(l_nvmData_t.dataU_u16 + 1U));
        /* 打开NMI中断  */
        EALLOW;
        XIntruptRegs.XNMICR.bit.ENABLE = ON;
        EDIS;

        /* 记录待复位请求，返回主循环完成特定数据落盘后再触发软件复位。 */
        s_nmiResetRequest_u16 = VALID;
    }
    else  /* NMI中断源等于异常复位时 */
    {
        /* 获取异常复位次数 */
        SpeDataGet(SPE_DATA_DINDEX_NMI_ABNORM_NUM,&l_nvmData_t);

        /* 异常复位次数加1后只更新镜像，实际FLASH落盘延后到主循环。 */
        (void)SpeDataWriteDefer(SPE_DATA_DINDEX_NMI_ABNORM_NUM,(l_nvmData_t.dataU_u16 + 1U));

        /* 打开NMI中断  */
        EALLOW;
        XIntruptRegs.XNMICR.bit.ENABLE = ON;
        EDIS;

        /* 记录待复位请求，返回主循环完成特定数据落盘后再触发软件复位。 */
        s_nmiResetRequest_u16 = VALID;
    }

    /*下电时写一次当前存储扇区号*/
    l_sector_u16 =FlashRecordStartSector();

    if( 8192U >= l_sector_u16)
    {
        /* 不在 NMI ISR 内直接写 Flash,改用延迟写,主循环 4POWERDOWN 态统一落盘 */
        (void)SpeDataWriteDefer(SPE_DATA_DINDEX_FLASH_STORE_SECTOR, l_sector_u16);
    }


}

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
