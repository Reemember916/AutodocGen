#ifndef DSP_XINTF_

#define DSP_XINTF_

// XINTF timing register bit definitions:
struct XTIMING_BITS {    // bits  description
   Uint16 XWRTRAIL:2;    // 1:0   Write access trail timing
   Uint16 XWRACTIVE:3;   // 4:2   Write access active timing
   Uint16 XWRLEAD:2;     // 6:5   Write access lead timing
   Uint16 XRDTRAIL:2;    // 8:7   Read access trail timing
   Uint16 XRDACTIVE:3;   // 11:9  Read access active timing
   Uint16 XRDLEAD:2;     // 13:12 Read access lead timing
   Uint16 USEREADY:1;    // 14    Extend access using HW waitstates
   Uint16 READYMODE:1;   // 15    Ready mode
   Uint16 XSIZE:2;       // 17:16 XINTF bus width - must be written as 11b
   Uint16 rsvd1:4;       // 21:18 reserved
   Uint16 X2TIMING:1;    // 22    Double lead/active/trail timing
   Uint16 rsvd3:9;       // 31:23 reserved
};

union XTIMING_REG {
   Uint32               all;
   struct XTIMING_BITS  bit;
};

// XINTF control register bit definitions:
struct XINTCNF2_BITS {    // bits  description
   Uint16 WRBUFF:2;       // 1:0   Write buffer depth
   Uint16 CLKMODE:1;      // 2     Ratio for XCLKOUT with respect to XTIMCLK
   Uint16 CLKOFF:1;       // 3     Disable XCLKOUT
   Uint16 rsvd1:2;        // 5:4   reserved
   Uint16 WLEVEL:2;       // 7:6   Current level of the write buffer
   Uint16 rsvd2:1;        // 8     reserved
   Uint16 HOLD:1;         // 9     Hold enable/disable
   Uint16 HOLDS:1;        // 10    Current state of HOLDn input
   Uint16 HOLDAS:1;       // 11    Current state of HOLDAn output
   Uint16 rsvd3:4;        // 15:12 reserved
   Uint16 XTIMCLK:3;      // 18:16 Ratio for XTIMCLK
   Uint16 rsvd4:13;       // 31:19 reserved
};

union XINTCNF2_REG {      //共用体
   Uint32                all;
   struct XINTCNF2_BITS  bit;
};

// XINTF bank switching register bit definitions:
struct XBANK_BITS {      // bits  description
   Uint16  BANK:3;       // 2:0   Zone for which banking is enabled
   Uint16  BCYC:3;       // 5:3   XTIMCLK cycles to add
   Uint16  rsvd:10;      // 15:6  reserved
};

union XBANK_REG {      //共用体
   Uint16             all;
   struct XBANK_BITS  bit;
};

struct XRESET_BITS {   //复位结构体
    Uint16  XHARDRESET:1;
    Uint16  rsvd1:15;
};

union XRESET_REG {      //共用体
    Uint16            all;
    struct XBANK_BITS bit;
};


//---------------------------------------------------------------------------
// XINTF Register File:
//
struct XINTF_REGS {    //外扩总线寄存器
   union XTIMING_REG XTIMING0;   //XTIMING0寄存器
   Uint32  rsvd1[5];           //保留
   union XTIMING_REG XTIMING6;   //XTIMING6寄存器
   union XTIMING_REG XTIMING7;   //XTIMING7寄存器
   Uint32  rsvd2[2];          //保留
   union XINTCNF2_REG XINTCNF2;   //XINTCNF2寄存器
   Uint32  rsvd3;             //保留
   union XBANK_REG    XBANK;   //XBANK寄存器
   Uint16  rsvd4;             //保留
   Uint16  XREVISION;
   Uint16  rsvd5[2];          //保留
   union XRESET_REG   XRESET;   //XRESET寄存器
};

//---------------------------------------------------------------------------
// XINTF External References & Function Declarations:
//
/*外部接口*/
extern volatile struct XINTF_REGS XintfRegs;
extern void InitXintf(void);  //外扩总线初始化

#endif /* end of include guard: DSP_XINTF_ */
