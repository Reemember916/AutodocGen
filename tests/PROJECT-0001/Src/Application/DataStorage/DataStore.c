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
* 文件名称:   DataStore_2.c
*
* 文件日期:   REDACTED
*
*
* 程序版本:   V1.00
*
**********************************************************************************
* 功能说明:
* 适用于数据存储应用场景2：故障触发存储：存储关键故障前M拍和故障后N拍数据，按需进行正常周期存储。
*
* 本功能模块用以实现基于FLASH的数据存储和管理，实现数据存储的基本原则如下：
*
* 1. 在头文件中STORE_CONF_TAB配置存储模式、故障前后拍数、正常存储周期时间；
* 2. 为防止初始化中查找扇区时间过长影响正常控制周期，完成初始化进入while周期后进行查找扇区，
* 	  在控制时间空闲时分查询扇区，单次只查找一个扇区，查找扇区完成后进行数据存储；
* 3. 查找起始地址时先找记录起始扇区，然后通过二分法扇区内找地址，若扇区全满则擦除扇区取扇区首地址为记录起始地址;
* 4. 在控制周期内调用函数FlashRecordDataUpdate，实时刷新临时缓存数据，故障触发或周期触发时将标记缓存区待存储计数；
* 5. 对当前扇区进行写入操作时，提前将下一个扇区擦除;
* 6. 对于单条记录数据，分多次完成数据写入;
*
* 7. 头文件中模块调用的FLASH驱动层函数接口如下：
*       STORE_DATAREAD_DRI     ---- 记录数据读取
*       STORE_DATAWRITE_DRI    ---- 记录数据 写入
*       STORE_SECTORERASE_DRI  ---- 记录扇区擦除
*       STORE_FLASHISBUSY_DRI  ---- FLASH忙状态查询
* 8. 头文件中模块调用的应用层函数接口如下：
*       STORE_DATA_PACK        ---- 记录数据打包
*       WATCH_DOG_FEED         ---- 硬件喂狗
*
* 9. 头文件中模块提供外部调用的API函数接口如下：
*       FlashDataRecordInit 	---- FLASH数据记录初始化
*		FlashDataStore      	---- FLASH数据存储
*		FlashCycleStoreFreqAdust---- FLASH正常周期存储频率调整
*		FlashRecordDataUpdate   ---- FLASH记录数据更新
*		FlashSingleStoreDataUpdate ---- FLASH单次存储数据更新
*
*********************************************************************************/

 #include "Global.h"

/* ***************************************************************** */
/* 本地函数声明 */
Uint32 FlashAddrIsEmpty(Uint32 v_addr_u32,Uint16 v_len_u16);
Uint16 FlashSectorIsErased(Uint32 v_addr_u32);
/* ***************************************************************** */
/**
 * 【函数名】:StorePackU16
 *
 * 【功能描述】U16数据存储打包, 参数 v_value_u16
 *
 * 【输入参数说明】vp_buff_u16 ---- 缓冲区指针
                 v_offset_u16 ---- 偏移量
                 v_data_u16 ---- U16数据
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static Uint16 StorePackU16(Uint16 *vp_buff_u16, Uint16 v_offset_u16, Uint16 v_data_u16);
/* ***************************************************************** */
/**
 * 【函数名】:StorePackU32
 *
 * 【功能描述】U32数据存储打包, 参数 v_value_u32
 *
 * 【输入参数说明】vp_buff_u16 ---- 缓冲区指针
                 v_offset_u16 ---- 偏移量
                 v_data_u32 ---- U32数据
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static Uint16 StorePackU32(Uint16 *vp_buff_u16, Uint16 v_offset_u16, Uint32 v_data_u32);
/* ***************************************************************** */
/**
 * 【函数名】:StorePackF32
 *
 * 【功能描述】F32数据存储打包, 参数 v_value_f
 *
 * 【输入参数说明】vp_buff_u16 ---- 缓冲区指针
                 v_offset_u16 ---- 偏移量
                 v_data_f ---- F32数据
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static Uint16 StorePackF32(Uint16 *vp_buff_u16, Uint16 v_offset_u16, float v_data_f);
static Uint16 FlashSectorNumByAddr(Uint32 v_addr_u32);
static void FlashStartSectorPersistDefer(Uint16 v_sector_u16);
static void FlashStartSectorRestoreFast(void);

/* 本地全局变量 */
FlashDataRecord_t s_flashRecords_t;         /* Flash记录数据  */

/* 故障数据存储配置信息 */
struct storeConf s_myStoreConf_t = STORE_CONF_TAB;

/* ***************************************************************** */
/**
 *    [函数名]	FlashRecordStartSector
 *
 *    [功能描述]	FLASH记录起始扇区获取
 *       1、检索每一个扇区的尾部数据是否为0xFF(空)，若是，且该扇区不是第一个扇区，则视该扇区为起始扇区；
 *       2、若该扇区为第一个扇区，则检索最后一个扇区，若最后一个扇区尾部数据为空，则检索倒数第二个扇区，若尾部地址不为空，则起始扇区为最后一个扇区。
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	 为了防止查找扇区时间过长影响正常控制周期，在控制时间空闲时分多次查询扇区，未查找到扇区时不进行数据存储!!!
 *    [返回]		  记录起始扇区号
 */
/* ***************************************************************** */
Uint16 FlashRecordStartSector(void)
{
    Uint32 l_tAddr_u32       = FLASH_BASE_ADDR;     /* 扇区地址                                               	  */
    Uint16 l_tempCount_u16   = 0U;                  /* 临时计数                                                       */

    /* 查找扇区状态未完成时进行扇区查找  */
    if(FIND_STATE_NO == s_flashRecords_t.findStartSectorState_u16)
    {
        /* 计算本扇区尾部地址 ,为了减少查询时间，只读尾部最后一条数据地址中头部地址和尾部地址数据状态进行判断*/
        l_tAddr_u32 = FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * s_flashRecords_t.startSector_u16) + FLASH_SECTOR_LEN - ADDR_CHECK_LEN;

        /* 扇区尾部最后一条数据地址中头部地址数据不为空  */
        if( ADDR_DATA_IS_EMPTY != FlashAddrIsEmpty(l_tAddr_u32,JUDGE_EMPTY_ADDR_LEN))
        {
            /* 地址有数，临时计数加1 */
            l_tempCount_u16 = l_tempCount_u16 + 1U;
        }

        /* 扇区尾部最后一条数据地址中尾部地址数据不为空  */
        if( ADDR_DATA_IS_EMPTY != FlashAddrIsEmpty(l_tAddr_u32 + ADDR_CHECK_LEN - JUDGE_EMPTY_ADDR_LEN,JUDGE_EMPTY_ADDR_LEN))
        {
            /* 地址有数，临时计数加1 */
            l_tempCount_u16 = l_tempCount_u16 + 1U;
        }

        /* 临时计数等于0时，扇区尾部数据为空，完成查找起始扇区 */
        if( 0U == l_tempCount_u16 )
        {
            /* 若找到的扇区为起始第一个扇区，需要依据最后一个扇区是否写满的状态进行判断 */
            if( FLASH_SECTOR_FIRST == s_flashRecords_t.startSector_u16)
            {
                /* 计算最后一个扇区尾部地址 */
                l_tAddr_u32 = FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * FLASH_SECTOR_LAST) + FLASH_SECTOR_LEN - ADDR_CHECK_LEN;

                /*最后一个扇区尾部地址为空时，查看倒数第二个扇区尾部地址状态 */
                if( ADDR_DATA_IS_EMPTY == FlashAddrIsEmpty(l_tAddr_u32,ADDR_CHECK_LEN))
                {
                    /* 计算倒数第二个扇区尾部地址 */
                    l_tAddr_u32 = FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * (FLASH_SECTOR_LAST - 1U)) + FLASH_SECTOR_LEN - ADDR_CHECK_LEN;

                    /* 扇区尾部最后一条数据地址中尾部地址数据不为空  */
                    if( ADDR_DATA_IS_EMPTY != FlashAddrIsEmpty(l_tAddr_u32,ADDR_CHECK_LEN))
                    {
                        /*倒数第二扇区尾部地址不为空时，返回最后一个扇区 */
                        s_flashRecords_t.startSector_u16 = FLASH_SECTOR_LAST;
                    }
                }
            }

            /* 查找扇区状态更新为已完成 */
            s_flashRecords_t.findStartSectorState_u16 = FIND_STATE_YES;
        }
        else
        {
            /* 找到的扇区为最后一个扇区号时  */
            if( s_flashRecords_t.startSector_u16 >= FLASH_SECTOR_LAST )
            {
                /* 若所有扇区均写满，则默认使用第一个扇区,查找扇区完成 */
                s_flashRecords_t.startSector_u16 = FLASH_SECTOR_FIRST;

                /* 查找扇区状态更新为已完成 */
                s_flashRecords_t.findStartSectorState_u16 = FIND_STATE_YES;
            }
            else
            {
                /* 未完成扇区查找时扇区号加1，等待下一个周期查询下一个扇区号 */
                s_flashRecords_t.startSector_u16 = s_flashRecords_t.startSector_u16 + 1U;
            }
        }
    }

    /* 返回查询扇区号  */
    return s_flashRecords_t.startSector_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]	 FlashAddrIsEmpty
 *
 *    [功能描述]	 FLASH地址有无数据判断
 *    			   1、若输入地址起始在指定长度地址内数据均为0xFF(空)，视为地址无数，否则视为地址有数；
 *    			   2、数据长度超过单条记录长度时，按照单条记录长度进行地址有无数据判断。
 *    [输入参数说明] v_addr_u32 ---- 数据地址
 *    			  v_len_u16  ---- 数据长度
 *	  [输出参数说明] NONE
 *    [其他说明]	  查找地址长度不超过单条记录数据长度！！！
 *    [返回]		   地址无数判断结果，取值如下:
 *    	ADDR_DATA_IS_EMPTY    ---- 地址无数据
 * 	    ADDR_DATA_IS_EMPTY_NO ---- 地址有数据
 */
/* ***************************************************************** */
Uint32 FlashAddrIsEmpty(Uint32 v_addr_u32,Uint16 v_len_u16)
{
    Uint32 l_rData_u32   = ADDR_DATA_IS_EMPTY;          /* 地址状态，函数输出，初始化为地址无数 */
    Uint16 l_buff_u16[ADDR_EMPTY_CHECK_LEN_MAX]; /* 数据缓存数组 */
    Uint16 l_ii_u16    	 = 0U;  				  /* 循环计数           */
    Uint16 l_temp_u16    = 0U;  				  /* 临时数据           */
    Uint16 l_dataLen_u16 = 0U;                    /* 地址长度           */
    memset(l_buff_u16, 0, sizeof(l_buff_u16));

    /* 输入地址大于等于起始地址 且  小于结束地址时  */
    if( (v_addr_u32 >= (FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * FLASH_SECTOR_FIRST)))
     && ((v_addr_u32 + v_len_u16) <  (FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * FLASH_SECTOR_LAST) + FLASH_SECTOR_LEN)) )
    {
        /* 输入数据长度大于最大值时  */
        if( v_len_u16 > ADDR_EMPTY_CHECK_LEN_MAX )
        {
            /* 地址长度限幅为长度最大值  */
            l_dataLen_u16 = ADDR_EMPTY_CHECK_LEN_MAX;
        }
        else /* 地址长度在合理范围内  */
        {
            /* 地址长度更新为输入数据长度  */
            l_dataLen_u16 = v_len_u16;
        }

        /* 读取一条记录长度数据 */
        (void)STORE_DATAREAD_DRI(v_addr_u32,l_buff_u16,l_dataLen_u16);

        /*查询地址内是否有数*/
        for( l_ii_u16 = 0U; l_ii_u16 < l_dataLen_u16; l_ii_u16++)
        {
            /*取数据低八位*/
            l_temp_u16 = l_buff_u16[l_ii_u16] & ADDR_DATA_VALID_BIT;

            /* 地址数据不为空时 */
            if( ADDR_DATA_VALID_BIT != l_temp_u16 )
            {
                /*当数据不为0xFF认为数据不为空，跳出FOR循环 */
                break;
            }
        }

        /* 循环计数小于数据长度时  */
        if( l_ii_u16 < l_dataLen_u16 )
        {
            /*返回数据不为空*/
            l_rData_u32 = ADDR_DATA_IS_EMPTY_NO;
        }
    }

    /* 返回 地址状态  */
    return l_rData_u32;
}

/* ***************************************************************** */
/**
 *    [函数名]	DichoFindSectorStartAddr
 *
 *    [功能描述]	二分法查找扇区起始地址
 *    			1、当空扇区时返回扇区首地址
 *    			2、输入扇区号超过扇区数量时，返回记录起始扇区首地址；
 *    		    3、扇区写满时查找地址失败，擦除当前扇区，返回当前扇区首地址；
 *    [输入参数说明]	v_sectorNum_u16 ---- 查询起始地址的扇区号。
 *	  [输出参数说明]	NONE
 *    [其他说明]		为了减少读取内存数据消耗时间，通过读取头部和尾部地址数据进行判断单条记录长度地址是否为空！
 *                  为了减少扇区内二分法查找软件执行时间，不执行while一次性查找结束，拆分成多次执行，调用一次函数执行一次查找
 *    [返回]			当前扇区记录起始地址，默认起始扇区首地址
 */
/* ***************************************************************** */
Uint32 DichoFindSectorStartAddr(Uint16 v_sectorNum_u16)
{
    static Uint32 ls_shiftAddr_u32  = 0xFFFFFFFFUL;  /* 扇区偏移地址，默认数值满量程，用于第一次执行将数据进行初始化   */
    static Uint32 ls_halfLen_u32    = FLASH_SECTOR_LEN; /* 二分地址长度                   	 */
    Uint32 l_startAddr_u32  = FLASH_BASE_ADDR;  /* 记录起始地址                   	 */
    Uint16 l_tempCount_u16  = 0U;               /* 临时计数                           	 */

    /* 只执行一次，第一次执行时将偏移地址初始化为起始扇区首地址 */
    if(0xFFFFFFFFUL == ls_shiftAddr_u32)
    {
        /*扇区偏移地址，默认起始扇区首地址 */
        ls_shiftAddr_u32  = FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * FLASH_SECTOR_FIRST);

        /* 输入扇区号大于等于起始扇区号 且 小于等于结束扇区号时  */
        if( (v_sectorNum_u16 >= FLASH_SECTOR_FIRST) && (v_sectorNum_u16 <= FLASH_SECTOR_LAST))
        {
            /*偏移地址初始化为扇区首地址*/
            ls_shiftAddr_u32 = FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * v_sectorNum_u16);
        }
    }

    /* 输入扇区号大于等于起始扇区号 且 小于等于结束扇区号时  */
    if( (v_sectorNum_u16 >= FLASH_SECTOR_FIRST) && (v_sectorNum_u16 <= FLASH_SECTOR_LAST))
    {
        /*获取扇区首地址*/
        l_startAddr_u32 = FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * v_sectorNum_u16);

        /* 看门狗喂狗 */
        WATCH_DOG_FEED;

        /*更新二分地址长度*/
        ls_halfLen_u32 = (ls_halfLen_u32 >> 1UL);

        /* 偏移地址单条记录数据头部地址数据状态不为空时  */
        if( ADDR_DATA_IS_EMPTY != FlashAddrIsEmpty(ls_shiftAddr_u32,JUDGE_EMPTY_ADDR_LEN))
        {
            /* 地址有数，临时计数加1 */
            l_tempCount_u16 = l_tempCount_u16 + 1U;
        }

        /* 偏移地址单条记录数据尾部地址数据状态不为空时  */
        if( ADDR_DATA_IS_EMPTY != FlashAddrIsEmpty((ls_shiftAddr_u32 + (ADDR_CHECK_LEN - JUDGE_EMPTY_ADDR_LEN)),JUDGE_EMPTY_ADDR_LEN))
        {
            /* 地址有数，临时计数加1 */
            l_tempCount_u16 = l_tempCount_u16 + 1U;
        }

        /* 偏移地址数据为空时 */
        if( 0U == l_tempCount_u16 )
        {
            /*偏移地址内无数*/

            /*当地址内无数，首次或最后一次寻址时退出循环*/
            if( (ls_shiftAddr_u32 == l_startAddr_u32) || (ls_halfLen_u32 < ADDR_CHECK_LEN))
            {
                /* 查找状态更新为已完成 */
                s_flashRecords_t.findStartAddrState_u16 = FIND_STATE_YES;
            }
            else
            {
                /*偏移地址减去二分地址长度*/
                ls_shiftAddr_u32 = ls_shiftAddr_u32 - ls_halfLen_u32;
            }
        }
        else
        {
            /*偏移地址内有数*/

            if(ls_halfLen_u32 >= ADDR_CHECK_LEN)
            {
                /*偏移地址加上二分地址长度*/
                ls_shiftAddr_u32 = ls_shiftAddr_u32 + ls_halfLen_u32;
            }
            else
            {
                /*最后一次寻址时，退出循环*/
                ls_shiftAddr_u32 = ls_shiftAddr_u32 + ADDR_CHECK_LEN;
            }
        }

        /* 若该扇区所有字段都满了，查找扇区失败，则清除该扇区，同时返回该扇区首地址 */
        if(ls_shiftAddr_u32 >= (l_startAddr_u32 + FLASH_SECTOR_LEN))
        {
            /*返回当前扇区首地址*/
            ls_shiftAddr_u32 = l_startAddr_u32;

            /* 查找状态更新为已完成 */
            s_flashRecords_t.findStartAddrState_u16 = FIND_STATE_YES;

            /*擦除扇区 */
            STORE_SECTORERASE_DRI(ls_shiftAddr_u32);
        }
    }

    /* 返回扇区偏移地址  */
    return ls_shiftAddr_u32;
}

/* ***************************************************************** */
/**
 *    [函数名]     FlashRecordStartAddr
 *
 *    [功能描述]	 FLASH中记录起始地址获取
 *    			  查找FLASH中数据记录当前地址
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		 NONE
 */
/* ***************************************************************** */
void FlashRecordStartAddr(void)
{
    Uint16 l_sector_u16 = 0U;   /*当前写入扇区		   */

    if(FIND_STATE_NO == s_flashRecords_t.findStartSectorState_u16)
    {
        /* 获取FLASH中数据记录当前写入的扇区，20250509实测耗时最大174us*/
        l_sector_u16 = FlashRecordStartSector();
    }
    else
    {
        l_sector_u16 = s_flashRecords_t.startSector_u16;
    }

    /* 查找扇区完成后，对扇区进行起始地址查找 */
    if( FIND_STATE_YES == s_flashRecords_t.findStartSectorState_u16)
    {
        /* 扇区内地址查找未完成时 */
        if( FIND_STATE_NO == s_flashRecords_t.findStartAddrState_u16)
        {
            /*通过二分法查找当前记录地址，20250511实测耗时最大178us*/
            s_flashRecords_t.writeAddr_u32 = DichoFindSectorStartAddr(l_sector_u16);

            if(FIND_STATE_YES == s_flashRecords_t.findStartAddrState_u16)
            {
                /* 一旦完成地址恢复，异步固化当前扇区，供下次上电快速命中。 */
                FlashStartSectorPersistDefer(l_sector_u16);
            }
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	 FlashNextSectorAddrGet
 *
 *    [功能描述]	  FLASH下一扇区首地址获取
 *    [输入参数说明] v_addr_u32 ---- 地址数据
 *	  [输出参数说明] NONE
 *    [其他说明]	  	NONE
 *    [返回]		  返回下一扇区的首地址，默认返回第一个扇区首地址
 */
/* ***************************************************************** */
Uint32 FlashNextSectorAddrGet(Uint32 v_addr_u32)
{
    Uint32 l_rData_u32 = 0UL;  /* 下一扇区首地址，函数输出   */
    Uint16 l_ii_u16    = 0U;   /* 查询扇区号                              */

    /*下一个扇区首地址默认为第一个扇区首地址*/
    l_rData_u32 = FLASH_BASE_ADDR + (FLASH_SECTOR_FIRST * FLASH_SECTOR_LEN);

    /*地址大于等于起始地址时，输入地址有效*/
    if( v_addr_u32 >= l_rData_u32 )
    {
        /* 获取输入地址所在扇区号 */
        l_ii_u16 = (v_addr_u32 - FLASH_BASE_ADDR) / FLASH_SECTOR_LEN;

        /*计算下一扇区起始地址, 最后一个扇区时返回默认地址*/
        if( l_ii_u16 < FLASH_SECTOR_LAST )
        {
            l_rData_u32 = FLASH_BASE_ADDR + (l_ii_u16 * FLASH_SECTOR_LEN) + FLASH_SECTOR_LEN;
        }
    }

    /* 返回下一扇区首地址  */
    return l_rData_u32;
}

/* ***************************************************************** */
/**
 *    [函数名]	 FlashErrStoreDataCheck
 *
 *    [功能描述]	 FLASH故障存储数据检查，以如下故障数据存储算法进行存储数据更新：
 *  	1.控制周期内实时缓存系统控制数据
 *		2.故障触发标志无效时，以正常周期(如1s)存储最新一拍临时缓存区数据，周期可配置；
 *		3.故障触发标志有效时，存储故障前M拍数数据（如10拍）和故障后N拍数数据（如5拍），故障前后拍数可以设置。
 *		4.当临时缓存数据未满M拍时发生故障，只需存储故障前未满M拍数据；
 *		5.故障发生后N拍内有新故障项发生时，继续往后存储N拍数据
 *		6.前后2次故障触发间隔不满M拍时只需间隔未满M拍数据；
 *    [输入参数说明] v_errStoreFlag_u16 ---- 故障存储触发标志，取值如下：
 *    				ERR_STORE_FLAG_OFF ---- 故障触发标志无效
 *    				ERR_STORE_FLAG_ON  ---- 故障触发标志有效
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void FlashErrStoreDataCheck(Uint16 v_errStoreFlag_u16)
{
    Uint32 l_lTime_u32     					  = 0UL;    /* 系统时间计数                                  */
    Uint32 l_countbias_u32 					  = 0UL;    /* 计数差值                                          */
    static Uint32 l_s_tempBuffCountOnLast_u32 = 0UL;    /* 上一次临时缓存区存储触发计数    */

    /* 获取系统时间计数  */
    l_lTime_u32 = sysTime();

    /* 触发故障存储标志有效时  */
    if( ERR_STORE_FLAG_ON == v_errStoreFlag_u16)
    {
        /* 触发故障存储标志有效，触发故障存储 */

        /*更新上一次临时缓存区存储触发计数*/
        l_s_tempBuffCountOnLast_u32 = s_flashRecords_t.tempBuffCountOn_u32;

        /* 更新临时缓存区存储触发计数*/
        s_flashRecords_t.tempBuffCountOn_u32 = s_flashRecords_t.tempBuffCount_u32;

        /* 故障后数据记录完成时  */
        if(ERR_AFTER_DATA_NEW == s_flashRecords_t.errAfterFlag_u16)
        {
            /*故障后数据缓存进行中，更新待存储数据个数*/
            s_flashRecords_t.storeBuffCount_u32 = s_flashRecords_t.storeBuffCount_u32 + 1UL;
        }
        else  /*上一次故障前拍数和故障后拍数数据更新完成*/
        {
            /*故障后数据开始缓存标志更新*/
            s_flashRecords_t.errAfterFlag_u16 = ERR_AFTER_DATA_NEW;

            /*获取前后两次存储触发计数差值*/
            l_countbias_u32 = s_flashRecords_t.tempBuffCountOn_u32 - l_s_tempBuffCountOnLast_u32;

            /* 第一次触发故障数据存储时 */
            if( 0UL == s_flashRecords_t.errStoreCount_u32)
            {
                /* 计数差值小于存储故障前数据拍数时  */
                if( l_countbias_u32 < s_myStoreConf_t.errDataLenBefore_u32)
                {
                    /* 待存储计数增当前拍数数据 */
                    s_flashRecords_t.storeBuffCount_u32 = s_flashRecords_t.storeBuffCount_u32 + l_countbias_u32;
                }
                else /* 计数差值大于等于存储故障前数据拍数时  */
                {
                    /* 两次故障触发间隔超过指定拍数时，待存储区增加指定拍数数据 */
                    s_flashRecords_t.storeBuffCount_u32 = s_flashRecords_t.storeBuffCount_u32 + s_myStoreConf_t.errDataLenBefore_u32;
                }
            }
            else /* 再次触发故障数据存储时  */
            {
                /* 计数差值小于存储故障前后数据拍数和值时  */
                if( l_countbias_u32 < (s_myStoreConf_t.errDataLenBefore_u32 + s_myStoreConf_t.errDataLenAfter_u32))
                {
                    /*两次故障触发间隔不超过指定拍数时，待存储区增加当前拍数数据*/
                    s_flashRecords_t.storeBuffCount_u32 = s_flashRecords_t.storeBuffCount_u32 + (l_countbias_u32 - s_myStoreConf_t.errDataLenAfter_u32);
                }
                else
                {
                    /*两次故障触发间隔超过指定拍数时，待存储数据计数加上故障前存储拍数*/
                    s_flashRecords_t.storeBuffCount_u32 = s_flashRecords_t.storeBuffCount_u32 + s_myStoreConf_t.errDataLenBefore_u32;
                }
            }
        }

        /* 故障存储计数加1 */
        s_flashRecords_t.errStoreCount_u32 = s_flashRecords_t.errStoreCount_u32 + 1UL;
    }
    else /* 故障触发标志无效 */
    {
        /* 故障后拍数数据开始缓存标志有效时  */
        if(ERR_AFTER_DATA_NEW == s_flashRecords_t.errAfterFlag_u16)
        {
            /* 待存储数据计数加1 */
            s_flashRecords_t.storeBuffCount_u32 = s_flashRecords_t.storeBuffCount_u32 + 1UL;

            /* 开始缓存故障后拍数数据 */
            if(s_flashRecords_t.tempBuffCount_u32 >= (s_flashRecords_t.tempBuffCountOn_u32 + s_myStoreConf_t.errDataLenAfter_u32) )
            {
                /* 故障后数据更新完毕，标志置为无效 */
                s_flashRecords_t.errAfterFlag_u16 = ERR_AFTER_DATA_NONE;
            }
        }
        else /* 故障后拍数数据开始缓存标志无效时  */
        {
            /* 正常周期存储数据时，且周期存储时间到  */
            if( ( STORE_MODE_ERR_AND_NOR == s_myStoreConf_t.errStoreMode_u16 ) && ((l_lTime_u32 - s_flashRecords_t.storeTime_u32) >= s_myStoreConf_t.cycleStoreFreq_u32) )
            {
                /* 更新上一次临时缓存区触发计数 */
                l_s_tempBuffCountOnLast_u32 = s_flashRecords_t.tempBuffCountOn_u32;

                /* 更新临时缓存区触发计数 */
                s_flashRecords_t.tempBuffCountOn_u32 = s_flashRecords_t.tempBuffCount_u32;

                /* 更新待存储缓存区个数加1 */
                s_flashRecords_t.storeBuffCount_u32 = s_flashRecords_t.storeBuffCount_u32 + 1UL;

                /* 正常周期储存计数加1 */
                s_flashRecords_t.cycleStoreCount_u32 = s_flashRecords_t.cycleStoreCount_u32 + 1UL;
            }
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	 FlashBuffStoreCountRecord
 *
 *    [功能描述]	 FLASH缓存区待存储计数记录
 *    			故障触发后记录需要存储的缓存区更新计数值
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  	NONE
 *    [返回]		  	NONE
 */
/* ***************************************************************** */
void FlashBuffStoreCountRecord(void)
{
    Uint32 l_storeLen_u32     = 0UL;  /* 写入待存储区数据个数       */
    Uint32 l_tempCountOn_u32  = 0UL;  /* 临时缓存区触发计数           */
    Uint32 l_storeCountOn_u32 = 0UL;  /* 待存储触发计数                   */
    Uint32 l_sIndex_u32       = 0UL;  /* 待存储计数索引                   */
    Uint32 l_ii_u32           = 0UL;  /* 循环计数                              */

    /* 待存储数据计数刷新时，记录需要存储的缓存区更新计数值*/
    if( s_flashRecords_t.storeBuffCount_u32 > s_flashRecords_t.storeBuffCountLast_u32 )
    {
        /* 更新数据写入时间 */
        s_flashRecords_t.storeTime_u32 = sysTime();

        /* 获取本次需要记录的数据个数 */
        l_storeLen_u32 = s_flashRecords_t.storeBuffCount_u32 - s_flashRecords_t.storeBuffCountLast_u32;

        l_storeCountOn_u32 = s_flashRecords_t.storeBuffCountLast_u32;                   /* 获取待存储触发计数         */
        l_tempCountOn_u32  = s_flashRecords_t.tempBuffCount_u32 - l_storeLen_u32 + 1UL; /* 获取临时缓存区触发计数  */

        /* 记录需要存储的缓存计数值 */
        for( l_ii_u32 = 0UL; l_ii_u32 < l_storeLen_u32;l_ii_u32++)
        {
            /* 获取待存储计数索引 */
            l_sIndex_u32 = (l_storeCountOn_u32 + l_ii_u32) % STORE_COUNT_ARRAY_LEN;

            /* 记录需要存储的缓存区更新计数值 */
            s_flashRecords_t.needStoreCount_u32[l_sIndex_u32] = l_tempCountOn_u32 + l_ii_u32;
        }

        /* 写入完成后更新当前待存储数据计数 */
        s_flashRecords_t.storeBuffCountLast_u32 = s_flashRecords_t.storeBuffCount_u32;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	 FlashBuffDataUpdateCheck
 *
 *    [功能描述]	 FLASH缓存区数据更新检查
 *    			当缓存区中待存储数据会被刷新覆盖时，停止数据实时刷新
 *    			确保需要存储的数据不被刷新覆盖
 *
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  缓存区数据更新标志，数值如下：
 *    			FLASH_BUFF_UPDATE_VALID   ---- 缓存区数据更新标志有效
 *    			FLASH_BUFF_UPDATE_INVALID ---- 缓存区数据更新标志无效
 */
/* ***************************************************************** */
Uint16 FlashBuffDataUpdateCheck(void)
{
    Uint32 l_sIndex_u32 = 0UL;  /* 待存储计数索引       */
    Uint32 l_tCount_u32 = 0UL;  /* 缓存区更新计数值   */
    Uint16 l_rData_u16  = FLASH_BUFF_UPDATE_VALID;  /* 数据更新标志,函数输出，默认有效 */

    /* 当前缓存区有未存储完的数据时 */
    if(s_flashRecords_t.storeBuffCount_u32 > s_flashRecords_t.storeCount_u32)
    {
        /* 当前正在存储数据 */

        /* 获取缓存区中正在存储的更新计数值 */
        l_sIndex_u32 = s_flashRecords_t.storeCount_u32 % STORE_COUNT_ARRAY_LEN;
        l_tCount_u32 = s_flashRecords_t.needStoreCount_u32[l_sIndex_u32];

        /* 缓存区中待存储数据被刷新覆盖时，不进行数据更新  */
        if((s_flashRecords_t.tempBuffCount_u32 + 1UL - l_tCount_u32) >= TEMP_DATA_BUFF_LEN)
        {
            /* 数据更新标志无效 */
            l_rData_u16  = FLASH_BUFF_UPDATE_INVALID;
        }
    }

    /* 返回数据更新标志  */
    return l_rData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名] StorePackU16
 *
 *    [功能描述] 向存储记录缓冲按低字节在前的顺序写入Uint16
 *    [返回]     下一个写入偏移
 */
/* ***************************************************************** */
static Uint16 StorePackU16(Uint16 *vp_buff_u16, Uint16 v_offset_u16, Uint16 v_data_u16)
{
    vp_buff_u16[v_offset_u16] = (Uint16)(v_data_u16 & 0x00FFU);
    vp_buff_u16[v_offset_u16 + 1U] = (Uint16)((v_data_u16 >> 8U) & 0x00FFU);

    return (Uint16)(v_offset_u16 + 2U);
}

/* ***************************************************************** */
/**
 *    [函数名] StorePackU32
 *
 *    [功能描述] 向存储记录缓冲按低字节在前的顺序写入Uint32
 *    [返回]     下一个写入偏移
 */
/* ***************************************************************** */
static Uint16 StorePackU32(Uint16 *vp_buff_u16, Uint16 v_offset_u16, Uint32 v_data_u32)
{
    vp_buff_u16[v_offset_u16] = (Uint16)(v_data_u32 & 0x000000FFUL);
    vp_buff_u16[v_offset_u16 + 1U] = (Uint16)((v_data_u32 >> 8U) & 0x000000FFUL);
    vp_buff_u16[v_offset_u16 + 2U] = (Uint16)((v_data_u32 >> 16U) & 0x000000FFUL);
    vp_buff_u16[v_offset_u16 + 3U] = (Uint16)((v_data_u32 >> 24U) & 0x000000FFUL);

    return (Uint16)(v_offset_u16 + 4U);
}

/* ***************************************************************** */
/**
 *    [函数名] StorePackF32
 *
 *    [功能描述] 将float按其32位原始内存映射写入存储记录缓冲
 *    [返回]     下一个写入偏移
 */
/* ***************************************************************** */
static Uint16 StorePackF32(Uint16 *vp_buff_u16, Uint16 v_offset_u16, float v_data_f)
{
    union
    {
        float dataF_f;
        Uint32 dataU_u32;
    }l_conv_un32;

    l_conv_un32.dataF_f = v_data_f;

    return StorePackU32(vp_buff_u16, v_offset_u16, l_conv_un32.dataU_u32);
}

/* ***************************************************************** */
/**
 *    [函数名]  FlashSectorNumByAddr
 *
 *    [功能描述] 根据记录地址计算所在扇区号
 *    [返回]    合法扇区号；非法地址时返回起始扇区号
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:FlashSectorNumByAddr
 *
 * 【功能描述】按地址查找Flash扇区号, 参数 v_addr_u32, 返回扇区号
 *
 * 【输入参数说明】v_addr_u32 ---- Flash地址
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】扇区号
 */
/* ***************************************************************** */
static Uint16 FlashSectorNumByAddr(Uint32 v_addr_u32)
{
    Uint16 l_sector_u16 = FLASH_SECTOR_FIRST;

    if((v_addr_u32 >= (FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * FLASH_SECTOR_FIRST))) &&
       (v_addr_u32 < (FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * FLASH_SECTOR_LAST) + FLASH_SECTOR_LEN)))
    {
        l_sector_u16 = (Uint16)((v_addr_u32 - FLASH_BASE_ADDR) / FLASH_SECTOR_LEN);
    }

    return l_sector_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]  FlashStartSectorPersistDefer
 *
 *    [功能描述] 异步固化当前周期记录写扇区号
 *    [返回]    NONE
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:FlashStartSectorPersistDefer
 *
 * 【功能描述】起始扇区持久化延后
 *
 * 【输入参数说明】v_sector_u16 ---- 扇区号
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static void FlashStartSectorPersistDefer(Uint16 v_sector_u16)
{
    SpeData_t l_storeSector_t = {0};

    if((v_sector_u16 < FLASH_SECTOR_FIRST) || (v_sector_u16 > FLASH_SECTOR_LAST))
    {
        return;
    }

    SpeDataGet(SPE_DATA_DINDEX_FLASH_STORE_SECTOR, &l_storeSector_t);

    if((SPE_DATA_DINDEX_FLASH_STORE_SECTOR < SPE_DATA_DINDEX_MAX) &&
       ((SPE_DATA_STATE_OK != l_storeSector_t.dataState_u16) ||
        (l_storeSector_t.dataU_u16 != v_sector_u16)))
    {
        (void)SpeDataWriteDefer(SPE_DATA_DINDEX_FLASH_STORE_SECTOR, v_sector_u16);
    }
}

/* ***************************************************************** */
/**
 *    [函数名]  FlashStartSectorRestoreFast
 *
 *    [功能描述] 从特定数据恢复上次记录扇区，命中后跳过全盘逐扇区扫描
 *    [返回]    NONE
 */
/* ***************************************************************** */
/* ***************************************************************** */
/**
 * 【函数名】:FlashStartSectorRestoreFast
 *
 * 【功能描述】起始扇区快速恢复, 上电时快速从Flash读取起始扇区
 *
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】NONE
 */
/* ***************************************************************** */
static void FlashStartSectorRestoreFast(void)
{
    SpeData_t l_storeSector_t = {0};

    SpeDataGet(SPE_DATA_DINDEX_FLASH_STORE_SECTOR, &l_storeSector_t);

    if((SPE_DATA_STATE_OK == l_storeSector_t.dataState_u16) &&
       (l_storeSector_t.dataU_u16 >= FLASH_SECTOR_FIRST) &&
       (l_storeSector_t.dataU_u16 <= FLASH_SECTOR_LAST))
    {
        s_flashRecords_t.startSector_u16 = l_storeSector_t.dataU_u16;
        s_flashRecords_t.findStartSectorState_u16 = FIND_STATE_YES;
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	 StoreDataPack
 *
 *    [功能描述]	 存储数据打包
 *    [输入参数说明] v_pBuff_u16 ---- 打包数组指针
 *    			  v_len_u16   ---- 打包数组长度
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void StoreDataPack(Uint16 *v_pBuff_u16,Uint16 v_len_u16)
{
    Uint16 l_ii_u16 = 0U;
    Uint16 l_offset_u16 = 0U;
    Uint16 l_flag_u16 = 0U;
    Uint16 l_sourceState_u16 = 0U;
    Uint16 l_ccdlSummary_u16 = 0U;
    Uint32 l_sum_u32 = 0UL;
    Uint32 l_lTime_u32 = 0UL;
    Uint32 l_ioData_u32 = 0UL;
    const ConData_t *lc_p_conData_t = NULL;
    const RIU429SendData_t *lc_p_riuSendData_t = NULL;
    ControlFaultEval_t l_faultEval_t;
    RedunData_t l_redunData_t;
    RedunData_t l_riuState_t;
    RedunData_t l_kzzzLeftState_t;
    RedunData_t l_kzzzRightState_t;
    RedunData_t l_ccdlState_t;
    /* 整体流程：
     * 1. 参数校验后清零目标缓存，获取控制数据、RIU 发送数据、故障评估、余度池快照；
     * 2. 依次填充周期记录帧：帧头(0x90EB)/版本/标志/时间/状态摘要/BIT结果/IO摘要；
     * 3. 从余度池提取 RIU 关键快照（心跳/指令/阀位/泵/油量等）并打包；
     * 4. 从余度池提取 KZZZ 左右吊舱快照（请求/寿命/流量/状态/故障等）并打包；
     * 5. 生成 CCDL 来源摘要并计算末字节补码校验，使整帧累加结果为0。
     */
    if ((NULL != v_pBuff_u16) && (v_len_u16 >= DATA_RECORD_NUM))
    {
        for (l_ii_u16 = 0U; l_ii_u16 < v_len_u16; l_ii_u16++)
        {
            v_pBuff_u16[l_ii_u16] = 0U;
        }

        lc_p_conData_t = ConDataGet();
        lc_p_riuSendData_t = RIU429SendDataGet();
        l_faultEval_t = ControlFaultEvalGet();
        l_riuState_t = RedunDataGet(REDUN_INDEX_RIU_HEART);
        l_kzzzLeftState_t = RedunDataGet(REDUN_INDEX_KZZZ_L_CURR_TIME_REQ);
        l_kzzzRightState_t = RedunDataGet(REDUN_INDEX_KZZZ_R_CURR_TIME_REQ);
        l_ccdlState_t = RedunDataGet(REDUN_INDEX_CCDL_SYSST);
        l_lTime_u32 = sysTime();

        if (VALID == l_faultEval_t.hasFault_u16)
        {
            l_flag_u16 |= (0x01U << 0U);
        }
        if (VALID == l_faultEval_t.commFault_u16)
        {
            l_flag_u16 |= (0x01U << 1U);
        }
        if (VALID == l_faultEval_t.measureFault_u16)
        {
            l_flag_u16 |= (0x01U << 2U);
        }
        if (VALID == l_faultEval_t.imbalanceFault_u16)
        {
            l_flag_u16 |= (0x01U << 3U);
        }
        if (RECEIVE_RIU_REASON_NONE != lc_p_riuSendData_t->checkState_u16)
        {
            l_flag_u16 |= (0x01U << 4U);
        }
        if (CON_OUT_STATE_VALID == lc_p_conData_t->ConOutData_t.conOutState_u16)
        {
            l_flag_u16 |= (0x01U << 5U);
        }
        if (CHV_VALID == lc_p_conData_t->ConOutData_t.localChvPermit_u16)
        {
            l_flag_u16 |= (0x01U << 6U);
        }

        /* 来源摘要字节（l_sourceState_u16）布局：
         * bit0~1: RIU有效源数据状态
         * bit2~3: KZZZ左链路数据状态
         * bit4~5: KZZZ右链路数据状态
         * bit6   : 本通道ID摘要（1=通道2，0=通道1）
         * bit7   : 保留
         *
         * 注意这里显式拆左右KZZZ链路，不再折叠成“综合KZZZ来源”，
         * 便于离线追溯单侧链路异常。 */
        l_sourceState_u16 = (l_riuState_t.dataState_u16 & 0x03U);
        /* 来源摘要现在分别记录左吊舱和右吊舱链路状态，不再把两侧折叠成一份统一KZZZ来源。 */
        l_sourceState_u16 |= (Uint16)((l_kzzzLeftState_t.dataState_u16 & 0x03U) << 2U);
        l_sourceState_u16 |= (Uint16)((l_kzzzRightState_t.dataState_u16 & 0x03U) << 4U);
        if (SYS_CH_ID_2 == lc_p_conData_t->myChID_u16)
        {
            l_sourceState_u16 |= (0x01U << 6U);
        }

        for (l_ii_u16 = 0U; l_ii_u16 < IO_DATA_NUM; l_ii_u16++)
        {
            if (GPIO_SET == IoDataGet(l_ii_u16))
            {
                l_ioData_u32 |= (0x1UL << l_ii_u16);
            }
        }

        /* 周期记录帧（二进制）布局约定：
         * [帧头/版本/标志/时间] + [状态摘要] + [BIT结果] + [IO摘要]
         * + [RIU关键快照] + [KZZZ左右关键快照] + [CCDL摘要] + [末尾8bit补码校验]。
         *
         * 该顺序是维护口/离线工具的既有解析口径，字段顺序与压缩位定义都依赖历史兼容；
         * 补注释不代表可随意重排。若调整任一字段顺序，需同步维护端解析协议。 */
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, 0x90EBU);
        v_pBuff_u16[l_offset_u16++] = 0x02U;
        v_pBuff_u16[l_offset_u16++] = l_flag_u16 & 0x00FFU;
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_lTime_u32);
        v_pBuff_u16[l_offset_u16++] = (lc_p_conData_t->sysState_u16 & 0x0FU) | ((lc_p_conData_t->workMode_u16 & 0x0FU) << 4U);
        v_pBuff_u16[l_offset_u16++] = (lc_p_conData_t->conFunc_u16 & 0x3FU) | ((lc_p_conData_t->conMode_u16 & 0x03U) << 6U);
        v_pBuff_u16[l_offset_u16++] = (lc_p_conData_t->ChType_u16 & 0x0FU) | ((lc_p_conData_t->ChTypeCode_u16 & 0x0FU) << 4U);
        v_pBuff_u16[l_offset_u16++] = l_sourceState_u16 & 0x00FFU;
        v_pBuff_u16[l_offset_u16++] = lc_p_conData_t->airOilEndState_u16 & 0x00FFU;
        v_pBuff_u16[l_offset_u16++] = l_faultEval_t.reason_u16 & 0x00FFU;
        v_pBuff_u16[l_offset_u16++] = lc_p_riuSendData_t->checkState_u16 & 0x00FFU;
        v_pBuff_u16[l_offset_u16++] = PuBITDataGet() & 0x00FFU;

        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, IFBITResultGet(IFBIT_DINDEX_RESULTS_BIT32_1));
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, MBITResultGet(MBIT_DINDEX_RESULTS_BIT32_1));
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_ioData_u32);

        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_HEART);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FAULTINFO);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_REFUEL_CMD);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_RCV);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_VALVE1);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_VALVE2);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FUELPUMP);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_HL_SENSOR);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_PRV);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_LP_PFV);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_RP_PFV);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FQ_TANK0);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FQ_TANK1);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FQ_TANK2);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FQ_TANK3);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_FQ_TANK4);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_TOTAL_FUEL);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_AIR_SPEED);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_LP_BRIGHT);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_RP_BRIGHT);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_RIU_CTRL_CMD);
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataU_u32);

        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_L_CURR_TIME_REQ);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_L_REMAIN_LIFE);
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_L_RG_LEN);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_L_STATE);
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_L_COMPONENT);
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_L_FAULT_INFO);
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_L_FUEL_PRESS);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);

        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_R_CURR_TIME_REQ);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_R_REMAIN_LIFE);
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_R_RG_LEN);
        l_offset_u16 = StorePackF32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataF_f);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_R_STATE);
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_R_COMPONENT);
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_R_FAULT_INFO);
        l_offset_u16 = StorePackU32(v_pBuff_u16, l_offset_u16, l_redunData_t.dataU_u32);
        l_redunData_t = RedunDataGet(REDUN_INDEX_KZZZ_R_FUEL_PRESS);
        l_offset_u16 = StorePackU16(v_pBuff_u16, l_offset_u16, (Uint16)l_redunData_t.dataU_u32);

        l_ccdlSummary_u16 = (Uint16)(l_ccdlState_t.dataU_u32 & 0x07U);
        l_redunData_t = RedunDataGet(REDUN_INDEX_CCDL_CHTYPE);
        l_ccdlSummary_u16 |= (Uint16)((l_redunData_t.dataU_u32 & 0x03U) << 3U);
        l_ccdlSummary_u16 |= (Uint16)((l_ccdlState_t.dataState_u16 & 0x03U) << 5U);
        v_pBuff_u16[l_offset_u16++] = l_ccdlSummary_u16 & 0x00FFU;

        /* 末字节校验：对前 (len-1) 字节求和后取二补码低8位，
         * 使整帧按8bit累加结果为0，便于维护口快速验帧。 */
        for (l_ii_u16 = 0U; l_ii_u16 < (v_len_u16 - 1U); l_ii_u16++)
        {
            l_sum_u32 = l_sum_u32 + v_pBuff_u16[l_ii_u16];
        }

        v_pBuff_u16[v_len_u16 - 1U] = (Uint16)((~l_sum_u32 + 1UL) & 0xFFUL);
    }
}
/* ***************************************************************** */
/**
 *    [函数名]	 FlashRecordDataUpdate
 *
 *    [功能描述]	 FLASH记录数据更新
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void FlashRecordDataUpdate(void)
{
    Uint32 l_tIndex_u32     = 0UL;                      /* 临时缓存数据索引     */
    Uint16 l_updateFlag_u16 = FLASH_BUFF_UPDATE_VALID;  /* 缓存区数据刷新标志 */
    Uint16 l_errStoreFlag_u16 = ERR_STORE_FLAG_OFF;     /* 故障存储触发标志，默认无效          */
    const ConData_t *lc_p_conData_t = NULL; /* 系统控制数据指针      */

    /* 获取系统控制数据 */
    lc_p_conData_t = ConDataGet();

    /* 系统状态不是地面维护和下电停机时进行存储数据更新 */
    if( SYS_STATE_4POWERDOWN != lc_p_conData_t->sysState_u16)
    {
        /* 获取故障存储触发标志 */
        l_errStoreFlag_u16 = ERR_STORE_FLAG_GET();

        /* 获取缓存区数据刷新标志 */
        l_updateFlag_u16 = FlashBuffDataUpdateCheck();

        /* 更新标志无效时，实时刷新数据 */
        if(FLASH_BUFF_UPDATE_VALID == l_updateFlag_u16)
        {
            /* 获取临时缓存数组索引 */
            l_tIndex_u32 = s_flashRecords_t.tempBuffCount_u32 % TEMP_DATA_BUFF_LEN;

            /* 更新当前临时缓存区周期索引数据 */
            STORE_DATA_PACK(s_flashRecords_t.tempBuff_t[l_tIndex_u32].dataBuff_u16,DATA_RECORD_NUM);

            /* 临时数据缓存区计数更新  */
            s_flashRecords_t.tempBuffCount_u32 = s_flashRecords_t.tempBuffCount_u32 + 1UL;

            /* 故障存储数据检查 */
            FlashErrStoreDataCheck(l_errStoreFlag_u16);

            /* 记录需要存储的缓存区更新计数值 */
            FlashBuffStoreCountRecord();
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	 FlashDataStore
 *
 *    [功能描述]	 FLASH数据存储
 * 	    记录数据到FLASH中，具体操作如下：
 *    1. 若当前无需要保存的数据，则重新获取数据；
 *    2. 若当前存在需要保存的数据，则保存该数据；
 *    3. 若当前写入扇区的下一扇区状态为未擦除，则擦除下一扇区;
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void FlashDataStore(void)
{
    Uint32 l_nextSectorAddr_u32 = 0UL;  /* 下一扇区地址                       */
    Uint32 l_sIndex_u32 = 0UL;          /* 待存储缓存计数值数组索引 */
    Uint32 l_tIndex_u32 = 0UL;          /* 临时缓存数据索引                */
    Uint16 l_currSector_u16 = 0U;      /* 当前写扇区号                    */

    /* 未查找起始地址时查找地址，此时不进行数据存储  */
    if( FIND_STATE_NO == s_flashRecords_t.findStartAddrState_u16)
    {
        /* FLASH中记录起始地址查找，20250511实测耗时最大356us */
        FlashRecordStartAddr();
    }
    else /* 已经完成查找扇区，启动数据存储 */
    {
        /* FLASH状态处于不忙时进行数据存储 */
        if( FLASH_NOT_BUSY == STORE_FLASHISBUSY_DRI())
        {
            /* 检查当前写入扇区的下一扇区状态是否为未擦除状态 */
            if( FLASH_SECTOR_NO_ERASED == s_flashRecords_t.nSectorEraseFlag_u16 )
            {
                /* 获取下一扇区地址 */
                l_nextSectorAddr_u32 = FlashNextSectorAddrGet(s_flashRecords_t.writeAddr_u32);

                /*FLASH扇区擦除状态获取*/
                if( FLASH_SECTOR_ERASED == FlashSectorIsErased(l_nextSectorAddr_u32))
                {
                    s_flashRecords_t.nSectorEraseFlag_u16 = FLASH_SECTOR_ERASED;
                }
                else
                {
                    /* 替换为SPI接口的扇区擦除函数 */
                    STORE_SECTORERASE_DRI(l_nextSectorAddr_u32);
                }
            }

            /* 若当前写入扇区的下一扇区为擦除状态，且当前存在待写入的数据 */
            else if( s_flashRecords_t.storeBuffCount_u32 > s_flashRecords_t.storeCount_u32)
            {
                /*获取缓存区需要存储的数据索引*/
                l_sIndex_u32 =  s_flashRecords_t.storeCount_u32 % STORE_COUNT_ARRAY_LEN;
                l_tIndex_u32 = (s_flashRecords_t.needStoreCount_u32[l_sIndex_u32] - 1UL) % TEMP_DATA_BUFF_LEN;

                /* 将数据写入FLASH */
                STORE_DATAWRITE_DRI(s_flashRecords_t.writeAddr_u32,(s_flashRecords_t.tempBuff_t[l_tIndex_u32].dataBuff_u16 + s_flashRecords_t.dataIndex_u16),STORE_WORD_NUM);

                /* 更新写入地址等信息 */
                s_flashRecords_t.writeAddr_u32 = s_flashRecords_t.writeAddr_u32 + STORE_WORD_NUM;

                /* 更新单拍数据记录索引*/
                s_flashRecords_t.dataIndex_u16 = s_flashRecords_t.dataIndex_u16 + STORE_WORD_NUM;

                /* 本条数据记录是否已经完整写完 */
                if(s_flashRecords_t.dataIndex_u16 >= DATA_RECORD_NUM)
                {
                    /*单拍数据记录索引清零*/
                    s_flashRecords_t.dataIndex_u16 = 0U;

                    /* 对写入地址进行整除处理 */
                    if( 0UL != (s_flashRecords_t.writeAddr_u32 % DATA_RECORD_NUM) )
                    {
                        s_flashRecords_t.writeAddr_u32 = (s_flashRecords_t.writeAddr_u32 - (s_flashRecords_t.writeAddr_u32 % DATA_RECORD_NUM)) + DATA_RECORD_NUM;
                    }

                    /*已存储数据计数更新*/
                    s_flashRecords_t.storeCount_u32 = s_flashRecords_t.storeCount_u32 + 1UL;
                }

                /* 检索是否写到新的扇区 */
                if( 0UL == (s_flashRecords_t.writeAddr_u32 % FLASH_SECTOR_LEN) )
                {
                    l_currSector_u16 = FlashSectorNumByAddr(s_flashRecords_t.writeAddr_u32);

                    /* 当前记录指针推进到新扇区后，异步保存新扇区号。 */
                    s_flashRecords_t.startSector_u16 = l_currSector_u16;
                    FlashStartSectorPersistDefer(l_currSector_u16);

                    /* 更新新扇区擦除状态 */
                    s_flashRecords_t.nSectorEraseFlag_u16 = FLASH_SECTOR_NO_ERASED;

                    /* FLASH写地址回绕 */
                    if( s_flashRecords_t.writeAddr_u32 >= (FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * FLASH_SECTOR_LAST) + FLASH_SECTOR_LEN))
                    {
                        s_flashRecords_t.writeAddr_u32 = FLASH_BASE_ADDR + (FLASH_SECTOR_LEN * FLASH_SECTOR_FIRST);
                        s_flashRecords_t.startSector_u16 = FLASH_SECTOR_FIRST;
                        FlashStartSectorPersistDefer(FLASH_SECTOR_FIRST);
                    }
                }
            }
            else
            {
                ;/* no deal with */
            }
        }
    }
}

/* ***************************************************************** */
/**
 *    [函数名]	 FlashSectorIsErased
 *
 *    [功能描述]	 FLASH扇区擦除状态获取
 *    			通过判断扇区头部、中部、尾部指定长度地址数据是否为空来判断扇区擦除状态。
 *    [输入参数说明] v_addr_u32 ---- FLASH中扇区起始地址
 *	  [输出参数说明] NONE
 *    [其他说明]	  	NONE
 *    [返回]		  扇区状态，取值如下：
 *          FLASH_SECTOR_ERASED ---- 该扇区为擦除状态
 *          FLASH_SECTOR_NO_ERASED ---- 该扇区为未擦除状态
 */
/* ***************************************************************** */
Uint16 FlashSectorIsErased(Uint32 v_addr_u32)
{
    Uint16 l_rData_u16      = FLASH_SECTOR_ERASED;  /* 扇区擦除状态，函数输出，默认为已擦除 */
    Uint16 l_tempCount_u16  = 0U;                   /* 临时计数  */

    /* 输入地址小于等于最后一个扇区起始地址时 */
    if(v_addr_u32 <= (FLASH_SECTOR_LAST * FLASH_SECTOR_LEN))
    {
        /* 扇区头部地址数据状态不为空时  */
        if( ADDR_DATA_IS_EMPTY != FlashAddrIsEmpty(v_addr_u32,JUDGE_EMPTY_ADDR_LEN))
        {
            /* 地址有数，临时计数加1 */
            l_tempCount_u16 = l_tempCount_u16 + 1U;
        }

        /* 扇区中部地址数据状态不为空时  */
        if( ADDR_DATA_IS_EMPTY != FlashAddrIsEmpty(v_addr_u32 + (FLASH_SECTOR_LEN / 2U),JUDGE_EMPTY_ADDR_LEN))
        {
            /* 地址有数，临时计数加1 */
            l_tempCount_u16 = l_tempCount_u16 + 1U;
        }

        /* 扇区尾部地址数据状态不为空时  */
        if( ADDR_DATA_IS_EMPTY != FlashAddrIsEmpty(v_addr_u32 + FLASH_SECTOR_LEN - JUDGE_EMPTY_ADDR_LEN,JUDGE_EMPTY_ADDR_LEN))
        {
            /* 地址有数，临时计数加1 */
            l_tempCount_u16 = l_tempCount_u16 + 1U;
        }

        /* 计数大于0时，扇区内有数 */
        if(l_tempCount_u16 > 0U)
        {
            /* 扇区地址有数，返回扇区未擦除  */
            l_rData_u16 = FLASH_SECTOR_NO_ERASED;
        }
    }

    /* 返回扇区擦除状态  */
    return l_rData_u16;
}

/* ***************************************************************** */
/**
 *    [函数名]	 FlashDataRecordInit
 *
 *    [功能描述]	 FLASH数据记录初始化
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  NONE
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void FlashDataRecordInit(void)
{
    Uint16 l_ii_u16 = 0U;  /* 循环计数ii */
    Uint16 l_jj_u16 = 0U;  /* 循环计数jj */

    /* 临时缓存区数据清零  */
    for(l_jj_u16 = 0U;l_jj_u16 < (TEMP_DATA_BUFF_LEN); l_jj_u16++)
    {
        for( l_ii_u16 = 0U; l_ii_u16 < DATA_RECORD_NUM; l_ii_u16++)
        {
            s_flashRecords_t.tempBuff_t[l_jj_u16].dataBuff_u16[l_ii_u16] = 0U;
        }
    }

    /* 待存储计数数组数据清零  */
    for(l_jj_u16 = 0U;l_jj_u16 < (STORE_COUNT_ARRAY_LEN); l_jj_u16++)
    {
        s_flashRecords_t.needStoreCount_u32[l_jj_u16] = 0U;
    }

    /* 相关计数清零  */
    s_flashRecords_t.tempBuffCount_u32         = 0UL;
    s_flashRecords_t.tempBuffCountOn_u32       = 0UL;
    s_flashRecords_t.storeBuffCount_u32        = 0UL;
    s_flashRecords_t.storeBuffCountLast_u32    = 0UL;
    s_flashRecords_t.storeCount_u32            = 0UL;
    s_flashRecords_t.dataIndex_u16             = 0U;
    s_flashRecords_t.errStoreCount_u32         = 0UL;
    s_flashRecords_t.cycleStoreCount_u32       = 0UL;

    /* 相关数据状态初始化 */
    s_flashRecords_t.errAfterFlag_u16         = ERR_AFTER_DATA_NONE;
    s_flashRecords_t.storeTime_u32            = sysTime();
    s_flashRecords_t.startSector_u16          = FLASH_SECTOR_FIRST;
    s_flashRecords_t.nSectorEraseFlag_u16     = FLASH_SECTOR_NO_ERASED;
    s_flashRecords_t.findStartSectorState_u16 = FIND_STATE_NO;
    s_flashRecords_t.findStartAddrState_u16   = FIND_STATE_NO;
    s_flashRecords_t.writeAddr_u32            = 0UL;

    /* 上电优先恢复上次写扇区，命中则只需在该扇区内继续找地址。 */
    FlashStartSectorRestoreFast();
}

/* ***************************************************************** */
/**
 *    [函数名]	 FlashSingleStoreDataUpdate
 *
 *    [功能描述]	 FLASH单次存储数据更新
 *    			更新一拍存储数据，进入主循环周期后进行数据存储。
 *
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	  主要应用于上电BIT故障或者NMI掉电中断等事件时，需更新一拍存储数据。
 *    [返回]		  NONE
 */
/* ***************************************************************** */
void FlashSingleStoreDataUpdate(void)
{
    Uint32 l_tIndex_u32 = 0UL; /* 缓存区数据索引     */

    /* 获取缓存区数据索引 */
    l_tIndex_u32 = s_flashRecords_t.tempBuffCount_u32 % TEMP_DATA_BUFF_LEN;

    /* 记录数据打包 */
    STORE_DATA_PACK(s_flashRecords_t.tempBuff_t[l_tIndex_u32].dataBuff_u16,DATA_RECORD_NUM);

    /* 缓存区计数加1 */
    s_flashRecords_t.tempBuffCount_u32 = s_flashRecords_t.tempBuffCount_u32 + 1UL;

    /* 待存储计数加1 */
    s_flashRecords_t.storeBuffCount_u32 = s_flashRecords_t.storeBuffCount_u32 + 1UL;

    /* 记录需要存储的缓存区更新计数值 */
    FlashBuffStoreCountRecord();
}

/* ***************************************************************** */
/* END OF FILE */
/* ***************************************************************** */
