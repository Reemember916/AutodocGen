#ifndef DSP_DEFAULTISR_

#define DSP_DEFAULTISR_

//---------------------------------------------------------------------------
// Default Interrupt Service Routine Declarations:
// 
// The following function prototypes are for the 
// default ISR routines used with the default PIE vector table.
// This default vector table is found in the DSP2833x_PieVect.h 
// file.  
//

interrupt void INT13_ISR(void);     // XINT13 or CPU-Timer 1
interrupt void NMI_ISR(void);       // Non-maskable interrupt

interrupt void rsvd_ISR(void);           // for test

#define XINT1_ISR rsvd_ISR
#define XINT2_ISR rsvd_ISR
#define XINT3_ISR rsvd_ISR
#define XINT4_ISR rsvd_ISR
#define XINT5_ISR rsvd_ISR
#define XINT6_ISR rsvd_ISR
#define XINT7_ISR rsvd_ISR
#define ADCINT_ISR rsvd_ISR
#define ISR_SPIRXINT rsvd_ISR
#define INT13_ISR rsvd_ISR
#define NMI_ISR rsvd_ISR


#endif /* end of include guard: DSP_DEFAULTISR_ */
