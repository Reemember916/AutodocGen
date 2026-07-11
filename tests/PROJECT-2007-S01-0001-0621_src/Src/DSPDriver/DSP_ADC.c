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
 * 文件名称:   DSP_ADC.c
 *
 * 功能说明:
 *          本程序实现TMS320F28335片上AD功能,支持的功能如下：
 *
 *          1 ADC模块最大16通道顺序采样；
 *          2 ADC转换时间配置;
 *          3 ADC采样通道配置;
 *          4 ADC数据码值转换;
 *          5 ADC模块软件触发转换;
 *          6 ADC模块采样保持时间设置;
 *          7 ADC模块PWM触发;
 *          8 ADC模块不支持OVERRIDE模式;
 *          9 ADC模块不支持偏移调校;
*          10 ADC模块，DMA方式暂不支持
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V1.02
 *
 *********************************************************************************/

#include "Global.h"

#if DSP_ADC

/* ADC最大转换通道数 */
#define ADC_MAX_CHANNEL            (16)
#define ADC_SINGLE_MAX_CHANNEL     (8)

/* ADC最大采样频率 */
#define ADC_MAX_FREQUENCY   (25)

//TI官方定义的ADC补偿函数
#define ADC_Cal (void (*) (void)) 0x380080

#define ADC_DATA_FACTOR     (0.0007326)        // (3.0 / 4095)

//ADC配置信息
struct adcConf myAdcConf_t = ADC_CONF_TAB;

//ADC转换通道信息
Uint8 adcSeq_1_Channels[ADCCHANNEL1NUM] = ADC_SEQ1_CHANNEL_TAB;
Uint8 adcSeq_2_Channels[ADCCHANNEL2NUM] = ADC_SEQ2_CHANNEL_TAB;

/* *******************************************************************/
/**
 *    [函数名]			AdcIntStatusGet
 *    [功能描述]			ADC中断状态获取
 *    [输入参数说明]		NONE
 *
 *    [输出参数说明]		同返回值
 *    [其他说明]			NONE
 *    [返回]				ADC中断状态，可能取值如下：
 *                      ADC_SEQ1_INT ---- SEQ1序列器中断
 *                      ADC_SEQ2_INT ---- SEQ2序列器中断
 */
/* *******************************************************************/
Uint16 AdcIntStatusGet(void)
{
    return (AdcRegs.ADCST.all & 0x03);
}

/* *******************************************************************/
/**
 *    [函数名]			AdcIsBusy
 *    [功能描述]			获取ADC当前忙状态。
 *    [输入参数说明]		v_seqnum_u8 ---- 序列器号，可能取值为：
 *              		ADC_SEQ1 ---- 序列器1
 *              		ADC_SEQ2 ---- 序列器2
 *
 *    [输出参数说明]		同返回值
 *    [其他说明]			NONE
 *    [返回]				ADC当前忙状态，可能取值为：
 *              		ADC_IS_BUSY  ---- ADC当前处于忙状态
 *              		ADC_NOT_BUSY ---- ADC当前不处于忙状态
 */
/* *******************************************************************/
Uint16 AdcIsBusy(Uint8 v_seqnum_u8)
{
    if( ADC_SEQ1 == v_seqnum_u8 )
    {
        return AdcRegs.ADCST.bit.SEQ1_BSY;
    }
    else
    {
        return AdcRegs.ADCST.bit.SEQ2_BSY;
    }
}

/* *******************************************************************/
/**
 *    [函数名]			AdcReset
 *    [功能描述]			复位ADC模块，对ADC模块复位后，
 *    					至少需要等待两个ADCCLK时钟后，再进行设置
 *    [输入参数说明]		NONE
 *
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcReset(void)
{
    Uint8 l_ii_u8 = 0;

    /* 复位ADC，该标志位不需要清零 */
    AdcRegs.ADCTRL1.bit.RESET = 1;

    /* 延时 */
    for( l_ii_u8 = 0; l_ii_u8 < 200; l_ii_u8++ )
    {
        NOP;
    }
}

/* *******************************************************************/
/**
 *    [函数名]			AdcSeqRst
 *    [功能描述]			复位ADC序列器。
 *    [输入参数说明]		v_seqnum_u8 ---- ADC序列器选择，可选择参数如下：
 *                      ADC_SEQ1 ---- 复位SEQ1序列器
 *                      ADC_SEQ2 ---- 复位SEQ2序列器
 *                 		ADC_SEQ1_SEQ2 ---- 复位SEQ1和SEQ2序列器
 *
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcSeqRst(Uint8 v_seqnum_u8)
{
    switch(v_seqnum_u8)
    {
        case ADC_SEQ1:
            AdcRegs.ADCTRL2.bit.RST_SEQ1 = 1;
            break;
        case ADC_SEQ2:
            AdcRegs.ADCTRL2.bit.RST_SEQ2 = 1;
            break;
        default:
            AdcRegs.ADCTRL2.bit.RST_SEQ1 = 1;
            AdcRegs.ADCTRL2.bit.RST_SEQ2 = 1;
            break;
    }
}

/* *******************************************************************/
/**
 *    [函数名]			AdcSocConf
 *    [功能描述]			ADC序列器SEQ触发方式配置。其中SEQ1可以配置为四种配置方式，分别为：
 *
 *						ADC_SOC_SOFT      ---- 软件触发
 * 						ADC_SOC_EPWM_SOCA ---- EPWM SOCA触发
 * 						ADC_SOC_EPWM_SOCB ---- EPWM SOCB触发
 * 						ADC_SOC_EXT_GPIO  ---- 外部GPIO中断方式触发
 *
 * 						SEQ2只能配置为 ADC_SOC_SOFT 和 ADC_SOC_EPWM_SOCB 两种方式。
 *
 *	 					NOTE:触发方式可以多种同时存在。
 *    [输入参数说明]
 *    					【参数】:v_conf_1_u8 ---- SEQ1序列器触发方式配置
 * 						【参数】:v_conf_2_u8 ---- SEQ2序列器触发方式配置
 *
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcSocConf(Uint8 v_conf_1_u8,Uint8 v_conf_2_u8)
{
    /* SEQ1序列器SOC触发配置 */
    if( (ADC_SOC_EPWM_SOCA & v_conf_1_u8) != 0 )
    {
        AdcRegs.ADCTRL2.bit.EPWM_SOCA_SEQ1 = 1;
    }

    /* SEQ1序列器EPWM SOCB触发设置，只在级联模式下有效 */
    if( (ADC_SOC_EPWM_SOCB & v_conf_1_u8) != 0 )
    {
        AdcRegs.ADCTRL2.bit.EPWM_SOCB_SEQ = 1;
    }

    /* SEQ1序列器外部GPIO触发设置 */
    if( (ADC_SOC_EXT_GPIO & v_conf_1_u8) != 0 )
    {
        AdcRegs.ADCTRL2.bit.EXT_SOC_SEQ1 = 1;
    }

    /* SEQ2序列器SOC触发配置 */
    if( (ADC_SOC_EPWM_SOCB & v_conf_2_u8) != 0 )
    {
        AdcRegs.ADCTRL2.bit.EPWM_SOCB_SEQ2 = 1;
    }
}

/* *******************************************************************/
/**
 *    [函数名]			AdcStartConv
 *    [功能描述]			软件启动ADC转换启动。
 *    [输入参数说明]		v_seqnum_u8 ---- 启动转换的序列器号，可选择的参数为：
 *
 *                      ADC_SEQ1 ---- 启动序列器SEQ1转换
 *                      ADC_SEQ2 ---- 启动序列器SEQ2转换
 *                 		ADC_SEQ1_SEQ2 ---- 启动序列器SEQ1和SEQ2转换
 *
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcStartConv(Uint8 v_seqnum_u8)
{
    switch(v_seqnum_u8)
    {
        case ADC_SEQ1:
            AdcRegs.ADCTRL2.bit.SOC_SEQ1 = 1;
            break;
        case ADC_SEQ2:
            AdcRegs.ADCTRL2.bit.SOC_SEQ2 = 1;
            break;
        case ADC_SEQ1_SEQ2:
            AdcRegs.ADCTRL2.bit.SOC_SEQ1 = 1;
            AdcRegs.ADCTRL2.bit.SOC_SEQ2 = 1;
            break;
        default:
            break;
    }
}

/* *******************************************************************/
/**
 *    [函数名]			AdcIntEnable
 *    [功能描述]			ADC中断使能，中断向量注册。
 *    [输入参数说明]		NONE
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcIntEnable(void)
{
    /* 注册ADC中断向量 */
    EALLOW;
    PieVectTable.ADCINT = &ADCINT_ISR;
    EDIS;

    /* 使能ADCINT中断 */
    PieCtrlRegs.PIEIER1.bit.INTx6 = 1;
    IER |= M_INT1;
}

/* *******************************************************************/
/**
 *    [函数名]			AdcIntConf
 *    [功能描述]			ADC转换中断配置,可分别对两个序列器进行配置。
 *
 * 						ADC转换中断可以配置为如下几种模式：
 *
 *      				ADC_CONV_POLL ---- 查询模式
 * 						ADC_CONV_INT_EVERY ---- 每一次转换结束都产生中断
 * 						ADC_CONV_INT_OTHER ---- 每间隔一次转换结束产生一次中断
 *    [输入参数说明]		【参数】:v_conf_1_u8 ---- 序列器1(SEQ1)中断配置
 * 						【参数】:v_conf_2_u8 ---- 序列器2(SEQ2)中断配置
 *    [输出参数说明]		NONE
 *    [其他说明]			NOTE:当配置为级联模式时，序列器2中断配置无意义
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcIntConf(Uint8 v_conf_1_u8,Uint8 v_conf_2_u8)
{
    /* 序列器1中断配置 */
    switch(v_conf_1_u8)
    {
        case ADC_CONV_INT_EVERY:
            {

                AdcRegs.ADCTRL2.bit.INT_ENA_SEQ1 = 1;
                AdcRegs.ADCTRL2.bit.INT_MOD_SEQ1 = 0;
            }
            break;
        case ADC_CONV_INT_OTHER:
            {

                AdcRegs.ADCTRL2.bit.INT_ENA_SEQ1 = 1;
                AdcRegs.ADCTRL2.bit.INT_MOD_SEQ1 = 1;
            }
            break;
        default:
            AdcRegs.ADCTRL2.bit.INT_ENA_SEQ1 = 0;
            break;
    }

    /* 序列器2中断配置 */
    switch(v_conf_2_u8)
    {
        case ADC_CONV_INT_EVERY:
            {
                AdcRegs.ADCTRL2.bit.INT_ENA_SEQ2 = 1;
                AdcRegs.ADCTRL2.bit.INT_MOD_SEQ2 = 0;
            }
            break;
        case ADC_CONV_INT_OTHER:
            {
                AdcRegs.ADCTRL2.bit.INT_ENA_SEQ2 = 1;
                AdcRegs.ADCTRL2.bit.INT_MOD_SEQ2 = 1;
            }
            break;
        default:
            AdcRegs.ADCTRL2.bit.INT_ENA_SEQ2 = 0;
            break;
    }

    /* 当配置有中断模式时，使能ADCINT中断，并注册中断向量 */
    if( (v_conf_1_u8 + v_conf_2_u8) > 0 )
    {
        AdcIntEnable();
    }
}

/* *******************************************************************/
/**
 *    [函数名]			AdcIntAck
 *    [功能描述]			ADC中断应答
 *    [输入参数说明]		NONE
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcIntAck(void)
{
    if( 1 == AdcRegs.ADCST.bit.INT_SEQ1 )
    {
        /* 清除ADC内部中断标志位 */
        AdcRegs.ADCST.bit.INT_SEQ1_CLR = 1;
    }
    else if( 1 == AdcRegs.ADCST.bit.INT_SEQ2)
    {
        /* 清除ADC内部中断标志位 */
        AdcRegs.ADCST.bit.INT_SEQ2_CLR = 1;
    }
    else
    {
        /* 无操作 */
    }

    /* 清除ADC中断应答标志位 */
    PieCtrlRegs.PIEACK.all = PIEACK_GROUP1;
}

/* *******************************************************************/
/**
 *    [函数名]			AdcFreConf
 *    [功能描述]			ADC模块频率设置，最大值为ADC_MAX_FREQUENCY(25MHZ)
 *
 * 						ADC模块频率 = DSP_HSPCLK / v_divide_u8
 *    [输入参数说明]
 *    		`			参数】:v_divide_u8 ---- ADC模块时钟分频系数，可以取0--30之间偶数
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcFreConf(Uint8 v_divide_u8,Uint16 v_dspHiSpeed_u16)
{
    Uint8 l_fre_u8 = 0;
    Uint8 l_divu8 = 0;

    /* divide为0-30之间的偶数 */
    l_divu8 = v_divide_u8 & 0x1f;

    /* 当div为零时，分频系数为1 */
    if( 0 == l_divu8 )
    {
        l_divu8 = 1;
    }

    l_fre_u8 = v_dspHiSpeed_u16 / l_divu8;

    /* 判断设置的ADC频率是否超过最大值 */
    if( l_fre_u8 >= ADC_MAX_FREQUENCY )
    {
        l_divu8 = (v_dspHiSpeed_u16 / ADC_MAX_FREQUENCY) + 2;
    }

    /* 设置ADC模块预分频系数 */
    AdcRegs.ADCTRL1.bit.CPS = 0;

    /* 设置ADC模块分频系数 */
    AdcRegs.ADCTRL3.bit.ADCCLKPS = l_divu8 / 2;
}

/* *******************************************************************/
/**
 *    [函数名]			AdcRefConf
 *    [功能描述]			ADC参考电源配置
 *    [输入参数说明]		adcRef_u8 ---- ADC参考电源选择，可选择参数为：
 *
 *                      ADC_REF_IN : ADC内部参考电源
 *                      ADC_REF_OUT_2048 : ADC外部参考电源，2.048V
 *                      ADC_REF_OUT_1500 : ADC外部参考电源，1.500V
 *                      ADC_REF_OUT_1024 : ADC外部参考电源，1.024V
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcRefConf(Uint8 v_adcRef_u8)
{
    AdcRegs.ADCREFSEL.bit.REF_SEL = v_adcRef_u8;
}

/* *******************************************************************/
/**
 *    [函数名]			AdcMaxConvSet
 *    [功能描述]			序列器最大转换通道数设置
 *    [输入参数说明]		【参数】:v_seqnum_u8 ---- 序列器序号，可设置参数为：
 *                      AC_SEQ1 ---- ADC序列器1
 *                      ADC_SEQ2 ---- ADC序列器2
 *
 * 						【参数】:count ---- 序列器通道最大转换数
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcMaxConvSet(Uint8 v_seqnum_u8,Uint8 v_count_u8)
{
    Uint8 l_temp_u8 = 0;

    if(v_count_u8 > 0)
    {
        l_temp_u8 = v_count_u8 - 1;
    }

    if(ADC_SEQ1 == v_seqnum_u8)
    {
        AdcRegs.ADCMAXCONV.bit.MAX_CONV1 = l_temp_u8;
    }
    else if(ADC_SEQ2 == v_seqnum_u8)
    {
        AdcRegs.ADCMAXCONV.bit.MAX_CONV2 = l_temp_u8;
    }
    else
    {
        /* 无操作 */
    }
}

/* *******************************************************************/
/**
 *    [函数名]			AdcChannelConf
 *    [功能描述]			ADC转换通道配置
 *    [输入参数说明]		【参数】:vp_channelBuff_u8 ---- ADC转换通道数组首地址，数组元素可以为
 *          			ADC_CHANNEL_0 到 ADC_CHANNEL_15
 *    [输出参数说明]		NONE
 *    [其他说明]			NOTE:数组必须以 ADC_CHANNEL_NULL 结尾
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcChannelConf(Uint8 * vp_channelBuff_u8,Uint8 v_seqnum_u8)
{
    Uint8  l_ii_u8 = 0,l_maxlen_u8 = 0;
    Uint8  l_bitShift_u8 = 0;
    Uint8  l_regShift_u8 = 0;
    Uint32 l_regAddr_u32 = 0,l_baseAddr_u32 = 0;

    /* 级联时，最大转换数为16，其余均为8 */
    if(ADC_CASCADE_ON == myAdcConf_t.adcCascadeMode_u8)
    {
        l_maxlen_u8 = ADC_MAX_CHANNEL;
    }
    else
    {
    	l_maxlen_u8 = ADC_SINGLE_MAX_CHANNEL;
    }

    if( ADC_SEQ1 == v_seqnum_u8 )
    {
        l_baseAddr_u32 = ADCCHSELSEQ_REG_BASE;
    }
    else
    {
        l_baseAddr_u32 = ADCCHSELSEQ_REG_BASE + 2;
    }

    /* 4个通道配置寄存器清零 */
    for( l_ii_u8 = 0; l_ii_u8 < (l_maxlen_u8 / 4) ; l_ii_u8++)
    {
        (*(volatile Uint16 * )(l_baseAddr_u32 + l_ii_u8)) = 0;
    }

    /* ADC采样通道配置，最大通道数为 ADC_MAX_CHANNEL */
    /* TODO:判断数组长度 */
    for (l_ii_u8 = 0; l_ii_u8 < l_maxlen_u8; l_ii_u8++)
    {
        /* 判断ADC通道配置是否结束 */
        if( ADC_CHANNEL_NULL != vp_channelBuff_u8[l_ii_u8] )
        {
            /* 每个配置寄存器最多可配置四个转换通道 */

            /* 寄存器内位偏移 */
            l_bitShift_u8  = (l_ii_u8 % 4) * 4;

            /* 寄存器地址偏移 */
            l_regShift_u8 = l_ii_u8 / 4;

            /* 寄存器地址 */
            l_regAddr_u32 = l_baseAddr_u32 + l_regShift_u8;

            (*(volatile Uint16 * )(l_regAddr_u32)) |= ((vp_channelBuff_u8[l_ii_u8] & 0x0FU) << l_bitShift_u8);
        }
        else
        {
            break;
        }
    }

    /* 序列器最大转换通道数设置 */
    AdcMaxConvSet(v_seqnum_u8,l_ii_u8);
}

/* *******************************************************************/
/**
 *    [函数名]			AdcPowerUP
 *    [功能描述]			ADC模块上电。
 *    [输入参数说明]		NONE
 *    [输出参数说明]		NONE
 *    [其他说明]			NOTE: 若ADC模块使用外部电源，需要在band gap上电之前，先使能外部电源
 *      	 			即：在调用本函数之前，先调用 adcRefConf 函数
 *
 * 						NOTE: ADC模块上电后，到第一次转换至少需要等待5ms
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcPowerUP(void)
{
    Uint8 l_ii_u8 = 0;

    /* 给 bandgap 和 reference 上电 */
    AdcRegs.ADCTRL3.bit.ADCBGRFDN = 0x03;

    /* 给ADC内部模拟电路上电 */
    AdcRegs.ADCTRL3.bit.ADCPWDN = 1;

    /* 延时 */
    for( l_ii_u8 = 0; l_ii_u8 < 200; l_ii_u8++ )
    {
        NOP;
    }
}

/* *******************************************************************/
/**
 *    [函数名]			AdcInit
 *    [功能描述]			ADC初始化。
 *    [输入参数说明]		NONE
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcInit(void)
{
    /* 复位ADC模块 */
    AdcReset();

    /* 调用TI官方的补偿函数 */
    (*ADC_Cal)();

    /* ADC参考电源设置 */
    AdcRefConf(myAdcConf_t.adcRef_u8);

    /* ADC模块上电 */
    AdcPowerUP();

    AdcRegs.ADCTRL1.bit.SUSMOD = 0x03;

    /* ADC模块频率设置 */
    AdcFreConf(myAdcConf_t.adcFreDivd_u8,(Uint16)DSP_HSPCLK);

    /* ADC采样脉宽设置 */
    AdcRegs.ADCTRL1.bit.ACQ_PS = myAdcConf_t.adcSocWidth_u8 - 1;

    /* ADC连续工作模式设定 */
    AdcRegs.ADCTRL1.bit.CONT_RUN = myAdcConf_t.adcContiRunMode_u8;

    /* 不使用OVERRIDE模式 */
    AdcRegs.ADCTRL1.bit.SEQ_OVRD = 0;

    /* 级联模式设定 */
    AdcRegs.ADCTRL1.bit.SEQ_CASC = myAdcConf_t.adcCascadeMode_u8;

    /* 采样模式设定 */
    AdcRegs.ADCTRL3.bit.SMODE_SEL = myAdcConf_t.adcSampleMode_u8;

    /* ADC触发方式选择 */
    AdcSocConf(myAdcConf_t.adcSocMode_1_u8,myAdcConf_t.adcSocMode_2_u8);

    /* ADC中断配置 */
    AdcIntConf(myAdcConf_t.adcIntMode_1_u8,myAdcConf_t.adcIntMode_2_u8);

    /* ADC转换通道配置，SEQ1序列器配置 */
    AdcChannelConf(adcSeq_1_Channels,ADC_SEQ1);

    /* 当工作于非级联模式时，配置SEQ2序列器 */
    if(ADC_CASCADE_OFF == myAdcConf_t.adcCascadeMode_u8)
    {
        AdcChannelConf(adcSeq_2_Channels,ADC_SEQ2);
    }
}

/* *******************************************************************/
/**
 *    [函数名]			AdcSeqCountGet
 *    [功能描述]			获取转换通道当前计数值，取值范围为【0,15】
 *    [输入参数说明]		NONE
 *    [输出参数说明]		同返回值
 *    [其他说明]			NONE
 *    [返回]				当前转换通道计数值
 */
/* *******************************************************************/
Uint16 AdcSeqCountGet(void)
{
    return AdcRegs.ADCASEQSR.bit.SEQ_CNTR;
}

/* *******************************************************************/
/**
 *    [函数名]			AdcDataConvert
 *    [功能描述]			ADC码值转换。转换公式为：
 *
 * 						模拟量 = ( 码值 ) / 4095 * 3.0
 *    [输入参数说明]		v_code_u16 ---- ADC采样码值
 *    [输出参数说明]		同返回值
 *    [其他说明]			NONE
 *    [返回]				ADC采集模拟量值
 */
/* *******************************************************************/
float AdcDataConvert(Uint16 v_code_u16)
{
    float l_rdata_f = 0.0;

    l_rdata_f = ( v_code_u16   * ADC_DATA_FACTOR);

    return l_rdata_f;
}

/* *******************************************************************/
/**
 *    [函数名]			AdcDataGetOne
 *    [功能描述]			单个ADC采集数据获取
 *    [输入参数说明]
 *    					v_channelNum_u16 ---- ADC通道号
 *    					v_seqnum_u8 ---- ADC序列号
 *    [输出参数说明]		同返回值
 *    [其他说明]			NONE
 *    [返回]				获取的ADC采集的模拟量
 */
/* *******************************************************************/
float AdcDataGetOne(Uint16 v_channelNum_u16,Uint8 v_seqnum_u8)
{
    float l_rdata_f = 0.0;
    Uint16 l_temp_u8 = 0;

    if( (ADC_SEQ1 == v_seqnum_u8) && (v_channelNum_u16 < ADC_MAX_CHANNEL))
    {
        l_temp_u8 = *((volatile Uint16 *)(ADC_RESULTS_REG_BASE + v_channelNum_u16));

        l_rdata_f = AdcDataConvert(l_temp_u8);
    }
    else if( (ADC_SEQ2 == v_seqnum_u8) && (v_channelNum_u16 < ADC_SINGLE_MAX_CHANNEL))
    {
        l_temp_u8 = *((volatile Uint16 *)(ADC_RESULTS_REG_BASE + v_channelNum_u16 + 8));

        l_rdata_f = AdcDataConvert(l_temp_u8);
    }
    else
    {
        /* DO NOTHING */
    }

    return l_rdata_f;
}

/* *******************************************************************/
/**
 *    [函数名]			AdcDataGet
 *    [功能描述]			ADC所有配置通道的转换结果--模拟量值的获取。调用该函数后，将主动复位ADC序列器。
 * 						获取数据的长度，由各序列器的最大通道配置个数决定。
 *    [输入参数说明]
 *    					【参数】:vp_buff__f    ---- ADC模拟量值保存数组首地址
 * 						【参数】:v_bufflen_u8 ---- 拟读取的数据长度，最大为16
 * 						【参数】:v_seqnum_u8  ---- 从哪个序列器缓冲区读取数据，可能为：ADC_SEQ1 或 ADC_SEQ2号
 *    [输出参数说明]		NONE
 *    [其他说明]			NONE
 *    [返回]				NONE
 */
/* *******************************************************************/
void AdcDataGet(float *vp_buff__f, Uint8 v_bufflen_u8, Uint8 v_seqnum_u8)
{
    Uint8  l_ii_u8 = 0,l_len_u8 = 0;
    Uint16 l_temp_u8 = 0;
    Uint32 l_baseAddr_u32 = ADC_RESULTS_REG_BASE;

    if( ADC_SEQ1 == v_seqnum_u8 )
    {
        if( v_bufflen_u8 <= ADC_MAX_CHANNEL)
        {
            l_len_u8 = v_bufflen_u8;
        }
        else
        {
            l_len_u8 = ADC_MAX_CHANNEL;
        }
    }
    else
    {
        l_baseAddr_u32 = l_baseAddr_u32 + 8;

        if( v_bufflen_u8 <= ADC_SINGLE_MAX_CHANNEL )
        {
            l_len_u8 = v_bufflen_u8;
        }
        else
        {
            l_len_u8 = ADC_SINGLE_MAX_CHANNEL;
        }
    }

    for( l_ii_u8 = 0; l_ii_u8 < l_len_u8; l_ii_u8++)
    {
        l_temp_u8 = (*((volatile Uint16 *)(l_baseAddr_u32 + l_ii_u8)) >> 4);

        vp_buff__f[l_ii_u8] = AdcDataConvert(l_temp_u8);
    }

    /* 当前不是工作在连续运行模式时，复位序列器 */
    if( ADC_CONTIN_RUN_OFF == myAdcConf_t.adcContiRunMode_u8)
    {
        AdcSeqRst(v_seqnum_u8);
    }
    else
    {
        /* NO ACTION */
    }
}

#endif
//====================================================================
// END OF FILE
//====================================================================

