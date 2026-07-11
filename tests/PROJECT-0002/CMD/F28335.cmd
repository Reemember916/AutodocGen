MEMORY
{
PAGE 0:    /* Program Memory */
   RAML0       : origin = 0x008000, length = 0x001000
   RAML1       : origin = 0x009000, length = 0x001000

   FLASHD      : origin = 0x320000, length = 0x008000
   FLASHC      : origin = 0x328000, length = 0x008000
   FLASHB      : origin = 0x330000, length = 0x007FFE
   APPBEGIN    : origin = 0x337FFE, length = 0x000002
   BEGIN       : origin = 0x33FFF6, length = 0x000002
   CSM_PWL     : origin = 0x33FFF8, length = 0x000008
   CSM_RSVD    : origin = 0x33FF80, length = 0x000076
   FLASHA      : origin = 0x338000, length = 0x007F80

   ADC_CAL     : origin = 0x380080, length = 0x000009

   IQTABLES    : origin = 0x3FE000, length = 0x000B50
   IQTABLES2   : origin = 0x3FEB50, length = 0x00008C
   FPUTABLES   : origin = 0x3FEBDC, length = 0x0006A0
   ROM         : origin = 0x3FF27C, length = 0x000D44
   RESET       : origin = 0x3FFFC0, length = 0x000002
   VECTORS     : origin = 0x3FFFC2, length = 0x00003E

PAGE 1:
   BOOT_RSVD   : origin = 0x000000, length = 0x000050
   RAMM1       : origin = 0x000050, length = 0x0007B0
   RAML4       : origin = 0x00A000, length = 0x006000
}

SECTIONS
{
    .cinit              : > FLASHD      PAGE = 0
    .pinit              : > FLASHD      PAGE = 0
    .text               : >> FLASHC|FLASHB      PAGE = 0
    appcodestart        : > BEGIN       PAGE = 0
    ramfuncs            : LOAD = FLASHB,
                          RUN = RAML0,
                          LOAD_START(_RamfuncsLoadStart),
                          LOAD_END(_RamfuncsLoadEnd),
                          RUN_START(_RamfuncsRunStart),
                          PAGE = 0

    .stack              : > RAML1       PAGE = 0
    .ebss               : > RAML4       PAGE = 1
    .esysmem            : > RAMM1       PAGE = 1
    startup_judge       : > RAMM1       PAGE = 1, TYPE = NOINIT

    .econst             : > FLASHB      PAGE = 0
    .switch             : > FLASHB      PAGE = 0

    IQmathTables        : > IQTABLES,   PAGE = 0, TYPE = NOLOAD
    IQmathTables2       : > IQTABLES2,  PAGE = 0, TYPE = NOLOAD
    FPUmathTables       : > FPUTABLES,  PAGE = 0, TYPE = NOLOAD

    .reset              : > RESET,      PAGE = 0, TYPE = DSECT
    vectors             : > VECTORS     PAGE = 0, TYPE = DSECT
    .adc_cal            : LOAD = ADC_CAL, PAGE = 0, TYPE = NOLOAD
}

