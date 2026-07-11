#ifndef DSP_XINTRUPT_

#define DSP_XINTRUPT_

//---------------------------------------------------------------------------

struct XINTCR_BITS {
    Uint16   ENABLE:1;    // 0      enable/disable
    Uint16   rsvd1:1;     // 1      reserved
    Uint16   POLARITY:2;  // 3:2    pos/neg, both triggered
    Uint16   rsvd2:12;    //15:4    reserved
};

union XINTCR_REG {
   Uint16               all;
   struct XINTCR_BITS   bit;
};  

struct XNMICR_BITS {
    Uint16   ENABLE:1;    // 0      enable/disable
    Uint16   SELECT:1;    // 1      Timer 1 or XNMI connected to int13
    Uint16   POLARITY:2;  // 3:2    pos/neg, or both triggered
    Uint16   rsvd2:12;    // 15:4   reserved
};

union XNMICR_REG {
   Uint16               all;
   struct XNMICR_BITS   bit;
};  




//---------------------------------------------------------------------------
// External Interrupt Register File:
//
struct XINTRUPT_REGS {          //中断寄存器
   union XINTCR_REG XINT1CR;         //中断控制寄存器1
   union XINTCR_REG XINT2CR;         //中断控制寄存器2
   union XINTCR_REG XINT3CR;         //中断控制寄存器3
   union XINTCR_REG XINT4CR;         //中断控制寄存器4
   union XINTCR_REG XINT5CR;         //中断控制寄存器5
   union XINTCR_REG XINT6CR;         //中断控制寄存器6
   union XINTCR_REG XINT7CR;         //中断控制寄存器7
   union XNMICR_REG XNMICR;         //不可屏蔽中断寄存器
   Uint16           XINT1CTR;         //CT寄存器
   Uint16           XINT2CTR;         //CT寄存器
   Uint16           rsvd[5];         //保留
   Uint16           XNMICTR;         //CT寄存器
};

//---------------------------------------------------------------------------
// External Interrupt References & Function Declarations:
//
/*外部接口*/
extern volatile struct XINTRUPT_REGS XIntruptRegs;


#endif /* end of include guard: DSP_XINTRUPT_ */
