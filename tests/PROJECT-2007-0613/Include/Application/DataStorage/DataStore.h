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
* 文件名称:   DataStore.h
*
* 文件日期:   REDACTED
*
*
* 程序版本:   V1.00
*
**********************************************************************************
*
* 功能说明:
* 适用于数据存储应用场景： 故障数据存储
*
*
*********************************************************************************/

#ifndef DATASTORECBB_2_

#define DATASTORECBB_2_

/*******************************************************************************/
/* 欢迎来到周期数据存储模块用户配置专区  */

/* ******************************** */
/* 配置第1步： 配置FLASH芯片基本参数信息！！！
 *      1）FLASH基地址；
 *      2）FLASH全片地址长度；
 *      3）FLASH扇区地址长度；
 *      4）FLASH扇区数。
 *
 * */


#define FLASH_BASE_ADDR           (0UL)            /* FLASH基地址           */
#define FLASH_LEN                 (0x2000000UL)    /* FLASH最大长度       */
#define FLASH_SECTOR_LEN          (0x1000UL)       /* FLASH扇区长度       */
#define FLASH_SECTOR_NUM          (8192U)          /* FLASH中的扇区数   */

/***********************************************/
/* 配置第2步：配置数据存储区域扇区号信息！！！
 *     1）起始扇区号；
 *     2）结束扇区号。
 *
 * 友情提醒：
 * 	   1）存储扇区区域为[起始扇区号，结束扇区号]！！！
 * */

/* 数据存储扇区信息配置 */
#define FLASH_SECTOR_FIRST        (10U)        /* FLASH记录起始扇区号  */
#define FLASH_SECTOR_LAST         (8191U)      /* FLASH记录结束扇区号  */

/***********************************************/
/* 配置第3步：故障数据存储信息配置！！！
 *     1）故障存储模式，取值有两种；故障、故障+周期；
 *     2）存储故障前数据拍数；
 *     3）存储故障后数据拍数；
 *     4）正常周期存储频率。
 *
 * 配置说明：
 * 	   1）当存储模式为故障存储时，忽略4），不需设置周期存储频率。
 *
 * */

/* 配置存储信息表，此处需要用户配置！！！ */
#define STORE_CONF_TAB     {                                                       \
                              STORE_MODE_ERR_AND_NOR,   /* 故障存储模式             */        \
		                      ERR_BEFORE_DATA_LEN,      /* 存储故障前数据拍数  */        \
		                      ERR_AFTER_DATA_LEN,       /* 存储故障后数据拍数  */        \
                              STORE_NORMAL_PERIOD_MS,   /* 正常周期存储频率，单位ms */   \
                           }

/* 故障存储模式数据定义，此处不需用户配置！！！ */
#define STORE_MODE_ERR                (0U)     /* 故障触发存储                  */
#define STORE_MODE_ERR_AND_NOR        (1U)     /* 故障触发+正常周期存储*/

/* 故障前后存储数据拍数 ，此处需要用户配置！！！ */
#define ERR_BEFORE_DATA_LEN           (20UL)        /* 故障前存储数据长度 */
#define ERR_AFTER_DATA_LEN            (0UL)        /* 故障后存储数据长度 */

/* 正常周期存储频率 ，单位ms，此处需要用户配置！！！
 * NOTE：周期时间取定时器时间计数，注意定时器中断时间，若定时器中断时间为100us时，此处时间需要放大10倍才是ms时间计数*/
#define STORE_NORMAL_PERIOD_MS        (10000UL)      /* 正常周期存储频率，单位ms  */

/***********************************************/
/* 配置第4步：数据存储缓存区长度配置！！！
 *     1）临时数据缓存区长度；
 *     2）待存储计数数组长度。
 *
 * 配置说明：
 * 	   1）待存储计数数组用于标记临时缓存区中哪几拍数据需要存储；
 * 	   2）临时数据缓存区长度应大于等于故障存储前后拍数之和；
 * 	   3）待存储计数数组长度应大于临时数据缓存区长度。
 *
 * */

/* 缓存区长度设置 ，此处需要用户配置！！！ */
#define TEMP_DATA_BUFF_LEN            (ERR_BEFORE_DATA_LEN + ERR_AFTER_DATA_LEN)           /* 临时数据缓存区长度    */
#define STORE_COUNT_ARRAY_LEN         ((ERR_BEFORE_DATA_LEN + ERR_AFTER_DATA_LEN) * 2UL)   /* 待存储计数数组长度    */

/***********************************************/
/* 配置第5步：配置数据存储数据长度信息！！！↖(^ω^
 *     1）单条记录数据长度；
 *     2）单次存储数据个数；
 *     3）检查地址为空数据最大长度。防止检查地址为空时输入地址长度过长，函数消耗时间过长影响程序正常运行；
 *     4）地址检查数据长度，查找起始地址时采用该地址长度进行二分法查找地址；
 *     5）判断地址数据为空的地址长度；
 *
 * 配置说明：
 * 		1）查找扇区尾部地址为空时，以单条记录地址长度32为例，先获取扇区最后32个地址，然后取32个地址中头部2个地址数据和尾部2个地址数据，
 * 		     若4个地址数据均为空，则认为扇区尾部数据为空，尽量减小调用驱动层读取数据消耗时间。
 * 友情建议：
 * 	    1）地址检查数据长度应设置为2^n数值（如16、32、64、128、256等）；
 * 	    2）检查地址为空数据最大长度建议为单条记录数据长度。
 * */

/* 以下5个宏定义数据均需要用户配置！！！ */

#define DATA_RECORD_NUM           (160UL)         			/* 单条记录数据长度,单位:字节 */
#define STORE_WORD_NUM            (32U)                     /* 单次存储数据个数,单位:字节 */

#define ADDR_EMPTY_CHECK_LEN_MAX  (DATA_RECORD_NUM)         /* 检查地址为空数据最大长度      */
#define ADDR_CHECK_LEN            (DATA_RECORD_NUM)         /* 地址检查数据长度,单位:字节，用于查找记录首地址  */

/* 判断地址数据为空的地址长度，如单条记录长度32个地址中取头部2个和尾部2个地址进行判断    */
#define JUDGE_EMPTY_ADDR_LEN      (2U)

/***********************************************/
/* 配置第6步：配置地址有效数据位！！！
 *     1）置地址有效数据位。
 *
 * 配置说明：
 * 		1）针对不同存储器芯片特点，有些存储器有效数据位为8位，有些为16位，
 * 		      为了给用户提供更加优质的服务，为了实现代码的通用性，提供该宏定义接口供客官使用。
 * */

/* 地址有效数据位宏定义，此处不需设置哦！！！  */
#define ADDR_DATA_VALID_BIT_8         (0xFFU)           /* 地址有效数据位为8位为0xFF        */
#define ADDR_DATA_VALID_BIT_16        (0xFFFFU)         /* 地址有效数据位为16位为0xFFFF     */
#define ADDR_DATA_VALID_BIT_32        (0xFFFFFFFFUL)    /* 地址有效数据位为32位为0xFFFFFFFF */

/* 配置地址有效数据位，此处需要用户配置！！！   */
#define ADDR_DATA_VALID_BIT           (ADDR_DATA_VALID_BIT_8)

/***************************************************************/
/* 配置第7步：配置数据存储应用层接口函数！！！
 *     1）记录数据打包；
 *     2）看门狗喂；
 *     3）故障存储出发标志获取。
 *
 * 友情提醒：
 * 	   1）看门狗喂狗宏定义可以是调用多个喂狗函数，如软件喂狗、外部硬件喂狗、FPGA喂狗等；
 * */

/* 记录数据打包 ,v_pBuff_u16--打包数组指针,v_dataLen_u16--打包数组数据长度  */
#define STORE_DATA_PACK(v_pBuff_u16,v_dataLen_u16)      		  StoreDataPack(v_pBuff_u16,v_dataLen_u16)

/* 看门狗喂狗  */
#define WATCH_DOG_FEED    CycleDogFeed()

/* 故障存储出发标志获取  */
#define ERR_STORE_FLAG_GET()    ControlErrStoreFlagGet()

/***************************************************************/
/* 配置第8步：配置数据存储驱动层接口函数！！！
 *     1）记录数据读取；
 *     2）记录数据写入；
 *     3）记录扇区擦除；
 *     4）FLASH忙状态查询。
 *
 *
 * */

/* 记录数据读取 ,v_addr_u32--读取数据地址  ,v_pBuff_u16--读取数据存放数组指针  ,v_len_u16--读取数据长度 */
#define STORE_DATAREAD_DRI(v_addr_u32,v_pBuff_u16,v_len_u16)      SpiFlashDataRead(v_addr_u32,v_pBuff_u16,v_len_u16)

/* 记录数据写入,v_addr_u32--写入数据地址  ,v_pBuff_u16--写入数据数组指针  ,v_len_u16--写入数据个数  */
#define STORE_DATAWRITE_DRI(v_addr_u32,v_pBuff_u16,v_len_u16)     SpiFlashPageProgram(v_addr_u32,v_pBuff_u16,v_len_u16)

/* 记录扇区擦除 ,v_addr_u32--擦除扇区地址 */
#define STORE_SECTORERASE_DRI(v_addr_u32)    SpiFlashSectorErase(v_addr_u32)

/* FLASH忙状态查询  */
#define STORE_FLASHISBUSY_DRI()              SpiFlashIsBusy()

/* 你已完成本模块所有配置信息(1-8)！！！ */

/***************************************************************/
/* 数据存储标志定义 */
#define FLASH_SECTOR_ERASED       	(0x1234U)     /* 扇区擦除状态标识      		*/
#define FLASH_SECTOR_NO_ERASED    	(0x0000U)     /* 扇区未擦除状态标识   		*/

#define FLASH_BUSY                	(1U)     	  /* FLASH处于忙状态中  		*/
#define FLASH_NOT_BUSY            	(0U)     	  /* FLASH未处于忙状态  		*/

#define ADDR_DATA_IS_EMPTY        	(0UL)     	  /* 地址无数据 			*/
#define ADDR_DATA_IS_EMPTY_NO     	(1UL)     	  /* 地址有数据			*/

#define ERR_AFTER_DATA_NEW       	(0x1122U)     /* 故障后开始缓存标志有效	*/
#define ERR_AFTER_DATA_NONE         (0x0000U)     /* 故障后开始缓存标志无效      */

#define FIND_STATE_YES     	(0U)     	  /* 查找状态完成	    */
#define FIND_STATE_NO      	(1U)     	  /* 查找状态未完成                */

#define ERR_STORE_FLAG_OFF        	(0U)     	  /* 故障触发标志无效                  */
#define ERR_STORE_FLAG_ON         	(1U)     	  /* 故障触发标志有效                  */

#define FLASH_BUFF_UPDATE_INVALID   (0x00U)       /* 缓存区数据更新标志无效       */
#define FLASH_BUFF_UPDATE_VALID     (0x11U)       /* 缓存区数据更新标志有效       */

/***************************************************************/
/* 数据存储配置信息结构体 */
struct storeConf
{
    Uint16 errStoreMode_u16;      /* 故障存储模式            		 */
    Uint32 errDataLenBefore_u32;  /* 存储故障前数据拍数  		 */
    Uint32 errDataLenAfter_u32;   /* 存储故障后数据拍数  		 */
    Uint32 cycleStoreFreq_u32;    /* 正常周期存储频率，单位ms   */
};

/***************************************************************/
/* FLASH单拍数据数组结构体 */

typedef struct _flashDataBuff
{
	Uint16 dataBuff_u16[DATA_RECORD_NUM];     /* 单拍数据缓存区      */

}flashDataBuff_t;

/***************************************************************/
/* FLASH数据存储结构体 */

typedef struct _FlashDataRecord
{
	/*临时缓存区*/
	flashDataBuff_t tempBuff_t[TEMP_DATA_BUFF_LEN];     /* 临时数据缓存区    			*/
    Uint32 tempBuffCount_u32;				   			/* 临时缓存区更新计数 		*/
	Uint32 tempBuffCountOn_u32;                		    /* 故障触发时临时缓存区触发计数  */

	/*待存储相关信息记录*/
	Uint32 needStoreCount_u32[STORE_COUNT_ARRAY_LEN];   /* 记录需要存储数据的缓存计数值，用于指向缓存区索引 */
    Uint32 storeBuffCount_u32;                			/*待存储数据计数		*/
    Uint32 storeBuffCountLast_u32;            			/*待存储数据计数上一拍	*/
    Uint32 storeCount_u32;                    			/*已存储数据计数			*/
	Uint16 dataIndex_u16;                     			/* 存储单拍数据索引 			*/

	Uint32 errStoreCount_u32;			      			/* 故障储存触发计数  			*/
    Uint32 cycleStoreCount_u32;               			/* 周期储存触发计数 			*/

	Uint32 storeTime_u32;					  			/* 数据记录时间  			*/
    Uint32 writeAddr_u32;                     			/* 数据写入地址  			*/
    Uint16 startSector_u16;                   			/* 当前记录起始扇区号      */
    Uint16 nSectorEraseFlag_u16;              			/* 下一个扇区的擦除状态     	*/
	Uint16 errAfterFlag_u16;                  			/* 故障后数据记录标志 		*/
	Uint16 findStartSectorState_u16;          			/* 查找起始扇区状态 			*/
	Uint16 findStartAddrState_u16;          			/* 查找起始地址状态 			*/
}FlashDataRecord_t;

/***************************************************************/
/* 外部调用接口 */
extern Uint16 FlashRecordStartSector(void);
extern void   FlashDataRecordInit(void);
extern void   FlashDataStore(void);
extern void   FlashRecordDataUpdate(void);
extern void   FlashSingleStoreDataUpdate(void);
extern Uint16 FlashSectorIsErased(Uint32 v_addr_u32);
extern void   StoreDataPack(Uint16 *v_pBuff_u16,Uint16 v_len_u16);
extern void   FlashRecordStartAddr(void);
#endif

/* ***************************************************************** */
/* END OF FILE */
/* ***************************************************************** */
