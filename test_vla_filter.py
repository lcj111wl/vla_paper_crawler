#!/usr/bin/env python3
"""
测试 VLA 过滤逻辑
"""

def is_vla_related(title: str, abstract: str) -> bool:
    """严格检查论文是否真正与 VLA 相关"""
    text = (title + " " + abstract).lower()
    
    # 规则1: 明确包含 Vision-Language-Action
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


# 测试用例
test_cases = [
    # 应该通过的
    ("MAP-VLA: Memory-Augmented Prompting for Vision-Language-Action Model", "", True),
    ("Audio-VLA: Adding Contact Audio to VLA model", "", True),
    ("Training VLA policy for robotic manipulation", "", True),
    ("A new VLA framework for embodied AI", "", True),
    ("", "We propose a Vision-Language-Action model for robots", True),
    ("", "Our vision language action approach improves performance", True),
    
    # 应该被过滤的
    ("Large Vision-Language Models for Visual Understanding", "", False),
    ("LVLM: A new approach to vision-language tasks", "", False),
    ("Embodied AI with foundation models", "", False),
    ("Multimodal Learning for Robotics", "", False),
    ("VLA in finance: value-at-risk analysis", "", False),  # VLA 但非机器人上下文
]

print("=" * 80)
print("测试 VLA 严格过滤逻辑")
print("=" * 80)

passed = 0
failed = 0

for title, abstract, expected in test_cases:
    result = is_vla_related(title, abstract)
    status = "✅ PASS" if result == expected else "❌ FAIL"
    
    if result == expected:
        passed += 1
    else:
        failed += 1
    
    display = title if title else abstract[:60]
    print(f"{status} | {display}")
    if result != expected:
        print(f"       Expected: {expected}, Got: {result}")

print("=" * 80)
print(f"测试结果: {passed} 通过, {failed} 失败")
print("=" * 80)
