#!/usr/bin/env python3
"""
VLA 论文过滤模块
提供通用的 VLA 相关性检查函数
"""


def is_vla_related(title: str, abstract: str) -> bool:
    """严格检查论文是否真正与 VLA 相关

    必须满足以下条件之一：
    1. 标题或摘要中包含 "Vision-Language-Action"（任意大小写、连字符形式）
    2. 标题或摘要中同时包含 "VLA" 且明确是 "model" 或 "policy" 或 "robot"
    3. 标题或摘要中包含完整短语 "vision language action"

    Args:
        title: 论文标题
        abstract: 论文摘要

    Returns:
        是否与 VLA 相关
    """
    text = (title + " " + abstract).lower()

    # 规则1: 明确包含 Vision-Language-Action（各种形式）
    vla_full_patterns = [
        "vision-language-action",
        "vision language action",
        "visionlanguageaction"
    ]
    if any(pattern in text for pattern in vla_full_patterns):
        return True

    # 规则2: 包含 VLA 且明确是模型/策略/机器人相关
    if " vla " in text or text.startswith("vla ") or text.endswith(" vla"):
        vla_contexts = [
            "vla model",
            "vla policy",
            "vla agent",
            "vla robot",
            "vla framework",
            "vla architecture"
        ]
        if any(ctx in text for ctx in vla_contexts):
            return True

    return False
