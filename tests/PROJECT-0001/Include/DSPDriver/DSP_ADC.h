#ifndef DSP_ADC_

#define DSP_ADC_

//---------------------------------------------------------------------------
// ADC Individual Register Bit Definitions:

struct ADCTRL1_BITS {     // bits  description
    Uint16  rsvd1:4;      // 3:0   reserved
    Uint16  SEQ_CASC:1;   // 4     Cascaded sequencer mode
    Uint16  SEQ_OVRD:1;   // 5     Sequencer override 
    Uint16  CONT_RUN:1;   // 6     Continuous run
    Uint16  CPS:1;        // 7     ADC core clock pre-scalar
    Uint16  ACQ_PS:4;     // 11:8  Acquisition window size
    Uint16  SUSMOD:2;     // 13:12 Emulation suspend mode
    Uint16  RESET:1;      // 14    ADC reset
    Uint16  rsvd2:1;      // 15    reserved
};

union ADCTRL1_REG {
   Uint16                all;
   struct ADCTRL1_BITS   bit;
};

struct ADCTRL2_BITS {         // bits  description
    Uint16  EPWM_SOCB_SEQ2:1; // 0     EPWM compare B SOC mask for SEQ2
    Uint16  rsvd1:1;          // 1     reserved
    Uint16  INT_MOD_SEQ2:1;   // 2     SEQ2 Interrupt mode
    Uint16  INT_ENA_SEQ2:1;   // 3     SEQ2 Interrupt enable
    Uint16  rsvd2:1;          // 4     reserved
    Uint16  SOC_SEQ2:1;       // 5     Start of conversion for SEQ2
    Uint16  RST_SEQ2:1;       // 6     Reset SEQ2
    Uint16  EXT_SOC_SEQ1:1;   // 7     External start of conversion for SEQ1
    Uint16  EPWM_SOCA_SEQ1:1; // 8     EPWM compare B SOC mask for SEQ1
    Uint16  rsvd3:1;          // 9     reserved
    Uint16  INT_MOD_SEQ1:1;   // 10    SEQ1 Interrupt mode
    Uint16  INT_ENA_SEQ1:1;   // 11    SEQ1 Interrupt enable
    Uint16  rsvd4:1;          // 12    reserved
    Uint16  SOC_SEQ1:1;       // 13    Start of conversion trigger for SEQ1
    Uint16  RST_SEQ1:1;       // 14    Restart sequencer 1   
    Uint16  EPWM_SOCB_SEQ:1;  // 15    EPWM compare B SOC enable
};


union ADCTRL2_REG {
   Uint16                all;
   struct ADCTRL2_BITS   bit;
};


struct ADCASEQSR_BITS {       // bits   description
    Uint16  SEQ1_STATE:4;     // 3:0    SEQ1 state
    Uint16  SEQ2_STATE:3;     // 6:4    SEQ2 state
    Uint16  rsvd1:1;          // 7      reserved
    Uint16  SEQ_CNTR:4;       // 11:8   Sequencing counter status 
    Uint16  rsvd2:4;          // 15:12  reserved  
};

union ADCASEQSR_REG {
   Uint16                 all;
   struct ADCASEQSR_BITS  bit;
};


struct ADCMAXCONV_BITS {      // bits  description
    Uint16  MAX_CONV1:4;      // 3:0   Max number of conversions
    Uint16  MAX_CONV2:3;      // 6:4   Max number of conversions    
    Uint16  rsvd1:9;          // 15:7  reserved 
};

union ADCMAXCONV_REG {
   Uint16                  all;
   struct ADCMAXCONV_BITS  bit;
};


struct ADCCHSELSEQ1_BITS {    // bits   description
    Uint16  CONV00:4;         // 3:0    Conversion selection 00
    Uint16  CONV01:4;         // 7:4    Conversion selection 01
    Uint16  CONV02:4;         // 11:8   Conversion selection 02
    Uint16  CONV03:4;         // 15:12  Conversion selection 03
};

union  ADCCHSELSEQ1_REG{
   Uint16                    all;
   struct ADCCHSELSEQ1_BITS  bit;
};

struct ADCCHSELSEQ2_BITS {    // bits   description
    Uint16  CONV04:4;         // 3:0    Conversion selection 04
    Uint16  CONV05:4;         // 7:4    Conversion selection 05
    Uint16  CONV06:4;         // 11:8   Conversion selection 06
    Uint16  CONV07:4;         // 15:12  Conversion selection 07
};

union  ADCCHSELSEQ2_REG{
   Uint16                    all;
   struct ADCCHSELSEQ2_BITS  bit;
};

struct ADCCHSELSEQ3_BITS {    // bits   description
    Uint16  CONV08:4;         // 3:0    Conversion selection 08
    Uint16  CONV09:4;         // 7:4    Conversion selection 09
    Uint16  CONV10:4;         // 11:8   Conversion selection 10
    Uint16  CONV11:4;         // 15:12  Conversion selection 11
};

union  ADCCHSELSEQ3_REG{
   Uint16                    all;
   struct ADCCHSELSEQ3_BITS  bit;
};

struct ADCCHSELSEQ4_BITS {    // bits   description
    Uint16  CONV12:4;         // 3:0    Conversion selection 12
    Uint16  CONV13:4;         // 7:4    Conversion selection 13
    Uint16  CONV14:4;         // 11:8   Conversion selection 14
    Uint16  CONV15:4;         // 15:12  Conversion selection 15
};

union  ADCCHSELSEQ4_REG {
   Uint16                    all;
   struct ADCCHSELSEQ4_BITS  bit;
};

struct ADCTRL3_BITS {         // bits   description
    Uint16   SMODE_SEL:1;     // 0      Sampling mode select
    Uint16   ADCCLKPS:4;      // 4:1    ADC core clock divider
    Uint16   ADCPWDN:1;       // 5      ADC powerdown
    Uint16   ADCBGRFDN:2;     // 7:6    ADC bandgap/ref power down
    Uint16   rsvd1:8;         // 15:8   reserved
}; 

union  ADCTRL3_REG {
   Uint16                all;
   struct ADCTRL3_BITS   bit;
};


struct ADCST_BITS {           // bits   description
    Uint16   INT_SEQ1:1;      // 0      SEQ1 Interrupt flag  
    Uint16   INT_SEQ2:1;      // 1      SEQ2 Interrupt flag
    Uint16   SEQ1_BSY:1;      // 2      SEQ1 busy status
    Uint16   SEQ2_BSY:1;      // 3      SEQ2 busy status
    Uint16   INT_SEQ1_CLR:1;  // 4      SEQ1 Interrupt clear
    Uint16   INT_SEQ2_CLR:1;  // 5      SEQ2 Interrupt clear
    Uint16   EOS_BUF1:1;      // 6      End of sequence buffer1
    Uint16   EOS_BUF2:1;      // 7      End of sequence buffer2
    Uint16   rsvd1:8;         // 15:8   reserved
};


union  ADCST_REG {
   Uint16             all;
   struct ADCST_BITS  bit;
};

struct ADCREFSEL_BITS {       // bits   description
	Uint16   rsvd1:14;        // 13:0   reserved
	Uint16   REF_SEL:2;       // 15:14  Reference select
};
union ADCREFSEL_REG {
	Uint16		all;
	struct ADCREFSEL_BITS bit;
};

struct ADCOFFTRIM_BITS{       // bits   description
	int16	OFFSET_TRIM:9;    // 8:0    Offset Trim  
	Uint16	rsvd1:7;          // 15:9   reserved
};

union ADCOFFTRIM_REG{
	Uint16		all;
	struct ADCOFFTRIM_BITS bit;
};
struct ADC_REGS {
    union ADCTRL1_REG      ADCTRL1;       // ADC Control 1
    union ADCTRL2_REG      ADCTRL2;       // ADC Control 2
    union ADCMAXCONV_REG   ADCMAXCONV;    // Max conversions
    union ADCCHSELSEQ1_REG ADCCHSELSEQ1;  // Channel select sequencing control 1
    union ADCCHSELSEQ2_REG ADCCHSELSEQ2;  // Channel select sequencing control 2
    union ADCCHSELSEQ3_REG ADCCHSELSEQ3;  // Channel select sequencing control 3
    union ADCCHSELSEQ4_REG ADCCHSELSEQ4;  // Channel select sequencing control 4
    union ADCASEQSR_REG    ADCASEQSR;     // Autosequence status register
    Uint16                 ADCRESULT0;    // Conversion Result Buffer 0
    Uint16                 ADCRESULT1;    // Conversion Result Buffer 1
    Uint16                 ADCRESULT2;    // Conversion Result Buffer 2
    Uint16                 ADCRESULT3;    // Conversion Result Buffer 3
    Uint16                 ADCRESULT4;    // Conversion Result Buffer 4
    Uint16                 ADCRESULT5;    // Conversion Result Buffer 5
    Uint16                 ADCRESULT6;    // Conversion Result Buffer 6
    Uint16                 ADCRESULT7;    // Conversion Result Buffer 7
    Uint16                 ADCRESULT8;    // Conversion Result Buffer 8
    Uint16                 ADCRESULT9;    // Conversion Result Buffer 9
    Uint16                 ADCRESULT10;   // Conversion Result Buffer 10
    Uint16                 ADCRESULT11;   // Conversion Result Buffer 11
    Uint16                 ADCRESULT12;   // Conversion Result Buffer 12
    Uint16                 ADCRESULT13;   // Conversion Result Buffer 13
    Uint16                 ADCRESULT14;   // Conversion Result Buffer 14
    Uint16                 ADCRESULT15;   // Conversion Result Buffer 15
    union ADCTRL3_REG      ADCTRL3;       // ADC Control 3  
    union ADCST_REG        ADCST;         // ADC Status Register
    Uint16				   rsvd1;
    Uint16                 rsvd2;
    union ADCREFSEL_REG    ADCREFSEL;     // Reference Select Register
    union ADCOFFTRIM_REG   ADCOFFTRIM;    // Offset Trim Register
};


struct ADC_RESULT_MIRROR_REGS
{
    Uint16                 ADCRESULT0;    // Conversion Result Buffer 0
    Uint16                 ADCRESULT1;    // Conversion Result Buffer 1
    Uint16                 ADCRESULT2;    // Conversion Result Buffer 2
    Uint16                 ADCRESULT3;    // Conversion Result Buffer 3
    Uint16                 ADCRESULT4;    // Conversion Result Buffer 4
    Uint16                 ADCRESULT5;    // Conversion Result Buffer 5
    Uint16                 ADCRESULT6;    // Conversion Result Buffer 6
    Uint16                 ADCRESULT7;    // Conversion Result Buffer 7
    Uint16                 ADCRESULT8;    // Conversion Result Buffer 8
    Uint16                 ADCRESULT9;    // Conversion Result Buffer 9
    Uint16                 ADCRESULT10;   // Conversion Result Buffer 10
    Uint16                 ADCRESULT11;   // Conversion Result Buffer 11
    Uint16                 ADCRESULT12;   // Conversion Result Buffer 12
    Uint16                 ADCRESULT13;   // Conversion Result Buffer 13
    Uint16                 ADCRESULT14;   // Conversion Result Buffer 14
    Uint16                 ADCRESULT15;   // Conversion Result Buffer 15
};

/* ***************************************************************** */
/**
 * 【说明】:ADC部分寄存器重定义
 */
/* ***************************************************************** */

/* ADC通道序列配置寄存器基地址 */
#define    ADCCHSELSEQ_REG_BASE     (0x7103UL)

/* ADC转换结果寄存器基地址 */
#define    ADC_RESULTS_REG_BASE     (0x7108UL)

/* ***************************************************************** */
/**
 * 【说明】: ADC 位定义
 */
/* ***************************************************************** */

//ADC 通道定义
#define     ADC_CHANNEL_0       (0U)
#define     ADC_CHANNEL_1       (1U)
#define     ADC_CHANNEL_2       (2U)
#define     ADC_CHANNEL_3       (3U)
#define     ADC_CHANNEL_4       (4U)
#define     ADC_CHANNEL_5       (5U)
#define     ADC_CHANNEL_6       (6U)
#define     ADC_CHANNEL_7       (7U)
#define     ADC_CHANNEL_8       (8U)
#define     ADC_CHANNEL_9       (9U)
#define     ADC_CHANNEL_10      (10U)
#define     ADC_CHANNEL_11      (11U)
#define     ADC_CHANNEL_12      (12U)
#define     ADC_CHANNEL_13      (13U)
#define     ADC_CHANNEL_14      (14U)
#define     ADC_CHANNEL_15      (15U)
#define     ADC_CHANNEL_NULL    (30U)

//ADC 外部参考源定义
#define     ADC_REF_IN          (0U)
#define     ADC_REF_OUT_2048    (1U)
#define     ADC_REF_OUT_1500    (2U)
#define     ADC_REF_OUT_1024    (3U)

//ADC 转换方式
#define     ADC_CONV_POLL       (0U)     //ADC转换工作在查询模式
#define     ADC_CONV_INT_EVERY  (1U)     //ADC转换工作在中断模式
#define     ADC_CONV_INT_OTHER  (2U)     //ADC转换工作在 EVERY OTHER 中断模式

/* ADC SOC模式定义 */
#define     ADC_SOC_SOFT        (0x01U << 0U)     //软件触发ADC转换
#define     ADC_SOC_EPWM_SOCB   (0x01U << 1U)     //EPWM SOCB信号触发ADC转换
#define     ADC_SOC_EPWM_SOCA   (0x01U << 2U)     //EPWM SOCA信号触发ADC转换
#define     ADC_SOC_EXT_GPIO    (0x01U << 3U)     //EXT信号触发ADC转换

/* ADC SOC转换位定义 */
#define     ADC_SEQ1        (0U)     //启动ADC SEQ1转换
#define     ADC_SEQ2        (1U)     //启动ADC SEQ2转换
#define     ADC_SEQ1_SEQ2   (2U)     //启动ADC SEQ1 和 SEQ2 转换

/* ADC忙状态位定义 */
#define     ADC_IS_BUSY     (1U)
#define     ADC_NOT_BUSY    (0U)

/* 连续运行模式设置 */
#define     ADC_CONTIN_RUN_ON   (1U)     //连续运行模式
#define     ADC_CONTIN_RUN_OFF  (0U)     //Start-Stop模式

/* 级联模式设置 */
#define     ADC_CASCADE_ON      (1U)     //级联模式
#define     ADC_CASCADE_OFF     (0U)     //非级联模式

/* 采样模式设置 */
#define     ADC_SAMPLE_SEQUEN   (0U)     //顺序采样模式
#define     ADC_SAMPLE_SIMULT   (1U)     //并发采样

#define     ADC_SEQ1_INT        (1U)     //SEQ1中断
#define     ADC_SEQ2_INT        (2U)     //SEQ2中断

//---------------------------------------------------------------------------

struct adcConf
{
    Uint8 adcRef_u8;           //ADC参考电源
    Uint8 adcSocWidth_u8;      //ADC采样脉宽
    Uint8 adcFreDivd_u8;       //ADC时钟分频系数
    Uint8 adcContiRunMode_u8;  //ADC连续运行模式
    Uint8 adcCascadeMode_u8;   //ADC级联模式
    Uint8 adcSampleMode_u8;    //ADC采样模式
    Uint8 adcIntMode_1_u8;     //ADC转换方式，轮询还是中断，SEQ1
    Uint8 adcSocMode_1_u8;     //ADC触发方式选择，SEQ1
    Uint8 adcIntMode_2_u8;     //ADC转换方式，轮询还是中断，SEQ2
    Uint8 adcSocMode_2_u8;     //ADC触发方式选择，SEQ2
};

//---------------------------------------------------------------------------
// ADC External References & Function Declarations:
//
extern volatile struct ADC_REGS AdcRegs;
extern volatile struct ADC_RESULT_MIRROR_REGS AdcMirror;

extern interrupt void ISR_ADC(void);

extern Uint16 AdcIsBusy(Uint8 seqnum);
extern void AdcReset(void);
extern void AdcSeqRst(Uint8 seqnum);
extern void AdcSocConf(Uint8 conf_1,Uint8 conf_2);
extern void AdcStartConv(Uint8 seqnum);
extern void AdcIntEnable(void);
extern void AdcIntConf(Uint8 conf_1,Uint8 conf_2);
extern void AdcIntAck(void);
extern void AdcFreConf(Uint8 divide,Uint16 dspHiSpeed);
extern void AdcRefConf(Uint8 adcRef);
extern void AdcChannelConf(Uint8 * channelBuff,Uint8 seqnum);
extern void AdcPowerUP(void);
extern void AdcInit(void);
extern Uint16 AdcSeqCountGet(void);
extern float AdcDataConvert(Uint16 code);
extern void AdcDataGet(float *buff,Uint8 bufflen,Uint8 seqnum);
extern void AdcCodeGet(Uint16 * buff,Uint8 bufflen,Uint8 seqnum);
extern void AdcMaxConvSet(Uint8 seqnum,Uint8 count);
extern Uint16 AdcIntStatusGet(void);
extern float AdcDataGetOne(Uint16 channelNum,Uint8 seqnum);

/* ***************************************************************** */
/* DSP_ADC.c 私有宏定义 */
/* ***************************************************************** */
#if DSP_ADC
#define ADC_MAX_CHANNEL            (16)
#define ADC_SINGLE_MAX_CHANNEL     (8)
#define ADC_MAX_FREQUENCY   (25)
#define ADC_Cal (void (*) (void)) 0x380080
#define ADC_DATA_FACTOR     (0.0007326)        /* (3.0 / 4095) */
#endif

#endif /* end of include guard: DSP_ADC_ */
