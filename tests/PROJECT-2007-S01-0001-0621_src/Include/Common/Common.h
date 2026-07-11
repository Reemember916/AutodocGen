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
 * 文件名称:    Common.h
 *
 * 文件日期：       REDACTED
 *
 *
 * 程序版本:   V1.00
 *
 **********************************************************************************
 *
 * 功能说明:   实现公共接口的声明
 *
 * 1.
 *
 *********************************************************************************/

#ifndef COMMON_

#define COMMON_

/* 外扩总线16位读。 */
extern Uint16 HardXintUint16Read(Uint32 v_addr_u32);

/* 外扩总线16位写。 */
extern void HardXintUint16Write(Uint32 v_addr_u32, Uint16 v_data_u16);

/*********************************************************************************/
/*
 * GPIO输入输出管脚配置相关宏定义
 *
 * */

/* GPIO输出管脚配置相关宏定义 */
#define GPIO_OUT_DSP_HARDWOG         GPIO_NUM_13  /* DSP硬件喂狗GPIO口    */
#define GPIO_OUT_LED_CON             GPIO_NUM_9  /* 呼吸灯控制输出                                    */
#define GPIO_OUT_DSP_HEART           GPIO_NUM_59  /* 心跳字输出                                    */
#define GPIO_OUT_DSP_CHV             GPIO_NUM_58  /* CHV输出			*/


#define GPIO_OUT_SYNC_TX             GPIO_NUM_0   /* 通道同步信号发送                                */
#define GPIO_OUT_SOV_CON_KQ          GPIO_NUM_20  /* 舱门开启电磁阀                                    */
#define GPIO_OUT_SOV_CON_GB          GPIO_NUM_21  /* 舱门关闭电磁阀                                    */
#define GPIO_OUT_SOV_CON_ZD          GPIO_NUM_22  /* 舱门制动电磁阀                                    */

#define GPIO_OUT_SPI_EN              GPIO_NUM_57  /* SPI片选使能                                    */

/* GPIO输入管脚配置相关宏定义 */
#define GPIO_IN_SYNC_RX             GPIO_NUM_1   /* 通道同步信号接收                                */
#define GPIO_IN_DSP_HEART           GPIO_NUM_61  /* 心跳字                                    */
#define GPIO_IN_DSP_CHV             GPIO_NUM_60  /* CHV			*/
/*********************************************************************************/
/*
 * CPLD地址及数据相关宏定义
 *
 * */
/***************************/
/* CPLD握手地址及握手数据 */
#define CPLD_ADDR_WR_HANDSHAKE_1        (0x4AAAU) /* 握手地址1，检测到写入字为0xAAAA后，本数据置0xAAAA */
#define CPLD_ADDR_WR_HANDSHAKE_2        (0x4555U) /* 握手地址2，检测到写入字为0x5555后，本数据置0x5555 */

#define CPLD_DATA_HANDSHAKE_5555        (0x5555U) /* CPLD握手读回数据0x5555 */
#define CPLD_DATA_HANDSHAKE_AAAA        (0xAAAAU) /* CPLD握手读回数据0xAAAA */

#define CPLD_ADDR_W_HANDSHAKE_FLAG      (0x4110U) /* 握手成功标记地址，1有效，其他无效 */

#define CPLD_DATA_HANDSHAKE_VALID       (0x1U)  /* 握手成功标记有效  */
#define CPLD_DATA_HANDSHAKE_INVALID     (0x0U)  /* 握手成功标记无效  */

/***************************/
/* 上电完成标志地址及数据 */
#define CPLD_ADDR_R_POWERUP_FLAG        (0x400FU) /* 上电完成标志地址 */

#define CPLD_DATA_POWERUP_FLAG          (0x5A5AU) /* 上电完成标志 有效：0x5A5A */

/***************************/
/* 冷热启动标志地址 */
#define CPLD_ADDR_R_STARTUP_FLAG        (0x400EU) /* 冷热启动标志读取地址 */
#define CPLD_ADDR_W_STARTUP_FLAG        (0x410EU) /* 冷热启动标志写入地址 */

/***************************/
/* 通道间心跳检测计数地址  */
#define CPLD_ADDR_W_HEART_CNT           (0x4111U) /* 心跳信号计数，加1计数 */

/***************************/
/* KZZZ发送有效标志地址及数据（低有效：0x0000=有效，0xFFFF=无效） */
#define CPLD_ADDR_W_KZZZ_SEND_VALID              (0x4170U) /* KZZZ发送有效标志  */

#define CPLD_DATA_KZZZ_SEND_VALID                (0x0000U) /* KZZZ发送有效，低有效，0x0000使能 */
#define CPLD_DATA_KZZZ_SEND_INVALID              (0xFFFFU) /* KZZZ发送无效，0xFFFF禁止   */

/***************************/
/* 通道有效信号CHV地址 */

#define CPLD_ADDR_W_CPUV_OUT               (0x410CU)  /* 写入地址 本通道有效信号输出    */
#define CPLD_ADDR_W_CPUV_IN                (0x400CU)  /* 采集地址 本通道有效信号回绕    */

/***************************/
/* CPLD心跳（10ms刷新一次）地址  */
#define CPLD_ADDR_R_CPLD_HEART           (0x4010U)  /* 读取地址 CPLD心跳地址    */

/***************************/
/* CPLD软件版本地址  */
#define CPLD_ADDR_R_CPLD_VER           (0x4024U)  /* 读取地址 CPLD软件版本地址    */

/* 自检信号地址及数据宏定义  */
#define CPLD_DATA_POWER_BIT_OK     		(0x1U)			/* 电源自检信号正常  */
#define CPLD_DATA_POWER_BIT_ERR         (0x0U)			/* 电源自检信号异常  */

#define CPLD_DATA_WDV_OK     		    (0x1U)			/* 狗叫信号正常  */
#define CPLD_DATA_WDV_ERR               (0x0U)			/* 狗叫信号异常  */

#define CPLD_ADDR_R_HKA_DATA1                     (0x4023U) /* HKA_DATA1离散量接口芯片数据*/

/***********************************************************************/
/* 与在线加载软件交互地址及数据宏定义 */
#define OFP_FUNC_FLG          (0x69U)              /*OFP功能标志*/

#define OFP_FLG_ADDR          (0x200100UL)         /*OFP标志起点地址*/
#define OFP_FLG_ADDR2         (OFP_FLG_ADDR + 1UL) /*OFP标志2的地址*/
#define OFP_FLG_ADDR3         (OFP_FLG_ADDR + 2UL) /*OFP标志3的地址*/
#define APP_FLG_ADDR          (0x200103UL)         /*APP擦除标志地址*/

/* 在线加载软件版本用两个地址进行记录，先低字节后高字节 */
#define SOFT_VERSION_ADDR_L   (0x20010AUL)         /* 软件版本低字节记录地址 */
#define SOFT_VERSION_ADDR_H   (0x20010BUL)         /* 软件版本高字节记录地址 */

/*********************************初始化******************************************/
/* 握手阶段最大重试次数（任务书0005：每阶段最多3次） */
#define CPLD_HANDSHAKE_PHASE_RETRY_MAX (3U)
/* 单阶段握手读回等待（约1ms） */
#define CPLD_HANDSHAKE_PHASE_RETRY_DELAY_US (333UL)
/* CPLD上电完成标志最大等待次数（10ms步长，共200ms） */
#define CPLD_POWERUP_WAIT_MAX (20U)
/* CPLD上电完成标志轮询间隔（10ms） */
#define CPLD_POWERUP_WAIT_DELAY_US (3333UL)
/* 握手轮询总窗口（1ms） */
#define CPLD_HANDSHAKE_WAIT_CYCLES_MAX (4U)
/* 握手轮询间隔（约10ms） */
#define CPLD_HANDSHAKE_WAIT_DELAY_US (333UL)
/* 初始化阶段CCDL心跳轮询间隔（10ms） */
#define CCDL_HEART_POLL_DELAY_US (3333UL)
/* 握手成功后，CPLD侧CCDL心跳检测最大轮询次数（10ms步长，共150ms） */
#define CPLD_CCDL_HEART_WAIT_MAX (15U)
/* 通道间握手：SCI侧CCDL心跳检测最大轮询次数（10ms步长，共150ms） */
#define INTERCH_CCDL_HEART_WAIT_MAX (15U)
/* 通道间握手：SCI降级链路单次发送等待（1ms步长，最多20ms） */
#define INTERCH_CCDL_SCI_TX_WAIT_MAX (20U)
#define INTERCH_CCDL_SCI_TX_WAIT_DELAY_US (333UL)
/* 长同步后的稳定等待次数（10ms步长，共100ms） */
#define INIT_POST_LONG_SYNC_DELAY_MAX (10U)
/* 长同步后的稳定等待间隔（10ms） */
#define INIT_POST_LONG_SYNC_DELAY_US (3333UL)

/************************************************************************************/
/*函数外部接口*/
extern void delayUs(Uint32 l_timCount_u32);  /* 微秒延时函数，实际延迟时间约为 l_timCount_u32的3倍 */

#endif /* end of include guard: COMMON_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
