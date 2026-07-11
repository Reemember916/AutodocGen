#ifndef COMMDRI_CAN_

#define COMMDRI_CAN_

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
 * 文件名称:   CommDRI_CAN.h
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V2.00
 *
 **********************************************************************************
 *
 * 功能说明:    本功能模块，实现基于CCDL的CAN通信底层接口
 *
 *********************************************************************************/
/* ***************************************************************** */
#define COMMDRI_CAN_NUM        (12U)  /* 快存CAN 邮箱数量 */
#define COMMDRI_CAN_STORE_NUM  (6U)  /* 快存CAN 邮箱数量 */
#define COMMDRI_CAN_CCDL_NUM   (6U)  /* CCDL CAN 邮箱数量 */

#define COMMDRI_CAN_ID_0       (0U)  /* CAN 邮箱0 */
#define COMMDRI_CAN_ID_1       (1U)  /* CAN 邮箱1 */
#define COMMDRI_CAN_ID_2       (2U)  /* CAN 邮箱2 */
#define COMMDRI_CAN_ID_3       (3U)  /* CAN 邮箱3 */
#define COMMDRI_CAN_ID_4       (4U)  /* CAN 邮箱4 */
#define COMMDRI_CAN_ID_5       (5U)  /* CAN 邮箱5 */

#define COMMDRI_CAN_ID_6       (6U)  /* CAN 邮箱6 */
#define COMMDRI_CAN_ID_7       (7U)  /* CAN 邮箱7 */
#define COMMDRI_CAN_ID_8       (8U)  /* CAN 邮箱8 */
#define COMMDRI_CAN_ID_9       (9U)  /* CAN 邮箱9 */
#define COMMDRI_CAN_ID_10      (10U) /* CAN 邮箱10 */
#define COMMDRI_CAN_ID_11      (11U) /* CAN 邮箱11 */

#define COMMCAN_DATA_ADR_NUM   (4U)  /* CAN 单个邮箱数据对应总线地址数目 */
#define COMMCAN_DATA_LEN       (8U)  /* CAN 发送数据长度，默认为8 */

/* ***************************************************************** */

/*  CAN驱动设置第2步：寄存器设置 */
/******* 快存邮箱寄存器地址设置  *******/
/* CAN 0邮箱寄存器地址设置  */
#define COMMCAN_0_REG_CONF_TAB {                      \
                              0x4071U, /* 发送起始地址 */  \
                              0x4071U  /* 接收起始地址 */  \
                            }

/* CAN 1邮箱寄存器地址设置  */
#define COMMCAN_1_REG_CONF_TAB {                      \
                              0x4075U, /* 发送起始地址 */  \
                              0x4075U  /* 接收起始地址 */  \
                            }

/* CAN 2邮箱寄存器地址设置  */
#define COMMCAN_2_REG_CONF_TAB {                      \
                              0x4079U, /* 发送起始地址 */  \
                              0x4079U  /* 接收起始地址 */  \
                            }

/* CAN 3邮箱寄存器地址设置  */
#define COMMCAN_3_REG_CONF_TAB {                      \
                              0x407DU, /* 发送起始地址 */  \
                              0x407DU  /* 接收起始地址 */  \
                            }

/* CAN 4邮箱寄存器地址设置  */
#define COMMCAN_4_REG_CONF_TAB {                      \
                              0x4081U, /* 发送起始地址 */  \
							  0x4081U  /* 接收起始地址 */  \
                            }

/* CAN 5邮箱寄存器地址设置  */
#define COMMCAN_5_REG_CONF_TAB {                      \
                              0x4085U, /* 发送起始地址 */  \
							  0x4085U  /* 接收起始地址 */  \
                            }

/******* CCDL邮箱寄存器地址设置  *******/
/* CAN 6邮箱寄存器地址设置  */
#define COMMCAN_6_REG_CONF_TAB {                      \
                              0x4089U, /* 发送起始地址 */  \
							  0x406FU  /* 接收起始地址 */  \
                            }
/* CAN 7邮箱寄存器地址设置  */
#define COMMCAN_7_REG_CONF_TAB {                      \
                              0x408DU, /* 发送起始地址 */  \
							  0x4073U  /* 接收起始地址 */  \
                            }

/* CAN 8邮箱寄存器地址设置  */
#define COMMCAN_8_REG_CONF_TAB {                      \
                              0x4091U, /* 发送起始地址 */  \
							  0x4077U  /* 接收起始地址 */  \
                            }

/* CAN 9邮箱寄存器地址设置  */
#define COMMCAN_9_REG_CONF_TAB {                      \
                              0x4095U, /* 发送起始地址 */  \
							  0x407BU  /* 接收起始地址 */  \
                            }

/* CAN 10邮箱寄存器地址设置  */
#define COMMCAN_10_REG_CONF_TAB {                      \
                              0x4099U, /* 发送起始地址 */  \
							  0x407FU  /* 接收起始地址 */  \
                            }

/* CAN 11邮箱寄存器地址设置  */
#define COMMCAN_11_REG_CONF_TAB {                      \
                              0x409DU, /* 发送起始地址 */  \
							  0x4083U  /* 接收起始地址 */  \
                            }
/* ***************************************************************** */

/************************************************************************************/
/* CCDL寄存器设置结构体 */
typedef struct _RegCANConf
{
    Uint16  WReg_FiFo_Start_u16;   /* 发送FIFO开始地址，从开始地址起4个地址用于发送，每个地址发送2个字节，共发送8字节数据  */
    Uint16  RReg_FiFo_Start_u16;   /* 接收FIFO开始地址，从开始地址起4个地址用于接收，每个地址接收2个字节，共接收8字节数据  */

}RegCanConf_t;

/***************************************************************************/
/* 外部调用函数接口 */

extern void CcdlCanMboxSendFix(Uint16 v_mboxNum_u16,Uint16 *vp_wBuff_u16);
extern void CcdlCanMboxRx(Uint16 v_rboxNum_u16,Uint16 *vp_rBuff_u16);

#endif /* end of include guard: COMMDRI_CAN_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
