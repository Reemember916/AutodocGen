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
 * 文件名称:    synchronous.h
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
 * 1.
 *
 *********************************************************************************/


#ifndef SYNCHRONOUS_H_
#define SYNCHRONOUS_H_


/*************-----------------------  需要按需配置的部分如下   -------------------------------***********************/

/* 同步整体的ID */
#define SYNC_LONG_ID    (0U) /* 长同步  */
#define SYNC_SHORT_ID   (1U) /* 短同步  */
#define SYNC_FRAME_ID   (2U) /* 帧同步  */

#define SYNC_STYL_NUM   (3U) /* 同步类型总数  */

/*********************************************/
/* 高、低电平硬件接口选择 */
#define SYNC_RX_B	(GPIO_IN_SYNC_RX)  /* 同步接收管脚 */
#define SYNC_TX_B	(GPIO_OUT_SYNC_TX)  /* 同步发送管脚 */

/* 同步通道ID */
#define SYNC_AB_ID   (0U) /* AB同步通道 */

#define SYNC_ID_NUM  (1U) /* 同步通道总数 */

/* 同步通道的GPIO口配置 */
#define DEFAULT_SYNC_GPIO_CONFG  {SYNC_TX_B,SYNC_RX_B}
/*********************************************/
/* 通道同步的时间配置，依次长同步、短同步、周期同步  */
#define LONG_SYNC_TIME             (1000000UL)  /* 上电的长同步时间         */
#define SHORT_SYNC_TIME            (10000UL)    /* 上电的短同步时间         */
#define FRAME_SYNC_TIME            (100UL)      /* 帧同步时间                     */
#define HANDSHAKE_L_HOLD_US        (7UL)        /* 低握手成功后的板级稳定等待时间 */

/*************     --------------------------  需要按需配置的部分如上 ----------------------------------      ********************/



/*********************************************/
/* 握手ID */
#define HANDSK_L_ID      (0U)  /* 低握手，读取的引脚电平为低时有效 */
#define HANDSK_H_ID      (1U)  /* 高握手，读取的引脚电平为高时有效 */
#define HANDSK_ID_NUM    (2U)

#define HANDSK_SUCC      (0U) /* 握手成功 */
#define HANDSK_FAULT     (1U) /* 握手失败 */
#define HANDSHAKE_END    (123U) /* 握手结束*/

/*********************************************/
#define SYNC_NORM   (0U)  /* 同步正常 */
#define SYNC_ERR    (1U)  /* 同步故障 */
/*************************************************************/
/* 同步故障码 */
typedef union{  /* 0--正常， 1--故障 */
	Uint16 all;
	struct{
		Uint16 handShakeL:1;       //bit0  低握手
		Uint16 handShakeH:1;       //bit1 高握手
		Uint16 synRelRslt:1;       //bit2 同步的实时拍结果
		Uint16 resvd3_15:13;       //bit3_15
	} bit;
}SynFaultCode_TypeDef;


/* 同步整体的状态信息 */
typedef struct{
    Uint32 costTimHdSk_u32[HANDSK_ID_NUM]; /* 高、低握手消耗的时间 */
	Uint32 cstTimSyn_u32;                  /* 同步消耗的时间             */
	Uint32 cstMaxTimSyn_u32;               /* 同步消耗的最长时间 */

	SynFaultCode_TypeDef faltCod_un16;     /* 故障码 */

}SynWholeInform_TypeDef;

/* 同步状态信息 */
typedef struct{
	Uint16 pinOut_u16;                  /* 同步输出引脚 */
	Uint16 pinInt_u16;                  /* 同步读取引脚 */
	SynFaultCode_TypeDef faltCod_un16;  /* 故障码 */
	Uint16 synFaltSum_u16;              /* 帧同步错误总数 */
	Uint16 synFaltCnt_u16;              /* 帧同步连续错误数 */
	Uint16 synFaltMaxCnt_u16;           /* 帧同步连续最大错误数 */

}SynInform_TypeDef;


/* 同步信息配置表 */
typedef struct{
	Uint16 confPinOut_u16;                  /* 同步输出引脚 */
	Uint16 confPinInt_u16;                  /* 同步读取引脚 */
}SynConf_TypeDef;

/* ***************************************************************** */
/**
 * 供外部调用函数接口
 */
/* ***************************************************************** */
extern void SynchroInit(void);     /* 同步数据初始化 */
extern void FrameSyn(Uint16 l_synStyleID_u16,Uint32 l_frmSynTim_u32);

extern SynWholeInform_TypeDef SynWholeInfGet(Uint16 l_synStyleID_u16); /* 同步类型的信息获取 */
extern Uint16 SyncFrameHealthyGet(void);                 /* 帧同步本拍是否健康 */

/*********************************************************************************************************************/

#endif /* SYNCHRONOUS_H_ */

/* ========================================================================== */
/* END OF FILE */
/* ========================================================================== */
