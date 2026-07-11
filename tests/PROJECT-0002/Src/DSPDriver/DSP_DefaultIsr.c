// TI File $Revision: /main/1 $
// Checkin $Date: August 18, 2006   13:46:06 $
//###########################################################################
//
// FILE:	DSP2833x_DefaultIsr.c
//
// TITLE:	DSP2833x Device Default Interrupt Service Routines.
//
// This file contains shell ISR routines for the 2833x PIE vector table.
// Typically these shell ISR routines can be used to populate the entire PIE 
// vector table during device debug.  In this manner if an interrupt is taken
// during firmware development, there will always be an ISR to catch it.  
//
// As develpment progresses, these ISR rotuines can be eliminated and replaced
// with the user's own ISR routines for each interrupt.  Since these shell ISRs
// include infinite loops they will typically not be included as-is in the final
// production firmware. 
//
//###########################################################################
// $TI Release: DSP2833x Header Files V1.01 $
// $Release Date: September 26, 2007 $
//###########################################################################

/* #include "DSP2833x_Device.h"     // DSP2833x Headerfile Include File */
/* #include "DSP2833x_Examples.h"   // DSP2833x Examples Include File */
#include "Global.h"
interrupt void rsvd_ISR(void)      // For test
{
    WDogResetTrigger();
    for(;;)
    {
        ;
    }
}

//===========================================================================
// End of file.
//===========================================================================

