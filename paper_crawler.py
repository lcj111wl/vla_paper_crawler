#!/usr/bin/env python3
"""
自动爬取 VLA (Vision-Language-Action) 领域最新论文并写入 Notion 数据库
支持数据源：arXiv API, Semantic Scholar API
定时运行：每 3 天执行一次
"""

import os
import sys
import json
import time
import logging
import requests
import math
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path

# VLA 过滤模块
from vla_filter import is_vla_related

# PDF 解析
try:
    import fitz  # PyMuPDF
    PDF_PARSING_AVAILABLE = True
except ImportError:
    PDF_PARSING_AVAILABLE = False
    fitz = None

# 导入图片提取器
try:
    from figure_extractor import FigureExtractor
    FIGURE_EXTRACTION_AVAILABLE = True
except ImportError:
    FIGURE_EXTRACTION_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("图片提取模块不可用")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('paper_crawler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ===================== 缺失字段补全辅助函数 =====================

def _derive_pdf_link(paper: Dict[str, Any]) -> Optional[str]:
    """从 DOI 或 URL 推导 PDF 链接

    Args:
        paper: 论文数据字典

    Returns:
        PDF 链接或 None
    """
    # 如果已有 PDF Link，返回 None
    if paper.get('pdf_url'):
        return None

    # 1. 尝试从 arXiv ID 构建
    doi = paper.get('doi', '')
    if doi.lower().startswith('arxiv:'):
        arxiv_id = doi.split(':', 1)[1]
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    # 2. 从 URL 推导（如果是 arxiv 网址）
    url = paper.get('url', '')
    if 'arxiv.org' in url:
        if '/abs/' in url:
            arxiv_id = url.split('/abs/')[-1].split('v')[0]  # 移除版本号
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        elif '/pdf/' in url:
            return url  # 已经是 PDF 链接

    return None


def _fetch_institutions_from_semantic_scholar(paper: Dict[str, Any],
                                               ss_api_base: str = "https://api.semanticscholar.org/graph/v1") -> List[str]:
    """从 Semantic Scholar 查询作者机构（发表论文的学校/企业等）

    Args:
        paper: 论文数据字典
        ss_api_base: Semantic Scholar API 基础 URL

    Returns:
        机构名称列表（如 MIT, Stanford, Google DeepMind 等）
    """
    institutions = []

    try:
        # 优先级1: 通过 DOI 查询（最准确）
        doi = paper.get('doi', '')
        paper_id = None

        if doi and doi.startswith('10.'):
            paper_id = f"DOI:{doi}"
            logger.debug(f"使用 DOI 查询机构: {paper_id}")
        elif doi and doi.lower().startswith('arxiv:'):
            arxiv_id = doi.split(':', 1)[1]
            paper_id = f"arXiv:{arxiv_id}"
            logger.debug(f"使用 arXiv ID 查询机构: {paper_id}")

        # 优先级2: 通过 URL 提取 DOI/arXiv
        if not paper_id:
            url = paper.get('url', '')
            if 'arxiv.org' in url:
                if '/abs/' in url:
                    arxiv_id = url.split('/abs/')[-1].split('v')[0]
                    paper_id = f"arXiv:{arxiv_id}"
                    logger.debug(f"从 URL 提取 arXiv ID: {paper_id}")
            elif 'doi.org' in url:
                import re
                match = re.search(r'doi\.org/(10\.\S+)', url)
                if match:
                    paper_id = f"DOI:{match.group(1)}"
                    logger.debug(f"从 URL 提取 DOI: {paper_id}")

        # 优先级3: 通过标题搜索（最不准确）
        if not paper_id:
            title = paper.get('title')
            if not title:
                logger.warning(f"论文缺少 DOI 和标题，无法查询机构")
                return institutions

            logger.debug(f"使用标题搜索机构: {title[:50]}...")
            search_url = f"{ss_api_base}/paper/search"
            params = {"query": title, "limit": 1, "fields": "paperId"}
            response = requests.get(search_url, params=params, timeout=20)

            if response.status_code == 429:
                logger.warning("Semantic Scholar API 限流，跳过机构查询")
                return institutions

            response.raise_for_status()
            data = response.json()

            if data.get('data'):
                paper_id = data['data'][0].get('paperId')
                logger.debug(f"搜索到论文 ID: {paper_id}")
            else:
                logger.warning(f"未找到论文: {title[:50]}")
                return institutions

        # 查询论文详情（包含作者及其机构）
        paper_url = f"{ss_api_base}/paper/{paper_id}"
        params = {"fields": "authors.affiliations,authors.name"}

        response = requests.get(paper_url, params=params, timeout=20)

        if response.status_code == 429:
            logger.warning("Semantic Scholar API 限流")
            return institutions

        if response.status_code == 404:
            logger.warning(f"论文不存在: {paper_id}")
            return institutions

        response.raise_for_status()
        paper_data = response.json()

        # 提取作者机构
        authors = paper_data.get('authors', [])
        logger.info(f"📚 论文有 {len(authors)} 位作者")

        for idx, author in enumerate(authors[:15]):  # 限制前 15 位作者
            author_name = author.get('name', 'Unknown')
            affiliations = author.get('affiliations', [])

            if not affiliations:
                logger.debug(f"  作者 {idx+1}/{len(authors)}: {author_name} - 无机构信息")
                continue

            logger.debug(f"  作者 {idx+1}/{len(authors)}: {author_name} - {len(affiliations)} 个机构")

            for aff in affiliations:
                # affiliations 可能是字符串或字典
                if isinstance(aff, str):
                    name = aff
                elif isinstance(aff, dict):
                    name = aff.get('name') or aff.get('displayName')
                else:
                    continue

                if name and name not in institutions:
                    institutions.append(name)
                    logger.debug(f"    ✓ 添加机构: {name}")

                if len(institutions) >= 15:
                    break

            if len(institutions) >= 15:
                break

        if institutions:
            logger.info(f"✅ 找到 {len(institutions)} 个机构: {', '.join(institutions[:3])}...")
        else:
            logger.warning(f"⚠️  未找到任何机构信息")

    except Exception as e:
        logger.error(f"❌ Semantic Scholar 机构查询失败: {e}")

    return institutions


def detect_missing_fields(papers: List[Dict[str, Any]],
                         check_fields: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
    """检测论文的缺失字段

    Args:
        papers: 论文列表（来自 fetch_existing_papers）
        check_fields: 要检查的字段列表

    Returns:
        {
            'missing_pdf_url': [{'page_id': '...', 'title': '...', ...}, ...],
            'missing_institutions': [...],
            ...
        }
    """
    if check_fields is None:
        check_fields = ['pdf_url', 'doi', 'institutions', 'citations', 'recommend_score', 'recommend_rationale']

    missing = {f'missing_{field}': [] for field in check_fields}

    for paper in papers:
        if not paper.get('page_id'):
            continue

        for field in check_fields:
            value = paper.get(field)
            is_missing = False

            # 缺失的定义
            if value is None:
                is_missing = True
            elif isinstance(value, str) and not value.strip():
                is_missing = True
            elif isinstance(value, list) and len(value) == 0:
                is_missing = True
            # 注意：0 对于数字字段不算缺失

            if is_missing:
                missing[f'missing_{field}'].append({
                    'page_id': paper['page_id'],
                    'title': paper.get('title', 'Unknown'),
                    'doi': paper.get('doi'),
                    'url': paper.get('url'),
                    'pdf_url': paper.get('pdf_url'),
                    'year': paper.get('year'),
                    'authors': paper.get('authors'),
                    'abstract': paper.get('abstract'),
                })

    # 统计
    stats = {k: len(v) for k, v in missing.items() if v}
    if stats:
        logger.info(f"缺失字段统计: {json.dumps(stats, ensure_ascii=False)}")

    return missing


def patch_missing_fields(notion_client: "NotionClient",
                        papers_with_missing: List[Dict],
                        field_type: str,
                        enricher: Optional["MetricsEnricher"] = None,
                        llm_engine: Optional["LLMScoringEngine"] = None,
                        max_papers: int = 10) -> Tuple[int, int]:
    """补全指定类型的缺失字段

    Args:
        notion_client: NotionClient 实例
        papers_with_missing: 缺失字段的论文列表
        field_type: 要补全的字段类型
        enricher: MetricsEnricher 实例（用于 citations/institutions）
        llm_engine: LLMScoringEngine 实例（用于 recommend_score）
        max_papers: 最多补全多少篇论文

    Returns:
        (成功数, 失败数)
    """
    success, failed = 0, 0
    papers_to_process = papers_with_missing[:max_papers]

    for idx, paper in enumerate(papers_to_process):
        try:
            updates = {}
            page_id = paper['page_id']

            # 优先级1: PDF Link（快速，从 arXiv/DOI 构建）
            if field_type == 'pdf_url':
                pdf_url = _derive_pdf_link(paper)
                if pdf_url:
                    updates['PDF Link'] = {'url': pdf_url}
                    logger.info(f"✅ 生成 PDF Link: {paper['title'][:40]} → {pdf_url[:60]}")

            # 优先级2: Citations（Semantic Scholar API）
            elif field_type == 'citations' and enricher:
                cites, infl_cites = enricher.enrich_semantic_scholar(paper)
                if cites is not None:
                    updates['Citations'] = {'number': int(cites)}
                    if infl_cites is not None:
                        updates['Influential Citations'] = {'number': int(infl_cites)}
                    logger.info(f"✅ 添加引用数: {paper['title'][:40]} → {cites} citations")

            # 优先级2+: Institutions（Semantic Scholar API）
            elif field_type == 'institutions':
                institutions = _fetch_institutions_from_semantic_scholar(paper)
                if institutions:
                    updates['Institutions'] = {
                        'multi_select': [{'name': inst[:100]} for inst in institutions[:15]]
                    }
                    logger.info(f"✅ 添加机构: {paper['title'][:40]} → {len(institutions)} 个机构")

            # 优先级3: Recommend Score（LLM）
            elif field_type == 'recommend_score' and llm_engine:
                score, rationale = llm_engine.score_paper(paper)
                if score is not None:
                    updates['Recommend Score'] = {'number': float(score)}
                    if rationale:
                        updates['Recommend Rationale'] = {
                            'rich_text': [{'text': {'content': str(rationale)[:2000]}}]
                        }
                    logger.info(f"✅ LLM 评分: {paper['title'][:40]} → {score}")
                    time.sleep(0.5)  # LLM API 延迟

            # 执行更新
            if updates:
                if notion_client.update_paper_fields(page_id, updates):
                    success += 1
                else:
                    failed += 1

            time.sleep(0.3)  # Notion API 限流保护

        except Exception as e:
            logger.error(f"补全字段失败 ({field_type}): {paper.get('title', 'Unknown')[:40]} - {e}")
            failed += 1

    logger.info(f"📊 {field_type} 补全完成: {success} 成功, {failed} 失败")
    return success, failed


# ===================== Notion API 客户端 =====================


class NotionClient:
    """Notion API 客户端"""
    
    def __init__(self, token: str, database_id: str):
        self.token = token
        self.database_id = database_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        self.base_url = "https://api.notion.com/v1"
        self._db_properties_cache: Optional[Dict[str, Any]] = None

    def _get_database(self) -> Dict[str, Any]:
        if self._db_properties_cache is None:
            resp = requests.get(f"{self.base_url}/databases/{self.database_id}", headers=self.headers, timeout=15)
            resp.raise_for_status()
            props = resp.json().get("properties", {}) or {}
            self._db_properties_cache = props
        return self._db_properties_cache or {}

    def ensure_metrics_properties(self):
        """确保数据库存在用于指标的属性，如果缺失则自动创建。

        创建的属性：
          - Citations: number
          - Influential Citations: number
          - Impact (2yr mean): number
        """
        desired = {
            "Citations": {"number": {}},
            "Influential Citations": {"number": {}},
            "Impact (2yr mean)": {"number": {}}
        }
        try:
            props = self._get_database()
            missing = {k: v for k, v in desired.items() if k not in props}
            if not missing:
                return
            patch_body = {"properties": missing}
            resp = requests.patch(
                f"{self.base_url}/databases/{self.database_id}",
                headers=self.headers,
                json=patch_body,
                timeout=15
            )
            resp.raise_for_status()
            # 失效缓存
            self._db_properties_cache = None
            logger.info("已为数据库添加指标属性: %s", ", ".join(missing.keys()))
        except Exception as e:
            logger.warning("无法自动添加指标属性（忽略，仍尝试写入已存在字段）: %s", e)
    
    def ensure_enrichment_properties(self):
        """确保数据库存在扩展属性（机构 & 推荐评分）。

        创建的属性：
          - Institutions: multi_select
          - Recommend Score: number
          - Recommend Rationale: rich_text
        """
        desired = {
            "Institutions": {"multi_select": {}},
            "Recommend Score": {"number": {}},
            "Recommend Rationale": {"rich_text": {}}
        }
        try:
            props = self._get_database()
            missing = {k: v for k, v in desired.items() if k not in props}
            if not missing:
                return
            patch_body = {"properties": missing}
            resp = requests.patch(
                f"{self.base_url}/databases/{self.database_id}",
                headers=self.headers,
                json=patch_body,
                timeout=15
            )
            resp.raise_for_status()
            self._db_properties_cache = None
            logger.info("已为数据库添加扩展属性: %s", ", ".join(missing.keys()))
        except Exception as e:
            logger.warning("无法自动添加扩展属性（忽略）: %s", e)
    
    def check_duplicate(self, title: Optional[str] = None, doi: Optional[str] = None, url: Optional[str] = None) -> bool:
        """检查论文是否已存在（通过标题/DOI/URL）"""
        filters = []

        if title:
            filters.append({
                "property": "Name",
                "title": {"equals": title}
            })
        if doi:
            filters.append({
                "property": "DOI",
                "rich_text": {"equals": doi}
            })
        if url:
            filters.append({
                "property": "userDefined:URL",
                "url": {"equals": url}
            })

        if not filters:
            return False

        query_body = {
            "filter": {
                "or": filters
            }
        }

        try:
            response = requests.post(
                f"{self.base_url}/databases/{self.database_id}/query",
                headers=self.headers,
                json=query_body,
                timeout=10
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            return len(results) > 0
        except Exception as e:
            logger.error(f"检查重复时出错: {e}")
            return False

    def filter_duplicates(self, papers: List[Dict]) -> List[Dict]:
        """批量检查并过滤重复论文，在指标增强和LLM评分之前调用以节省成本

        Args:
            papers: 论文列表

        Returns:
            去重后的论文列表
        """
        unique_papers = []
        duplicate_count = 0

        for paper in papers:
            if not self.check_duplicate(
                title=paper.get('title'),
                doi=paper.get('doi'),
                url=paper.get('url')
            ):
                unique_papers.append(paper)
            else:
                duplicate_count += 1
                logger.info(f"⊘ 论文已存在，过滤: {paper.get('title', 'Unknown')[:60]}")

        logger.info(f"✅ 过滤完成: {len(unique_papers)} 篇新论文 / {len(papers)} 篇总论文 (过滤 {duplicate_count} 篇重复)")
        return unique_papers

    def fetch_existing_papers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """从 Notion 数据库查询已有论文信息

        Args:
            limit: 每页查询数量（Notion 一次最多返回100条）

        Returns:
            论文列表，每个论文包含 page_id 和所有关键字段
        """
        papers = []
        has_more = True
        start_cursor = None

        # 关键字段映射（Notion → Python）
        field_mapping = {
            'Name': 'title',
            'userDefined:URL': 'url',
            'PDF Link': 'pdf_url',
            'DOI': 'doi',
            'Year': 'year',
            'Citations': 'citations',
            'Influential Citations': 'influential_citations',
            'Institutions': 'institutions',
            'Recommend Score': 'recommend_score',
            'Recommend Rationale': 'recommend_rationale',
            'Framework Diagram': 'framework_diagram',
            'Authors': 'authors',
            'Abstract': 'abstract',
        }

        while has_more:
            try:
                query_body = {"page_size": min(limit, 100)}
                if start_cursor:
                    query_body["start_cursor"] = start_cursor

                response = requests.post(
                    f"{self.base_url}/databases/{self.database_id}/query",
                    headers=self.headers,
                    json=query_body,
                    timeout=15
                )
                response.raise_for_status()
                data = response.json()

                for page in data.get('results', []):
                    paper_dict = {'page_id': page['id']}
                    properties = page.get('properties', {})

                    # 提取字段值
                    for notion_field, py_field in field_mapping.items():
                        if notion_field not in properties:
                            paper_dict[py_field] = None
                            continue

                        prop = properties[notion_field]
                        value = None

                        # 根据字段类型解析
                        prop_type = prop.get('type')
                        if prop_type == 'title':
                            value = ''.join([t.get('text', {}).get('content', '')
                                           for t in prop.get('title', [])])
                        elif prop_type == 'url':
                            value = prop.get('url')
                        elif prop_type == 'rich_text':
                            value = ''.join([t.get('text', {}).get('content', '')
                                           for t in prop.get('rich_text', [])])
                        elif prop_type == 'number':
                            value = prop.get('number')
                        elif prop_type == 'multi_select':
                            value = [opt.get('name') for opt in prop.get('multi_select', [])]

                        paper_dict[py_field] = value

                    papers.append(paper_dict)

                # 分页
                has_more = data.get('has_more', False)
                start_cursor = data.get('next_cursor')

                if has_more:
                    logger.info(f"已查询 {len(papers)} 篇论文（继续翻页）...")
                    time.sleep(0.3)  # API 限流保护

            except Exception as e:
                logger.error(f"查询已有论文失败: {e}")
                break

        logger.info(f"✅ 查询完成，共 {len(papers)} 篇论文")
        return papers

    def update_paper_fields(self, page_id: str, updates: Dict[str, Any]) -> bool:
        """更新论文页面的字段（通用PATCH方法）

        Args:
            page_id: Notion 页面 ID
            updates: 字段更新字典，格式如：
                    {
                        'PDF Link': {'url': 'https://...'},
                        'Citations': {'number': 100},
                        'Institutions': {'multi_select': [{'name': 'MIT'}, ...]},
                    }

        Returns:
            是否成功
        """
        if not updates:
            return True

        try:
            response = requests.patch(
                f"{self.base_url}/pages/{page_id}",
                headers=self.headers,
                json={"properties": updates},
                timeout=15
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"更新页面字段失败 ({page_id[:8]}...): {e}")
            return False

    def batch_update_papers(self, updates: List[Tuple[str, Dict[str, Any]]],
                           delay_s: float = 0.3) -> int:
        """批量更新多个论文页面

        Args:
            updates: [(page_id, fields_dict), ...]
            delay_s: 每次请求间的延迟（秒）

        Returns:
            成功更新的数量
        """
        success_count = 0
        for page_id, fields_dict in updates:
            if self.update_paper_fields(page_id, fields_dict):
                success_count += 1
            time.sleep(delay_s)

        logger.info(f"批量更新完成: {success_count}/{len(updates)} 成功")
        return success_count

    def add_paper(self, paper: Dict, skip_duplicate_check: bool = False) -> Optional[str]:
        """添加论文到 Notion 数据库，返回页面ID或None

        Args:
            paper: 论文数据字典
            skip_duplicate_check: 如果为True，跳过重复检查（因为已在批量过滤时检查）

        Returns:
            成功添加时返回页面ID，否则返回None
        """
        # 检查重复（如果未提前批量过滤）
        if not skip_duplicate_check:
            if self.check_duplicate(
                title=paper.get('title'),
                doi=paper.get('doi'),
                url=paper.get('url')
            ):
                logger.info(f"论文已存在，跳过: {paper.get('title', 'Unknown')}")
                return None
        
        # 构造 Notion 页面属性
        properties = {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": paper.get('title', 'Untitled')[:2000]
                        }
                    }
                ]
            },
            "Status": {
                "select": {
                    "name": "To Read"
                }
            },
            "Venue": {
                "select": {
                    "name": paper.get('venue', 'ArXiv')
                }
            }
        }
        
        # 添加 Added 日期
        properties["Added"] = {
            "date": {
                "start": datetime.now().strftime("%Y-%m-%d")
            }
        }
        
        # 添加可选字段
        if paper.get('authors'):
            properties["Authors"] = {
                "rich_text": [
                    {"text": {"content": paper['authors'][:2000]}}
                ]
            }
        
        if paper.get('year'):
            properties["Year"] = {"number": int(paper['year'])}
        
        if paper.get('abstract'):
            properties["Abstract"] = {
                "rich_text": [
                    {"text": {"content": paper['abstract'][:2000]}}
                ]
            }
        
        if paper.get('url'):
            properties["userDefined:URL"] = {"url": paper['url']}
        
        if paper.get('pdf_url'):
            properties["PDF Link"] = {"url": paper['pdf_url']}
        
        if paper.get('doi'):
            properties["DOI"] = {
                "rich_text": [
                    {"text": {"content": paper['doi']}}
                ]
            }
        
        if paper.get('tags'):
            properties["Tags"] = {
                "multi_select": [
                    {"name": tag} for tag in paper['tags'][:10]
                ]
            }
        
        # 指标字段（可选）
        if paper.get('citations') is not None:
            properties["Citations"] = {"number": int(paper['citations'])}
        if paper.get('influential_citations') is not None:
            properties["Influential Citations"] = {"number": int(paper['influential_citations'])}
        if paper.get('impact_2yr_mean') is not None:
            try:
                properties["Impact (2yr mean)"] = {"number": float(paper['impact_2yr_mean'])}
            except Exception:
                pass

        # 机构字段（如果有）
        if paper.get('institutions'):
            unique_insts = []
            for inst in paper['institutions']:
                name = inst.strip()[:100]
                if name and name not in unique_insts:
                    unique_insts.append(name)
            if unique_insts:
                properties["Institutions"] = {
                    "multi_select": [{"name": n} for n in unique_insts[:15]]
                }

        # 推荐评分字段
        if paper.get('recommend_score') is not None:
            try:
                properties["Recommend Score"] = {"number": float(paper['recommend_score'])}
            except Exception:
                pass

        # 大模型评分理由（可选）
        if paper.get('recommend_rationale'):
            properties["Recommend Rationale"] = {
                "rich_text": [
                    {"text": {"content": str(paper['recommend_rationale'])[:2000]}}
                ]
            }

        page_data = {
            "parent": {"database_id": self.database_id},
            "properties": properties
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/pages",
                headers=self.headers,
                json=page_data,
                timeout=15
            )
            response.raise_for_status()
            page_id = response.json().get('id')
            logger.info(f"✅ 成功添加论文: {paper.get('title', 'Unknown')}")
            return page_id
        except Exception as e:
            logger.error(f"❌ 添加论文失败: {paper.get('title', 'Unknown')}, 错误: {e}")
            return None
    
    def update_framework_diagram(self, page_id: str, image_url: str) -> bool:
        """更新页面的Framework Diagram字段
        
        Args:
            page_id: Notion页面ID
            image_url: 框架图URL
            
        Returns:
            是否成功更新
        """
        try:
            properties = {
                "Framework Diagram": {
                    "url": image_url
                }
            }
            
            response = requests.patch(
                f"{self.base_url}/pages/{page_id}",
                headers=self.headers,
                json={"properties": properties},
                timeout=15
            )
            response.raise_for_status()
            logger.info(f"✅ 成功更新Framework Diagram: {image_url[:60]}...")
            return True
        except Exception as e:
            logger.error(f"❌ 更新Framework Diagram失败: {e}")
            return False

    def update_framework_image_files(self, page_id: str, image_url: str, name: str = "framework.png") -> bool:
        """更新页面的Framework Image(文件与媒体)属性，使用外部HTTPS直链。

        Args:
            page_id: Notion页面ID
            image_url: 公开可访问的图片直链（https，建议.jpg/.png结尾）
            name: 显示名称

        Returns:
            是否成功更新
        """
        try:
            properties = {
                "Framework Image": {
                    "files": [
                        {
                            "name": name,
                            "external": {"url": image_url}
                        }
                    ]
                }
            }

            response = requests.patch(
                f"{self.base_url}/pages/{page_id}",
                headers=self.headers,
                json={"properties": properties},
                timeout=15
            )
            response.raise_for_status()
            logger.info(f"✅ 成功更新Framework Image(files): {image_url[:60]}...")
            return True
        except Exception as e:
            logger.error(f"❌ 更新Framework Image(files)失败: {e}")
            return False


class ArxivCrawler:
    """arXiv API 爬取器"""
    
    BASE_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self, keywords: List[str], days_back: int = 3):
        self.keywords = keywords
        self.days_back = days_back

    def search(self, max_results: int = 50) -> List[Dict]:
        """搜索最近的论文（支持分页）"""
        papers: List[Dict] = []

        # 构建搜索查询 - 使用严格关键字
        query = 'all:"Vision-Language-Action" OR all:"VLA model" OR all:"VLA policy" OR all:"vision language action model"'

        # 分页参数
        cutoff_date = datetime.now() - timedelta(days=self.days_back)
        fetched = 0
        start = 0
        page_size = 100  # 单次请求最大条数（适度，不要过大）

        try:
            import xml.etree.ElementTree as ET
            ns = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }

            while fetched < max_results:
                remaining = max_results - fetched
                this_page = min(page_size, remaining)
                params = {
                    "search_query": query,
                    "start": start,
                    "max_results": this_page,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending"
                }

                logger.info(f"正在搜索 arXiv: {query} (start={start}, max_results={this_page})")
                response = requests.get(self.BASE_URL, params=params, timeout=30)
                response.raise_for_status()

                root = ET.fromstring(response.content)
                entries = root.findall('atom:entry', ns)
                if not entries:
                    logger.info("arXiv 无更多结果，提前结束分页")
                    break

                added_this_round = 0
                for entry in entries:
                    # 提取信息
                    title_elem = entry.find('atom:title', ns)
                    title = (title_elem.text or "").strip().replace('\n', ' ') if title_elem is not None else "Untitled"

                    summary_elem = entry.find('atom:summary', ns)
                    summary = (summary_elem.text or "").strip().replace('\n', ' ') if summary_elem is not None else ""

                    published_elem = entry.find('atom:published', ns)
                    published_date = (published_elem.text or "") if published_elem is not None else ""

                    # 检查日期（只获取最近 N 天的）
                    try:
                        pub_datetime = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
                        if pub_datetime < cutoff_date.replace(tzinfo=pub_datetime.tzinfo):
                            # 当前结果已到达时间下限，本页后续更旧，直接结束外层循环
                            entries = []  # 触发外层 break
                            break
                    except Exception:
                        pass

                    # 作者
                    author_names = []
                    for author in entry.findall('atom:author', ns):
                        name = author.find('atom:name', ns)
                        if name is not None:
                            author_names.append(name.text)
                    authors_str = ", ".join(author_names)

                    # URL 和 PDF
                    url = ""
                    pdf_url = ""
                    for link in entry.findall('atom:link', ns):
                        if link.get('title') == 'pdf':
                            pdf_url = link.get('href', '')
                        else:
                            url = link.get('href', '')

                    # arXiv ID 作为 DOI 替代
                    arxiv_id_elem = entry.find('atom:id', ns)
                    arxiv_id_text = (arxiv_id_elem.text or "") if arxiv_id_elem is not None else ""
                    arxiv_id = arxiv_id_text.split('/')[-1] if arxiv_id_text else ""

                    # 年份
                    year = published_date[:4] if published_date and len(published_date) >= 4 else ""

                    # 严格过滤
                    if not is_vla_related(title, summary):
                        logger.debug(f"过滤非VLA论文: {title[:60]}")
                        continue

                    paper = {
                        'title': title,
                        'authors': authors_str,
                        'year': year,
                        'abstract': summary[:2000],
                        'url': url,
                        'pdf_url': pdf_url,
                        'doi': f"arXiv:{arxiv_id}",
                        'venue': 'ArXiv',
                        'tags': ['VLA', 'arXiv'],
                        'published_date': published_date,
                    }
                    papers.append(paper)
                    added_this_round += 1

                fetched += this_page
                start += this_page

                # 如果由于时间下限而提前结束当前页，退出分页
                if not entries:
                    break

                # 如果本页一个都没加，可能全部被过滤，继续下一页，直到达到限制或无更多
                if added_this_round == 0:
                    logger.debug("本页无新增（可能全部被过滤），继续下一页")

            logger.info(f"从 arXiv 找到 {len(papers)} 篇论文（分页累计）")
            return papers

        except Exception as e:
            logger.error(f"arXiv 搜索失败: {e}")
            return []


class SemanticScholarCrawler:
    """Semantic Scholar API 爬取器（备用）"""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    
    def __init__(self, keywords: List[str], days_back: int = 3, enrich_institutions: bool = False):
        self.keywords = keywords
        self.days_back = days_back
        self.enrich_institutions = enrich_institutions

    def search(self, max_results: int = 30) -> List[Dict]:
        """搜索最近的论文"""
        papers = []
        
        query = " ".join(self.keywords)
        cutoff_date = (datetime.now() - timedelta(days=self.days_back)).strftime("%Y-%m-%d")
        
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,authors.name,authors.affiliations,year,abstract,url,openAccessPdf,externalIds,venue,publicationDate",
            "publicationDateOrYear": f"{cutoff_date}:"
        }
        
        try:
            logger.info(f"正在搜索 Semantic Scholar: {query}")
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            
            # 处理 429 限流错误
            if response.status_code == 429:
                logger.warning("Semantic Scholar API 限流 (429)，跳过此数据源")
                logger.info("提示: Semantic Scholar 有请求频率限制，建议减少查询频率或稍后重试")
                return []
            
            response.raise_for_status()
            
            data = response.json()
            
            for item in data.get('data', []):
                title = item.get('title', 'Untitled')
                abstract = item.get('abstract', '')

                # 严格过滤：只保留真正的 VLA 论文
                if not is_vla_related(title, abstract):
                    logger.debug(f"过滤非VLA论文: {title[:60]}")
                    continue
                
                authors_list = item.get('authors', [])
                authors_str = ", ".join([a.get('name', '') for a in authors_list])
                
                # 获取外部 ID
                external_ids = item.get('externalIds', {}) or {}
                doi = external_ids.get('DOI', '')
                arxiv_id = external_ids.get('ArXiv', '')
                
                # 构建 PDF URL（优先级：openAccessPdf > arXiv 直接构建 > 空）
                pdf_url = ""
                if item.get('openAccessPdf'):
                    pdf_url = item['openAccessPdf'].get('url', '')
                elif arxiv_id:
                    # 从 arXiv ID 构建 PDF 链接
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                    logger.debug(f"从 arXiv ID 构建 PDF 链接: {arxiv_id}")
                
                # 保存 DOI（优先 DOI，其次 ArXiv ID）
                doi_field = doi if doi else (f"arXiv:{arxiv_id}" if arxiv_id else "")
                
                # 获取发布日期（优先使用 publicationDate，否则使用年份）
                year = item.get('year', '')
                pub_date = item.get('publicationDate', '')
                if pub_date:
                    published_date = pub_date  # 格式如 "2024-03-15"
                elif year:
                    published_date = f"{year}-01-01"
                else:
                    published_date = ""
                
                # 机构提取（直接从返回数据中获取，无需额外 API 调用）
                institutions: List[str] = []
                if self.enrich_institutions:
                    for a in authors_list[:20]:  # 限制前 20 个作者
                        # 直接从搜索结果中获取机构信息（authors.affiliations 已在 fields 中请求）
                        affs = a.get('affiliations', []) or []
                        for aff in affs:
                            # affiliation 可能是字符串或字典
                            if isinstance(aff, str):
                                name = aff
                            elif isinstance(aff, dict):
                                name = aff.get('name') or aff.get('displayName')
                            else:
                                continue

                            if name and name not in institutions:
                                institutions.append(name)
                                logger.debug(f"  ✓ 添加机构: {name}")

                        if len(institutions) >= 15:  # 安全上限
                            break

                    if institutions:
                        logger.info(f"✅ 从 {len(authors_list)} 位作者中提取到 {len(institutions)} 个机构")

                paper = {
                    'title': title,
                    'authors': authors_str,
                    'year': str(year),
                    'abstract': abstract[:2000],
                    'url': item.get('url', ''),
                    'pdf_url': pdf_url,
                    'doi': doi_field,  # 修复：使用 doi_field 而不是 doi
                    'venue': item.get('venue', 'Conference'),
                    'tags': ['VLA', 'Semantic Scholar'],
                    'published_date': published_date,  # 保存发布时间用于排序
                    'institutions': institutions,
                }
                
                papers.append(paper)
            
            logger.info(f"从 Semantic Scholar 找到 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            logger.error(f"Semantic Scholar 搜索失败: {e}")
            return []


class MetricsEnricher:
    """引用数/影响力指标增强器。

    - 引用数：优先使用 Semantic Scholar（citationCount, influentialCitationCount）
    - 影响因子近似：使用 OpenAlex Source 的 2yr_mean_citedness（非官方 IF，仅供参考）
    """

    def __init__(self, openalex_mailto: Optional[str] = None, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.ss_base_item = "https://api.semanticscholar.org/graph/v1/paper/"
        self.openalex_base = "https://api.openalex.org"
        self.mailto = openalex_mailto

    def _fetch_json(self, url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 20) -> Optional[Dict[str, Any]]:
        try:
            r = self.session.get(url, params=params or {}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.debug("GET %s failed: %s", url, e)
            return None

    def enrich_semantic_scholar(self, paper: Dict) -> Tuple[Optional[int], Optional[int]]:
        """返回 (citations, influential_citations)"""
        fields = "citationCount,influentialCitationCount,title,venue"
        # 1) DOI
        doi = None
        if paper.get('doi'):
            d = paper['doi']
            if d.lower().startswith('doi:'):
                doi = d.split(':', 1)[1]
            elif d.lower().startswith('10.'):
                doi = d
        if doi:
            data = self._fetch_json(self.ss_base_item + f"DOI:{doi}", {"fields": fields})
            if data and 'citationCount' in data:
                return data.get('citationCount'), data.get('influentialCitationCount')
        # 2) arXiv
        if paper.get('doi', '').lower().startswith('arxiv:'):
            arx = paper['doi'].split(':', 1)[1]
            data = self._fetch_json(self.ss_base_item + f"arXiv:{arx}", {"fields": fields})
            if data and 'citationCount' in data:
                return data.get('citationCount'), data.get('influentialCitationCount')
        # 3) 标题搜索
        title = paper.get('title')
        if title:
            search = self._fetch_json(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                {"query": title, "limit": 1, "fields": fields}
            )
            if search and search.get('data'):
                d0 = search['data'][0]
                return d0.get('citationCount'), d0.get('influentialCitationCount')
        return None, None

    def enrich_openalex(self, paper: Dict) -> Optional[float]:
        """返回近似影响指标（2yr_mean_citedness），需要从 work -> source 获取。"""
        params = {}
        if self.mailto:
            params['mailto'] = self.mailto
        work = None
        # work by DOI or arXiv
        if paper.get('doi'):
            d = paper['doi']
            if d.lower().startswith('10.'):
                work = self._fetch_json(f"{self.openalex_base}/works/doi:{d}", params)
            elif d.lower().startswith('arxiv:'):
                work = self._fetch_json(f"{self.openalex_base}/works/arXiv:{d.split(':',1)[1]}", params)
        if work is None and paper.get('title'):
            work = self._fetch_json(f"{self.openalex_base}/works", {**params, "search": paper['title'], "per_page": 1})
            if work and isinstance(work.get('results'), list) and work['results']:
                work = work['results'][0]
        if not work:
            return None
        venue = work.get('host_venue') or {}
        source_id = venue.get('id')
        if not source_id:
            return None
        # source_id 形如 https://openalex.org/S123456789
        src = self._fetch_json(f"{self.openalex_base}/sources/{source_id.split('/')[-1]}", params)
        if not src:
            return None
        summary = src.get('summary_stats') or {}
        return summary.get('2yr_mean_citedness')


class ScoringEngine:
    """推荐评分引擎。

    基于多维度对论文进行 0-100 浮点评分：
      - 新鲜度 (freshness)
      - 引用数 (citations)
      - 影响力引用 (influential_citations)
      - 期刊/会议影响近似 (impact)
      - 摘要长度 (abstract_length)
      - PDF 可用性 (has_pdf)
      - 来源质量 (source_quality)

    权重通过配置 recommend_score_weights 提供，缺省自动填充。
    """
    DEFAULT_WEIGHTS = {
        "freshness": 2.0,
        "citations": 1.5,
        "influential_citations": 1.0,
        "impact": 1.0,
        "abstract_length": 0.5,
        "has_pdf": 0.5,
        "source_quality": 1.0,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}

    def compute(self, paper: Dict) -> float:
        w = self.weights
        total_w = sum(w.values()) if w else 0.0
        if total_w == 0:
            return 0.0

        # Freshness: 1 - (days / 365), clipped [0,1]
        freshness = 0.0
        pub_date = paper.get('published_date') or ''
        try:
            if pub_date:
                dt = datetime.strptime(pub_date[:10], "%Y-%m-%d")
                days = (datetime.now() - dt).days
                freshness = max(0.0, 1.0 - min(days / 365.0, 1.0))
        except Exception:
            pass

        citations_val = paper.get('citations') or 0
        citations = min(1.0, (0.0 if citations_val <= 0 else (math.log10(citations_val + 1) / 3)))  # log scale
        infl_val = paper.get('influential_citations') or 0
        influential = min(1.0, (0.0 if infl_val <= 0 else (math.log10(infl_val + 1) / 2.5)))
        impact = paper.get('impact_2yr_mean') or 0.0
        impact_norm = min(1.0, impact / 5.0)  # 粗略归一化
        abs_len = len(paper.get('abstract', '') or '')
        abstract_length = min(1.0, abs_len / 1500.0)
        has_pdf = 1.0 if paper.get('pdf_url') else 0.0
        source_quality = 0.8  # 默认
        tags = paper.get('tags') or []
        if 'Semantic Scholar' in tags and 'ArXiv' not in tags:
            source_quality = 0.75
        if 'ArXiv' in tags:
            source_quality = 0.85
        # 简单加权求和
        score = (
            w["freshness"] * freshness +
            w["citations"] * citations +
            w["influential_citations"] * influential +
            w["impact"] * impact_norm +
            w["abstract_length"] * abstract_length +
            w["has_pdf"] * has_pdf +
            w["source_quality"] * source_quality
        )
        # 归一化到 0-100
        final_score = (score / total_w) * 100.0
        return round(final_score, 2)


class PDFParser:
    """PDF 全文解析器（提取文本和图片用于深度评分）"""
    
    @staticmethod
    def extract_text_from_pdf(pdf_path: str, max_pages: int = 30, max_chars: int = 50000, extract_images: bool = True, max_images: int = 10) -> Dict[str, Any]:
        """从本地 PDF 提取文本和图片。
        
        Args:
            pdf_path: PDF 文件路径
            max_pages: 最多解析页数
            max_chars: 最多提取字符数
            extract_images: 是否提取图片
            max_images: 最多提取图片数（优先提取前面的大图）
        
        Returns:
            {
                "full_text": str,  # 全文文本
                "images": List[str],  # base64 编码的图片列表
                "sections": dict,  # 各节文本（如果能识别）
                "num_pages": int,
                "num_images": int,
                "truncated": bool
            }
        """
        if not PDF_PARSING_AVAILABLE or fitz is None:
            logger.warning("PyMuPDF 未安装，无法解析 PDF 全文")
            return {"full_text": "", "images": [], "sections": {}, "num_pages": 0, "num_images": 0, "truncated": False}
        
        try:
            import base64
            from io import BytesIO
            try:
                from PIL import Image
                PIL_AVAILABLE = True
            except ImportError:
                PIL_AVAILABLE = False
                if extract_images:
                    logger.warning("PIL 未安装，将跳过图片压缩")
            
            doc = fitz.open(pdf_path)
            num_pages = min(len(doc), max_pages)
            full_text = ""
            images_base64 = []
            
            # 第一遍：提取文本
            for page_num in range(num_pages):
                page = doc[page_num]
                text = page.get_text()
                full_text += f"\n--- Page {page_num + 1} ---\n{text}"
                if len(full_text) >= max_chars:
                    full_text = full_text[:max_chars]
                    break
            
            # 第二遍：提取图片（如果启用）
            if extract_images and max_images > 0:
                image_list = []
                for page_num in range(num_pages):
                    if len(image_list) >= max_images:
                        break
                    page = doc[page_num]
                    images = page.get_images()
                    
                    for img_index, img in enumerate(images):
                        if len(image_list) >= max_images:
                            break
                        try:
                            xref = img[0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            image_size_kb = len(image_bytes) / 1024
                            
                            # 过滤过小的图片（可能是 logo/icon）
                            if len(image_bytes) < 2000:  # 小于 2KB（降低阈值）
                                logger.debug(f"跳过小图 (page {page_num+1}, {image_size_kb:.1f}KB)")
                                continue
                            
                            logger.debug(f"找到图片 (page {page_num+1}, {image_size_kb:.1f}KB, {base_image.get('width')}x{base_image.get('height')})")
                            
                            # 压缩大图片（避免超出 API 限制）
                            if PIL_AVAILABLE and len(image_bytes) > 200 * 1024:  # 大于 200KB
                                try:
                                    img = Image.open(BytesIO(image_bytes))
                                    
                                    # 调整尺寸（保持宽高比，最大边长 1024px）
                                    max_size = 1024
                                    if max(img.size) > max_size:
                                        ratio = max_size / max(img.size)
                                        new_size = tuple(int(dim * ratio) for dim in img.size)
                                        img = img.resize(new_size, Image.LANCZOS)
                                    
                                    # 转为 JPEG 并压缩
                                    output = BytesIO()
                                    if img.mode in ('RGBA', 'LA', 'P'):
                                        img = img.convert('RGB')
                                    img.save(output, format='JPEG', quality=85, optimize=True)
                                    image_bytes = output.getvalue()
                                    image_ext = "jpeg"
                                    logger.debug(f"图片已压缩: {len(image_bytes) / 1024:.1f} KB")
                                except Exception as e:
                                    logger.debug(f"图片压缩失败，使用原图: {e}")
                            
                            # 转为 base64
                            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
                            
                            # 构造 data URL 格式（适用于大多数多模态 API）
                            mime_type = f"image/{image_ext}"
                            data_url = f"data:{mime_type};base64,{image_b64}"
                            
                            image_list.append({
                                "page": page_num + 1,
                                "index": img_index,
                                "data_url": data_url,
                                "size": len(image_bytes)
                            })
                            
                        except Exception as e:
                            logger.debug(f"提取图片失败 (page {page_num+1}, img {img_index}): {e}")
                            continue
                
                # 按图片大小排序（大图更重要）
                image_list.sort(key=lambda x: x["size"], reverse=True)
                images_base64 = [img["data_url"] for img in image_list[:max_images]]
                logger.info(f"PDF 提取了 {len(images_base64)} 张图片（共扫描 {num_pages} 页）")
            
            doc.close()
            return {
                "full_text": full_text,
                "images": images_base64,
                "sections": {},
                "num_pages": num_pages,
                "num_images": len(images_base64),
                "truncated": len(full_text) >= max_chars
            }
        except Exception as e:
            logger.warning(f"PDF 解析失败: {e}")
            return {"full_text": "", "images": [], "sections": {}, "num_pages": 0, "num_images": 0, "truncated": False}
    
    @staticmethod
    def download_and_parse_pdf(pdf_url: str, max_pages: int = 30, max_chars: int = 50000, extract_images: bool = True, max_images: int = 10) -> Dict[str, Any]:
        """下载并解析 PDF（包含图片）"""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                resp = requests.get(pdf_url, timeout=60, stream=True)
                resp.raise_for_status()
                for chunk in resp.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                tmp_path = tmp.name
            
            result = PDFParser.extract_text_from_pdf(tmp_path, max_pages, max_chars, extract_images, max_images)
            os.unlink(tmp_path)
            return result
        except Exception as e:
            logger.warning(f"PDF 下载/解析失败 ({pdf_url}): {e}")
            return {"full_text": "", "images": [], "sections": {}, "num_pages": 0, "num_images": 0, "truncated": False}


class LLMScoringEngine:
    """使用大模型进行推荐评分（支持 PDF 全文输入）。

    默认对接 OpenAI 兼容的 Chat Completions 接口；
    - provider: "openai" 或 "openai-compatible"
    - api_base: 默认为 https://api.openai.com/v1
    - api_key: 建议从环境变量 OPENAI_API_KEY 提供
    - use_full_pdf: 是否下载并解析 PDF 全文（默认 False）
    """
    def __init__(self, provider: str = "openai", api_key: Optional[str] = None, model: str = "gpt-4o-mini",
                 api_base: Optional[str] = None, temperature: float = 0.2, timeout: int = 30, max_tokens: int = 300,
                 use_full_pdf: bool = False, pdf_max_pages: int = 30, pdf_max_chars: int = 50000,
                 pdf_extract_images: bool = True, pdf_max_images: int = 10):
        self.provider = provider
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.api_base = api_base.rstrip("/") if api_base else "https://api.openai.com/v1"
        self.temperature = float(temperature)
        self.timeout = int(timeout)
        self.max_tokens = int(max_tokens)
        self.use_full_pdf = use_full_pdf
        self.pdf_max_pages = pdf_max_pages
        self.pdf_max_chars = pdf_max_chars
        self.pdf_extract_images = pdf_extract_images
        self.pdf_max_images = pdf_max_images

    def _endpoint(self) -> str:
        return f"{self.api_base}/chat/completions"

    def _build_messages(self, paper: Dict, extra_instructions: Optional[str] = None, pdf_content: Optional[str] = None, pdf_images: Optional[List[str]] = None) -> List[Dict]:
        """构建多模态消息（支持文本+图片）"""
        if pdf_content or pdf_images:
            sys_prompt = (
                "你是VLA(Vision-Language-Action)领域资深论文评审专家。你已获得论文的**完整PDF全文和关键图片**，请深度阅读并分析图片后进行严格且具有区分度的打分(0-100)。\n\n"
                "**评分标准（权重递减）**：\n"
                "1. VLA相关性(30%)：是否直接涉及视觉-语言-动作融合/具身智能/机器人操控？泛泛的多模态不算高分\n"
                "2. 方法创新性(25%)：提出新架构/训练范式/数据策略？还是仅微调/简单组合现有方法？检查Method章节细节和架构图\n"
                "3. 实验严谨性(20%)：真实机器人实验>仿真>纯数据集；多场景多任务>单场景；有消融实验更佳。细看Experiments章节和结果图表\n"
                "4. 技术深度(15%)：解决核心难点(长horizon规划/sim2real/泛化/安全)?还是浅层应用？检查技术细节\n"
                "5. 影响潜力(10%)：顶会/高引/知名机构/开源代码/可复现性高？\n\n"
                "**打分区间参考**：\n"
                "- 90-100: 突破性工作(新范式/SOTA刷榜/顶会oral/高引用/开源benchmark)\n"
                "- 75-89: 优秀创新(方法新颖/实验扎实/真实机器人验证/顶会accepted)\n"
                "- 60-74: 中等质量(有一定创新但不够突出/仿真为主/普通会议)\n"
                "- 40-59: 边缘相关(VLA相关性弱/方法平庸/实验单薄/ArXiv预印本)\n"
                "- 0-39: 不推荐(与VLA关系不大/纯综述无新意/实验缺失)\n\n"
                "**严格要求**：\n"
                "- 避免打分集中在70-80，主动拉开差距！顶级工作给满分，平庸工作给低分\n"
                "- **必须分析图片内容**（架构图、实验结果图、对比图表等），并在评分依据中引用\n"
                "- 必须引用PDF中的具体章节/实验/图表来支撑你的评分\n"
                "- 如果PDF不完整或无法解析关键内容，在rationale中说明\n"
                "- **评分理由必须用中文书写**，不要使用英文\n\n"
                "只返回JSON格式: {\"score\": 数字, \"rationale\": \"<300字中文评分依据，需引用PDF具体内容和图片分析>\"}，不要其它内容。"
            )
        else:
            sys_prompt = (
                "你是VLA(Vision-Language-Action)领域资深论文评审专家。请基于元数据进行严格且具有区分度的打分(0-100)。\n\n"
                "**评分标准（权重递减）**：\n"
                "1. VLA相关性(30%)：是否直接涉及视觉-语言-动作融合/具身智能/机器人操控？泛泛的多模态不算高分\n"
                "2. 方法创新性(25%)：提出新架构/训练范式/数据策略？还是仅微调/简单组合现有方法？\n"
                "3. 实验严谨性(20%)：真实机器人实验>仿真>纯数据集；多场景多任务>单场景；有消融实验更佳\n"
                "4. 技术深度(15%)：解决核心难点(长horizon规划/sim2real/泛化/安全)?还是浅层应用？\n"
                "5. 影响潜力(10%)：顶会/高引/知名机构/开源代码/可复现性高？\n\n"
                "**打分区间参考**：\n"
                "- 90-100: 突破性工作(新范式/SOTA刷榜/顶会oral/高引用/开源benchmark)\n"
                "- 75-89: 优秀创新(方法新颖/实验扎实/真实机器人验证/顶会accepted)\n"
                "- 60-74: 中等质量(有一定创新但不够突出/仿真为主/普通会议)\n"
                "- 40-59: 边缘相关(VLA相关性弱/方法平庸/实验单薄/ArXiv预印本)\n"
                "- 0-39: 不推荐(与VLA关系不大/纯综述无新意/实验缺失)\n\n"
                "**严格要求**：\n"
                "- 避免打分集中在70-80，主动拉开差距！顶级工作给满分，平庸工作给低分\n"
                "- **评分理由必须用中文书写**，不要使用英文\n\n"
                "只返回JSON格式: {\"score\": 数字, \"rationale\": \"<200字中文评分依据，需说明扣分/加分原因>\"}，不要其它内容。"
            )
        if extra_instructions:
            sys_prompt += "\n\n**用户补充要求**: " + str(extra_instructions)
        
        # 构建用户消息（支持多模态）
        abstract = paper.get("abstract") or ""
        institutions = paper.get("institutions") or []
        
        text_content = {
            "title": paper.get("title"),
            "abstract": abstract[:1500] if abstract else "",
            "venue": paper.get("venue"),
            "year": paper.get("year"),
            "published_date": paper.get("published_date"),
            "citations": paper.get("citations"),
            "influential_citations": paper.get("influential_citations"),
            "impact_2yr_mean": paper.get("impact_2yr_mean"),
            "has_pdf": bool(paper.get("pdf_url")),
            "tags": paper.get("tags"),
            "institutions": institutions[:5] if institutions else [],
        }
        
        if pdf_content:
            text_content["full_pdf_text"] = pdf_content
        
        # 如果有图片，使用多模态格式（OpenAI vision API 格式）
        if pdf_images:
            user_content = [
                {
                    "type": "text",
                    "text": f"**论文元数据和全文**:\n{json.dumps(text_content, ensure_ascii=False, indent=2)}\n\n**PDF图片**（共{len(pdf_images)}张，请仔细分析）："
                }
            ]
            for idx, img_url in enumerate(pdf_images, 1):
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": img_url,
                        "detail": "high"  # 高精度分析图片
                    }
                })
            
            return [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_content}
            ]
        else:
            # 纯文本模式
            return [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": json.dumps(text_content, ensure_ascii=False, indent=2)}
            ]

    def score_paper(self, paper: Dict, extra_instructions: Optional[str] = None) -> Tuple[Optional[float], Optional[str]]:
        if not self.api_key:
            logger.warning("LLM 评分已启用但缺少 API Key，跳过 LLM 打分")
            return None, None
        
        # 如果启用 PDF 全文解析
        pdf_content = None
        pdf_images = None
        if self.use_full_pdf and paper.get("pdf_url"):
            logger.info(f"📄 下载并解析 PDF (含图片): {paper.get('title', '')[:50]}...")
            pdf_result = PDFParser.download_and_parse_pdf(
                paper["pdf_url"],
                max_pages=self.pdf_max_pages,
                max_chars=self.pdf_max_chars,
                extract_images=self.pdf_extract_images,
                max_images=self.pdf_max_images
            )
            if pdf_result.get("full_text"):
                pdf_content = pdf_result["full_text"]
                pdf_images = pdf_result.get("images") or []
                logger.info(f"✅ PDF 解析成功 ({pdf_result['num_pages']} 页, {len(pdf_content)} 字符, {len(pdf_images)} 张图片)")
            else:
                logger.warning(f"⚠️  PDF 解析失败，回退到摘要打分")
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            messages = self._build_messages(paper, extra_instructions, pdf_content, pdf_images)
            body = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            
            # 估算输入大小
            import sys
            body_size_mb = sys.getsizeof(json.dumps(body)) / (1024 * 1024)
            logger.info(f"🤖 调用大模型 API: {self.model}（请求大小: {body_size_mb:.2f} MB，图片数: {len(pdf_images) if pdf_images else 0}）...")
            
            resp = requests.post(self._endpoint(), headers=headers, json=body, timeout=self.timeout)
            if resp.status_code == 429:
                logger.warning("LLM 接口限流(429)，跳过该条")
                return None, None
            resp.raise_for_status()
            data = resp.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            content = content.strip()
            # 期望纯 JSON
            try:
                obj = json.loads(content)
                score = float(obj.get("score"))
                rationale = str(obj.get("rationale", "")).strip()
                if score < 0: score = 0.0
                if score > 100: score = 100.0
                return round(score, 2), rationale[:2000]
            except Exception:
                # 容错：粗暴提取 0-100 数字
                import re
                m = re.search(r"(\d{1,3})", content)
                if m:
                    sc = min(100.0, max(0.0, float(m.group(1))))
                    return round(sc, 2), content[:2000]
                return None, content[:2000] if content else None
        except Exception as e:
            logger.debug("LLM 打分失败: %s", e)
            return None, None


def load_config(config_path: str = "config_lcj.json") -> Dict:
    """加载配置文件"""
    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始执行论文爬取任务")
    logger.info("=" * 60)

    # 支持命令行参数指定配置文件
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    config = load_config(config_path)

    notion_token = config.get('notion_token')
    database_id = config.get('database_id')
    keywords = config.get('keywords', ['VLA', 'Vision Language Action', 'robot foundation model'])
    days_back = config.get('days_back', 3)
    arxiv_max_results = int(config.get('arxiv_max_results', 200))
    ss_max_results = int(config.get('semantic_scholar_max_results', 50))

    if not notion_token or not database_id:
        logger.error("配置文件缺少 notion_token 或 database_id")
        sys.exit(1)

    # 初始化客户端
    notion = NotionClient(notion_token, database_id)

    # 爬取论文
    all_papers = []

    # 1. arXiv
    arxiv_crawler = ArxivCrawler(keywords, days_back)
    arxiv_papers = arxiv_crawler.search(max_results=arxiv_max_results)
    all_papers.extend(arxiv_papers)

    # 2. Semantic Scholar（可选）
    if config.get('use_semantic_scholar', False):
        logger.info("等待 3 秒后查询 Semantic Scholar (避免API限流)...")
        time.sleep(3)  # 增加延迟避免 429 错误
        ss_crawler = SemanticScholarCrawler(keywords, days_back, enrich_institutions=config.get('enrich_institutions', True))
        ss_papers = ss_crawler.search(max_results=ss_max_results)
        if ss_papers:
            all_papers.extend(ss_papers)
            logger.info(f"从 Semantic Scholar 获得 {len(ss_papers)} 篇额外论文")
        else:
            logger.info("Semantic Scholar 未返回结果（可能因限流或无新论文）")
    
    # 按发布时间排序（最新的在前）
    all_papers.sort(key=lambda p: p.get('published_date', ''), reverse=True)

    logger.info(f"总共找到 {len(all_papers)} 篇论文（已按发布时间排序）")

    # 【优化】提前过滤重复论文，避免浪费 API 调用和 LLM token
    logger.info("=" * 60)
    logger.info("开始过滤已存在的论文...")
    logger.info("=" * 60)
    all_papers = notion.filter_duplicates(all_papers)

    # 指标增强（可选）
    enrich_citations = config.get('enrich_citations', True)
    enrich_impact = config.get('enrich_impact', False)
    openalex_mailto = config.get('openalex_mailto')
    if enrich_citations or enrich_impact:
        # 确保指标属性存在
        try:
            notion.ensure_metrics_properties()
        except Exception as e:
            logger.warning("无法确认/创建指标属性: %s", e)
        enricher = MetricsEnricher(openalex_mailto=openalex_mailto)
        for p in all_papers:
            try:
                if enrich_citations:
                    c, ic = enricher.enrich_semantic_scholar(p)
                    if c is not None:
                        p['citations'] = c
                    if ic is not None:
                        p['influential_citations'] = ic
                if enrich_impact:
                    imp = enricher.enrich_openalex(p)
                    if imp is not None:
                        p['impact_2yr_mean'] = imp
            except Exception as e:
                logger.debug("指标增强失败（忽略该条）: %s", e)
            time.sleep(0.2)

    # 推荐评分（依赖部分增强后的指标）
    if config.get('recommend_score_enabled', True):
        try:
            notion.ensure_enrichment_properties()
        except Exception as e:
            logger.warning("无法确认/创建扩展属性: %s", e)

        # 规则打分作为兜底
        rb_weights = config.get('recommend_score_weights', {})
        rule_engine = ScoringEngine(rb_weights)

        # 大模型打分（可选，优先）
        llm_enabled = bool(config.get('llm_recommend_score_enabled', False))
        llm_engine = None
        llm_max_papers = int(config.get('llm_max_papers', 50))
        llm_interval_s = float(config.get('llm_call_interval_s', 0.4))
        if llm_enabled:
            llm_engine = LLMScoringEngine(
                provider=config.get('llm_provider', 'openai'),
                api_key=config.get('llm_api_key') or os.environ.get('OPENAI_API_KEY'),
                model=config.get('llm_model', 'gpt-4o-mini'),
                api_base=config.get('llm_api_base'),
                temperature=float(config.get('llm_temperature', 0.2)),
                timeout=int(config.get('llm_timeout', 60)),
                max_tokens=int(config.get('llm_max_tokens', 500)),
                use_full_pdf=bool(config.get('llm_use_full_pdf', True)),
                pdf_max_pages=int(config.get('llm_pdf_max_pages', 30)),
                pdf_max_chars=int(config.get('llm_pdf_max_chars', 50000)),
                pdf_extract_images=bool(config.get('llm_pdf_extract_images', True)),
                pdf_max_images=int(config.get('llm_pdf_max_images', 10))
            )
            if not llm_engine.api_key:
                logger.warning('LLM 评分启用但未提供 API Key，将回退规则打分')
                llm_enabled = False
            if llm_engine.use_full_pdf and not PDF_PARSING_AVAILABLE:
                logger.warning('PDF 全文解析已启用但 PyMuPDF 未安装，将回退到摘要打分')
                llm_engine.use_full_pdf = False

        for idx, p in enumerate(all_papers):
            try:
                if llm_enabled and llm_engine is not None and idx < llm_max_papers:
                    score, rationale = llm_engine.score_paper(p)
                    if score is not None:
                        p['recommend_score'] = score
                        if rationale:
                            p['recommend_rationale'] = rationale
                    else:
                        p['recommend_score'] = rule_engine.compute(p)
                    time.sleep(llm_interval_s)
                else:
                    p['recommend_score'] = rule_engine.compute(p)
            except Exception as e:
                logger.debug("推荐评分计算失败（忽略该条）: %s", e)
    
    # 初始化图片提取器（如果启用）
    extract_figures = config.get('extract_figures', False)
    figure_extractor = None
    if extract_figures and FIGURE_EXTRACTION_AVAILABLE:
        # 读取图床配置
        image_host_service = config.get('image_host_service', 'auto')
        imgur_client_id = config.get('imgur_client_id', '')
        
        figure_extractor = FigureExtractor(
            notion_token, 
            max_figures=3,
            image_host_service=image_host_service,
            imgur_client_id=imgur_client_id if imgur_client_id else None
        )
        if not figure_extractor.is_available():
            logger.warning("图片提取依赖未安装，跳过图片提取功能")
            figure_extractor = None
    
    # 写入 Notion
    added_count = 0
    max_papers_to_add = config.get('max_papers', 999)  # 从配置读取，默认999篇
    for paper in all_papers:
        # 论文数量限制
        if added_count >= max_papers_to_add:
            logger.info(f"✅ 已添加 {max_papers_to_add} 篇论文，达到配置的上限")
            break

        # 由于已在前面批量过滤重复，此处跳过重复检查以提高性能
        page_id = notion.add_paper(paper, skip_duplicate_check=True)
        if page_id:
            added_count += 1
            
            # 提取并添加框架图
            if figure_extractor and paper.get('pdf_url'):
                try:
                    logger.info(f"正在提取论文框架图: {paper.get('title', 'Unknown')[:50]}")
                    # process_paper返回第一张图片的URL (可能是http URL或data: URL)
                    framework_url = figure_extractor.process_paper(paper, page_id)
                    
                    # 如果成功提取到框架图，处理结果
                    if framework_url:
                        title = paper.get('title', 'framework')[:50]
                        # 检查是否是HTTPS URL
                        if framework_url.startswith('http'):
                            notion.update_framework_diagram(page_id, framework_url)
                            notion.update_framework_image_files(page_id, framework_url, name=f"{title}.png")
                            logger.info(f"✅ Framework Diagram已更新: {framework_url[:80]}")
                        # 如果是本地文件路径
                        elif framework_url.startswith('/'):
                            logger.info(f"📁 Framework图片已保存到本地: {framework_url}")
                            logger.info(f"   可以手动打开文件并上传到Notion: https://www.notion.so/{page_id}")
                        else:
                            logger.warning("提取到的链接格式不支持")
                        
                except Exception as e:
                    logger.warning(f"图片提取失败（跳过）: {e}")
        
        time.sleep(0.5)  # 避免 API 限流

    # 【新增】补全已有论文的缺失字段
    patch_config = config.get('patch_config', {})
    if patch_config.get('enabled', False):
        logger.info("=" * 60)
        logger.info("开始补全已有论文的缺失字段...")
        logger.info("=" * 60)

        # 1. 查询已有论文
        max_scan = patch_config.get('max_papers_to_scan', 200)
        existing_papers = notion.fetch_existing_papers(limit=max_scan)

        if not existing_papers:
            logger.info("未找到已有论文，跳过补全")
        else:
            # 2. 检测缺失字段
            fields_to_check = patch_config.get('fields_to_patch', [
                'pdf_url', 'institutions', 'citations', 'recommend_score'
            ])
            missing_by_field = detect_missing_fields(existing_papers, fields_to_check)

            # 3. 初始化增强器（如果需要）
            enricher = None
            need_enricher = any([
                patch_config.get('citations', {}).get('enabled', False),
                patch_config.get('institutions', {}).get('enabled', False)
            ])
            if need_enricher:
                enricher = MetricsEnricher(
                    openalex_mailto=config.get('openalex_mailto')
                )

            # 4. 初始化 LLM（如果需要）
            llm_engine_for_patch = None
            if patch_config.get('recommend_score', {}).get('enabled', False):
                llm_engine_for_patch = LLMScoringEngine(
                    provider=config.get('llm_provider', 'openai'),
                    api_key=config.get('llm_api_key') or os.environ.get('OPENAI_API_KEY'),
                    model=config.get('llm_model', 'gpt-4o-mini'),
                    api_base=config.get('llm_api_base'),
                    temperature=float(config.get('llm_temperature', 0.2)),
                    timeout=int(config.get('llm_timeout', 60)),
                    max_tokens=int(config.get('llm_max_tokens', 500)),
                    use_full_pdf=patch_config.get('recommend_score', {}).get('use_full_pdf', False),
                    pdf_max_pages=int(config.get('llm_pdf_max_pages', 30)),
                    pdf_max_chars=int(config.get('llm_pdf_max_chars', 50000)),
                    pdf_extract_images=bool(config.get('llm_pdf_extract_images', True)),
                    pdf_max_images=int(config.get('llm_pdf_max_images', 10))
                )

            # 5. 逐字段补全（按优先级）
            priority_order = ['pdf_url', 'citations', 'institutions', 'recommend_score']
            total_patched = 0

            for field in priority_order:
                field_config = patch_config.get(field, {})
                if not field_config.get('enabled', False):
                    logger.debug(f"⊘ {field}: 未启用，跳过")
                    continue

                missing_key = f'missing_{field}'
                if missing_key not in missing_by_field or not missing_by_field[missing_key]:
                    logger.info(f"⊘ {field}: 无缺失")
                    continue

                missing_papers = missing_by_field[missing_key]
                max_papers = field_config.get('max_papers', 10)

                logger.info(f"🔧 开始补全 {field} ({len(missing_papers)} 篇缺失，限制 {max_papers} 篇)...")
                success, failed = patch_missing_fields(
                    notion, missing_papers, field,
                    enricher=enricher,
                    llm_engine=llm_engine_for_patch,
                    max_papers=max_papers
                )
                total_patched += success

            logger.info("=" * 60)
            logger.info(f"✅ 缺失字段补全完成！总补全 {total_patched} 个字段")
            logger.info("=" * 60)

    logger.info("=" * 60)
    logger.info(f"任务完成！成功添加 {added_count} 篇新论文到 Notion")
    if extract_figures and added_count > 0:
        logger.info("已尝试为论文提取框架图")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
