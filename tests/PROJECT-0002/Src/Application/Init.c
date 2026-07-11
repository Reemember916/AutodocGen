
/**********************************************************************************
 *
 *             ***     **      **   **     ******
 *             ***     **     **    **   ***   ***
 *            ****     **     **   **   **      **
 *           ** **     **    **    **  **       **
 *          *** **     **   **     **  **
 *          **  **     **   **    **  **
 *         **   **     **  **     **  **
 *        ***   **     ** **      **  **
 *        ********     ** **     **   **      **
 *       **     **     ****      **   **     **
 *      **      **     ***       **   ***   **
 *      **      **     ***      **     ******
 *
 **********************************************************************************
 *
 * 文件名称:    init.c
 *
 * 文件日期：       REDACTED
 *
 *
 * 程序版本:
 *
 **********************************************************************************
 *
 * 功能说明:
 *
 * 1. 实现DSP基础硬件初始化与用户模块初始化。
 * 2. 完成CPLD上电等待、握手检测、通道同步和初始化握手结果上报。
 *
 *********************************************************************************/

#include "Global.h"


/* 保存初始化阶段“上电与CPLD握手”最终结果，供Control/维护422状态上报 */
Uint16 s_initCpldBusHandshakeResult_u16 = INVALID;
/* 保存初始化阶段与CPLD的CCDL心跳检测结果 */
Uint16 s_initCpldCcdlHeartResult_u16 = INVALID;
/* 保存初始化阶段“通道间握手(长同步+CCDL心跳)”最终结果 */
Uint16 s_initInterChHandshakeResult_u16 = INVALID;

/* ***************************************************************** */
/**
 * 【函数名】:CPLDHandshake
 *
 * 【功能描述】按任务书0005执行双阶段握手：
 *            1) 0x4555写0xAAAA后读0x4AAA校验；
 *            2) 0x4AAA写0x5555后读0x4555校验。
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】    每阶段最多重试3次，与任务书0005条款一致。
 * 【返回】      VALID-握手成功 / INVALID-握手失败
 */
/* ***************************************************************** */
static Uint16 CPLDHandshake(void)
{
    Uint16 l_retry_u16 = 0U;    /* 当前阶段的重试计数 */
    Uint16 l_readData_u16 = 0U; /* 回读到的握手字 */

    /* 第一阶段：向握手寄存器2写0xAAAA，并在寄存器1读回同值。 */
    for(l_retry_u16 = 0U; l_retry_u16 < CPLD_HANDSHAKE_PHASE_RETRY_MAX; l_retry_u16++)
    {
        /* 触发CPLD内部把握手状态从“阶段1待确认”推进到“阶段1已完成”。 */
        HardXintUint16Write(CPLD_ADDR_WR_HANDSHAKE_2, 0xAAAAU);
        /* 给CPLD留出一个最小内部处理时间，再读回结果。 */
        delayUs(CPLD_HANDSHAKE_PHASE_RETRY_DELAY_US);
        l_readData_u16 = HardXintUint16Read(CPLD_ADDR_WR_HANDSHAKE_1);

        /* 阶段1回读正确，进入下一阶段。 */
        if(0xAAAAU == l_readData_u16)
        {
            break;
        }
    }

    /* 第一阶段多次重试仍失败，则整个双阶段握手失败。 */
    if(l_retry_u16 >= CPLD_HANDSHAKE_PHASE_RETRY_MAX)
    {
        return INVALID;
    }

    /* 第二阶段：向握手寄存器1写0x5555，并在寄存器2读回同值。 */
    for(l_retry_u16 = 0U; l_retry_u16 < CPLD_HANDSHAKE_PHASE_RETRY_MAX; l_retry_u16++)
    {
        /* 触发CPLD把握手状态推进到“阶段2完成”。 */
        HardXintUint16Write(CPLD_ADDR_WR_HANDSHAKE_1, 0x5555U);
        /* 给总线写入和CPLD内部更新留最小稳定时间。 */
        delayUs(CPLD_HANDSHAKE_PHASE_RETRY_DELAY_US);
        l_readData_u16 = HardXintUint16Read(CPLD_ADDR_WR_HANDSHAKE_2);

        /* 两阶段都通过，按任务书判定握手成功。 */
        if(0x5555U == l_readData_u16)
        {
            return VALID;
        }
    }

    /* 第二阶段未在重试窗口内成功，整体判为失败。 */
    return INVALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:CPLDCCDLHeartCheck
 *
 * 【功能描述】按任务书0005执行握手后的CCDL心跳检测：
 *            每轮先发送一次CCDL报文，再读取CCDL数据，若心跳字发生变化则成功；
 *            否则延时10ms后重读，最多读取3次。
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【其他说明】    读取对象为“与CPLD的CCDL链路”(COMM_CCDL_CPLD)。
 * 【返回】      VALID-读取成功 / INVALID-读取失败
 */
/* ***************************************************************** */
static Uint16 CPLDCCDLHeartCheck(void)
{
    Uint16 l_readCnt_u16 = 0U;
    Uint16 l_hasLastHeart_u16 = INVALID; /* 是否已经拿到上一拍心跳样本 */
    Uint16 l_heartLast_u16 = 0U;         /* 上一次读取到的CPLD心跳值 */
    PeerBaseStatus_t l_peerBase_t;       /* 当前轮解析出的对端基础帧状态 */

    /* 以“心跳字发生变化”作为对端CCDL链路在线的判据。 */
    for(l_readCnt_u16 = 0U; l_readCnt_u16 < CPLD_CCDL_HEART_WAIT_MAX; l_readCnt_u16++)
    {
        /* 主动触发一次基础帧发送，给运行中的对端提供一次更快的重同步机会。 */
        CommCCDLDataSend();
        /* CCDL心跳检查处于初始化长轮询中，期间保持常规喂狗。 */
        CycleDogFeed();
        /* 给对端和本端收发链路留一个基础帧传播窗口。 */
        delayUs(CCDL_HEART_POLL_DELAY_US);

        /* 读取并解析当前CPLD-CCDL链路的最新帧镜像。 */
        CommCCDLDataBuffRead(COMM_CCDL_CPLD);
        CommCCDLFrameProcess(COMM_CCDL_CPLD);
        l_peerBase_t = CommCCDLPeerBaseGet(COMM_CCDL_CPLD);

        if(VALID == l_hasLastHeart_u16)
        {
            /* 只要心跳字发生跳变，就说明对端在持续发送基础帧。 */
            if(l_peerBase_t.cpldHeart_u16 != l_heartLast_u16)
            {
                return VALID;
            }
        }
        else
        {
            /* 第一拍只建立基线，不立即判失败。 */
            l_hasLastHeart_u16 = VALID;
        }
        /* 记住当前心跳值，供下一轮比较。 */
        l_heartLast_u16 = l_peerBase_t.cpldHeart_u16;
    }

    /* 轮询窗口内未观察到心跳变化，则判定链路未在线。 */
    return INVALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:CPLDStateInit
 *
 * 【功能描述】CPLD状态初始化
 * 			在初始化中，等待CPLD开始工作
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】        NONE
 * 【返回】               NONE
 */
/* ***************************************************************** */
static void CPLDBusHandshakeInit(void)
{
    Uint16 l_temp_1_u16 = 0U;  /* 临时数据1 */
    Uint16 l_timeCnt_u16 = 0U;  /* 时间计数 */
    Uint16 l_handshakeOk_u16 = INVALID; /* 握手结果 */
    Uint16 l_powerupReady_u16 = INVALID; /* 上电完成标志 */

    /***********读取CPLD上电完成标识*************/
    l_timeCnt_u16 = 0U;  /* 从0开始累计等待拍数 */

    /* 获取CPLD上电完成标识 */
    l_temp_1_u16 = HardXintUint16Read(CPLD_ADDR_R_POWERUP_FLAG);

    /* 200ms内查询CPLD上电标志，上电完成后跳出循环 */
    while((l_timeCnt_u16 < CPLD_POWERUP_WAIT_MAX) && (CPLD_DATA_POWERUP_FLAG != l_temp_1_u16))
    {
		/* 喂狗 */
		CycleDogFeed();

        /* 延时10ms */
        delayUs(CPLD_POWERUP_WAIT_DELAY_US);

        l_timeCnt_u16 = l_timeCnt_u16 + 1U; /* 累计已经等待的10ms拍数 */

        /* 获取新的CPLD状态 */
        l_temp_1_u16 = HardXintUint16Read(CPLD_ADDR_R_POWERUP_FLAG);
    }

    /* 只有读到规定上电完成标识，才允许进入后续握手流程。 */
    if(CPLD_DATA_POWERUP_FLAG == l_temp_1_u16)
    {
        l_powerupReady_u16 = VALID;
    }

    /* CPLD上电未就绪时，不再继续握手，直接向外上报失败。 */
    if(INVALID == l_powerupReady_u16)
    {
        s_initCpldBusHandshakeResult_u16 = INVALID;
        s_initCpldCcdlHeartResult_u16 = INVALID;
        HardXintUint16Write(CPLD_ADDR_W_HANDSHAKE_FLAG, CPLD_DATA_HANDSHAKE_INVALID);
        return;
    }

    /* 上电确认完成后，再按任务书执行双阶段握手。 */
    l_timeCnt_u16 = 0U;

    /* 先等待双阶段握手成功，避免在长轮询中反复放大CCDL心跳检测耗时 */
    while(l_timeCnt_u16 < CPLD_HANDSHAKE_WAIT_CYCLES_MAX)
    {
		/* 喂狗 */
		CycleDogFeed();

        if(VALID == CPLDHandshake())
        {
            /* 双阶段握手一旦成功即可结束轮询，后续转入CCDL心跳确认。 */
            l_handshakeOk_u16 = VALID;
            break;
        }

        /* 当前轮未满足握手成功，延时1ms后再发起下一轮 */
        delayUs(CPLD_HANDSHAKE_WAIT_DELAY_US);
        l_timeCnt_u16 = l_timeCnt_u16 + 1U; /* 计数加1 */
    }

    /* 握手失败则直接上报失败 */
    if(INVALID == l_handshakeOk_u16)
    {
        s_initCpldBusHandshakeResult_u16 = INVALID;
        s_initCpldCcdlHeartResult_u16 = INVALID;
        HardXintUint16Write(CPLD_ADDR_W_HANDSHAKE_FLAG, CPLD_DATA_HANDSHAKE_INVALID);
        return;
    }

    s_initCpldBusHandshakeResult_u16 = VALID;
    s_initCpldCcdlHeartResult_u16 = INVALID;
    HardXintUint16Write(CPLD_ADDR_W_HANDSHAKE_FLAG, CPLD_DATA_HANDSHAKE_VALID);
}

/* ***************************************************************** */
/**
 * 【函数名】:CPLDCcdlHeartCheckUpdate
 *
 * 【功能描述】在完成通道内寄存器握手后，更新经CPLD的CCDL心跳检测结果。
 *            该步骤依赖对端基础帧在线，适合放在长同步后执行。
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【返回】      无
 */
/* ***************************************************************** */
static void CPLDCcdlHeartCheckUpdate(void)
{
    if(VALID != s_initCpldBusHandshakeResult_u16)
    {
        s_initCpldCcdlHeartResult_u16 = INVALID;
        return;
    }

    if(VALID == CPLDCCDLHeartCheck())
    {
        s_initCpldCcdlHeartResult_u16 = VALID;

    }
    else
    {
        s_initCpldCcdlHeartResult_u16 = INVALID;

    }
}

/* ***************************************************************** */
/**
 * 【函数名】:InitStatusGet
 *
 * 【功能描述】获取初始化/热重连阶段统一状态。
 *            统一返回CPLD寄存器握手结果、CPLD CCDL心跳结果和板间资格结果。
 *            热重连流程已并入INIT统一判型，hotResyncActive兼容返回固定无效。
 * 【输入参数说明】vp_status_t：状态输出指针
 * 【输出参数说明】无
 * 【返回】      无
 */
/* ***************************************************************** */
void InitStatusGet(InitStatus_t *vp_status_t)
{
    if(NULL == vp_status_t)
    {
        return;
    }

    vp_status_t->cpldBusHandshakeOk_u16 = s_initCpldBusHandshakeResult_u16;
    vp_status_t->cpldCcdlHeartOk_u16 = s_initCpldCcdlHeartResult_u16;
    vp_status_t->interChHandshakeOk_u16 = s_initInterChHandshakeResult_u16;
    vp_status_t->hotResyncActive_u16 = INVALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:InterChCCDLHeartCheck
 *
 * 【功能描述】按当前启动模式执行通道间CCDL基础帧心跳检查：
 *            仅使用CCDL-SCI链路；
 *            每次读取前触发一次基础帧发送，若心跳字(CPLDHeart)发生变化则成功；
 *            冷启动时作为“长同步后的二次确认”，热启动时作为“复位重连主判据”。
 * 【输入参数说明】无
 * 【输出参数说明】无
 * 【返回】      VALID-读取成功 / INVALID-读取失败
 */
/* ***************************************************************** */
static Uint16 InterChCCDLHeartCheck(void)
{
    Uint16 l_readCnt_u16 = 0U;
    Uint16 l_tailSendCnt_u16 = 0U;                         /* 成功后继续补发基础帧的次数 */
    Uint16 l_tailWaitCnt_u16 = 0U;                         /* 补发基础帧时的发送等待计数 */
    Uint16 l_hasLastHeart_u16 = INVALID;                     /* 是否已有上一拍心跳值 */
    Uint16 l_heartLast_u16 = 0U;                             /* 上一拍心跳值 */
    PeerBaseStatus_t l_peerBase_t;                           /* 当前轮读取到的对端基础帧状态 */

    /* 初始化/热复位前先清场本地SCI-CCDL收发状态，避免沿用残留半帧和旧队列。 */
    CommCCDLSCIChannelReset();

    for(l_readCnt_u16 = 0U; l_readCnt_u16 < INTERCH_CCDL_HEART_WAIT_MAX; l_readCnt_u16++)
    {
        Uint16 l_waitCnt_u16 = 0U;

        /* 初始化阶段按轮询窗口重复起发基础帧，避免只给运行中对端一个 30ms 检测窗口。 */
        CommCCDLSCIDataStartSend();
        while((RS422_COMM_TX_FLAG_ON == CommCCDL422TxFlagGet ()) &&
              (l_waitCnt_u16 < INTERCH_CCDL_SCI_TX_WAIT_MAX))
        {
            /* 初始化阶段的SCI发送需要靠轮询持续推进直到TX空闲。 */
            CommCCDLSCIDataSend();
            delayUs(INTERCH_CCDL_SCI_TX_WAIT_DELAY_US);
            CycleDogFeed();
            l_waitCnt_u16 = l_waitCnt_u16 + 1U;
        }

        /* 给对端发送完成和本端SCI接收缓冲留出传播窗口，再读取本轮基础帧。 */
        delayUs(CCDL_HEART_POLL_DELAY_US);

        /* 拉取当前SCI链路的基础帧并更新解析镜像。 */
        CommCCDLDataBuffRead(COMM_CCDL_SCI);
        CommCCDLFrameProcess(COMM_CCDL_SCI);
        l_peerBase_t = CommCCDLPeerBaseGet(COMM_CCDL_SCI);

        if(VALID == l_hasLastHeart_u16)
        {
            /* 连续两拍只要出现心跳跳变或帧计数推进，都认为对端基础帧在线。 */
            if((l_peerBase_t.cpldHeart_u16 != l_heartLast_u16) ||
               (VALID == CommCCDLPeerBaseAdvancedGet(COMM_CCDL_SCI)))
            {
                /* 首次确认成功后，再补发两拍基础帧，降低“本端先退出、对端还差最后一拍”时的竞态窗口。 */
                for(l_tailSendCnt_u16 = 0U; l_tailSendCnt_u16 < 2U; l_tailSendCnt_u16++)
                {
                    l_tailWaitCnt_u16 = 0U;
                    CommCCDLSCIDataStartSend();
                    while((RS422_COMM_TX_FLAG_ON == CommCCDL422TxFlagGet()) &&
                          (l_tailWaitCnt_u16 < INTERCH_CCDL_SCI_TX_WAIT_MAX))
                    {
                        CommCCDLSCIDataSend();
                        delayUs(INTERCH_CCDL_SCI_TX_WAIT_DELAY_US);
                        CycleDogFeed();
                        l_tailWaitCnt_u16 = l_tailWaitCnt_u16 + 1U;
                    }
                    delayUs(CCDL_HEART_POLL_DELAY_US);
                }
                return VALID;
            }
        }
        else
        {
            /* 第一拍只记录初值，不立即给失败结论。 */
            l_hasLastHeart_u16 = VALID;
        }
        /* 保存当前心跳，供下一拍对比。 */
        l_heartLast_u16 = l_peerBase_t.cpldHeart_u16;

        /* 每轮读取前已经显式等待传播窗口，这里不再额外补第二个等待。 */
    }

    /* 轮询窗口内未观察到心跳跳变，则判通道间基础帧未建立。 */
    return INVALID;
}

/* ***************************************************************** */
/**
 * 【函数名】:UsrInit
 *
 * 【功能描述】执行用户初始化相关操作。
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】              NONE
 ***************************************************************** */
static void UsrInit(void)
{
    /* CCDL通信初始化  */
    CommCCDLInit();

	/* 模拟量数据初始化  */
    AnaDataInit();

    /*离散量初始化 */
    IoDataInit();

    /* ARINC422通信模块初始化 */
    Comm422Init();

    /* ARINC429通信模块初始化 */
    /* 两路429职责不同，分别单独初始化。 */
    Comm429KZZZInit();
    Comm429RIUInit();

    /* 周期BIT信息初始化  */
    IFBITDataInit();

	/* MBIT信息初始化 */
    MBITDataInit();

    /* 启动ADC转换 */
    AdcStartConv(ADC_SEQ1);

    /* FLASH特定数据记录初始化  */
    SpeDataRecordInit();

    /* 数据记录初始化 */
    FlashDataRecordInit();

	/* 同步数据初始化 */
	SynchroInit();

	/* 余度管理初始化 */
	RedundancyInit();

    /* 系统控制初始化  */
    /* 这里会建立控制模块默认输出和初始状态机。 */
    SysConInit();
}

/* ***************************************************************** */
/**
 * 【函数名】:Init
 *
 * 【功能描述】实现系统初始化和用户程序初始化
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       NONE
 * 【返回】               NONE
 ***************************************************************** */
void Init(void)
{
	Uint16 l_delayCnt_u16    = 0U; /* 延时计数    */
	Uint16 l_startUpMode_u16 = 0U; /* 启动模式    */
	SynWholeInform_TypeDef l_syncResult_t;  /* 同步数据 */

    /* 关闭全局中断 */
    DINT;

	/* 早期启动阶段只执行“冷启动首拍是否需要先软件复位一次”的判断，不访问CPLD。 */
	StartUpEarlyColdResetOnce();

    /* 关闭看门狗 */
    wDogDisable();

    /* 系统时钟初始化 */
    initPLL(DSP_SYSCLK,EXTERN_CLOCK);

    /* 外设时钟使能 */
    periClkEnable();

	/* XINTF接口初始化 */
    InitXintf();

	/* PIE中断控制初始化  */
    InitPieCtrl();

    /* PIE中断向量表初始化  */
    InitPieVectTable();

    /* GPIO引脚初始化 */
    GPIOInit();

	EALLOW;
    /* 初始化期间不接受NMI，避免外设状态尚未稳定时进入异常路径。 */
	XIntruptRegs.XNMICR.bit.ENABLE = OFF;
	EDIS;

    /* 定时器初始化 */
    InitCpuTimers();

    /* SCI口初始化 */
    SciInit();

#if DSP_MCBSP_A | DSP_MCBSP_B
    /* McBsp初始化 */
    mcbspInit();
#endif

#if DSP_ADC
    /* ADC初始化 */
    AdcInit();
#endif

#if DSP_SPI
    /* SPI用于外部Flash等器件，先于用户层存储模块初始化。 */
    SpiInit();
#endif

#if DSP_ECAN_A | DSP_ECAN_B
    eCanInit();
#endif

#if DSP_FLASH

    /* 完成RAM函数拷贝 */
    MemCopy(&RamfuncsLoadStart, &RamfuncsLoadEnd, &RamfuncsRunStart);

    /* FLASH初始化 */
    InitFlash();

#endif
	/*用户程序初始化 */
	UsrInit();

#if DSP_WDOG
    /* 使能DSP片上看门狗 */
    wDogEnable(WDOG_TIME,WDOG_MODE);
#endif

#if DSP_TIMER_0
    /* 打开Timer0定时器 */
    StartCpuTimer0();
#endif

#if DSP_TIMER_1
    /* 打开Timer1定时器 */
    StartCpuTimer1();
#endif

#if DSP_TIMER_2
    /* 打开Timer2定时器 */
    StartCpuTimer2();
#endif

	/* 打开NMI中断  */
	EALLOW;
    /* 基础时钟、外设和用户模块都完成后，再恢复NMI响应。 */
	XIntruptRegs.XNMICR.bit.ENABLE = ON;
	EDIS;

	/* 使能全局中断 */
    /* 从这里开始系统进入可响应中断的正常初始化后半段。 */
    EINT;

    /* 初始化后半段决策树（高层）：
     * A. 先完成通道内CPLD握手，再读取/回写启动标志并判定冷/热启动；
     * B. 冷启动：长同步 -> 稳定等待 -> CCDL心跳确认 -> PuBIT -> 主备判型/轮值提交；
     * C. 热启动：跳过长同步与PuBIT，走热重连心跳确认 + 主备判型；
     * D. 仅冷启动且长同步成功时才追加短同步。 */

	/*清除CPLD握手成功标记*/
		HardXintUint16Write(CPLD_ADDR_W_HANDSHAKE_FLAG, CPLD_DATA_HANDSHAKE_INVALID);
    /* 通道内CPLD握手 */
    CPLDBusHandshakeInit();

    if(VALID == s_initCpldBusHandshakeResult_u16)
    {
        /* 仅在确认CPLD已上电且总线握手成功后，再读取/回写启动标志。 */
        StartUpModeJudge();
    }

    /* 冷/热启动模式会决定后续是否做长同步和热重连。 */
    l_startUpMode_u16 = StartUpModeGet();

	/* 冷启动时通过GPIO执行长同步；热启动/复位重连不再要求对端回到初始化态配合同步。 */
	if(COLD_POW_STARTUP_MODE == l_startUpMode_u16)
	{
		/* 长同步 */
		FrameSyn(SYNC_LONG_ID,LONG_SYNC_TIME);

		/* 获取长同步结果 */
		l_syncResult_t = SynWholeInfGet(SYNC_LONG_ID);
	}
	else
	{
		/* 热启动场景跳过长同步，板间重连主要依赖CCDL基础帧心跳。 */
		l_syncResult_t.faltCod_un16.bit.synRelRslt = SYNC_ERR;

	}

		/* 初始化后保留稳定等待，给冷启动同步收尾和热启动重连前的外设状态恢复留出时间。
		 * 注意：该等待窗口对冷/热路径都执行，用于统一后续CCDL心跳检查的起点。 */
		while(l_delayCnt_u16 < INIT_POST_LONG_SYNC_DELAY_MAX)
	{
        /* 周期喂狗  */
    	CycleDogFeed();

        /* 延时10ms */
        delayUs(INIT_POST_LONG_SYNC_DELAY_US);

        l_delayCnt_u16 = l_delayCnt_u16 + 1U; /* 延时计数加1 */
	}

    /* 经CPLD的CCDL心跳依赖对端基础帧在线，放到长同步后的稳定窗口再做。 */
    CPLDCcdlHeartCheckUpdate();

	if(COLD_POW_STARTUP_MODE == l_startUpMode_u16)
	{
        /* 冷启动要求“长同步 + CCDL心跳”都成功。 */
		if(SYNC_NORM == l_syncResult_t.faltCod_un16.bit.synRelRslt)
		{
			if(VALID == InterChCCDLHeartCheck())
			{
				s_initInterChHandshakeResult_u16 = VALID;
			}
			else
			{
				s_initInterChHandshakeResult_u16 = INVALID;
			}
		}
		else
		{
			s_initInterChHandshakeResult_u16 = INVALID;
		}

		/* 冷启动路径在通道内/通道间握手完成后，再执行PuBIT与启动期主备判型。 */
		(void)PuBITTest();

		/* 建立启动期默认主备：优先服从对端稳定角色，否则按冷启动轮值落位；轮值异常时保守回退到通道1优先。 */
		ChTypeJudge();

        if (VALID == s_initInterChHandshakeResult_u16)
        {
            ChTypeRoundRobinCommitColdStartup();
        }
	}
	else
	{
        s_initInterChHandshakeResult_u16 = InterChCCDLHeartCheck();

		/* 热复位路径跳过上电BIT，但主备判型与冷启动使用同一套Flash+CCDL协商逻辑。 */
		PuBITHotResetBypassInit();
        ChTypeJudge();
	}

	/* 仅冷启动长同步成功时再做短同步；热启动重连不要求运行中的对端回到GPIO同步流程。 */
	if((COLD_POW_STARTUP_MODE == l_startUpMode_u16) &&
	   (SYNC_NORM == l_syncResult_t.faltCod_un16.bit.synRelRslt))
	{
		/* 短同步 */
		FrameSyn(SYNC_SHORT_ID,SHORT_SYNC_TIME);
	}
}

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
