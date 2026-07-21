"""C 语言"保护区无损合并引擎"。

每次正向生成新 C 代码文件时，不能覆盖工程师在文件中手写的业务逻辑。
本模块通过 ``/* USER CODE BEGIN: <Block_ID> */`` /
``/* USER CODE END: <Block_ID> */`` 保护区标签，
实现旧代码中手写内容的提取与新骨架代码的精确注入。

兼容 Windows 7 / Python 3.8+，仅依赖标准库。
"""

from __future__ import annotations

import re
import sys
from typing import Dict


# ── 正则表达式 ──────────────────────────────────────────────────
# 匹配保护区标签，允许标签周围有合理空格，捕获 Block_ID 和中间内容
# re.DOTALL 确保 . 匹配换行符（跨行内容）
_BLOCK_RE = re.compile(
    r"/\*\s*USER\s+CODE\s+BEGIN:\s*(\S+)\s*\*/"
    r"(.*?)"
    r"/\*\s*USER\s+CODE\s+END:\s*\1\s*\*/",
    re.DOTALL,
)


class UserCodeMerger:
    """C 代码保护区无损合并引擎。

    用法::

        merger = UserCodeMerger()
        user_blocks = merger.extract(old_c_code)
        merged = merger.merge(new_generated_code, user_blocks)
    """

    # ── 公开 API ──────────────────────────────────────────────────

    def extract(self, source_code: str) -> Dict[str, str]:
        """从旧代码中提取所有保护区的内容。

        参数
        ----
        source_code : str
            旧版本 C 源码全文

        返回
        ----
        dict[str, str]
            ``{Block_ID: 纯净的手写代码内容（保留原有缩进和换行）}``
        """
        if not source_code:
            return {}
        blocks: Dict[str, str] = {}
        for match in _BLOCK_RE.finditer(source_code):
            block_id = match.group(1)
            # 直接保留原始内容，不 trim——保留工程师的缩进和换行风格
            content = match.group(2)
            blocks[block_id] = content
        return blocks

    def merge(
        self,
        new_generated_code: str,
        user_blocks: Dict[str, str],
    ) -> str:
        """将手写代码块注入新生成的骨架代码中。

        参数
        ----
        new_generated_code : str
            新生成的骨架代码（含保护区标签但内容为空）
        user_blocks : dict[str, str]
            从旧代码中提取的 ``{Block_ID: 手写代码}``

        返回
        ----
        str
            合并后的完整代码字符串
        """
        if not new_generated_code:
            return ""

        # 扫描新骨架中声明的所有 Block_ID
        declared_ids: set[str] = set()
        for match in _BLOCK_RE.finditer(new_generated_code):
            declared_ids.add(match.group(1))

        # 检查孤儿块：user_blocks 有但新骨架没有的 Block_ID
        for block_id in user_blocks:
            if block_id not in declared_ids:
                print(
                    f"[UserCodeMerger] WARNING: 旧代码中存在保护区 '{block_id}'，"
                    f"但新生成的骨架中已删除该区块——手写代码将被丢弃。",
                    file=sys.stderr,
                )

        # 替换函数：对每个匹配到的保护区，填入对应的手写代码
        def _replace(match: re.Match) -> str:
            block_id = match.group(1)
            # 保留 BEGIN 标签，注入用户代码，保留 END 标签
            replacement = user_blocks.get(block_id, "")
            return (
                f"/* USER CODE BEGIN: {block_id} */"
                f"{replacement}"
                f"/* USER CODE END: {block_id} */"
            )

        return _BLOCK_RE.sub(_replace, new_generated_code)

    def extract_to_file(self, source_code: str, output_path: str) -> None:
        """提取保护区并写入 JSON 文件（方便人工审查）。"""
        import json
        blocks = self.extract(source_code)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(blocks, f, ensure_ascii=False, indent=2)

    def merge_from_file(
        self,
        new_generated_code: str,
        user_blocks_path: str,
    ) -> str:
        """从 JSON 文件加载手写代码块并合并。"""
        import json
        with open(user_blocks_path, "r", encoding="utf-8") as f:
            user_blocks = json.load(f)
        return self.merge(new_generated_code, user_blocks)