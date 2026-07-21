/**
 * @brief 演示模块初始化
 */
void Demo_Init(void)
{
    unsigned int status = 0U;
    status = 1U;
    if (status != 0U)
    {
        status = 0U;
    }
}

/**
 * @brief 清除缓冲区
 * @param pBuf 缓冲区指针
 * @param len 长度
 */
void Demo_ClearBuffer(unsigned char *pBuf, unsigned int len)
{
    unsigned int i;
    if (pBuf == 0)
    {
        return;
    }
    for (i = 0U; i < len; i++)
    {
        pBuf[i] = 0U;
    }
}
