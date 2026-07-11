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
 * 文件名称:    SM25QH256M_SpiFlash
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V1.00
 *
 **********************************************************************************
 *
 * 功能说明:   本模块为SPI FLASH芯片(SM25QH256M)驱动接口程序
 *
 * 该功能模块不支持：
 * 1. FLASH芯片快速读取数据
 * 2. FLASH芯片快速写入数据
 * 3. FLASH芯片电子签名读取
 * 4. FLASH芯片功能寄存器值读取
 * 5. FLASH芯片功能寄存器值写入
 * 6. FLASH芯片总线操作（QPI）模式
 * 7. FLASH芯片低功耗（DPD）模式
 *
 * 该功能模块支持：
 * 1.FLASH芯片扇区擦除
 * 2.FLASH芯片全片擦除
 * 3.FLASH芯片ID读取
 * 4.FLASH芯片数据写入
 * 5.FLASH芯片数据读取
 * 6.FLASH芯片状态寄存器值读取
 * 7.FLASH芯片状态寄存器值写入
 * 8.FLASH芯片忙状态查询
 * 9.FLASH芯片写使能
 * 10.FLASH芯片写禁止
 *
 * NOTE：SM25QH256M芯片空间为256M（32M*8bit）,根据芯片手册，做以下说明：
 * 1）FLASH扇区地址长度为0x1000，扇区个数为8192；
 *   块号（32byte）地址长度为0x8000，块号个数为1024个；
 *   块号（64byte）地址长度为0x10000，块号个数为512个。
 * 2）写入单次最多写入256个字节
 *
 *
 *********************************************************************************/

#ifndef M25QH256FLASH_

#define M25QH256FLASH_

/*********************************************************************************/
/* 本模块需要调用外部接口 */

/* SPI数据传输函数，v_dataBuff_u16--待发送（拟接收）数据缓冲区首地址，v_dataBuff_u16--发送(接收)数据长度  */
#define SPI_FLASH_DATATRANS(v_dataBuff_u16,v_len_u8)   SpiDataTrans((v_dataBuff_u16),(v_len_u8))   /* SPI数据传输函数，v_dataBuff_u16--待发送（拟接收）数据缓冲区首地址，v_dataBuff_u16--发送(接收)数据长度  */

#define SPI_FLASH_CS_LOW      GPIOClearNum((GPIO_OUT_SPI_EN))    /* SPI片选使能线拉低  */
#define SPI_FLASH_CS_HIGH     GPIOSetNum((GPIO_OUT_SPI_EN))      /* SPI片选使能线拉高  */

/******************************************************************/
/* FLASH芯片地址长度信息宏定义 */
#define M25QH256FLASH_BASE_ADDR           (0x0UL)      /* FLASH基地址        */
#define M25QH256FLASH_LEN                 (0x2000000UL) /* FLASH最大长度    */

#define M25QH256FLASH_SECTOR_LEN          (0x1000UL)    /* FLASH扇区长度    */
#define M25QH256FLASH_SECTOR_NUM          (8192U)       /* FLASH中的扇区数*/

#define M25QH256FLASH_B32K_LEN            (0x8000UL)    /* FLASH块32K地址长度    */
#define M25QH256FLASH_B32K_NUM            (1024U)       /* FLASH块32K个数            */

#define M25QH256FLASH_B64K_LEN            (0x10000UL)   /* FLASH块64K地址长度    */
#define M25QH256FLASH_B64K_NUM            (512U)        /* FLASH块64K个数            */

/******************************************************************/
/* FLASH指令宏定义 */

#define INSTRUCTION_WRITE_SR        (0x01U)  /* 写状态寄存器   */
#define INSTRUCTION_PAGE_PROGRAM    (0x12U)  /* 页写入               */
#define INSTRUCTION_READ_DATA       (0x13U)  /* 读取数据           */
#define INSTRUCTION_WRITE_DISABLE   (0x04U)  /* 写禁止              */
#define INSTRUCTION_READ_SR         (0x05U)  /* 读状态寄存器   */
#define INSTRUCTION_WRITE_ENABLE    (0x06U)  /* 写使能              */
#define INSTRUCTION_READ_ID         (0x9FU)  /* 读ID       */
#define INSTRUCTION_SER             (0x21U)  /* 扇区擦除         */
#define INSTRUCTION_BER_32K         (0x5CU)  /* 32K块擦除         */
#define INSTRUCTION_BER_64K         (0xDCU)  /* 64K块擦除         */
#define INSTRUCTION_CER             (0x60U)  /* 全片擦除        */

/******************************************************************/
/* FLASH忙状态位定义 */

#define SPI_FLASH_BUSY              (1U)     /* FLASH处于忙状态中 */
#define SPI_FLASH_NOT_BUSY          (0U)     /* FLASH未处于忙状态 */

/******************************************************************/
/* 状态寄存器位定义 */

#define SPI_FLASH_SR_SRWD           (0x01U << 7U)   /* 状态寄存器写保护位  */
#define SPI_FLASH_SR_WEL            (0x01U << 1U)   /* 写使能标志位        */
#define SPI_FLASH_SR_WIP            (0x01U << 0U)   /* FLASH是否处于忙状态 */

#define SPI_FLASH_SR_WIP_NO_BUSY    (0U)            /* FLASH当前未处于忙状态 */
#define SPI_FLASH_SR_WIP_BUSY       (1U << 0U)      /* FLASH当前处于忙状态   */

#define SPI_FLASH_SR_WEL_DISABLE    (0U)            /* 写使能标志位，禁止  */
#define SPI_FLASH_SR_WEL_ENABLE     (1U << 1U)      /* 写使能标志位，使能  */

/******************************************************************/

#define SPI_FLASH_PAGE_NUM          (256U)   /* SPI FLASH 页存储字节数据 */

#define FLASH_DEVICE_ID          (0x20U)   /* FLASH芯片设备ID号  */

/******************************************************************/
/* 供外部调用接口 */

extern void   SpiFlashWriteEn(void);
extern void   SpiFlashWriteDis(void);
extern void   SpiFlashReadID(Uint16 *v_dBuff_u16,Uint16 v_len_u16);
extern Uint8  SpiFlashReadSR(void);
extern void   SpiFlashWriteSR(Uint8 v_data_u8);
extern Uint16 SpiFlashDataRead(Uint32 v_addr_u32,Uint16 *v_dBuff_u16,Uint16 v_len_u16);
extern Uint16 SpiFlashPageProgram(Uint32 v_addr_u32,Uint16 *v_dBuff_u16,Uint16 v_len_u16);
extern void   SpiFlashSectorErase(Uint32 v_addr_u32);
extern void   SpiFlashBulkErase(void);
extern Uint16 SpiFlashIsBusy(void);

#endif /* end of include guard: M25QH256FLASH_ */

/* ***************************************************************** */
/* END OF FILE */
/* ***************************************************************** */
