#ifndef COMMDRI_429_

#define COMMDRI_429_

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
 * 文件名称:   CommDRI_429.h
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V2.00
 *
 **********************************************************************************
 *
 * 功能说明:    本功能模块，实现基于CCDL的Arinc429通信底层接口
 *
 *********************************************************************************/
/* ***************************************************************** */
#define COMMDRI_429_NUM        (12U)  /* CCDL 端口数量 */

#define COMMDRI_429_ID_0       (0U)  /* Arinc429 通道0 */
#define COMMDRI_429_ID_1       (1U)  /* Arinc429 通道1 */
#define COMMDRI_429_ID_2       (2U)  /* Arinc429 通道2 */
#define COMMDRI_429_ID_3       (3U)  /* Arinc429 通道3 */

#define COMMDRI_429_ID_4       (4U)  /* Arinc429 通道4 */
#define COMMDRI_429_ID_5       (5U)  /* Arinc429 通道5 */
#define COMMDRI_429_ID_6       (6U)  /* Arinc429 通道6 */
#define COMMDRI_429_ID_7       (7U)  /* Arinc429 通道7 */

#define COMMDRI_429_ID_8       (8U)  /* Arinc429 通道8 */
#define COMMDRI_429_ID_9       (9U)  /* Arinc429 通道9 */
#define COMMDRI_429_ID_10      (10U)  /* Arinc429 通道10 */
#define COMMDRI_429_ID_11      (11U)  /* Arinc429 通道11 */


#define A429_RX_DATA_NUM_MAX      (64U)  /* 429接收数据个数最大值    */


/* ***************************************************************** */

/*  奇偶校验设置 */



/*  429驱动设置第2步：寄存器设置 */


/* 429 0-3通道寄存器地址设置 (补全丢失配置) */
#define COMM429_0_REG_CONF_TAB {                                  \
                              0x4080U,  /* 接收低2字节 */  \
                              0x4081U,  /* 接收高2字节 */  \
                              0x4082U,  /* 接收FIFO可读计数   */  \
		 	 	 	 	 	  0x4086U,  /* 接收FIFO读使能    */  \
                              0x4084U,  /* 发送低2字节 */  \
                              0x4085U,  /* 接收高2字节 */  \
                              0x4087U,  /* 复位接收FIFO */  \
                            }
#define COMM429_1_REG_CONF_TAB COMM429_0_REG_CONF_TAB
#define COMM429_2_REG_CONF_TAB COMM429_0_REG_CONF_TAB
#define COMM429_3_REG_CONF_TAB COMM429_0_REG_CONF_TAB

/* 429 4通道寄存器地址设置  ：加油泵控制器1*/
#define COMM429_4_REG_CONF_TAB {                                  \
                              0x4064U,  /* 接收低2字节 */  \
                              0x4065U,  /* 接收高2字节 */  \
                              0x4066U,  /* 接收FIFO可读计数   */  \
		 	 	 	 	 	  0x406AU,  /* 接收FIFO读使能    */  \
                              0x4068U,  /* 发送低2字节 */  \
                              0x4069U,  /* 接收高2字节 */  \
                              0x406BU,  /* 复位接收FIFO */  \
                            }

/* 429 5通道寄存器地址设置  ：加油泵控制器2*/
#define COMM429_5_REG_CONF_TAB {                                  \
                              0x4068U,  /* 接收低2字节 */  \
                              0x4069U,  /* 接收高2字节 */  \
                              0x406AU,  /* 接收FIFO可读计数   */  \
		 	 	 	 	 	  0x406EU,  /* 接收FIFO读使能    */  \
                              0x406CU,  /* 发送低2字节 */  \
                              0x406DU,  /* 接收高2字节 */  \
                              0x406FU,  /* 复位接收FIFO */  \
                            }


/* 429 6通道寄存器地址设置  ：控制装置*/
#define COMM429_6_REG_CONF_TAB {                                  \
                              0x4050U,  /* 接收低2字节 */  \
                              0x4051U,  /* 接收高2字节 */  \
                              0x4052U,  /* 接收FIFO可读计数   */  \
		 	 	 	 	 	  0x4056U,  /* 接收FIFO读使能    */  \
                              0x4054U,  /* 发送低2字节 */  \
                              0x4055U,  /* 接收高2字节 */  \
                              0x4057U,  /* 复位接收FIFO */  \
                            }

/* 429 7通道寄存器地址设置  ：任务计算机1*/
#define COMM429_7_REG_CONF_TAB {                                  \
                              0x4040U,  /* 接收低2字节 */  \
                              0x4041U,  /* 接收高2字节 */  \
                              0x4042U,  /* 接收FIFO可读计数   */  \
		 	 	 	 	 	  0x4042U,  /* 接收FIFO读使能    */  \
                              0x4040U,  /* 发送低2字节 */  \
                              0x4041U,  /* 接收高2字节 */  \
                              0x4043U,  /* 复位接收FIFO */  \
                            }

/* 429 8通道寄存器地址设置  ：任务计算机2*/
#define COMM429_8_REG_CONF_TAB {                                  \
                              0x4044U,  /* 接收低2字节 */  \
                              0x4045U,  /* 接收高2字节 */  \
                              0x4046U,  /* 接收FIFO可读计数   */  \
		 	 	 	 	 	  0x4046U,  /* 接收FIFO读使能    */  \
                              0x4044U,  /* 发送低2字节 */  \
                              0x4045U,  /* 接收高2字节 */  \
                              0x4047U,  /* 复位接收FIFO */  \
                            }

/* 429 9通道寄存器地址设置  ：机电管理计算机*/
#define COMM429_9_REG_CONF_TAB {                                  \
                              0x4003U,  /* 接收低2字节 */  \
                              0x4004U,  /* 接收高2字节 */  \
                              0x4005U,  /* 接收FIFO可读计数   */  \
		 	 	 	 	 	  0x4142U,  /* 接收FIFO读使能    */  \
                              0x4140U,  /* 发送低2字节 */  \
                              0x4141U,  /* 接收高2字节 */  \
                              0x4143U,  /* 复位接收FIFO */  \
                            }

/* 429 10通道寄存器地址设置  ：左吊舱控制装置*/
#define COMM429_10_REG_CONF_TAB {                                  \
                              0x4006U,  /* 接收低2字节 */  \
                              0x4007U,  /* 接收高2字节 */  \
                              0x4008U,  /* 接收FIFO可读计数   */  \
		 	 	 	 	 	  0x4146U,  /* 接收FIFO读使能    */  \
                              0x4144U,  /* 发送低2字节 */  \
                              0x4145U,  /* 接收高2字节 */  \
                              0x4147U,  /* 复位接收FIFO */  \
                            }

/* 429 11通道寄存器地址设置  ：右吊舱控制装置*/
#define COMM429_11_REG_CONF_TAB {                                  \
                              0x4009U,  /* 接收低2字节 */  \
                              0x400AU,  /* 接收高2字节 */  \
                              0x400BU,  /* 接收FIFO可读计数   */  \
		 	 	 	 	 	  0x414AU,  /* 接收FIFO读使能    */  \
                              0x4148U,  /* 发送低2字节 */  \
                              0x4149U,  /* 接收高2字节 */  \
                              0x414BU,  /* 复位接收FIFO */  \
                            }
/* ***************************************************************** */
/* 429发送回绕寄存器地址设置 */
/* RIU通道9发送回绕寄存器 */
#define COMM429_9_REG_LOOPBACK_L     (0x4025U)  /* 回绕低2字节 */
#define COMM429_9_REG_LOOPBACK_H     (0x4026U)  /* 回绕高2字节 */
#define COMM429_9_REG_LOOPBACK_CNT   (0x4027U)  /* 回绕FIFO可读计数 */
/* 左吊舱通道10发送回绕寄存器 */
#define COMM429_10_REG_LOOPBACK_L    (0x4028U)  /* 回绕低2字节 */
#define COMM429_10_REG_LOOPBACK_H    (0x4029U)  /* 回绕高2字节 */
#define COMM429_10_REG_LOOPBACK_CNT  (0x402AU)  /* 回绕FIFO可读计数 */
/* 右吊舱通道11发送回绕寄存器 */
#define COMM429_11_REG_LOOPBACK_L    (0x402BU)  /* 回绕低2字节 */
#define COMM429_11_REG_LOOPBACK_H    (0x402CU)  /* 回绕高2字节 */
#define COMM429_11_REG_LOOPBACK_CNT  (0x402DU)  /* 回绕FIFO可读计数 */
/* RIU通道9发送回绕使能开关 */
#define COMM429_9_REG_LOOPBACK_EN     (0x414CU)  /* RIU发送回绕使能   */
/* 左吊舱通道10发送回绕使能开关 */
#define COMM429_10_REG_LOOPBACK_EN    (0x414EU)  /* 左吊舱发送回绕使能 */
/* 右吊舱通道11发送回绕使能开关 */
#define COMM429_11_REG_LOOPBACK_EN    (0x4150U)  /* 右吊舱发送回绕使能 */


/* ***************************************************************** */

/* CCDL发送准备状态定义 */
#define DRI429_R_EN_VALID     (0x01U)  /* 接收读取使能有效     */
#define DRI429_R_EN_INVALID   (0x00U)  /* 接收读取使能无效     */

/* 429接收FIFO复位状态定义 */
#define DRI429_RFIFO_RESET_EN_VALID     (0x01U)  /* 接收FIFO复位使能有效     */
#define DRI429_RFIFO_RESET_EN_INVALID   (0x00U)  /* 接收FIFO复位使能无效     */

/* CCDL接收状态定义 */
#define DRI429_R_FIFO_OK     (0x00U)        /* CCDL FIFO接收未溢出  */
#define DRI429_R_FIFO_OVFL   (0x01U)        /* CCDL FIFO接收溢出      */

#define DRI429_T_FIFO_FULL   (0x01U)        /* 发送FIFO满状态位，发送状态寄存器未配置时不启用 */
#define DRI429_T_EN_VALID    (0x01U)        /* 发送触发有效，发送触发寄存器未配置时不启用 */
#define DRI429_T_EN_INVALID  (0x00U)        /* 发送触发无效 */
#define DRI429_TX_WAIT_MAX   (1000U)        /* 发送FIFO非满等待上限 */

#define PARITY_ODD           (1U)           /* 奇校验 */
#define PARITY_EVEN          (0U)           /* 偶校验 */
/* ***************************************************************** */

/************************************************************************************/
/* CCDL寄存器设置结构体 */
typedef struct _Reg429Conf
{
    Uint16  RReg_FiFo_2Byte_L_u16;   /* 接收低2字节 */
    Uint16  RReg_FiFo_2Byte_H_u16;   /* 接收高2字节 */
    Uint16  RReg_FiFo_Cnt_u16;       /* 接收FIFO可读计数   */
    Uint16  WReg_rFifo_EN_u16;    /* 接收FIFO读使能    */
    Uint16  WReg_FiFo_2Byte_L_u16;   /* 发送低2字节 */
    Uint16  WReg_FiFo_2Byte_H_u16;   /* 发送高2字节 */
    Uint16  WReg_resetRFifo_u16;    /* 复位接收FIFO    */
    Uint16  RReg_TFifo_Status_u16;  /* 发送FIFO状态，可选，0表示未配置 */
    Uint16  WReg_tFifo_EN_u16;      /* 发送FIFO触发，可选，0表示未配置 */
}Reg429Conf_t;

struct arinc429Bit
{
    Uint16 label:8;     //Label标号
    Uint32 data:21;     //数据，当前协议无SDI，Label后直接跟Data
    Uint16 ssm:2;       //SSM标号
    Uint16 parity:1;    //校验位
};

union arinc429Data
{
    Uint32  msgData;        //ARINC429四字节数据
    struct arinc429Bit bit; //ARINC429协议字段数据
};

/***************************************************************************/
/* 外部调用函数接口 */

extern Uint16 Ccdl429RxFifoStatusGet(Uint16 v_ccdlID_u16);
extern Uint16 Ccdl429ReadBuff(Uint16 v_ccdlID_u16,union arinc429Data *v_pbuff_un);
extern void Ccdl429DataSend(Uint16 v_ccdlID_u16,union arinc429Data v_mydata_un);
extern void Ccdl429RFIFOReset(Uint16 v_ccdlID_u16);
extern union arinc429Data Ccdl429ParityCalc(union arinc429Data v_msgData_un, Uint16 v_odd_u16);
extern Uint16 Ccdl429ParityCheck(union arinc429Data v_msgData_un, Uint16 v_odd_u16);

#endif /* end of include guard: DRI_CCDL_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
