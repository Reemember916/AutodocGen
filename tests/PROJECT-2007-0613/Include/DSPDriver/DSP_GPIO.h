

#ifndef DSP_GPIO_
#define DSP_GPIO_

//----------------------------------------------------
// GPIO A control register bit definitions */                                    
struct GPACTRL_BITS {        // bits   description
   Uint16 QUALPRD0:8;        // 7:0    Qual period 
   Uint16 QUALPRD1:8;        // 15:8   Qual period 
   Uint16 QUALPRD2:8;        // 23:16  Qual period 
   Uint16 QUALPRD3:8;        // 31:24  Qual period  
};

union GPACTRL_REG {
   Uint32              all;
   struct GPACTRL_BITS bit;
};

//----------------------------------------------------
// GPIO B control register bit definitions */                                    
struct GPBCTRL_BITS {        // bits   description
   Uint16 QUALPRD0:8;        // 7:0    Qual period
   Uint16 rsvd1:8;           // 15:8   reserved 
   Uint16 QUALPRD2:8;        // 23:16  Qual period
   Uint16 QUALPRD3:8;        // 31:24
};

union GPBCTRL_REG {
   Uint32              all;
   struct GPBCTRL_BITS bit;
};

//----------------------------------------------------
// GPIO A Qual/MUX select register bit definitions */                                    
struct GPA1_BITS {            // bits   description
   Uint16 GPIO0:2;            // 1:0    GPIO0   
   Uint16 GPIO1:2;            // 3:2    GPIO1 
   Uint16 GPIO2:2;            // 5:4    GPIO2 
   Uint16 GPIO3:2;            // 7:6    GPIO3    
   Uint16 GPIO4:2;            // 9:8    GPIO4 
   Uint16 GPIO5:2;            // 11:10  GPIO5 
   Uint16 GPIO6:2;            // 13:12  GPIO6    
   Uint16 GPIO7:2;            // 15:14  GPIO7 
   Uint16 GPIO8:2;            // 17:16  GPIO8 
   Uint16 GPIO9:2;            // 19:18  GPIO9    
   Uint16 GPIO10:2;           // 21:20  GPIO10 
   Uint16 GPIO11:2;           // 23:22  GPIO11       
   Uint16 GPIO12:2;           // 25:24  GPIO12 
   Uint16 GPIO13:2;           // 27:26  GPIO13 
   Uint16 GPIO14:2;           // 29:28  GPIO14 
   Uint16 GPIO15:2;           // 31:30  GPIO15 
};


struct GPA2_BITS {            // bits   description
   Uint16 GPIO16:2;           // 1:0    GPIO16   
   Uint16 GPIO17:2;           // 3:2    GPIO17 
   Uint16 GPIO18:2;           // 5:4    GPIO18 
   Uint16 GPIO19:2;           // 7:6    GPIO19   
   Uint16 GPIO20:2;           // 9:8    GPIO20
   Uint16 GPIO21:2;           // 11:10  GPIO21 
   Uint16 GPIO22:2;           // 13:12  GPIO22    
   Uint16 GPIO23:2;           // 15:14  GPIO23
   Uint16 GPIO24:2;           // 17:16  GPIO24 
   Uint16 GPIO25:2;           // 19:18  GPIO25    
   Uint16 GPIO26:2;           // 21:20  GPIO26 
   Uint16 GPIO27:2;           // 23:22  GPIO27       
   Uint16 GPIO28:2;           // 25:24  GPIO28 
   Uint16 GPIO29:2;           // 27:26  GPIO29 
   Uint16 GPIO30:2;           // 29:28  GPIO30 
   Uint16 GPIO31:2;           // 31:30  GPIO31 
};

struct GPB1_BITS {            // bits   description
   Uint16 GPIO32:2;           // 1:0    GPIO32   
   Uint16 GPIO33:2;           // 3:2    GPIO33
   Uint16 GPIO34:2;           // 5:4    GPIO34   
   Uint16 GPIO35:2;           // 7:6    GPIO35  
   Uint16 GPIO36:2;           // 9:8    GPIO36
   Uint16 GPIO37:2;           // 11:10  GPIO37
   Uint16 GPIO38:2;           // 13:12  GPIO38
   Uint16 GPIO39:2;           // 15:14  GPIO39
   Uint16 GPIO40:2;           // 17:16  GPIO40
   Uint16 GPIO41:2;           // 19:16  GPIO41
   Uint16 GPIO42:2;           // 21:20  GPIO42
   Uint16 GPIO43:2;           // 23:22  GPIO43
   Uint16 GPIO44:2;           // 25:24  GPIO44
   Uint16 GPIO45:2;           // 27:26  GPIO45
   Uint16 GPIO46:2;           // 29:28  GPIO46
   Uint16 GPIO47:2;           // 31:30  GPIO47
};  

struct GPB2_BITS  {           // bits   description
   Uint16 GPIO48:2;           // 1:0    GPIO48   
   Uint16 GPIO49:2;           // 3:2    GPIO49 
   Uint16 GPIO50:2;           // 5:4    GPIO50 
   Uint16 GPIO51:2;           // 7:6    GPIO51   
   Uint16 GPIO52:2;           // 9:8    GPIO52
   Uint16 GPIO53:2;           // 11:10  GPIO53 
   Uint16 GPIO54:2;           // 13:12  GPIO54    
   Uint16 GPIO55:2;           // 15:14  GPIO55
   Uint16 GPIO56:2;           // 17:16  GPIO56 
   Uint16 GPIO57:2;           // 19:18  GPIO57    
   Uint16 GPIO58:2;           // 21:20  GPIO58 
   Uint16 GPIO59:2;           // 23:22  GPIO59       
   Uint16 GPIO60:2;           // 25:24  GPIO60 
   Uint16 GPIO61:2;           // 27:26  GPIO61 
   Uint16 GPIO62:2;           // 29:28  GPIO62 
   Uint16 GPIO63:2;           // 31:30  GPIO63 
};

struct GPC1_BITS {            // bits   description
   Uint16 GPIO64:2;           // 1:0    GPIO64   
   Uint16 GPIO65:2;           // 3:2    GPIO65
   Uint16 GPIO66:2;           // 5:4    GPIO66
   Uint16 GPIO67:2;           // 7:6    GPIO67   
   Uint16 GPIO68:2;           // 9:8    GPIO68
   Uint16 GPIO69:2;           // 11:10  GPIO69
   Uint16 GPIO70:2;           // 13:12  GPIO70   
   Uint16 GPIO71:2;           // 15:14  GPIO71 
   Uint16 GPIO72:2;           // 17:16  GPIO72 
   Uint16 GPIO73:2;           // 19:18  GPIO73   
   Uint16 GPIO74:2;           // 21:20  GPIO74 
   Uint16 GPIO75:2;           // 23:22  GPIO75       
   Uint16 GPIO76:2;           // 25:24  GPIO76 
   Uint16 GPIO77:2;           // 27:26  GPIO77 
   Uint16 GPIO78:2;           // 29:28  GPIO78 
   Uint16 GPIO79:2;           // 31:30  GPIO79 
};


struct GPC2_BITS {            // bits   description
   Uint16 GPIO80:2;           // 1:0    GPIO80   
   Uint16 GPIO81:2;           // 3:2    GPIO81 
   Uint16 GPIO82:2;           // 5:4    GPIO82 
   Uint16 GPIO83:2;           // 7:6    GPIO83   
   Uint16 GPIO84:2;           // 9:8    GPIO84
   Uint16 GPIO85:2;           // 11:10  GPIO85 
   Uint16 GPIO86:2;           // 13:12  GPIO86    
   Uint16 GPIO87:2;           // 15:14  GPIO87
   Uint16 rsvd:16;            // 31:16  reserved
};


union GPA1_REG {
   Uint32              all;
   struct GPA1_BITS    bit;
};

union GPA2_REG {
   Uint32              all;
   struct GPA2_BITS    bit;
};      

union GPB1_REG {
   Uint32              all;
   struct GPB1_BITS    bit;
};

union GPB2_REG {
   Uint32              all;
   struct GPB2_BITS    bit;
};

union GPC1_REG {
   Uint32              all;
   struct GPC1_BITS    bit;
};

union GPC2_REG {
   Uint32              all;
   struct GPC2_BITS    bit;
};

//----------------------------------------------------
// GPIO A DIR/TOGGLE/SET/CLEAR register bit definitions */                                    
struct GPADAT_BITS {          // bits   description
   Uint16 GPIO0:1;            // 0      GPIO0   
   Uint16 GPIO1:1;            // 1      GPIO1 
   Uint16 GPIO2:1;            // 2      GPIO2 
   Uint16 GPIO3:1;            // 3      GPIO3    
   Uint16 GPIO4:1;            // 4      GPIO4 
   Uint16 GPIO5:1;            // 5      GPIO5 
   Uint16 GPIO6:1;            // 6      GPIO6    
   Uint16 GPIO7:1;            // 7      GPIO7 
   Uint16 GPIO8:1;            // 8      GPIO8 
   Uint16 GPIO9:1;            // 9      GPIO9    
   Uint16 GPIO10:1;           // 10     GPIO10 
   Uint16 GPIO11:1;           // 11     GPIO11       
   Uint16 GPIO12:1;           // 12     GPIO12 
   Uint16 GPIO13:1;           // 13     GPIO13 
   Uint16 GPIO14:1;           // 14     GPIO14 
   Uint16 GPIO15:1;           // 15     GPIO15 
   Uint16 GPIO16:1;           // 16     GPIO16   
   Uint16 GPIO17:1;           // 17     GPIO17 
   Uint16 GPIO18:1;           // 18     GPIO18 
   Uint16 GPIO19:1;           // 19     GPIO19   
   Uint16 GPIO20:1;           // 20     GPIO20
   Uint16 GPIO21:1;           // 21     GPIO21 
   Uint16 GPIO22:1;           // 22     GPIO22    
   Uint16 GPIO23:1;           // 23     GPIO23
   Uint16 GPIO24:1;           // 24     GPIO24 
   Uint16 GPIO25:1;           // 25     GPIO25    
   Uint16 GPIO26:1;           // 26     GPIO26 
   Uint16 GPIO27:1;           // 27     GPIO27       
   Uint16 GPIO28:1;           // 28     GPIO28 
   Uint16 GPIO29:1;           // 29     GPIO29 
   Uint16 GPIO30:1;           // 30     GPIO30 
   Uint16 GPIO31:1;           // 31     GPIO31 
};

struct GPBDAT_BITS {          // bits   description
   Uint16 GPIO32:1;           // 0      GPIO32   
   Uint16 GPIO33:1;           // 1      GPIO33
   Uint16 GPIO34:1;           // 2      GPIO34   
   Uint16 GPIO35:1;           // 3      GPIO35    
   Uint16 GPIO36:1;           // 4      GPIO36 
   Uint16 GPIO37:1;           // 5      GPIO37
   Uint16 GPIO38:1;           // 6      GPIO38   
   Uint16 GPIO39:1;           // 7      GPIO39 
   Uint16 GPIO40:1;           // 8      GPIO40 
   Uint16 GPIO41:1;           // 9      GPIO41 
   Uint16 GPIO42:1;           // 10     GPIO42 
   Uint16 GPIO43:1;           // 11     GPIO43 
   Uint16 GPIO44:1;           // 12     GPIO44 
   Uint16 GPIO45:1;           // 13     GPIO45 
   Uint16 GPIO46:1;           // 14     GPIO46 
   Uint16 GPIO47:1;           // 15     GPIO47 
   Uint16 GPIO48:1;           // 16     GPIO48   
   Uint16 GPIO49:1;           // 17     GPIO49 
   Uint16 GPIO50:1;           // 18     GPIO50 
   Uint16 GPIO51:1;           // 19     GPIO51   
   Uint16 GPIO52:1;           // 20     GPIO52
   Uint16 GPIO53:1;           // 21     GPIO53 
   Uint16 GPIO54:1;           // 22     GPIO54    
   Uint16 GPIO55:1;           // 23     GPIO55
   Uint16 GPIO56:1;           // 24     GPIO56 
   Uint16 GPIO57:1;           // 25     GPIO57    
   Uint16 GPIO58:1;           // 26     GPIO58 
   Uint16 GPIO59:1;           // 27     GPIO59       
   Uint16 GPIO60:1;           // 28     GPIO60 
   Uint16 GPIO61:1;           // 29     GPIO61 
   Uint16 GPIO62:1;           // 30     GPIO62 
   Uint16 GPIO63:1;           // 31     GPIO63 
};

struct GPCDAT_BITS {          // bits   description
   Uint16 GPIO64:1;           // 0      GPIO64   
   Uint16 GPIO65:1;           // 1      GPIO65
   Uint16 GPIO66:1;           // 2      GPIO66   
   Uint16 GPIO67:1;           // 3      GPIO67    
   Uint16 GPIO68:1;           // 4      GPIO68 
   Uint16 GPIO69:1;           // 5      GPIO69
   Uint16 GPIO70:1;           // 6      GPIO70   
   Uint16 GPIO71:1;           // 7      GPIO71 
   Uint16 GPIO72:1;           // 8      GPIO72
   Uint16 GPIO73:1;           // 9      GPIO73   
   Uint16 GPIO74:1;           // 10     GPIO74 
   Uint16 GPIO75:1;           // 11     GPIO75       
   Uint16 GPIO76:1;           // 12     GPIO76 
   Uint16 GPIO77:1;           // 13     GPIO77 
   Uint16 GPIO78:1;           // 14     GPIO78 
   Uint16 GPIO79:1;           // 15     GPIO79 
   Uint16 GPIO80:1;           // 16     GPIO80   
   Uint16 GPIO81:1;           // 17     GPIO81 
   Uint16 GPIO82:1;           // 18     GPIO82 
   Uint16 GPIO83:1;           // 19     GPIO83   
   Uint16 GPIO84:1;           // 20     GPIO84
   Uint16 GPIO85:1;           // 21     GPIO85 
   Uint16 GPIO86:1;           // 22     GPIO86    
   Uint16 GPIO87:1;           // 23     GPIO87
   Uint16 rsvd1:8;            // 31:24  reserved
};


union GPADAT_REG {
   Uint32              all;
   struct GPADAT_BITS  bit;
};

union GPBDAT_REG {
   Uint32              all;
   struct GPBDAT_BITS  bit;
};

union GPCDAT_REG {
   Uint32              all;
   struct GPCDAT_BITS  bit;
};

//----------------------------------------------------
// GPIO Xint1/XINT2/XNMI select register bit definitions */                                    
struct GPIOXINT_BITS {        // bits   description
    Uint16 GPIOSEL:5;         // 4:0    Select GPIO interrupt input source
    Uint16 rsvd1:11;          // 15:5   reserved
};

union GPIOXINT_REG {
   Uint16                all;
   struct GPIOXINT_BITS  bit;
};


struct GPIO_CTRL_REGS {
   union  GPACTRL_REG  GPACTRL;   // GPIO A Control Register (GPIO0 to 31)
   union  GPA1_REG     GPAQSEL1;  // GPIO A Qualifier Select 1 Register (GPIO0 to 15)
   union  GPA2_REG     GPAQSEL2;  // GPIO A Qualifier Select 2 Register (GPIO16 to 31)
   union  GPA1_REG     GPAMUX1;   // GPIO A Mux 1 Register (GPIO0 to 15)
   union  GPA2_REG     GPAMUX2;   // GPIO A Mux 2 Register (GPIO16 to 31)
   union  GPADAT_REG   GPADIR;    // GPIO A Direction Register (GPIO0 to 31)
   union  GPADAT_REG   GPAPUD;    // GPIO A Pull Up Disable Register (GPIO0 to 31)
   Uint32              rsvd1;
   union  GPBCTRL_REG  GPBCTRL;   // GPIO B Control Register (GPIO32 to 63)
   union  GPB1_REG     GPBQSEL1;  // GPIO B Qualifier Select 1 Register (GPIO32 to 47)
   union  GPB2_REG     GPBQSEL2;  // GPIO B Qualifier Select 2 Register (GPIO48 to 63)
   union  GPB1_REG     GPBMUX1;   // GPIO B Mux 1 Register (GPIO32 to 47)
   union  GPB2_REG     GPBMUX2;   // GPIO B Mux 2 Register (GPIO48 to 63)
   union  GPBDAT_REG   GPBDIR;    // GPIO B Direction Register (GPIO32 to 63)
   union  GPBDAT_REG   GPBPUD;    // GPIO B Pull Up Disable Register (GPIO32 to 63)
   Uint16              rsvd2[8];
   union  GPC1_REG     GPCMUX1;   // GPIO C Mux 1 Register (GPIO64 to 79)
   union  GPC2_REG     GPCMUX2;   // GPIO C Mux 2 Register (GPIO80 to 95)
   union  GPCDAT_REG   GPCDIR;    // GPIO C Direction Register (GPIO64 to 95)
   union  GPCDAT_REG   GPCPUD;    // GPIO C Pull Up Disable Register (GPIO64 to 95)
};

struct GPIO_DATA_REGS {
   union  GPADAT_REG       GPADAT;       // GPIO Data Register (GPIO0 to 31)
   union  GPADAT_REG       GPASET;       // GPIO Data Set Register (GPIO0 to 31)
   union  GPADAT_REG       GPACLEAR;     // GPIO Data Clear Register (GPIO0 to 31)
   union  GPADAT_REG       GPATOGGLE;    // GPIO Data Toggle Register (GPIO0 to 31) 
   union  GPBDAT_REG       GPBDAT;       // GPIO Data Register (GPIO32 to 63)
   union  GPBDAT_REG       GPBSET;       // GPIO Data Set Register (GPIO32 to 63)
   union  GPBDAT_REG       GPBCLEAR;     // GPIO Data Clear Register (GPIO32 to 63)
   union  GPBDAT_REG       GPBTOGGLE;    // GPIO Data Toggle Register (GPIO32 to 63)
   union  GPCDAT_REG       GPCDAT;       // GPIO Data Register (GPIO64 to 95)
   union  GPCDAT_REG       GPCSET;       // GPIO Data Set Register (GPIO64 to 95)
   union  GPCDAT_REG       GPCCLEAR;     // GPIO Data Clear Register (GPIO64 to 95)
   union  GPCDAT_REG       GPCTOGGLE;    // GPIO Data Toggle Register (GPIO64 to 95)
   Uint16                  rsvd1[8];
};

struct GPIO_INT_REGS {
   union  GPIOXINT_REG     GPIOXINT1SEL; // XINT1 GPIO Input Selection
   union  GPIOXINT_REG     GPIOXINT2SEL; // XINT2 GPIO Input Selection
   union  GPIOXINT_REG     GPIOXNMISEL;  // XNMI_Xint13 GPIO Input Selection
   union  GPIOXINT_REG     GPIOXINT3SEL; // XINT3 GPIO Input Selection
   union  GPIOXINT_REG     GPIOXINT4SEL; // XINT4 GPIO Input Selection
   union  GPIOXINT_REG     GPIOXINT5SEL; // XINT5 GPIO Input Selection
   union  GPIOXINT_REG     GPIOXINT6SEL; // XINT6 GPIO Input Selection
   union  GPIOXINT_REG     GPIOXINT7SEL; // XINT7 GPIO Input Selection
   union  GPADAT_REG       GPIOLPMSEL;   // Low power modes GP I/O input select
};      

/****************************************
 *
 * GPIO端口和引脚定义
 *
 ****************************************/

#define GPIO_PortA       (0U)//GPIO端口号
#define GPIO_PortB       (1U)
#define GPIO_PortC       (2U)

#define GPIO_NULL        (0U)

#define GPIO_SET         (1U)            //GPIO引脚状态，SET
#define GPIO_CLEAR       (0U)            //GPIO引脚状态

#define GPIO_BIT_0       (0x01UL << 0U)
#define GPIO_BIT_1       (0x01UL << 1U)
#define GPIO_BIT_2       (0x01UL << 2U)
#define GPIO_BIT_3       (0x01UL << 3U)
#define GPIO_BIT_4       (0x01UL << 4U)

#define GPIO_BIT_5       (0x01UL << 5U)
#define GPIO_BIT_6       (0x01UL << 6U)
#define GPIO_BIT_7       (0x01UL << 7U)
#define GPIO_BIT_8       (0x01UL << 8U)
#define GPIO_BIT_9       (0x01UL << 9U)

#define GPIO_BIT_10      (0x01UL << 10U)
#define GPIO_BIT_11      (0x01UL << 11U)
#define GPIO_BIT_12      (0x01UL << 12U)
#define GPIO_BIT_13      (0x01UL << 13U)
#define GPIO_BIT_14      (0x01UL << 14U)

#define GPIO_BIT_15      (0x01UL << 15U)
#define GPIO_BIT_16      (0x01UL << 16U)
#define GPIO_BIT_17      (0x01UL << 17U)
#define GPIO_BIT_18      (0x01UL << 18U)
#define GPIO_BIT_19      (0x01UL << 19U)

#define GPIO_BIT_20      (0x01UL << 20U)
#define GPIO_BIT_21      (0x01UL << 21U)
#define GPIO_BIT_22      (0x01UL << 22U)
#define GPIO_BIT_23      (0x01UL << 23U)
#define GPIO_BIT_24      (0x01UL << 24U)

#define GPIO_BIT_25      (0x01UL << 25U)
#define GPIO_BIT_26      (0x01UL << 26U)
#define GPIO_BIT_27      (0x01UL << 27U)
#define GPIO_BIT_28      (0x01UL << 28U)
#define GPIO_BIT_29      (0x01UL << 29U)

#define GPIO_BIT_30      (0x01UL << 30U)
#define GPIO_BIT_31      (0x01UL << 31U)

#define GPIO_BIT_NULL    (0x55UL << 10U)           //GPIO无效BIT标志

/***************************************/

#define GPIO_NUM_0      (0U)             //GPIO0引脚序号
#define GPIO_NUM_1      (1U)             //GPIO1引脚序号
#define GPIO_NUM_2      (2U)             //GPIO2引脚序号
#define GPIO_NUM_3      (3U)             //GPIO3引脚序号
#define GPIO_NUM_4      (4U)             //GPIO4引脚序号
#define GPIO_NUM_5      (5U)             //GPIO5引脚序号
#define GPIO_NUM_6      (6U)             //GPIO6引脚序号
#define GPIO_NUM_7      (7U)             //GPIO7引脚序号
#define GPIO_NUM_8      (8U)             //GPIO8引脚序号
#define GPIO_NUM_9      (9U)             //GPIO9引脚序号

#define GPIO_NUM_10      (10U)             //GPIO10引脚序号
#define GPIO_NUM_11      (11U)             //GPIO11引脚序号
#define GPIO_NUM_12      (12U)             //GPIO12引脚序号
#define GPIO_NUM_13      (13U)             //GPIO13引脚序号
#define GPIO_NUM_14      (14U)             //GPIO14引脚序号
#define GPIO_NUM_15      (15U)             //GPIO15引脚序号
#define GPIO_NUM_16      (16U)             //GPIO16引脚序号
#define GPIO_NUM_17      (17U)             //GPIO17引脚序号
#define GPIO_NUM_18      (18U)             //GPIO18引脚序号
#define GPIO_NUM_19      (19U)             //GPIO19引脚序号

#define GPIO_NUM_20      (20U)             //GPIO20引脚序号
#define GPIO_NUM_21      (21U)             //GPIO21引脚序号
#define GPIO_NUM_22      (22U)             //GPIO22引脚序号
#define GPIO_NUM_23      (23U)             //GPIO23引脚序号
#define GPIO_NUM_24      (24U)             //GPIO24引脚序号
#define GPIO_NUM_25      (25U)             //GPIO25引脚序号
#define GPIO_NUM_26      (26U)             //GPIO26引脚序号
#define GPIO_NUM_27      (27U)             //GPIO27引脚序号
#define GPIO_NUM_28      (28U)             //GPIO28引脚序号
#define GPIO_NUM_29      (29U)             //GPIO29引脚序号

#define GPIO_NUM_30      (30U)             //GPIO30引脚序号
#define GPIO_NUM_31      (31U)             //GPIO31引脚序号
#define GPIO_NUM_32      (32U)             //GPIO32引脚序号
#define GPIO_NUM_33      (33U)             //GPIO33引脚序号
#define GPIO_NUM_34      (34U)             //GPIO34引脚序号
#define GPIO_NUM_35      (35U)             //GPIO35引脚序号
#define GPIO_NUM_36      (36U)             //GPIO36引脚序号
#define GPIO_NUM_37      (37U)             //GPIO37引脚序号
#define GPIO_NUM_38      (38U)             //GPIO38引脚序号
#define GPIO_NUM_39      (39U)             //GPIO39引脚序号

#define GPIO_NUM_40      (40U)             //GPIO40引脚序号
#define GPIO_NUM_41      (41U)             //GPIO41引脚序号
#define GPIO_NUM_42      (42U)             //GPIO42引脚序号
#define GPIO_NUM_43      (43U)             //GPIO43引脚序号
#define GPIO_NUM_44      (44U)             //GPIO44引脚序号
#define GPIO_NUM_45      (45U)             //GPIO45引脚序号
#define GPIO_NUM_46      (46U)             //GPIO46引脚序号
#define GPIO_NUM_47      (47U)             //GPIO47引脚序号
#define GPIO_NUM_48      (48U)             //GPIO48引脚序号
#define GPIO_NUM_49      (49U)             //GPIO49引脚序号

#define GPIO_NUM_50      (50U)             //GPIO引脚序号
#define GPIO_NUM_51      (51U)             //GPIO引脚序号
#define GPIO_NUM_52      (52U)             //GPIO引脚序号
#define GPIO_NUM_53      (53U)             //GPIO引脚序号
#define GPIO_NUM_54      (54U)             //GPIO引脚序号
#define GPIO_NUM_55      (55U)             //GPIO引脚序号
#define GPIO_NUM_56      (56U)             //GPIO引脚序号
#define GPIO_NUM_57      (57U)             //GPIO引脚序号
#define GPIO_NUM_58      (58U)             //GPIO引脚序号
#define GPIO_NUM_59      (59U)             //GPIO引脚序号

#define GPIO_NUM_60      (60U)             //GPIO引脚序号
#define GPIO_NUM_61      (61U)             //GPIO引脚序号
#define GPIO_NUM_62      (62U)             //GPIO引脚序号
#define GPIO_NUM_63      (63U)             //GPIO引脚序号
#define GPIO_NUM_64      (64U)             //GPIO引脚序号
#define GPIO_NUM_65      (65U)             //GPIO引脚序号
#define GPIO_NUM_66      (66U)             //GPIO引脚序号
#define GPIO_NUM_67      (67U)             //GPIO引脚序号
#define GPIO_NUM_68      (68U)             //GPIO引脚序号
#define GPIO_NUM_69      (69U)             //GPIO引脚序号

#define GPIO_NUM_70      (70U)             //GPIO引脚序号
#define GPIO_NUM_71      (71U)             //GPIO引脚序号
#define GPIO_NUM_72      (72U)             //GPIO引脚序号
#define GPIO_NUM_73      (73U)             //GPIO引脚序号
#define GPIO_NUM_74      (74U)             //GPIO引脚序号
#define GPIO_NUM_75      (75U)             //GPIO引脚序号
#define GPIO_NUM_76      (76U)             //GPIO引脚序号
#define GPIO_NUM_77      (77U)             //GPIO引脚序号
#define GPIO_NUM_78      (78U)             //GPIO引脚序号
#define GPIO_NUM_79      (79U)             //GPIO引脚序号

#define GPIO_NUM_80      (80U)             //GPIO引脚序号
#define GPIO_NUM_81      (81U)             //GPIO引脚序号
#define GPIO_NUM_82      (82U)             //GPIO引脚序号
#define GPIO_NUM_83      (83U)             //GPIO引脚序号
#define GPIO_NUM_84      (84U)             //GPIO引脚序号
#define GPIO_NUM_85      (85U)             //GPIO引脚序号
#define GPIO_NUM_86      (86U)             //GPIO引脚序号
#define GPIO_NUM_87      (87U)             //GPIO引脚序号

#define GPIO_NUM_NULL    (100U)             //结束标志

//---------------------------------------------------------------------------

#define GPIO_INT_POL_RISING     (0x01U)      //GPIO外部中断，上升沿触发
#define GPIO_INT_POL_FALLIN     (0x10U)      //GPIO外部中断，下降沿触发
#define GPIO_INT_POL_BOTH       (0x11U)      //GPIO外部中断，上升沿、下降沿均触发

//---------------------------------------------------------------------------

#define GPIO_PULL_UP_EN   (0U)   //GPIO 内部上拉使能
#define GPIO_PULL_UP_DIS  (1U)   //GPIO 内部上拉禁止

#define GPIO_OUTPUT       (1U)   //GPIO输出
#define GPIO_INPUT        (0U)   //GPIO输入

//---------------------------------------------------------------------------

#define GPIO_PUD_REG_BASE   (0x6F8CUL)    //GPIO上拉电阻配置寄存器
#define GPIO_DIR_REG_BASE   (0x6F8AUL)    //GPIO方向配置寄存器
#define GPIO_DATA_REG_BASE  (0x6FC0UL)    //GPIO数据寄存器
#define GPIO_SET_REG_BASE   (0x6FC2UL)    //GPIO 置位寄存器
#define GPIO_CLEAR_REG_BASE (0x6FC4UL)    //GPIO 清零寄存器
#define GPIO_MUX_REG_BASE   (0x6F86UL)    //GPIO 引脚复用功能

//---------------------------------------------------------------------------

struct g_GPIOOut_t {

    Uint32  g_GPIONum_u32;        //GPIO引脚序号
    Uint8   g_GPIOInitValue_u8;  //GPIO引脚初始值
};

struct g_GPIOIn_t {

    Uint32  g_GPIONum_u32;            //GPIO引脚序号
    Uint8   g_GPIOPullUpValue_u8;    //GPIO引脚内部上拉使能状态
};

struct g_GPIOExIntConfData_t {

    Uint8 g_Enable_u8;           //中断的使能状态
    Uint8 g_Polarity_u8;         //中断的边沿触发
    Uint8 g_GpioNum_u8;          //中断的GPIO引脚
};

//---------------------------------------------------------------------------
// GPI/O External References & Function Declarations:
//
extern volatile struct GPIO_CTRL_REGS GpioCtrlRegs;
extern volatile struct GPIO_DATA_REGS GpioDataRegs;
extern volatile struct GPIO_INT_REGS GpioIntRegs;

/****************************************
 *
 * GPIO外部接口
 *
 ****************************************/

extern void GPIOInit(void);
extern void GPIOSet(Uint8 l_GpioPort_u8, Uint32 l_GpioBit_u32);
extern void GPIOSetNum(Uint8 l_GpioNum_u8);
extern void GPIOClear(Uint8 l_GpioPort_u8, Uint32 l_GpioBit_u32);
extern void GPIOClearNum(Uint8 l_GpioNum_u8);
extern void GPIOToggle(Uint8 l_GpioPort_u8, Uint32 l_GpioBit_u32);
extern void GPIOToggleNum(Uint8 l_GpioNum_u8);
extern void GPIOWrite(Uint8 l_GpioPort_u8, Uint32 l_data_u32);
extern Uint32 GPIORead(Uint8 l_GpioPort_u8);
extern Uint8 GPIOReadBit(Uint8 l_GpioPort_u8,Uint32 l_GpioBit_u32);
extern Uint8 GPIOReadBitNum(Uint8 l_GpioPortNum_u8);

extern interrupt void ISR_XNMIInt(void);
extern interrupt void ISR_XINT_1(void);
extern interrupt void ISR_XINT_2(void);
extern interrupt void ISR_XINT_3(void);
extern interrupt void ISR_XINT_4(void);
extern interrupt void ISR_XINT_5(void);
extern interrupt void ISR_XINT_6(void);
extern interrupt void ISR_XINT_7(void);

extern interrupt void ISR_XINT_13(void);

/* ***************************************************************** */
/* DSP_GPIO.c 私有宏定义 */
/* ***************************************************************** */
#define GPIO_MAX        (32UL)
#define GPIO_EXINT_MAX  (8U)

#endif /* end of include guard: DSP_GPIO_ */
