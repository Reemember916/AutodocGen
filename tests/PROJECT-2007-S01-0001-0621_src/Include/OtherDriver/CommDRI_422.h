#ifndef COMMDRI_422_

#define COMMDRI_422_

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
 * 文件名称:   CommDRI_422.h
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
/* ***************************************************************** */
#define COMMDRI_422_NUM        (1U)  /* CCDL 端口数量 */

#define COMMDRI_422_ID_CCDL       (0U)  /* RS422 CCDL 通道0 */


/* ***************************************************************** */

/******* 板间通信422寄存器地址设置  *******/
/* CCDL 0通道寄存器地址设置  */
#define COMM422_0_REG_CONF_TAB {                                  \
                              0x4000U,  /* 接收缓冲寄存器 (或接收FIFO) */  \
                              0x4001U,  /* 接收FIFO可读计数   */  \
		                      0x4002U,  /* 奇偶校验错误计数   */  \
		 	 	 	 	 	  0x4101U,  /* 接收FIFO读使能    */  \
							  0x4100U,  /* 发送数据FIFO  */  \
		                      0x4102U,  /* 复位接收FIFO  */  \
                            }
/* ***************************************************************** */

/* CCDL发送准备状态定义 */
#define DRI422_R_EN_VALID     (0x01U)  /* 接收读取使能有效     */
#define DRI422_R_EN_INVALID   (0x00U)  /* 接收读取使能无效     */

/* 422接收FIFO复位状态定义 */
#define DRI422_RFIFO_RESET_EN_VALID     (0x01U)  /* 接收FIFO复位使能有效     */
#define DRI422_RFIFO_RESET_EN_INVALID   (0x00U)  /* 接收FIFO复位使能无效     */

/* CCDL接收状态定义 */
#define DRI422_R_FIFO_OK     (0x00U)        /* CCDL FIFO接收未溢出  */
#define DRI422_R_FIFO_OVFL   (0x01U)        /* CCDL FIFO接收溢出      */

/* CCDL接收状态定义 */
#define CCDL_RX_FIFO_OK     (0x00U)        /* CCDL FIFO接收未溢出  */
#define CCDL_RX_FIFO_OVFL   (0x01U)        /* CCDL FIFO接收溢出      */

#define CCDL_RX_DATA_NUM_MAX      (256U)  /* CCDL 接收数据个数最大值    */

/* CCDL数据设置结构体 */
typedef struct _ccdlDataConf
{
    Uint16  baudFactor_u16;/* 波特率分频因子     */
    Uint8   databits_u8;   /* 数据位     */
    Uint8   stopBITs_u8;   /* 停止位     */
    Uint8   parity_u8;     /* 校验位     */
}ccdlDataConf_t;

/************************************************************************************/
/* CCDL寄存器设置结构体 */
typedef struct _Reg422Conf
{
    Uint16  RReg_FiFo_Data_u16;      /* 接收缓冲寄存器 (或接收FIFO) */
    Uint16  RReg_FiFo_Cnt_u16;       /* 接收FIFO可读计数   */
    Uint16  RReg_parity_ErrCnt_u16;  /* 奇偶校验错误计数   */
    Uint16  WReg_rFifo_EN_u16;       /* 接收FIFO读使能    */
    Uint16  WReg_wData_u16;          /* 发送数据FIFO  */
    Uint16  WReg_resetRFifo_u16;     /* 复位接收FIFO  */
}Reg422Conf_t;

/***************************************************************************/
/* 外部调用函数接口 */

extern Uint16 Ccdl422RxFifoStatusGet(Uint16 v_ccdlID_u16);
extern Uint16 Ccdl422ReadBuff(Uint16 v_ccdlID_u16,Uint16 *v_pbuff_i16);
extern void Ccdl422SendBuff(Uint16 v_ccdlID_u16,Uint16 *v_pbuff_u16,Uint16 v_len_u16);
extern void Ccdl422RFIFOReset(Uint16 v_ccdlID_u16);

#endif /* end of include guard: DRI_CCDL_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
