#ifndef DSP_SPI_

#define DSP_SPI_

#include "Global.h"

//---------------------------------------------------------------------------
// SPI Individual Register Bit Definitions:
//
// SPI FIFO Transmit register bit    definitions:
struct  SPIFFTX_BITS {       // bit    description
   Uint16 TXFFIL:5;          // 4:0    Interrupt level
   Uint16 TXFFIENA:1;        // 5      Interrupt enable
   Uint16 TXFFINTCLR:1;      // 6      Clear INT flag
   Uint16 TXFFINT:1;         // 7      INT flag
   Uint16 TXFFST:5;          // 12:8   FIFO status
   Uint16 TXFIFO:1;          // 13     FIFO reset
   Uint16 SPIFFENA:1;        // 14     Enhancement enable
   Uint16 SPIRST:1;          // 15     Reset SPI
};

union SPIFFTX_REG {
   Uint16               all;
   struct SPIFFTX_BITS  bit;
};

//--------------------------------------------
// SPI FIFO recieve register bit definitions:
//
//
struct  SPIFFRX_BITS {       // bits   description
   Uint16 RXFFIL:5;          // 4:0    Interrupt level
   Uint16 RXFFIENA:1;        // 5      Interrupt enable
   Uint16 RXFFINTCLR:1;      // 6      Clear INT flag
   Uint16 RXFFINT:1;         // 7      INT flag
   Uint16 RXFFST:5;          // 12:8   FIFO status
   Uint16 RXFIFORESET:1;     // 13     FIFO reset
   Uint16 RXFFOVFCLR:1;      // 14     Clear overflow
   Uint16 RXFFOVF:1;         // 15     FIFO overflow

};

union SPIFFRX_REG {
   Uint16               all;
   struct SPIFFRX_BITS  bit;
};

//--------------------------------------------
// SPI FIFO control register bit definitions:
//
//
struct  SPIFFCT_BITS {       // bits   description
   Uint16 TXDLY:8;           // 7:0    FIFO transmit delay
   Uint16 rsvd:8;            // 15:8   reserved
};

union SPIFFCT_REG {
   Uint16               all;
   struct SPIFFCT_BITS  bit;
};

//---------------------------------------------
// SPI configuration register bit definitions:
//
//
struct  SPICCR_BITS {        // bits   description
   Uint16 SPICHAR:4;         // 3:0    Character length control
   Uint16 SPILBK:1;          // 4      Loop-back enable/disable
   Uint16 rsvd1:1;           // 5      reserved
   Uint16 CLKPOLARITY:1;     // 6      Clock polarity
   Uint16 SPISWRESET:1;      // 7      SPI SW Reset
   Uint16 rsvd2:8;           // 15:8   reserved
};

union SPICCR_REG {
   Uint16              all;
   struct SPICCR_BITS  bit;
};

//-------------------------------------------------
// SPI operation control register bit definitions:
//
//
struct  SPICTL_BITS {        // bits   description
   Uint16 SPIINTENA:1;       // 0      Interrupt enable
   Uint16 TALK:1;            // 1      Master/Slave transmit enable
   Uint16 MASTER_SLAVE:1;    // 2      Network control mode
   Uint16 CLK_PHASE:1;       // 3      Clock phase select
   Uint16 OVERRUNINTENA:1;   // 4      Overrun interrupt enable
   Uint16 rsvd:11;           // 15:5   reserved
};

union SPICTL_REG {
   Uint16              all;
   struct SPICTL_BITS  bit;
};

//--------------------------------------
// SPI status register bit definitions:
//
//
struct  SPISTS_BITS {        // bits   description
   Uint16 rsvd1:5;           // 4:0    reserved
   Uint16 BUFFULL_FLAG:1;    // 5      SPI transmit buffer full flag
   Uint16 INT_FLAG:1;        // 6      SPI interrupt flag
   Uint16 OVERRUN_FLAG:1;    // 7      SPI reciever overrun flag
   Uint16 rsvd2:8;           // 15:8   reserved
};

union SPISTS_REG {
   Uint16              all;
   struct SPISTS_BITS  bit;
};

//------------------------------------------------
// SPI priority control register bit definitions:
//
//
struct  SPIPRI_BITS {        // bits   description
   Uint16 rsvd1:4;           // 3:0    reserved
   Uint16 FREE:1;            // 4      Free emulation mode control
   Uint16 SOFT:1;            // 5      Soft emulation mode control
   Uint16 PRIORITY:1;        // 6      Interrupt priority select
   Uint16 rsvd2:9;           // 15:7   reserved
};

union SPIPRI_REG {
   Uint16              all;
   struct SPIPRI_BITS  bit;
};

//---------------------------------------------------------------------------
// SPI Register File:
//
struct  SPI_REGS {
   union SPICCR_REG     SPICCR;      // Configuration register
   union SPICTL_REG     SPICTL;      // Operation control register
   union SPISTS_REG     SPISTS;      // Status register
   Uint16               rsvd1;       // reserved
   Uint16               SPIBRR;      // Baud Rate
   Uint16               rsvd2;       // reserved
   Uint16               SPIRXEMU;    // Emulation buffer
   Uint16               SPIRXBUF;    // Serial input buffer
   Uint16               SPITXBUF;    // Serial output buffer
   Uint16               SPIDAT;      // Serial data
   union SPIFFTX_REG    SPIFFTX;     // FIFO transmit register
   union SPIFFRX_REG    SPIFFRX;     // FIFO recieve register
   union SPIFFCT_REG    SPIFFCT;     // FIFO control register
   Uint16               rsvd3[2];    // reserved
   union SPIPRI_REG     SPIPRI;      // FIFO Priority control
};

//---------------------------------------------------------------------------
struct g_SpiConf_t {

    Uint8  g_SpiMode_u8;         /* SPI主从模式    */
    Uint8  g_ClkPolarity_u8;     /* SPI 时钟极性   */
    Uint8  g_ClkPhase_u8;        /* SPI时钟相位    */
    Uint16 g_BaudRate_u16;        /* SPI波特率      */
    Uint8  g_DataBits_u8;        /* SPI数据位数    */
    Uint8  g_LoopBackMode_u8;    /* SPI回环模式    */
    Uint8  g_IntMode_u8;         /* SPI中断使能    */
    Uint8  g_FifoLevel_u8;       /* SPI FIFO触发数 */
    Uint8  g_SimoGpio_u8;        /* SPISIMO 引脚   */
    Uint8  g_SomiGpio_u8;        /* SPISOMI 引脚   */
    Uint8  g_ClkGpio_u8;         /* SPICLK 引脚    */
    Uint8  g_SpisteGpio_u8;      /* SPISTE 引脚*/
};

/* SPI 主动模式 */
#define SPI_SLAVE    (0U)
#define SPI_MASTER   (1U)

/* SPI 回环模式 */
#define SPI_LOOP_DIS (0U)
#define SPI_LOOP_EN  (1U)

/* SPI 中断使能 */
#define SPI_INT_EN   (1U)
#define SPI_INT_DIS  (0U)

/* SPI接收就绪状态 */
#define SPI_RX_READY        (0U) //SPI接收就绪
#define SPI_RX_NOT_READY    (1U) //SPI接收未就绪

/* SPI发送就绪状态 */
#define SPI_TX_READY        (0U) //SPI发送就绪
#define SPI_TX_NOT_READY    (1U) //SPI发送未就绪

/* SPI接收中断标志 */
#define SPI_INT_RXFFINT  (0x01U << 8U) //SPI FIFO接收中断
#define SPI_INT_INTFLAG  (0x01U << 6U) //SPI 接收中断
#define SPI_INT_OVERRUN  (0x01U << 7U) //SPI OVERRUN中断

//---------------------------------------------------------------------------
// SPI External References & Function Declarations:
//
extern volatile struct SPI_REGS SpiaRegs;

#if DSP_SPI

extern Uint16 SpiIsRxReady(void);
extern Uint16 SpiIsTxReady(void);
extern void SpiDataTrans(Uint16 * l_DataBuff_u16, Uint8 l_len_u8);
extern void SpiReadBuff(Uint16 *l_buff_u16, Uint16 l_len_u16);
extern Uint16 SpiRead(void);
extern void SpiWriteBuff(Uint16 *l_buff_u16, Uint16 l_len_u16);
extern void SpiWrite(Uint16 l_data_u16);
extern void SpiInit(void);
extern interrupt void ISR_SPIRXINT(void);
extern void SpiIntAck(Uint8 l_IntFlag_u8);
extern Uint16 SpiStatusGet(void);
extern Uint16 SpiRxFifoCount(void);

#endif

/* ***************************************************************** */
/* DSP_SPI.c 私有宏定义 */
/* ***************************************************************** */
#if DSP_SPI
#define BAUDRATE_DIVIDE_MIN (4U)
#define BAUDRATE_DIVIDE_MAX (128U)
#define SPI_FIFO_MAX     (16U)        /* SPI FIFO最大缓存字节数 */
#define SPI_MAX_DBITS    (16U)        /* SPI 最大的数据BIT数 */
#endif

#endif /* end of include guard: DSP_SPI_ */
