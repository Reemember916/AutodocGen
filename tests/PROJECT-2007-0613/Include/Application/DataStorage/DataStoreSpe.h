
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
* 文件名称:   DataStoreSpe.h
*
* 文件日期:   REDACTED
*
*
* 程序版本:
*
**********************************************************************************
*
* 功能说明:在flash中存储特定数据，因flash是扇区操作，每个扇区置存储一个特定数据或者1组数据（含几个数据），每次数据更新存储时先擦除扇区，再进行存储
*
*
*********************************************************************************/
#ifndef DATASTOE_SPE_H_
#define DATASTOE_SPE_H_

/*******************************************************************************/

/* 特定数据存储地址定义 */
#define SPE_DATA_STUCT_NUM       (3U)     	/* 单个特定数据占据的字节 		*/

#define SPE_DATA_START_SECTOR       (0U)     	/* 特定数据存储开始扇区号		    */

/*******************************************************************************/
/* 特定数据存储索引  */
#define SPE_DATA_DINDEX_COLD_STARTUP_NUM    (0U)   /* 特定数据获取索引，上电冷启动次数,单独占1个扇区                       */
#define SPE_DATA_DINDEX_HOT_EXT_STARTUP_NUM (1U)   /* 特定数据获取索引，外狗热启动次数,单独占1个扇区                       */
#define SPE_DATA_DINDEX_HOT_IN_STARTUP_NUM  (2U)   /* 特定数据获取索引，内狗热启动次数,单独占1个扇区                       */
#define SPE_DATA_DINDEX_HARDW_VER           (3U)   /* 特定数据获取索引，硬件版本,单独占1个扇区                                   */

#define SPE_DATA_DINDEX_CH_TYPE_CODE        (4U)   /* 特定数据获取索引，下次冷启动默认主通道ID */
#define SPE_DATA_DINDEX_NMI_POWER_DOWN_NUM  (5U)   /* 特定数据获取索引，下电NMI中断次数                  */
#define SPE_DATA_DINDEX_NMI_WDOG_NUM        (6U)   /* 特定数据获取索引，看门狗NMI中断次数               */
#define SPE_DATA_DINDEX_NMI_ABNORM_NUM      (7U)   /* 特定数据获取索引，异常NMI中断次数                   */
#define SPE_DATA_DINDEX_SYS_TIME_SUM        (8U)   /* 特定数据获取索引，系统累计工作时间，单位min    */
#define SPE_DATA_DINDEX_FLASH_STORE_SECTOR  (9U)   /* 特定数据获取索引，周期记录当前写入扇区号 */

#define SPE_DATA_DINDEX_MAX                 (10U)   /*  特定数据获取个数					 */
/*******************************************************************************/
/* 特定数据状态宏定义 */

#define SPE_DATA_STATE_OK                    (0U)     /* 数据状态正常 */
#define SPE_DATA_STATE_ERR                   (1U)     /* 数据状态异常 */
#define SPE_DATA_STATE_ERR_CRC               (SPE_DATA_STATE_ERR)     /* 数据状态读取校验异常 */
#define SPE_DATA_STATE_ERR_ERASE_BUSY        (2U)     /* 数据状态写入擦除扇区超时异常(擦除扇区超时异常) */
#define SPE_DATA_STATE_ERR_WRITE_BUSY        (3U)     /* 数据状态写入超时异常(写入数据后超时异常) */
#define SPE_DATA_STATE_ERR_WRITE_READ_BACK   (4U)     /* 数据状态写入回读异常 */

#define SPE_DATA_WRITE_OVER_TIME_MS   (1500U)     /* 数据写入超时时间，单位ms */
#define SPE_BULK_ERAZE_OVER_TIME_MS   (5000U)     /* 数据写入超时时间，单位ms */


/*******************************************************************************/
/* 特定数据结构体 */
typedef struct _SpeData
{
    float  dataF_f;        /* 浮点数    */
    Uint16 dataU_u16;      /* 整形数    */
    Uint16 dataState_u16;  /* 数据状态*/

}SpeData_t;

/* ***************************************************************** */
/**
 * 供外部调用函数接口
 */
/* ***************************************************************** */
extern Uint16 SpeDataWrite(Uint16 v_index_u16,Uint16 v_wData_u16);
extern Uint16 SpeDataWriteDefer(Uint16 v_index_u16,Uint16 v_wData_u16);
extern void   SpeDataFlushPending(void);
extern Uint16 SpeDataPendingExist(void);
extern Uint16 SpeDataCheck(Uint16 v_index_u16);
extern void   SpeDataRecordInit(void);
extern Uint16 SpeDataRead(Uint16 v_index_u16);
extern void   SpeDataGet(Uint16 v_index_u16,SpeData_t *v_pSpeData_t);

#endif /* DATASTOE_SPE_H_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
