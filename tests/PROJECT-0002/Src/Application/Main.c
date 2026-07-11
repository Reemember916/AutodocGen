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
 * 文件名称:    Main.c
 *
 * 文件日期:   REDACTED
 *
 *
 * 【程序版本】   V0.0.0.1
 *
 * 【功能描述】实现软件主控功能
 * 【其他说明】无
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 *
 *********************************************************************************/

#include "Global.h"
#include "Main.h"

/* ******************************************************************************** */
/* 配置第1步：配置任务时间片数量和索引！！！ */
/* 任务时间片宏定义、本地变量及函数原型已迁移至 Main.h，此处仅保留实现数据。 */

Uint32 s_taskTimeData_u32[TASK_TIME_NUM];           /* 任务时间数据                                            */
Uint32 s_syncTime_u32 = 0UL;  /* 同步时间           */

/* ******************************** */
/* 配置第2步：配置任务时间片执行时刻！！！ */

/* 任务配置时间，以同步完成时间为基准时间，配置每个任务片开始执行时刻         */
Uint32 s_taskTimeConf_u32[TASK_TIME_NUM] =
       {
              0UL,     /* 0任务偏移时间配置  数据采集          */
            600UL,     /* 1任务偏移时间配置   通信接收         */
            3200UL,    /* 2任务偏移时间配置   系统控制         */
            4400UL,    /* 3任务偏移时间配置   通信发送         */
            8350UL,    /* 4任务偏移时间配置   维护通信发送  */
            8580UL,    /* 5任务偏移时间配置   数据存储         */
            9980UL     /* 6任务偏移时间配置 心跳灯闪烁        */
       };

/* 敲黑板划重点：
 * 		1）同步时间初始化时应为（定时器微秒计数值 + 控制周期），保证程序进入主循环后立刻进行一次通道同步和任务片时间更新！！！  */

/* ******************************************************************************** */
/* 定义本地变量 */
Uint16 s_ConCnt_u16 = 0U;       /* 系统控制计数   */
Uint16 s_ccdlTxPhase_u16 = 0U;  /* CCDL运行期发送相位(100ms内10个10ms子相位) */
Uint16 s_429RIUTxCnt_u16 = 0U;  /* RIU通信发送计数 */
Uint16 s_429RIURxCnt_u16 = 0U;  /* RIU通信接收计数 */
Uint16 s_ledCount_u16 = 0U;     /* 心跳灯闪烁计数      */
Uint16 s_SovConCnt_u16 = 0U;    /* 电磁阀控制计数      */
Uint16 s_CarbinConCnt_u16 = 0U; /* 舱门控制计数      */
Uint16 s_WDogCnt_u16 = 0U;      /* 喂狗计数      */
TaskTimeDriftInfo_t s_taskTimeDriftInfo_t; /* 任务片漂移统计数据 */

/* ******************************************************************************** */

/* ***************************************************************** */
/**
 * 【函数名】:TaskTimeDriftReset
 *
 * 【功能描述】任务片漂移统计复位
 * 【输入参数说明】v_windowTime_u32 ---- 统计窗口长度，单位us，0表示使用默认窗口
 * 【输出参数说明】NONE
 * 【其他说明】       只清统计结果，不调整任务片原有调度时间
 * 【返回】           NONE
 */
/* ***************************************************************** */
void TaskTimeDriftReset(Uint32 v_windowTime_u32)
{
    /* 这里只清观察用的数据，任务片下一次什么时候执行仍由 s_taskTimeData_u32 决定。 */
    memset(&s_taskTimeDriftInfo_t, 0, sizeof(s_taskTimeDriftInfo_t));

    if(0UL == v_windowTime_u32)
    {
        s_taskTimeDriftInfo_t.windowTime_u32 = TASK_TIME_DRIFT_WINDOW_US;
    }
    else
    {
        s_taskTimeDriftInfo_t.windowTime_u32 = v_windowTime_u32;
    }
}

/* ***************************************************************** */
/**
 * 【函数名】:TaskTimeDriftWindowFinish
 *
 * 【功能描述】结束当前任务片漂移统计窗口
 * 【输入参数说明】v_nowTime_u32 ---- 当前Timer1计数
 * 【输出参数说明】NONE
 * 【其他说明】       保存本窗口结果，并从当前时刻开始下一轮统计
 * 【返回】           NONE
 */
/* ***************************************************************** */
static void TaskTimeDriftWindowFinish(Uint32 v_nowTime_u32)
{
    Uint16 l_index_u16 = 0U;

    /* 把这一段时间的统计值留在 last 里，下一段重新从 0 开始累计。 */
    for(l_index_u16 = 0U; l_index_u16 < TASK_TIME_NUM; l_index_u16++)
    {
        s_taskTimeDriftInfo_t.lastMaxDrift_u32[l_index_u16] =
            s_taskTimeDriftInfo_t.currMaxDrift_u32[l_index_u16];
        s_taskTimeDriftInfo_t.lastSampleCnt_u32[l_index_u16] =
            s_taskTimeDriftInfo_t.currSampleCnt_u32[l_index_u16];
        s_taskTimeDriftInfo_t.currMaxDrift_u32[l_index_u16] = 0UL;
        s_taskTimeDriftInfo_t.currSampleCnt_u32[l_index_u16] = 0UL;
    }

    s_taskTimeDriftInfo_t.windowStart_u32 = v_nowTime_u32;
    s_taskTimeDriftInfo_t.windowDone_u16 = VALID;
    s_taskTimeDriftInfo_t.windowCount_u16++;
}

/* ***************************************************************** */
/**
 * 【函数名】:TaskTimeDriftSample
 *
 * 【功能描述】记录任务片本次执行相对到期时刻晚了多少
 * 【输入参数说明】v_taskIndex_u16 ---- 任务片索引
 *                 v_planTime_u32 ---- 本任务片当前保存的调度基准时间
 *                 v_nowTime_u32 ---- 本轮循环锁存的Timer1时间
 * 【输出参数说明】NONE
 * 【其他说明】       只做观测，不补偿、不重排任务片
 * 【返回】           NONE
 */
/* ***************************************************************** */
void TaskTimeDriftSample(Uint16 v_taskIndex_u16, Uint32 v_planTime_u32, Uint32 v_nowTime_u32)
{
    Uint32 l_elapsed_u32 = 0UL;
    Uint32 l_drift_u32 = 0UL;

    if(v_taskIndex_u16 >= TASK_TIME_NUM)
    {
        return;
    }

    if(VALID != s_taskTimeDriftInfo_t.active_u16)
    {
        /* 等第一个任务片真正跑起来后再开始计窗口，不把上电初始化时间算进去。 */
        s_taskTimeDriftInfo_t.active_u16 = VALID;
        s_taskTimeDriftInfo_t.windowStart_u32 = v_nowTime_u32;
        if(0UL == s_taskTimeDriftInfo_t.windowTime_u32)
        {
            s_taskTimeDriftInfo_t.windowTime_u32 = TASK_TIME_DRIFT_WINDOW_US;
        }
    }

    if(CpuTimer1DeltaGet(s_taskTimeDriftInfo_t.windowStart_u32, v_nowTime_u32) >=
       s_taskTimeDriftInfo_t.windowTime_u32)
    {
        /* 一个统计窗口到时后换一页记录，任务片本身的节拍不在这里改。 */
        TaskTimeDriftWindowFinish(v_nowTime_u32);
    }

    /* 外层已经确认任务片到期才会调用本函数。
     * 刚好到期时 elapsed 等于 TASK_TIME_PERIOD，
     * 多出来的部分就是本次任务片被主循环拖晚的时间。 */
    l_elapsed_u32 = CpuTimer1DeltaGet(v_planTime_u32, v_nowTime_u32);
    if(l_elapsed_u32 >= TASK_TIME_PERIOD)
    {
        l_drift_u32 = l_elapsed_u32 - TASK_TIME_PERIOD;
    }

    if(l_drift_u32 > s_taskTimeDriftInfo_t.currMaxDrift_u32[v_taskIndex_u16])
    {
        s_taskTimeDriftInfo_t.currMaxDrift_u32[v_taskIndex_u16] = l_drift_u32;
    }
    if(l_drift_u32 > s_taskTimeDriftInfo_t.totalMaxDrift_u32[v_taskIndex_u16])
    {
        s_taskTimeDriftInfo_t.totalMaxDrift_u32[v_taskIndex_u16] = l_drift_u32;
    }

    s_taskTimeDriftInfo_t.currSampleCnt_u32[v_taskIndex_u16]++;
}

/* ***************************************************************** */
/**
 * 【函数名】:TaskTimeDriftInfoGet
 *
 * 【功能描述】获取任务片漂移统计数据
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       返回内部统计结构体，只供调试/维护观测读取
 * 【返回】           任务片漂移统计数据指针
 */
/* ***************************************************************** */
const TaskTimeDriftInfo_t * TaskTimeDriftInfoGet(void)
{
    return &s_taskTimeDriftInfo_t;
}

/* ***************************************************************** */
/**
 * 【函数名】:TimeCountInit
 *
 * 【功能描述】时间计数初始化
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】       同步时间初始化为定时器1微秒值加上任务主周期时间，用于实现进入while周期后立刻执行一次同步！！！
 * 【返回】               NONE
 */
/* ***************************************************************** */
void TimeCountInit(void)
{
    Uint16 l_index_u16       = 0U;  /* 循环索引         */

    /* 任务时间初始化 */
    for(l_index_u16 = 0U;l_index_u16 < TASK_TIME_NUM;l_index_u16++)
    {
        /* 任务时间初始化为定时器1微秒计数值   */
        s_taskTimeData_u32[l_index_u16] = ReadCpuTimer1Counter();
    }

    s_syncTime_u32  = (TASK_TIME_PERIOD + ReadCpuTimer1Counter());  /* 同步时间     */
    TaskTimeDriftReset(TASK_TIME_DRIFT_WINDOW_US);
}

/* ***************************************************************** */
/**
 *    [函数名]	 CycleDogFeed
 *
 *    [功能描述]	 周期看门狗喂狗
 *    			周期进行外部硬件喂狗和内部软件喂狗
 *    [输入参数说明] NONE
 *	  [输出参数说明] NONE
 *    [其他说明]	 NONE
 *    [返回]		 NONE
 */
/* ***************************************************************** */
void CycleDogFeed(void)
{
    /* 喂硬件狗 */
    GPIOToggleNum(GPIO_OUT_DSP_HARDWOG);

    /* 喂软件狗 */
    wDogFeed();
}

/* ***************************************************************** */
/**
 * 【函数名】:main
 *
 * 【功能描述】实现软件控制功能
 * 【输入参数说明】NONE
 * 【输出参数说明】NONE
 * 【其他说明】        NONE
 * 【返回】               NONE
 */
/* ***************************************************************** */
void main(void)
{
    Uint16 l_index_u16 = 0U; /* 循环索引  */
    Uint16 l_frameIndex_u16 = RS422_COMM_FRAM_NOT_EXIST; /* 维护422帧索引 */
    Uint16 l_ledToggleCount_u16 = LED_TOGGLE_COUNT_BACKUP; /* LED翻转门限 */
    const ConData_t *lc_p_conData_t = NULL; /* 系统控制数据指针 */
    Uint32 l_timerNow_u32 = 0UL; /* Timer1当前计数值 */

    /* 完成硬件、通信链路和应用状态初始化。 */
    Init();

    /* 冷启动和热复位都在Init阶段完成统一主备判型，进入主循环时直接建立本地任务时基。 */
    TimeCountInit();

    while(1)
    {
        /* 先锁存本轮循环入口时的Timer1计数，供各任务统一按同一时间基准判定是否到期。 */
        l_timerNow_u32 = ReadCpuTimer1Counter();

        /* 优先在主循环空闲点推进一次延迟落盘。
         * 该过程可能触发FLASH擦写，不能放到ISR或后续需要严格节拍的分支里执行。 */
        SpeDataFlushPending();

        /* NMI请求进入后，先等待挂起的特定数据落盘完成，再转入看门狗复位。
         * 这里直接continue，确保复位等待阶段不再执行任何常规调度任务。 */
        if(VALID == NMIResetRequestGet())
        {
            if(INVALID == SpeDataPendingExist())
            {
                /* 挂起落盘项已清空后，解除软件请求并触发看门狗复位。 */
                NMIResetRequestClear();
                WDogResetTrigger();
            }

            continue;
        }

        lc_p_conData_t = ConDataGet();

        /*********************************************************/
        /* 通道同步：
         * 每个100ms主周期更新一次同步基准，并按配置偏移重装各任务的触发时刻。 */
        if(CpuTimer1DeltaGet(s_syncTime_u32, l_timerNow_u32) >= TASK_TIME_PERIOD )
        {
            /* 帧同步。无论本拍是否锁定成功，都在周期边界重建一次本地时基；
             * 区别仅在于：成功时这是“同步重建”，失败时这是“失同步降级重建”。 */
            FrameSyn(SYNC_FRAME_ID,FRAME_SYNC_TIME);

            if(VALID == SyncFrameHealthyGet())
            {
                /* 同步健康：按锁相成功语义刷新100ms主周期基准。 */
                s_syncTime_u32 = ReadCpuTimer1Counter();
            }
            else
            {
                /* 同步异常：继续按本地自由运行语义刷新100ms主周期基准，
                 * 具体降级状态由同步模块内部的 faultCnt/degraded 标志对外提供。 */
                s_syncTime_u32 = ReadCpuTimer1Counter();
            }

            /*****************************************/
            /* 划分任务时间片  */
            for(l_index_u16 = 0U;l_index_u16 < TASK_TIME_NUM;l_index_u16++)
            {
                /* 更新任务执行时间 */
                s_taskTimeData_u32[l_index_u16] = s_syncTime_u32 + ( TASK_TIME_PERIOD - s_taskTimeConf_u32[l_index_u16]);
            }
        }

        /*********************************************************/
        /* 任务0：数据采集
         * 按10ms节拍执行模拟量/离散量采集，并在该节拍内维护周期喂狗计数。 */
        if(CpuTimer1DeltaGet(s_taskTimeData_u32[TASK_TIME_INDEX_SAMPLE], l_timerNow_u32) >= TASK_TIME_PERIOD)
        {
            /* 先用旧的时间基准算本次迟到量，下面重装时间后这个基准就会被覆盖。 */
            TaskTimeDriftSample(TASK_TIME_INDEX_SAMPLE,
                                s_taskTimeData_u32[TASK_TIME_INDEX_SAMPLE],
                                l_timerNow_u32);

            /* 更新任务时间，用于实现每10ms执行一次 */
            s_taskTimeData_u32[TASK_TIME_INDEX_SAMPLE] = (TASK_TIME_PERIOD - TASK_DATASAPLE_TIME_PERIOD) + ReadCpuTimer1Counter();

            /* 每10ms时喂狗计数加1 */
            s_WDogCnt_u16 = s_WDogCnt_u16 + 1U;

            /* 每40ms进行1次喂狗 */
            if(s_WDogCnt_u16 >= 4U)
            {
                /* 计数清零 */
                s_WDogCnt_u16 = 0U;

                /* 周期喂狗 */
                CycleDogFeed();
            }

            if(SYS_STATE_4POWERDOWN != lc_p_conData_t->sysState_u16)
            {
                /* 掉电态下停止常规模拟量采集，仅保留电源相关离散量刷新。 */
                AnaDataObtain();
            }

            IoDataObtain();
        }

        /*********************************************************/
        /* 任务1：通信接收
         * 按20ms节拍轮询维护422与CPLD-CCDL接收，再按100ms聚合一次429整帧处理。
         * SCI-CCDL接收改由任务3/任务4跟随SCI泵送节拍排空，避免RX FIFO堆积。 */
        if(CpuTimer1DeltaGet(s_taskTimeData_u32[TASK_TIME_INDEX_COMM_RX], l_timerNow_u32) >= TASK_TIME_PERIOD)
        {
            TaskTimeDriftSample(TASK_TIME_INDEX_COMM_RX,
                                s_taskTimeData_u32[TASK_TIME_INDEX_COMM_RX],
                                l_timerNow_u32);

            /* 更新任务时间  */
            s_taskTimeData_u32[TASK_TIME_INDEX_COMM_RX] = (TASK_TIME_PERIOD - TASK_COMM_RX_TIME_PERIOD) + ReadCpuTimer1Counter();

            if(SYS_STATE_4POWERDOWN == lc_p_conData_t->sysState_u16)
            {
                s_429RIURxCnt_u16 = 0U;
            }
            else
            {
                s_429RIURxCnt_u16 = s_429RIURxCnt_u16 + 1U;

                Comm422DataBuffRead(COMM422_MAINT_ID);
                l_frameIndex_u16 = Comm422FrameProcess(COMM422_MAINT_ID);

                if(RS422_COMM_FRAM_NOT_EXIST != l_frameIndex_u16)
                {
                    MaintRxDataProcess(COMM422_MAINT_ID, l_frameIndex_u16);
                }

                Comm422FrameCleanup(COMM422_MAINT_ID);

                CommCCDLDataBuffRead(COMM_CCDL_CPLD);
                CommCCDLFrameProcess(COMM_CCDL_CPLD);

                if(s_429RIURxCnt_u16 >= 5U)
                {
                    s_429RIURxCnt_u16 = 0U;
                    Comm429KZZZDataProcess();
                    Comm429RIUDataProcess();
                }
            }
        }

        /*********************************************************/
        /* 任务2：系统控制
         * 按50ms节拍推进控制任务；其中每两个节拍完成一次BIT、余度、状态机与记录缓存更新。
         *
         * 说明：
         * 1) 本任务片本身是50ms触发一次；
         * 2) s_ConCnt_u16 在 0/1 间翻转，只有计数到1时才真正执行 MBIT/IFBIT + Redundancy + SysControl + FlashRecordDataUpdate；
         * 3) 因此“控制主链”实际执行节拍是100ms，而不是50ms。 */
        if(CpuTimer1DeltaGet(s_taskTimeData_u32[TASK_TIME_INDEX_CON], l_timerNow_u32) >= TASK_TIME_PERIOD)
        {
            TaskTimeDriftSample(TASK_TIME_INDEX_CON,
                                s_taskTimeData_u32[TASK_TIME_INDEX_CON],
                                l_timerNow_u32);

            /* 更新任务时间，用于实现每周期执行一次 */
            s_taskTimeData_u32[TASK_TIME_INDEX_CON] = (TASK_TIME_PERIOD - TASK_CON_TIME_PERIOD) + ReadCpuTimer1Counter();

            if(SYS_STATE_4POWERDOWN == lc_p_conData_t->sysState_u16)
            {
                s_ConCnt_u16 = 0U;
                SysControlPowerDown();
            }
            else
            {
                s_ConCnt_u16 = s_ConCnt_u16 + 1U;  /* 系统控制计数加1 */

                if( 1U == s_ConCnt_u16)
                {
                    /* 执行拍：100ms主链（BIT/余度/状态机/记录缓存）都在这个分支内推进。 */
                    lc_p_conData_t = ConDataGet();
                    if(SYS_STATE_3MAINTG == lc_p_conData_t->sysState_u16)
                    {
                        MBITTest();
                    }
                    else
                    {
                        IFBITTest();
                    }

                    Redundancy();
                    SysControl();
                    FlashRecordDataUpdate();
                }
                else
                {
                    /* 跳过拍：仅把计数翻回0，保持下一拍再执行主链。 */
                    s_ConCnt_u16 = 0U;
                }
            }

        }

        /*********************************************************/
        /* 任务3：通信发送
         * 按10ms节拍推进CCDL分页发送与SCI泵送；累计到50ms后驱动一次发送调度。
         * 其中SysControlOut仍维持既有50ms调度，RIU在发送函数内部再限到ICD要求的10次/S，
         * KZZZ内部继续按ICD拆分为200ms周期量和事件量。 */
        if(CpuTimer1DeltaGet(s_taskTimeData_u32[TASK_TIME_INDEX_COMM_TX], l_timerNow_u32) >= TASK_TIME_PERIOD)
        {
            TaskTimeDriftSample(TASK_TIME_INDEX_COMM_TX,
                                s_taskTimeData_u32[TASK_TIME_INDEX_COMM_TX],
                                l_timerNow_u32);

            /* 更新任务时间 */
            s_taskTimeData_u32[TASK_TIME_INDEX_COMM_TX] = (TASK_TIME_PERIOD - TASK_COMM_TX_TIME_PERIOD) + ReadCpuTimer1Counter();

            if(SYS_STATE_4POWERDOWN == lc_p_conData_t->sysState_u16)
            {
                s_429RIUTxCnt_u16 = 0U;
            }
            else
            {
                s_429RIUTxCnt_u16 = s_429RIUTxCnt_u16 + 1U;

                CommCCDLRuntimeTxPhaseProcess(s_ccdlTxPhase_u16);
                CommCCDLSCIDataSend();
                CommCCDLDataBuffRead(COMM_CCDL_SCI);
                CommCCDLFrameProcess(COMM_CCDL_SCI);
                s_ccdlTxPhase_u16 = (s_ccdlTxPhase_u16 + 1U) % 10U;

                if(s_429RIUTxCnt_u16 >= 5U)
                {
                    s_429RIUTxCnt_u16 = 0U;

                    lc_p_conData_t = ConDataGet();
                    if(CON_OUT_STATE_VALID == lc_p_conData_t->ConOutData_t.conOutState_u16)
                    {
                        Comm429RIUPeriodInfoTx();
                        Comm429KZZZPeriodInfoTx();
                    }
                    SysControlOut();
                }
            }

        }

        /*********************************************************/
        /* 任务4：维护通信发送
         * 按10ms节拍查询维护发送；仅在输出授权有效时打包并发送维护报文，同时补一个SCI发送时隙。 */
        if(CpuTimer1DeltaGet(s_taskTimeData_u32[TASK_TIME_INDEX_MAINT_TX], l_timerNow_u32) >= TASK_TIME_PERIOD)
        {
            TaskTimeDriftSample(TASK_TIME_INDEX_MAINT_TX,
                                s_taskTimeData_u32[TASK_TIME_INDEX_MAINT_TX],
                                l_timerNow_u32);

            /* 更新任务时间，用于实现每周期执行一次 */
            s_taskTimeData_u32[TASK_TIME_INDEX_MAINT_TX] = (TASK_TIME_PERIOD - TASK_MAINT_TX_TIME_PERIOD) + ReadCpuTimer1Counter();

            if(SYS_STATE_4POWERDOWN != lc_p_conData_t->sysState_u16)
            {
                lc_p_conData_t = ConDataGet();
                if(CON_OUT_STATE_VALID == lc_p_conData_t->ConOutData_t.conOutState_u16)
                {
                    CommMaintTxDataPack();
                    CommMaintCommSend();
                }
                CommCCDLSCIDataSend();
                CommCCDLDataBuffRead(COMM_CCDL_SCI);
                CommCCDLFrameProcess(COMM_CCDL_SCI);
            }


        }

        /*********************************************************/
        /* 任务5：数据存储
         * 每个主周期执行一次后台存储搬运，单次推进一个固定存储步长。 */
        if(CpuTimer1DeltaGet(s_taskTimeData_u32[TASK_TIME_INDEX_STORE], l_timerNow_u32) >= TASK_TIME_PERIOD)
        {
            TaskTimeDriftSample(TASK_TIME_INDEX_STORE,
                                s_taskTimeData_u32[TASK_TIME_INDEX_STORE],
                                l_timerNow_u32);

            /* 更新任务时间，用于实现每周期执行一次 */
            s_taskTimeData_u32[TASK_TIME_INDEX_STORE] = ReadCpuTimer1Counter();

            if(SYS_STATE_4POWERDOWN != lc_p_conData_t->sysState_u16)
            {
                FlashDataStore();
            }
        }

        /*********************************************************/
        /* 任务6：心跳指示
         * 每个主周期维护一次心跳计数，并按主备角色切换呼吸灯翻转门限。 */
        if(CpuTimer1DeltaGet(s_taskTimeData_u32[TASK_TIME_INDEX_LED], l_timerNow_u32) >= TASK_TIME_PERIOD)
        {
            TaskTimeDriftSample(TASK_TIME_INDEX_LED,
                                s_taskTimeData_u32[TASK_TIME_INDEX_LED],
                                l_timerNow_u32);

            l_ledToggleCount_u16 = LED_TOGGLE_COUNT_BACKUP;
            lc_p_conData_t = ConDataGet();

            /* 更新任务时间，用于实现每周期执行一次 */
            s_taskTimeData_u32[TASK_TIME_INDEX_LED] = ReadCpuTimer1Counter();

            /* 每100ms时心跳灯闪烁计数加1 */
            s_ledCount_u16 = s_ledCount_u16 + 1U;

            /*DSP心跳周期翻转*/
            GPIOToggleNum(GPIO_OUT_DSP_HEART);

            if(ROLE_MASTER == lc_p_conData_t->runtimeRole_u16)
            {
                l_ledToggleCount_u16 = LED_TOGGLE_COUNT_MASTER;
            }


            /* 备份态保持常速闪烁，主控态提升为快闪，方便外观区分当前授权角色。 */
            if(s_ledCount_u16 >= l_ledToggleCount_u16)
            {
                /* 心跳灯闪烁计数清零 */
                s_ledCount_u16 = 0U;
                /* DSP心跳GPIO电平翻转  */
                GPIOToggleNum(GPIO_OUT_LED_CON);
            }
        }
    }
}
/* ========================================================================== */
/* END OF FILE */
/* ========================================================================== */
