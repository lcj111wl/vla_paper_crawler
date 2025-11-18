# PDF 多模态解析说明

## 🎯 功能概述

现在爬虫支持**完整 PDF 解析**，包括：
- ✅ **文本提取**：前 30 页的完整文本
- ✅ **图片提取**：最多 10 张关键图片（架构图、实验结果图、对比图表）
- ✅ **多模态评分**：大模型可以"看到"图片并进行深度分析

---

## 🔧 技术实现

### 1. 图片提取策略
```python
# 自动提取 PDF 图片
- 扫描前 30 页的所有图片
- 过滤小图（< 5KB，通常是 logo/icon）
- 按大小排序，优先保留大图（更重要）
- 转为 base64 编码（data URL 格式）
```

### 2. 多模态输入格式
```json
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "论文元数据和全文..."
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "data:image/png;base64,iVBORw0KG...",
        "detail": "high"
      }
    }
  ]
}
```

### 3. 支持的模型
| 模型 | 视觉支持 | 推荐用途 |
|------|----------|----------|
| `qwen-vl-plus` | ✅ | **推荐**，中文友好，价格适中 |
| `qwen-plus` | ❌ | 兼容，只分析文本（不看图） |
| `gpt-4o` | ✅ | 最强，但价格高 |
| `gpt-4-turbo` | ✅ | 较强，价格中等 |
| `gpt-4o-mini` | ❌ | 便宜，只分析文本 |

---

## ⚙️ 配置参数

```json
{
  "llm_model": "qwen-vl-plus",       // 必须使用支持vision的模型
  "llm_use_full_pdf": true,           // 启用PDF全文解析
  "llm_pdf_max_pages": 30,            // 提取前30页
  "llm_pdf_max_chars": 50000,         // 最多50k字符
  "llm_pdf_extract_images": true,     // 提取图片（新增）
  "llm_pdf_max_images": 10,           // 最多10张图片（新增）
  "llm_timeout": 120                  // 超时120秒（多模态需要更长）
}
```

### 参数调优建议
- **提高准确性**：增加 `llm_pdf_max_images` 到 15-20
- **降低成本**：减少 `llm_pdf_max_images` 到 3-5（只提取最关键的图）
- **加快速度**：设置 `llm_pdf_extract_images: false`（回退纯文本）

---

## 🧪 测试方法

### 快速测试（1篇论文）
```bash
./test_multimodal.sh
```

### 手动测试
```bash
python paper_crawler.py config_lcj.json
```

### 检查日志
成功提取图片时会显示：
```
📄 下载并解析 PDF (含图片): ...
PDF 提取了 8 张图片（共扫描 30 页）
✅ PDF 解析成功 (30 页, 45123 字符, 8 张图片)
```

---

## 📊 效果对比

### 纯文本模式（qwen-plus）
```json
{
  "score": 78,
  "rationale": "论文提出了新的VLA架构，实验部分提到在多个任务上测试..."
}
```

### 多模态模式（qwen-vl-plus）
```json
{
  "score": 85,
  "rationale": "论文提出了新的VLA架构（见Figure 2架构图，采用分层设计）。从Figure 5实验结果图可以看到，该方法在7个任务上均超过baseline 15%以上，特别是在长horizon任务上表现突出（Table 3）。消融实验（Figure 6）证明了各模块的有效性..."
}
```

**关键差异**：
- ✅ 多模态评分**更具体**（引用图表编号）
- ✅ 多模态评分**更准确**（能看到实验曲线、架构图）
- ✅ 多模态评分**更可信**（有图片证据支撑）

---

## 💰 成本估算

### 通义千问（DashScope）
- `qwen-plus`（纯文本）：¥0.004/1K tokens
- `qwen-vl-plus`（多模态）：¥0.008/1K tokens（图片按分辨率计费）

### 单篇论文成本
- 文本（50k字符 ≈ 35k tokens）：¥0.14
- 图片（10张，平均1024px）：约 ¥0.10
- **总计**：约 ¥0.24/篇（带图片）vs ¥0.14/篇（纯文本）

### 月度成本（每天10篇）
- 纯文本：¥0.14 × 10 × 30 = ¥42/月
- 多模态：¥0.24 × 10 × 30 = ¥72/月

---

## ⚠️ 注意事项

1. **模型兼容性**
   - 必须使用支持 vision 的模型（qwen-vl-plus/gpt-4o）
   - 如果用 qwen-plus，请设置 `llm_pdf_extract_images: false`

2. **超时设置**
   - 多模态推理比纯文本慢 2-3 倍
   - 建议设置 `llm_timeout: 120`

3. **图片质量**
   - 自动过滤小图（< 5KB）
   - 优先保留大图（架构图、结果图通常较大）
   - 如果图片模糊，大模型可能无法准确分析

4. **限流问题**
   - 多模态 API 限流更严格
   - 建议设置 `llm_call_interval_s: 2.0`（增加调用间隔）

---

## 🔍 故障排查

### 问题1：API 返回 400 错误
```
原因：模型不支持视觉输入（如 qwen-plus）
解决：切换到 qwen-vl-plus 或设置 llm_pdf_extract_images: false
```

### 问题2：评分没有引用图片
```
原因：图片提取失败或未发送
解决：检查日志是否显示"PDF 提取了 X 张图片"
```

### 问题3：超时错误
```
原因：多模态推理耗时长
解决：增加 llm_timeout 到 120-180 秒
```

### 问题4：图片过多导致超限
```
原因：某些 PDF 包含大量图片
解决：降低 llm_pdf_max_images 到 5-8 张
```

---

## 🚀 下一步优化

- [ ] 支持表格识别（OCR）
- [ ] 支持公式识别（LaTeX）
- [ ] 智能图片筛选（只提取架构图+结果图）
- [ ] 图片压缩（降低分辨率以减少token消耗）
- [ ] 支持更多多模态模型（Claude 3.5 Sonnet等）

---

## 📚 参考资料

- [通义千问 VL-Plus 文档](https://help.aliyun.com/zh/dashscope/developer-reference/vl-plus-quick-start)
- [OpenAI Vision API 文档](https://platform.openai.com/docs/guides/vision)
- [PyMuPDF 图片提取教程](https://pymupdf.readthedocs.io/en/latest/recipes-images.html)
