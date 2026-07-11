#ifndef DSP_SCI_

#define DSP_SCI_

//---------------------------------------------------------------------------
// SCI Individual Register Bit Definitions

//----------------------------------------------------------
// SCICCR communication control register bit definitions:
//

struct  SCICCR_BITS {        // bit    description
   Uint16 SCICHAR:3;         // 2:0    Character length control        
   Uint16 ADDRIDLE_MODE:1;   // 3      ADDR/IDLE Mode control
   Uint16 LOOPBKENA:1;       // 4      Loop Back enable
   Uint16 PARITYENA:1;       // 5      Parity enable   
   Uint16 PARITY:1;          // 6      Even or Odd Parity
   Uint16 STOPBITS:1;        // 7      Number of Stop Bits
   Uint16 rsvd1:8;           // 15:8   reserved
}; 


union SCICCR_REG {
   Uint16              all;
   struct SCICCR_BITS  bit;
};

//-------------------------------------------
// SCICTL1 control register 1 bit definitions:
//
                       
struct  SCICTL1_BITS {       // bit    description
   Uint16 RXENA:1;           // 0      SCI receiver enable
   Uint16 TXENA:1;           // 1      SCI transmitter enable
   Uint16 SLEEP:1;           // 2      SCI sleep  
   Uint16 TXWAKE:1;          // 3      Transmitter wakeup method
   Uint16 rsvd:1;            // 4      reserved
   Uint16 SWRESET:1;         // 5      Software reset   
   Uint16 RXERRINTENA:1;     // 6      Recieve interrupt enable
   Uint16 rsvd1:9;           // 15:7   reserved

}; 

union SCICTL1_REG {
   Uint16               all;
   struct SCICTL1_BITS  bit;
};

//---------------------------------------------
// SCICTL2 control register 2 bit definitions:
// 

struct  SCICTL2_BITS {       // bit    description
   Uint16 TXINTENA:1;        // 0      Transmit interrupt enable    
   Uint16 RXBKINTENA:1;      // 1      Receiver-buffer break enable
   Uint16 rsvd:4;            // 5:2    reserved
   Uint16 TXEMPTY:1;         // 6      Transmitter empty flag
   Uint16 TXRDY:1;           // 7      Transmitter ready flag  
   Uint16 rsvd1:8;           // 15:8   reserved

}; 

union SCICTL2_REG {
   Uint16               all;
   struct SCICTL2_BITS  bit;
};

//---------------------------------------------------
// SCIRXST Receiver status register bit definitions:
//

struct  SCIRXST_BITS {       // bit    description
   Uint16 rsvd:1;            // 0      reserved
   Uint16 RXWAKE:1;          // 1      Receiver wakeup detect flag
   Uint16 PE:1;              // 2      Parity error flag
   Uint16 OE:1;              // 3      Overrun error flag
   Uint16 FE:1;              // 4      Framing error flag
   Uint16 BRKDT:1;           // 5      Break-detect flag   
   Uint16 RXRDY:1;           // 6      Receiver ready flag
   Uint16 RXERROR:1;         // 7      Receiver error flag

}; 

union SCIRXST_REG {
   Uint16               all;
   struct SCIRXST_BITS  bit;
};

//----------------------------------------------------
// SCIRXBUF Receiver Data Buffer with FIFO bit definitions:
// 

struct  SCIRXBUF_BITS {      // bits   description
   Uint16 RXDT:8;            // 7:0    Receive word
   Uint16 rsvd:6;            // 13:8   reserved
   Uint16 SCIFFPE:1;         // 14     SCI PE error in FIFO mode
   Uint16 SCIFFFE:1;         // 15     SCI FE error in FIFO mode
};

union SCIRXBUF_REG {
   Uint16                all;
   struct SCIRXBUF_BITS  bit;
};

//--------------------------------------------------
// SCIPRI Priority control register bit definitions:
// 
//
                                                   
struct  SCIPRI_BITS {        // bit    description
   Uint16 rsvd:3;            // 2:0    reserved
   Uint16 FREE:1;            // 3      Free emulation suspend mode
   Uint16 SOFT:1;            // 4      Soft emulation suspend mode
   Uint16 rsvd1:3;           // 7:5    reserved
}; 

union SCIPRI_REG {
   Uint16              all;
   struct SCIPRI_BITS  bit;
};

//-------------------------------------------------
// SCI FIFO Transmit register bit definitions:
// 
//
                                                  
struct  SCIFFTX_BITS {       // bit    description
   Uint16 TXFFIL:5;          // 4:0    Interrupt level
   Uint16 TXFFIENA:1;        // 5      Interrupt enable
   Uint16 TXFFINTCLR:1;      // 6      Clear INT flag
   Uint16 TXFFINT:1;         // 7      INT flag
   Uint16 TXFFST:5;          // 12:8   FIFO status
   Uint16 TXFIFOXRESET:1;    // 13     FIFO reset
   Uint16 SCIFFENA:1;        // 14     Enhancement enable
   Uint16 SCIRST:1;          // 15     SCI reset rx/tx channels 

}; 

union SCIFFTX_REG {
   Uint16               all;
   struct SCIFFTX_BITS  bit;
};

//------------------------------------------------
// SCI FIFO recieve register bit definitions:
// 
//
                                               
struct  SCIFFRX_BITS {       // bits   description
   Uint16 RXFFIL:5;          // 4:0    Interrupt level
   Uint16 RXFFIENA:1;        // 5      Interrupt enable
   Uint16 RXFFINTCLR:1;      // 6      Clear INT flag
   Uint16 RXFFINT:1;         // 7      INT flag
   Uint16 RXFFST:5;          // 12:8   FIFO status
   Uint16 RXFIFORESET:1;     // 13     FIFO reset
   Uint16 RXFFOVRCLR:1;      // 14     Clear overflow
   Uint16 RXFFOVF:1;         // 15     FIFO overflow

}; 

union SCIFFRX_REG {
   Uint16               all;
   struct SCIFFRX_BITS  bit;
};

// SCI FIFO control register bit definitions:
struct  SCIFFCT_BITS {     // bits   description
   Uint16 FFTXDLY:8;         // 7:0    FIFO transmit delay
   Uint16 rsvd:5;            // 12:8   reserved
   Uint16 CDC:1;             // 13     Auto baud mode enable
   Uint16 ABDCLR:1;          // 14     Auto baud clear
   Uint16 ABD:1;             // 15     Auto baud detect
};

union SCIFFCT_REG {
   Uint16               all;
   struct SCIFFCT_BITS  bit;
};

//---------------------------------------------------------------------------
// SCI Register File:
//
struct  SCI_REGS {
   union SCICCR_REG     SCICCR;     // Communications control register
   union SCICTL1_REG    SCICTL1;    // Control register 1
   Uint16               SCIHBAUD;   // Baud rate (high) register
   Uint16               SCILBAUD;   // Baud rate (low) register
   union SCICTL2_REG    SCICTL2;    // Control register 2
   union SCIRXST_REG    SCIRXST;    // Recieve status register
   Uint16               SCIRXEMU;   // Recieve emulation buffer register
   union SCIRXBUF_REG   SCIRXBUF;   // Recieve data buffer  
   Uint16               rsvd1;      // reserved
   Uint16               SCITXBUF;   // Transmit data buffer 
   union SCIFFTX_REG    SCIFFTX;    // FIFO transmit register
   union SCIFFRX_REG    SCIFFRX;    // FIFO recieve register
   union SCIFFCT_REG    SCIFFCT;    // FIFO control register
   Uint16               rsvd2;      // reserved
   Uint16               rsvd3;      // reserved
   union SCIPRI_REG     SCIPRI;     // FIFO Priority control   
};



/* ***************************************************************** */
/**
 * 【说明】:SCI位定义
 */
/* ***************************************************************** */

#define SCI_BAUDRATE_MAX   (115200UL)   /* 波特率最大值 */
#define SCI_BAUDRATE_MIN   (2400UL)     /* 波特率最小值 */

#define SCI_LOOPB_DIS      (0U)  /* 禁止回环模式 */
#define SCI_LOOPB_EN       (1U)  /* 使能回环模式 */

/* 数据位数位定义 */
#define SCI_DATABITS_8     (7U)  /* 数据位数为8 */
#define SCI_DATABITS_7     (6U)  /* 数据位数为7 */
#define SCI_DATABITS_6     (5U)  /* 数据位数为6 */
#define SCI_DATABITS_5     (4U)  /* 数据位数为5 */
#define SCI_DATABITS_4     (3U)  /* 数据位数为4 */
#define SCI_DATABITS_3     (2U)  /* 数据位数为3 */
#define SCI_DATABITS_2     (1U)  /* 数据位数为2 */
#define SCI_DATABITS_1     (0U)  /* 数据位数为1 */

/* 停止位位定义 */
#define SCI_STOPBITS_ONE   (0U)  /* 一位停止位 */
#define SCI_STOPBITS_TWO   (1U)  /* 两位停止位 */

/* 接收发送使能/禁止位定义 */
#define SCI_TX_EN          (1U)  /* 发送使能 */
#define SCI_RX_EN          (2U)  /* 接收使能 */
#define SCI_TXRX_EN        (3U)  /* 发送接收使能 */
#define SCI_TX_DIS         (4U)  /* 发送禁止 */
#define SCI_RX_DIS         (5U)  /* 接收禁止 */
#define SCI_TXRX_DIS       (6U)  /* 发送接收禁止 */

/* 奇偶校验位定义 */
#define SCI_PARITY_ODD     (2U)  /* 奇校验 */
#define SCI_PARITY_EVEN    (3U)  /* 偶校验 */
#define SCI_PARITY_NONE    (0U)  /* 无校验 */

#define SCI_RX_INT_DIS     (0U)  /* 接收中断禁止 */
#define SCI_RX_INT_EN      (1U)  /* 接收中断使能 */

#define SCI_A_ID           (0U)  /* SCI A 端口ID */
#define SCI_B_ID           (1U)  /* SCI B 端口ID */
#define SCI_C_ID           (2U)  /* SCI C 端口ID */
#define SCI_PORT_NUM       (3U)  /* SCI 端口数量 */

/* SCI接收状态位定义 */
#define SCI_RX_FIFO_OVFL   (0x01U << 9U)      /* SCI FIFO接收溢出 */
#define SCI_RX_FIFO_INT    (0x01U << 8U)      /* SCI 接收 FIFO 中断 */

#define SCI_RX_ERR         (0x01U << 7U)      /* SCI接收错误 */
#define SCI_RX_RDY         (0x01U << 6U)      /* SCI接收就绪 */
#define SCI_RX_BRKDT       (0x01U << 5U)      /* SCI接收 break detection */
#define SCI_RX_FE_ERR      (0x01U << 4U)      /* SCI接收报文错误 */
#define SCI_RX_OE_ERR      (0x01U << 3U)      /* SCI接收Overrun错误 */
#define SCI_RX_PE_ERR      (0x01U << 2U)      /* SCI接收校验错误 */

/**************************************************************************/

typedef struct _sciConf {

    Uint32 baud;      /* 波特率   */
    Uint8  databits;  /* 数据位   */
    Uint8  stopbits;  /* 停止位   */
    Uint8  parity;    /* 校验位   */
    Uint8  rxinten;   /* 接收中断模式使能 */
    Uint8  loopEn;    /* 回还模式使能 */
    Uint8  fifolevel; /* FIFO触发 */
    Uint8  txpin;     /* 发送引脚 */
    Uint8  rxpin;     /* 接收引脚 */
}sciConf_t;

typedef struct _SCIPort                 /* SCI端口 */
{
    volatile struct SCI_REGS *pSci;     /* SCI端口指针  */
    Uint16   delay;                     /* 发送等待延时 */
}SCIPort_t;

//---------------------------------------------------------------------------
// SCI External References & Function Declarations:
//
extern volatile struct SCI_REGS SciaRegs;
extern volatile struct SCI_REGS ScibRegs;
extern volatile struct SCI_REGS ScicRegs;

extern interrupt void ISR_SCIA_RXINT(void);
extern interrupt void ISR_SCIB_RXINT(void);
extern interrupt void ISR_SCIC_RXINT(void);

extern Uint8  SciSendBuff(Uint16 sciID,Uint8 *buff, Uint8 len);
extern void   SciSendChar(Uint16 sciID,Uint8 data);
extern Uint16 SciGetChar(Uint16 sciID);
extern Uint8  SciTxFIFOCount(Uint16 sciID);
extern Uint8  SciRxFIFOCount(Uint16 sciID);
extern Uint8  SciIsTxReady(Uint16 sciID);
extern Uint8  SciIsRxReady(Uint16 sciID);
extern void   SciInit(void);
extern Uint16 BaudRateSet(Uint16 sciID,Uint32 baud);
extern void   SciReadBuff(Uint16 sciID,Uint16 *buff,Uint8 len);
extern void   SciReset(Uint16 sciID);
extern Uint16 SciRxStatusGet(Uint16 sciID);
extern void   SciTxRxEnable(Uint16 sciID,Uint16 opCode);
extern void   SciLoopBackEn(Uint16 sciID, Uint16 opCode);
extern void   SciRxFFOVClear(Uint16 sciID);
extern void   SciISRAck(Uint8 sciID);
extern void   SciDataBitsSet(Uint16 sciID,Uint16 databits);
extern void   SciStopBitsSet(Uint16 sciID,Uint16 stopbits);
extern void   SciParitySet(Uint16 sciID,Uint16 parityMode);

/* ***************************************************************** */
/* DSP_SCI.c 私有宏定义 */
/* ***************************************************************** */
#define SCI_FIFO_MAX        (16U)

#endif /* end of include guard: DSP_SCI_ */
