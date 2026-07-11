MEMORY
{
PAGE 0:    /* Program Memory */
   RAML0       : origin = 0x008000, length = 0x001000
   RAML1       : origin = 0x009000, length = 0x001000

   /*
    * Self-contained flash layout (工程自包含, 无需外部 A 段 stub):
    * - 此布局与 TI F28335 256KB flash 默认布局兼容 (FLASHA 0x338000-0x33FFFF)。
    * - BEGIN 段 (0x33FFF6) 放 appcodestart (LB _c_int00)。
    * - FLASHB 起点改为 0x330000, 终点 0x337FFD, 长度 0x8000 (64KB)。
    * - APPBEGIN (0x337FFE) 保留作为 appcodestart 备选位置 (空时不被使用)。
    * - 上电 → 0x3FFFC0 (RESET) → BROM 跳到 0x33FFF6 (BEGIN) → _c_int00 → main。
    * - 警告: 升级烧片会覆盖 A 段入口, 失去 A 段独立保护。
    */
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
    .cinit              : > FLASHB      PAGE = 0
    .pinit              : > FLASHB      PAGE = 0
    .text               : {} >> FLASHB | FLASHA PAGE = 0
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

