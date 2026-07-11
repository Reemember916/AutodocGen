def extract_texts_from_p(p):
    """
    统一抽取文本（普通段落 + 文本框），不依赖 w: 前缀命名空间。
    返回多行文本列表（第一行通常为段落主文本，其后可能是文本框内容）。
    """
    texts = []

    def collect_text_from_node(node):
        # 不用 .//w:t，改用 local-name()='t'
        ts = node.xpath(".//*[local-name()='t']")
        t = "".join(x.text or "" for x in ts).strip()
        if t:
            texts.append(t)

    # 主体文字
    collect_text_from_node(p)

    # 文本框（Word / WPS 常见两种结构）
    for p2 in p.xpath(".//*[local-name()='txbxContent']//*[local-name()='p']"):
        collect_text_from_node(p2)

    for p2 in p.xpath(".//*[local-name()='txbx']//*[local-name()='txbxContent']//*[local-name()='p']"):
        collect_text_from_node(p2)

    return texts
