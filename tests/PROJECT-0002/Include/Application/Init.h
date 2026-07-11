#ifndef INIT_H_
#define INIT_H_

/* 热启动重定相参数定义 */
#define INIT_RESYNC_EXPECT_PERIOD_US      (100000UL)  /* 热启动重定相期望基础帧周期 */
#define INIT_RESYNC_PERIOD_TOLERANCE_US   (20000UL)   /* 热启动重定相周期容差 */
#define INIT_RESYNC_WAIT_MAX_MS           (300U)      /* 热启动重定相最大等待窗口 */
#define INIT_RESYNC_POLL_DELAY_US         (3333UL)    /* 热启动重定相轮询间隔 */

typedef struct _InitResyncContext
{
    Uint16 active_u16;          /* 热启动重定相流程激活标志 */
    Uint16 gotFirstFrame_u16;   /* 已捕获第一帧标志 */
    Uint16 gotSecondFrame_u16;  /* 已捕获第二帧标志 */
    Uint16 peerFrameCntLast_u16;/* 上一拍对端基础帧帧计数 */
    Uint16 peerHeartLast_u16;   /* 上一拍对端基础帧心跳 */
    Uint32 startTime_u32;       /* 重定相启动时刻(ms) */
    Uint32 firstFrameTime_u32;  /* 第一帧到达时本地计时器 */
    Uint32 secondFrameTime_u32; /* 第二帧到达时本地计时器 */
}InitResyncContext_t;

typedef struct _InitStatus
{
    Uint16 cpldBusHandshakeOk_u16; /* 初始化阶段通道内与CPLD的寄存器双阶段握手结果 */
    Uint16 cpldCcdlHeartOk_u16;    /* 初始化阶段与CPLD的CCDL心跳检测结果 */
    Uint16 interChHandshakeOk_u16; /* 初始化阶段板间基础帧在线确认结果，仅用于状态上报和诊断 */
    Uint16 hotResyncActive_u16;    /* 兼容保留字段：热重连流程已并入INIT统一判型，固定返回INVALID */
}InitStatus_t;

extern void   Init(void);
extern void   InitStatusGet(InitStatus_t *vp_status_t);

#endif /* INIT_H_ */

/* =========================================================================== */
/* END OF FILE */
/* =========================================================================== */
