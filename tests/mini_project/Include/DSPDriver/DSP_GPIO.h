#ifndef _DSP_GPIO_H_
#define _DSP_GPIO_H_

/* DSP 2833x GPIO 寄存器定义 */

typedef struct {
    Uint16 all;
    struct {
        Uint16 GPIO0:1;
        Uint16 GPIO1:1;
        Uint16 GPIO2:1;
        Uint16 GPIO3:1;
        Uint16 GPIO4:1;
        Uint16 GPIO5:1;
        Uint16 GPIO6:1;
        Uint16 GPIO7:1;
        Uint16 rsvd:8;
    } bit;
} GPIO_REG;

typedef struct {
    GPIO_REG GPADIR;
    GPIO_REG GPADAT;
    GPIO_REG GPASET;
    GPIO_REG GPACLEAR;
} GPIO_CTRL_REGS;

extern GPIO_CTRL_REGS GpioCtrlRegs;
extern GPIO_CTRL_REGS GpioDataRegs;

#endif /* _DSP_GPIO_H_ */