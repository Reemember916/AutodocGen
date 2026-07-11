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
 *
 *********************************************************************************/

#include "Global.h"

/* ***************************************************************** */
/**
 * 【函数名】:spiFlashDataTrans
 *
 * 【功能描述】SPI-FLASH数据交互
 *
 * 【输入参数说明】:v_dBuff_u16 ---- 拟交互的数据缓冲区地址
 *              v_len_u8    ---- 拟交互的数据长度
 * 【输出参数说明】NONE
 * 【其他说明】       该函数封装“单次CS会话”：CS拉低后连续移出v_len_u8个字节再拉高；
 *                  上层若要求“命令+地址+数据”在同一事务内，需保证一次调用内完成。
 *                  CS前后NOP用于满足片选建立/保持时间裕量，不承担忙等待语义。
 * 【返回】	   NONE
 */
/* ***************************************************************** */
void spiFlashDataTrans(Uint16 *v_dBuff_u16,Uint8 v_len_u8)
{
    /* 参数合法性检查 */
    if( (NULL != v_dBuff_u16) && ( 0U != v_len_u8) )
    {
        /* 片选拉低开始本次SPI事务。 */
        SPI_FLASH_CS_LOW;
        NOP;NOP;NOP;NOP;

        /* 事务内按缓冲区顺序连续移位。 */
        SPI_FLASH_DATATRANS(v_dBuff_u16,v_len_u8);
        NOP;NOP;NOP;NOP;

        /* 片选拉高结束本次SPI事务。 */
        SPI_FLASH_CS_HIGH;
        NOP;NOP;NOP;NOP;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:SpiFlashWriteEn
 *
 * 【功能描述】SPI-FLASH写使能
 *
 * 【输入参数说明】:NONE
 * 【输出参数说明】  NONE
 * 【其他说明】	NONE
 * 【返回】		NONE
 */
/* ***************************************************************** */
void SpiFlashWriteEn(void)
{
    Uint16 l_buff_u16 = INSTRUCTION_WRITE_ENABLE; /* 指令数据  */

    spiFlashDataTrans(&l_buff_u16,1U);
}

/* ***************************************************************** */
/**
 * 【函数名】:SpiFlashWriteDis
 *
 * 【功能描述】SPI-FLASH写禁止
 *
 * 【输入参数说明】:NONE
 * 【输出参数说明】  NONE
 * 【其他说明】	NONE
 * 【返回】		NONE
 */
/* ***************************************************************** */
void SpiFlashWriteDis(void)
{
    Uint16 l_buff_u16 = INSTRUCTION_WRITE_DISABLE; /* 指令数据  */

    spiFlashDataTrans(&l_buff_u16,1U);
}

/* ***************************************************************** */
/**
 * 【函数名】:SpiFlashReadID
 *
 * 【功能描述】SPI-FLASH器件ID读取
 *
 *  读取器件ID，最长三个字节，第一个字节为制造商ID,其余两个是器件ID
 *
 * 【输入函数说明】  v_dBuff_u16 ---- 保存ID数据的首地址
 *              v_len_u16   ---- 拟读取的ID数据个数
 * 【输出参数说明】NONE
 * 【其他说明】NONE
 * 【返回】:  NONE
 */
/* ***************************************************************** */
void SpiFlashReadID(Uint16 *v_dBuff_u16,Uint16 v_len_u16)
{
    Uint16 l_sBuff_u16[4] = {INSTRUCTION_READ_ID,0U,0U,0U};  /* 指令数据数组  */
    Uint16 l_num_u16      = 0U;							     /* 数据个数          */
    Uint16 l_i_u16        = 0U;								 /* 循环计数          */

    /* 参数合法性检查 */
    if((NULL != v_dBuff_u16) && (0U != v_len_u16))
    {
        /* 读取数据个数限幅  */
        if( v_len_u16 > 3U )
        {
            l_num_u16 = 4U;
        }
        else
        {
            l_num_u16 = v_len_u16 + 1U;
        }

        /* 通过SPI口与FLASH芯片交互 */
        spiFlashDataTrans(l_sBuff_u16,l_num_u16);

        /* ID数据拷贝 */
        for( l_i_u16 = 1U; l_i_u16 < l_num_u16; l_i_u16++)
        {
            v_dBuff_u16[l_i_u16 - 1U] = l_sBuff_u16[l_i_u16];
        }
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:SpiFlashReadSR
 *
 * 【功能描述】SPI-FLASH芯片状态寄存器读取
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】:SPI-FLASH状态寄存器值
 */
/* ***************************************************************** */
Uint8 SpiFlashReadSR(void)
{
    Uint16 l_sBuff_u16[2] = {INSTRUCTION_READ_SR,0U}; /* 指令数据数组  */
    Uint8 l_rData_u8 	  = 0U;						  /* 状态寄存器值  */

    /* 通过SPI口与FLASH芯片交互 */
    spiFlashDataTrans(l_sBuff_u16,2U);

    /* 状态寄存器值取低16位  */
    l_rData_u8 = l_sBuff_u16[1] & 0xFFU;

    return l_rData_u8;
}

/* ***************************************************************** */
/**
 * 【函数名】:SpiFlashWriteSR
 *
 * 【功能描述】SPI-FLASH状态寄存器值修改
 *
 * 【输入参数说明】:v_data_u8 ---- 拟写入的状态寄存器值
 * 【输出参数说明】  NONE
 * 【其他说明】NONE
 * 【返回】       NONE
 */
/* ***************************************************************** */
void SpiFlashWriteSR(Uint8 v_data_u8)
{
    Uint16 l_sBuff_u16[2] = {INSTRUCTION_WRITE_SR,0U};  /* 指令数据数组  */
    Uint16 l_temp_u16     = SPI_FLASH_BUSY;				/* 临时数据          */

    /* 获取 FLASH 当前的忙状态 */
    l_temp_u16 = SpiFlashIsBusy();

    /* 参数合法性检查 */
    if(SPI_FLASH_BUSY != l_temp_u16)
    {
        /* 执行写使能指令 */
        SpiFlashWriteEn();
        NOP;NOP;NOP;NOP;

        l_sBuff_u16[1] = v_data_u8;

        /* 通过SPI口与FLASH芯片交互 */
        spiFlashDataTrans(l_sBuff_u16,2U);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:SpiFlashDataRead
 *
 * 【功能描述】SPI-FLASH读取数据
 *
 * 【输入函数说明】  v_addr_u32 ---- 拟读取数据地址
 *             v_dBuff_u16 ---- 拟读取数据存放地址
 *               v_len_u16 ---- 拟读取数据长度
 * 【输出参数说明】NONE
 * 【其他说明】       读取采用“指令(1B)+地址(4B)+数据(NB)”单CS会话；
 *                  读长度限制到SPI_FLASH_PAGE_NUM，仅约束本驱动单次缓存交互规模。
 * 【返回】:     FLASH忙状态
 */
/* ***************************************************************** */
Uint16 SpiFlashDataRead(Uint32 v_addr_u32,Uint16 *v_dBuff_u16,Uint16 v_len_u16)
{
    Uint16 l_num_u16 	   = 0U;								  /* 数据个数         */
    Uint16 l_sBuff_u16[5U] = {INSTRUCTION_READ_DATA,0U,0U,0U,0U}; /* 指令数据数组  */
    Uint16 l_temp_u16      = SPI_FLASH_BUSY;								  /* FLASH忙状态  */

    /* 获取 FLASH当前的忙状态 */
    l_temp_u16 = SpiFlashIsBusy();

    /* 参数合法性检查 */
    if((NULL != v_dBuff_u16) && ( 0U != v_len_u16) && (SPI_FLASH_BUSY != l_temp_u16))
    {
        l_sBuff_u16[1] = (v_addr_u32 >> 24U) & 0xFFU;     /* 地址高高字节 */
        l_sBuff_u16[2] = (v_addr_u32 >> 16U) & 0xFFU;     /* 地址高低字节 */
        l_sBuff_u16[3] = (v_addr_u32 >> 8U ) & 0xFFU;     /* 地址低高字节 */
        l_sBuff_u16[4] = (v_addr_u32 >> 0U ) & 0xFFU;     /* 地址低低字节 */

        /* 输入数据长度限幅  */
        if( v_len_u16 > SPI_FLASH_PAGE_NUM )
        {
            l_num_u16 = SPI_FLASH_PAGE_NUM;
        }
        else
        {
            l_num_u16 = v_len_u16;
        }

        /* 与器件时序一致：命令/地址/数据必须在同一次CS拉低窗口内完成。 */
        SPI_FLASH_CS_LOW;
        NOP;NOP;NOP;NOP;

        /* 通过SPI口传输指令和地址 */
        SPI_FLASH_DATATRANS(l_sBuff_u16,5U);

        /* 连续时钟读出数据，保持CS不释放。 */
        SPI_FLASH_DATATRANS(v_dBuff_u16,l_num_u16);
        NOP;NOP;NOP;NOP;

        /* SPI片选使能无效 */
        SPI_FLASH_CS_HIGH;
        NOP;NOP;NOP;NOP;
    }

    /* 返回 FLASH忙状态  */
    return l_temp_u16;
}

/* *******************************************************************/
/**
 * 【函数名】 SpiFlashIsBusy
 *
 * 【功能描述】SPI-FLASH忙状态查询
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】可能的返回值如下：
 *          SPI_FLASH_BUSY ---- FLASH处于忙状态中
 *      SPI_FLASH_NOT_BUSY ---- FLASH未处于忙状态中
 */
/* *******************************************************************/
Uint16 SpiFlashIsBusy(void)
{
    Uint16 l_temp_u16  = 0U;              /* 状态寄存器值                                                 */
    Uint16 l_rData_u16 = SPI_FLASH_BUSY;  /* 忙状态数据，函数输出，默认状态处于忙    */

    /* 获取FLASH状态寄存器值   */
    l_temp_u16 = SpiFlashReadSR();

    /* 判断状态寄存器忙状态WIP位 */
    if( SPI_FLASH_SR_WIP_BUSY != (SPI_FLASH_SR_WIP & l_temp_u16))
    {
        l_rData_u16 = SPI_FLASH_NOT_BUSY;
    }

    return l_rData_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:SpiFlashPageProgram
 *
 * 【功能描述】SPI-FLASH数据写入
 *
 * 【输入参数说明】: v_addr_u32  ---- 拟写入数据地址
 *               v_dBuff_u16 ---- 拟写入数据首地址
 *               v_len_u16   ---- 拟写入数据个数
 * 【输出参数说明】NONE
 * 【其他说明】页编程语义：单次最多SPI_FLASH_PAGE_NUM字节，且不应跨页；
 *                  本函数仅做长度限幅，不校验页边界，调用方需保证addr与len处于同一页。
 *                  发送完编程命令后即返回，不等待WIP清零，后续需由调用方轮询忙状态。
 * 【返回】:返回成功写入的数据个数
 */
/* ***************************************************************** */
Uint16 SpiFlashPageProgram(Uint32 v_addr_u32,Uint16 *v_dBuff_u16,Uint16 v_len_u16)
{
    Uint16 l_num_u16      = 0U;                                     /* 写入数据个数，函数输出，默认为0 */
    Uint16 l_sBuff_u16[5] = {INSTRUCTION_PAGE_PROGRAM,0U,0U,0U,0U}; /* 指令数据数组          	        */
    Uint16 l_temp_u16     = SPI_FLASH_BUSY;                         /* FLASH忙状态	            */

    /* 获取 FLASH 当前的忙状态 */
    l_temp_u16 = SpiFlashIsBusy();

    /* 参数合法性检查 */
    if((NULL != v_dBuff_u16) && ( 0U != v_len_u16) && (SPI_FLASH_BUSY != l_temp_u16))
    {
        l_sBuff_u16[1] = (v_addr_u32 >> 24U) & 0xFFU;     /* 地址高高字节 */
        l_sBuff_u16[2] = (v_addr_u32 >> 16U) & 0xFFU;     /* 地址高低字节 */
        l_sBuff_u16[3] = (v_addr_u32 >> 8U ) & 0xFFU;     /* 地址低高字节 */
        l_sBuff_u16[4] = (v_addr_u32 >> 0U ) & 0xFFU;     /* 地址低低字节 */

        /* 输入数据长度限幅  */
        if( v_len_u16 > SPI_FLASH_PAGE_NUM )
        {
            l_num_u16 = SPI_FLASH_PAGE_NUM;
        }
        else
        {
            l_num_u16 = v_len_u16;
        }

        if((v_addr_u32 & (~((Uint32)SPI_FLASH_PAGE_NUM - 1UL))) !=
           (((v_addr_u32 + (Uint32)l_num_u16) - 1UL) & (~((Uint32)SPI_FLASH_PAGE_NUM - 1UL))))
        {
            l_num_u16 = 0U;
        }
        else
        {
            /* 执行写使能指令 */
            SpiFlashWriteEn();
            NOP;NOP;NOP;NOP;

            /* 维持同一CS会话：先发PP指令+地址，再发页内数据。 */
            SPI_FLASH_CS_LOW;
            NOP;NOP;NOP;NOP;

            /* 通过SPI口传输指令和地址 */
            SPI_FLASH_DATATRANS(l_sBuff_u16,5U);

            /* 实际为“发送待编程数据”，命名沿用DATATRANS宏。 */
            SPI_FLASH_DATATRANS(v_dBuff_u16,l_num_u16);
            NOP;NOP;NOP;NOP;

            /* SPI片选使能无效 */
            SPI_FLASH_CS_HIGH;
            NOP;NOP;NOP;NOP;
        }
    }

    return l_num_u16;
}

/* ***************************************************************** */
/**
 * 【函数名】:SpiFlashSectorErase
 *
 * 【功能描述】SPI-FLASH扇区擦除
 *
 * 【输入参数说明】v_addr_u32 ---- 拟擦除扇区地址
 * 【输出参数说明】  NONE
 * 【其他说明】	本函数仅下发“扇区擦除命令+地址”，不阻塞等待擦除完成；
 *                  上层若需确认完成，必须后续轮询SpiFlashIsBusy().
 * 【返回】	    NONE
 */
/* ***************************************************************** */
void SpiFlashSectorErase(Uint32 v_addr_u32)
{
    Uint16 l_sBuff_u16[5] = {INSTRUCTION_SER,0U,0U,0U,0U}; /* 指令数据数组   */
    Uint16 l_temp_u16     = 0U;								     /* FLASH忙状态  */

    /* 获取 FLASH 忙状态 */
    l_temp_u16 = SpiFlashIsBusy();

    /* 只有当FLASH未处于忙状态时，才执行扇区擦除指令 */
    if( SPI_FLASH_NOT_BUSY == l_temp_u16 )
    {
        /* 执行写使能指令 */
        SpiFlashWriteEn();
        NOP;NOP;NOP;NOP;
        l_sBuff_u16[1] = (v_addr_u32 >> 24U) & 0xFFU;        /* 地址高字节 */
        l_sBuff_u16[2] = (v_addr_u32 >> 16U) & 0xFFU;        /* 地址高字节 */
        l_sBuff_u16[3] = (v_addr_u32 >> 8U ) & 0xFFU;        /* 地址中字节 */
        l_sBuff_u16[4] = (v_addr_u32 >> 0U ) & 0xFFU;        /* 地址低字节 */

        /* 下发SER后立即返回，擦除在器件内部异步执行。 */
        spiFlashDataTrans(l_sBuff_u16,5U);
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:SpiFlashBulkErase
 *
 * 【功能描述】SPI-FLASH全片擦除
 *
 * 【输入参数说明】:NONE
 * 【输出参数说明】  NONE
 * 【其他说明】         NONE
 * 【返回】	   NONE
 */
/* ***************************************************************** */
void SpiFlashBulkErase(void)
{
    Uint16 l_sBuff_u16[1] = {INSTRUCTION_CER}; /* 指令数据数组   */
    Uint16 l_temp_u16 	  = 0U;  /* FLASH忙状态  */

    /* 获取 FLASH 忙状态 */
    l_temp_u16 = SpiFlashIsBusy();

    /* 只有当FLASH未处于忙状态时，才执行全片擦除指令 */
    if( SPI_FLASH_NOT_BUSY == l_temp_u16 )
    {
        /* 执行写使能指令 */
        SpiFlashWriteEn();
        NOP;NOP;NOP;NOP;

        /* 通过SPI口写入指令和地址 */
        spiFlashDataTrans(l_sBuff_u16,1U);
    }
}

/* ***************************************************************** */
/* END OF FILE */
/* ***************************************************************** */
