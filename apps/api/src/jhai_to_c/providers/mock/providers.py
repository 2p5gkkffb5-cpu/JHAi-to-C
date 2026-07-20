import asyncio
import json
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from jhai_to_c.contracts.director import DirectorOutput
from jhai_to_c.contracts.intent import IntentDecision
from jhai_to_c.contracts.packaging import BrandPackagingOutput
from jhai_to_c.contracts.production import (
    CopywritingOutput,
    ProductionCoordinatorOutput,
    ProductionPackageOutput,
    StoryboardOutput,
    VideoPromptOutput,
)
from jhai_to_c.contracts.research import (
    EvidenceType,
    ResearchOutput,
    ResearchSource,
    ResearchStrategyOutput,
)
from jhai_to_c.contracts.review import ReviewerOutput
from jhai_to_c.contracts.strategy import StrategyOutput
from jhai_to_c.contracts.video import (
    VideoGenerationRequest,
    VideoTask,
    VideoTaskStatus,
)
from jhai_to_c.contracts.video_clone import (
    VideoCloneMappingOutput,
    VideoClonePromptOutput,
)
from jhai_to_c.providers.interfaces import (
    ResearchProviderResult,
    ResearchQuery,
    StructuredGenerationResult,
)

from .interfaces import MockProviderControl


def _reference_labels(input_data: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for reference in input_data.get("references", []):
        if isinstance(reference, dict) and isinstance(reference.get("label"), str):
            labels.append(reference["label"])
    return labels


def _first_reference_label(input_data: dict[str, Any], reference_type: str) -> str | None:
    for reference in input_data.get("references", []):
        if not isinstance(reference, dict):
            continue
        if reference.get("type") != reference_type:
            continue
        label = reference.get("label")
        if isinstance(label, str) and label:
            return label
    return None


def _creative_brief_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    request_text = str(input_data.get("request_text", "生成一条产品营销短视频"))
    labels = _reference_labels(input_data)
    product = _first_reference_label(input_data, "product") or "演示商品"
    is_packaging = input_data.get("requested_mode") == "brand_packaging"
    return {
        "workflow_type": "brand_packaging" if is_packaging else "topic_to_video",
        "creative_brief": {
            "industry": "消费品",
            "product": product,
            "platform": input_data.get("target_platform", "douyin"),
            "goal": "完成可上线的店铺或品牌包装"
            if is_packaging
            else "用一条短视频建立认知并引导转化",
            "target_audience": "关注效率、品质与真实使用体验的年轻消费者",
            "content_direction": (
                f"围绕“{request_text[:120]}”统一品牌定位、视觉系统、店铺物料与核心文案"
                if is_packaging
                else f"围绕“{request_text[:120]}”构建问题、体验与行动闭环"
            ),
            "duration_seconds": input_data.get("duration_seconds", 20),
            "aspect_ratio": input_data.get("aspect_ratio", "9:16"),
            "tone": ["清晰", "可信", "有节奏"],
            "must_include": labels[:20],
            "must_avoid": ["无法验证的绝对化承诺"],
        },
        "missing_fields": [],
        "assumptions": ["默认按用户填写的平台与现有图片完成首版包装"]
        if is_packaging
        else ["默认面向短视频平台自然流量场景"],
    }


def _brand_packaging_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    request_text = str(input_data.get("request_text", "品牌包装"))
    brief = input_data.get("creative_brief", {})
    strategy = input_data.get("selected_strategy", {})
    reference_ids = [
        reference["id"]
        for reference in input_data.get("references", [])
        if isinstance(reference, dict) and isinstance(reference.get("id"), str)
    ]
    brand_name = str(brief.get("product") or "待命名品牌").lstrip("@")
    return {
        "package_type": "store" if "店铺" in request_text or "店" in request_text else "brand",
        "executive_summary": (
            f"以“{strategy.get('core_message', '清晰、可信、易识别')}”为核心，"
            "统一定位、视觉与销售表达，形成可以直接上线的首版包装。"
        ),
        "brand_foundation": {
            "brand_name": brand_name,
            "positioning": "面向重视品质与真实体验的人群，提供清楚、可信且易于选择的产品体验。",
            "target_audience": brief.get("target_audience", "关注品质与使用体验的消费者"),
            "value_proposition": strategy.get("core_message", "让核心价值更容易被看见和理解"),
            "slogan": "好体验，一眼就懂",
            "personality": ["真诚", "清晰", "有质感"],
        },
        "visual_system": {
            "creative_direction": strategy.get(
                "visual_direction", "以真实产品图片为核心，使用克制留白与统一信息层级建立品牌感。"
            ),
            "primary_color": "暖炭灰 #2D2A28",
            "secondary_colors": ["米白 #FAF9F6", "陶土橙 #C8683A"],
            "typography": "标题使用有识别度的衬线字，正文与价格信息使用清晰无衬线字。",
            "photography_style": "保留产品真实材质，采用自然柔光、干净背景和统一视角。",
            "logo_direction": "以品牌中文名或首字母构建简洁字标，优先保证头像与店招小尺寸识别。",
            "image_rules": [
                "主图只保留一个视觉焦点",
                "同系列图片统一光线与留白",
                "卖点文字不遮挡产品主体",
            ],
        },
        "assets": [
            {
                "asset_name": "品牌头像与字标",
                "channel": "全渠道",
                "purpose": "建立统一识别",
                "copy_text": brand_name,
                "image_brief": "简洁字标，适配圆形头像与小尺寸显示。",
                "recommended_ratio": "1:1",
            },
            {
                "asset_name": "店招/首页主视觉",
                "channel": "店铺首页",
                "purpose": "首屏说明品牌价值",
                "copy_text": "好体验，一眼就懂",
                "image_brief": "使用核心产品图，背景克制，突出品牌名与一句价值主张。",
                "recommended_ratio": "16:9",
            },
            {
                "asset_name": "核心卖点套图",
                "channel": "商品详情/品牌介绍",
                "purpose": "解释购买理由",
                "copy_text": "真实材质｜清晰体验｜放心选择",
                "image_brief": "三张一组，分别表现产品全貌、材质细节和使用场景。",
                "recommended_ratio": "1:1",
            },
            {
                "asset_name": "详情页信任模块",
                "channel": "商品详情",
                "purpose": "减少决策疑虑",
                "copy_text": "看得见的细节，才是可靠的品质",
                "image_brief": "使用局部细节与说明性标注，避免无法验证的夸张对比。",
                "recommended_ratio": "3:4",
            },
        ],
        "content_kit": {
            "brand_story": (
                f"{brand_name}希望把复杂的选择变简单。我们从真实图片和用户体验出发，"
                "让每一次表达都清楚、可信，也让真正重要的品质被看见。"
            ),
            "store_bio": f"{brand_name}｜认真做好产品，也认真讲清每一个细节。",
            "selling_points": ["视觉与表达统一", "真实图片优先", "核心价值清晰可见"],
            "tone_of_voice": ["直接", "真诚", "克制"],
            "reusable_headlines": [
                "第一眼看见真正重要的",
                "好产品，也要被好好表达",
                "细节清楚，选择更放心",
            ],
        },
        "rollout_plan": [
            {
                "order": 1,
                "task": "确认品牌名、定位和主色",
                "deliverable": "品牌基础信息定稿",
                "priority": "high",
            },
            {
                "order": 2,
                "task": "统一处理用户提供的图片",
                "deliverable": "可复用视觉素材库",
                "priority": "high",
            },
            {
                "order": 3,
                "task": "制作头像、店招与核心卖点套图",
                "deliverable": "首批上线物料",
                "priority": "high",
            },
            {
                "order": 4,
                "task": "补齐详情页与社交传播模板",
                "deliverable": "完整包装组件",
                "priority": "medium",
            },
            {
                "order": 5,
                "task": "检查各渠道裁切与文字可读性",
                "deliverable": "上线检查清单",
                "priority": "medium",
            },
        ],
        "reference_ids": reference_ids[:20],
        "assumptions": [
            "未提供的品牌历史与产品参数未作为事实使用",
            "色彩与字体为首版方向，需结合商标与平台规范复核",
        ],
    }


def _research_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    raw_sources = input_data.get("research_sources", [])
    sources = [
        ResearchSource.model_validate(source).model_dump(mode="json") for source in raw_sources
    ]
    source_ids = [source["source_id"] for source in sources]
    return {
        "audience_insights": [
            {
                "claim": "目标受众更容易被具体使用场景和可感知收益打动",
                "evidence_type": EvidenceType.DEMO_SOURCE,
                "source_ids": source_ids[:2],
                "confidence": 0.82,
            }
        ],
        "competitor_patterns": ["前三秒直接呈现问题", "使用前后对比强化记忆点"],
        "content_trends": ["场景化演示", "口语化旁白", "节奏紧凑的竖屏叙事"],
        "suggestions": ["用真实痛点开场", "将核心卖点转成可见动作", "结尾设置单一 CTA"],
        "risk_notes": ["示例研究数据仅用于 Demo，不代表实时市场结论"],
        "sources": sources,
    }


def _strategy_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    brief = input_data.get("creative_brief", {})
    audience = brief.get("target_audience", "年轻消费者")
    product = brief.get("product", "演示商品")
    option_specs = [
        (
            "strategy-scene",
            "痛点场景反转",
            "先放大高频痛点，再用产品动作完成反转",
            "你每天都在为这个小问题浪费时间吗？",
            [92, 90, 94, 86],
        ),
        (
            "strategy-proof",
            "体验证据推进",
            "用连续体验镜头建立可信度并带出核心卖点",
            "不讲参数，直接看一次真实体验。",
            [90, 86, 88, 82],
        ),
        (
            "strategy-lifestyle",
            "理想生活切片",
            "以轻快生活切片承载品牌调性和使用价值",
            "把复杂留给工具，把时间还给生活。",
            [88, 80, 90, 91],
        ),
    ]
    options = []
    for strategy_id, name, summary, hook, scores in option_specs:
        options.append(
            {
                "strategy_id": strategy_id,
                "name": name,
                "summary": summary,
                "target_audience": audience,
                "core_message": f"{product}让关键体验更简单、更直观",
                "selling_points": ["快速上手", "效果可感知", "适合日常场景"],
                "hook": hook,
                "narrative_structure": ["痛点钩子", "产品介入", "体验证明", "行动号召"],
                "visual_direction": "竖屏近景为主，使用动作清楚，画面明亮且节奏紧凑",
                "cta": "立即了解产品，开启更简单的体验",
                "risks": ["避免使用未经输入材料支持的量化效果"],
                "scores": {
                    "brand_fit": scores[0],
                    "conversion_fit": scores[1],
                    "execution_feasibility": scores[2],
                    "differentiation": scores[3],
                },
            }
        )
    return {
        "strategy_options": options,
        "recommended_strategy_id": "strategy-scene",
        "recommendation_reason": "痛点反转路径最适合在融资 Demo 中快速呈现端到端营销闭环",
    }


def _research_strategy_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    research = _research_payload(input_data)
    return {
        "research": research,
        "strategies": _strategy_payload({**input_data, "research": research}),
    }


def _intent_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    request_text = str(input_data.get("request_text", "")).lower()
    full_markers = (
        "策划",
        "研究",
        "策略",
        "营销方案",
        "完整方案",
        "文案",
        "脚本",
        "分镜",
        "campaign",
    )
    image_markers = (
        "图片",
        "图像",
        "海报",
        "商品图",
        "生图",
        "换背景",
        "去水印",
        "擦除水印",
        "画质增强",
    )
    video_markers = (
        "视频",
        "动起来",
        "动画",
        "运镜",
        "镜头运动",
        "转身",
        "口播",
    )
    if any(marker in request_text for marker in full_markers):
        return {
            "intent": "full_creation",
            "confidence": 0.96,
            "reason_code": "full_workflow_requested",
        }
    if any(marker in request_text for marker in video_markers):
        return {
            "intent": "video_generation",
            "confidence": 0.93,
            "reason_code": "video_output_requested",
        }
    if any(marker in request_text for marker in image_markers):
        return {
            "intent": "image_generation",
            "confidence": 0.94,
            "reason_code": "image_output_requested",
        }
    return {
        "intent": "full_creation",
        "confidence": 0.6,
        "reason_code": "ambiguous_default",
    }


def _copywriting_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    brief = input_data.get("creative_brief", {})
    strategy = input_data.get("selected_strategy", {})
    duration = int(brief.get("duration_seconds", 20))
    product = brief.get("product", "演示商品")
    hook = strategy.get("hook", "这个日常难题，其实可以更简单。")
    middle_start = min(3, max(duration - 2, 0))
    middle_end = max(middle_start + 1, min(duration - 1, 14))
    return {
        "title": f"{product}：把日常难题变简单",
        "hook": hook,
        "voiceover": (
            f"{hook} 现在，用{product}完成关键一步。操作直观，效果看得见，"
            "让每一次使用都更从容。立即了解，开启更简单的体验。"
        ),
        "onscreen_text": [
            {"start_seconds": 0, "end_seconds": min(3, duration), "text": "这个问题你也遇到过？"},
            {
                "start_seconds": middle_start,
                "end_seconds": middle_end,
                "text": f"{product} · 简单一步",
            },
            {
                "start_seconds": max(duration - 4, 1),
                "end_seconds": duration,
                "text": "现在就去了解",
            },
        ],
        "cta": strategy.get("cta", "立即了解，开启更简单的体验"),
        "estimated_duration_seconds": duration,
        "tone": "清晰、可信、有节奏",
        "fact_bindings": [],
    }


def _production_coordinator_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    brief = input_data.get("creative_brief", {})
    strategy = input_data.get("selected_strategy", {})
    allowed_reference_ids: list[str] = []
    for reference in input_data.get("references", []):
        if not isinstance(reference, dict):
            continue
        reference_id = reference.get("id")
        if isinstance(reference_id, str) and reference_id not in allowed_reference_ids:
            allowed_reference_ids.append(reference_id)
    return {
        "production_goal": (
            f"制作 {brief.get('duration_seconds', 20)} 秒 {brief.get('aspect_ratio', '9:16')} "
            f"短视频，传达“{strategy.get('core_message', '核心信息')}”"
        ),
        "copywriting_instruction": (
            f"以“{strategy.get('hook', '直接呈现问题')}”开场，围绕核心信息完成单一 CTA"
        ),
        "storyboard_instruction": "保持时长连续、镜头可执行，并严格承接已确认文案",
        "video_prompt_instruction": (
            "按 14 行紧凑纯文本格式输出，保持主体、商品、光线和风格连续"
        ),
        "continuity_rules": [
            "人物与商品外观跨镜头一致",
            "光线方向与色温连续",
            "不得引入结构化引用之外的商品事实",
        ],
        "allowed_reference_ids": allowed_reference_ids[:20],
    }


def _storyboard_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    copywriting = input_data.get("copywriting", {})
    duration = int(copywriting.get("estimated_duration_seconds", 20))
    boundaries = [0.0, duration * 0.2, duration * 0.55, duration * 0.8, float(duration)]
    purposes = ["hook", "selling_point", "proof", "cta"]
    visuals = [
        "高频痛点场景特写，人物动作略显迟滞",
        "产品进入画面，清楚展示一次核心操作",
        "连续使用镜头呈现轻松、顺畅的体验变化",
        "产品与品牌信息定格，人物自然看向镜头",
    ]
    onscreen = ["你也遇到过？", "简单一步", "体验看得见", "立即了解"]
    shots = []
    for index in range(4):
        start = round(boundaries[index], 2)
        end = round(boundaries[index + 1], 2)
        shots.append(
            {
                "shot_id": f"shot-{index + 1}",
                "order": index + 1,
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": round(end - start, 2),
                "purpose": purposes[index],
                "visual": visuals[index],
                "subject": "年轻消费者与演示商品",
                "action": "完成与该镜头叙事目的匹配的自然动作",
                "camera": {
                    "shot_size": "近景" if index < 2 else "中景",
                    "angle": "平视",
                    "movement": "轻微推进" if index < 3 else "固定",
                },
                "voiceover": copywriting.get("voiceover", ""),
                "onscreen_text": onscreen[index],
                "transition": "动作匹配剪辑" if index < 3 else "淡出",
                "reference_ids": [],
                "generation_prompt": f"竖屏商业短视频，{visuals[index]}，自然光，主体一致",
            }
        )
    return {
        "total_duration_seconds": duration,
        "visual_style": "真实生活方式广告，明亮自然光，干净构图，竖屏优先",
        "continuity_rules": ["人物与产品外观保持一致", "色温和光线方向保持连续"],
        "shots": shots,
    }


def _video_prompt_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    storyboard = input_data.get("storyboard", {})
    brief = input_data.get("creative_brief", {})
    copywriting = input_data.get("copywriting", {})
    shots = [shot for shot in storyboard.get("shots", []) if isinstance(shot, dict)]
    reference_ids = []
    for reference in input_data.get("references", []):
        if isinstance(reference, dict) and isinstance(reference.get("id"), str):
            reference_ids.append(reference["id"])
    return {
        "prompt": _compact_video_prompt(storyboard, copywriting, shots),
        "negative_prompt": "画面闪烁，主体变形，文字乱码，品牌标识错误，低清晰度",
        "duration_seconds": storyboard.get("total_duration_seconds", 20),
        "aspect_ratio": brief.get("aspect_ratio", "9:16"),
        "reference_ids": reference_ids[:10],
        "provider_parameters": {"seed": 42, "motion_strength": 0.65},
    }


def _compact_video_prompt(
    storyboard: dict[str, Any],
    copywriting: dict[str, Any],
    shots: list[dict[str, Any]],
) -> str:
    cameras = [shot.get("camera", {}) for shot in shots]
    shot_types = " → ".join(
        " ".join(
            str(value)
            for value in (camera.get("shot_size"), camera.get("angle"))
            if value
        )
        for camera in cameras
        if isinstance(camera, dict)
    )
    subjects = "、".join(
        dict.fromkeys(str(shot.get("subject")) for shot in shots if shot.get("subject"))
    )
    scenes = " → ".join(str(shot.get("visual")) for shot in shots if shot.get("visual"))
    actions = " → ".join(str(shot.get("action")) for shot in shots if shot.get("action"))
    movements = " → ".join(
        str(camera.get("movement"))
        for camera in cameras
        if isinstance(camera, dict) and camera.get("movement")
    )
    onscreen_text = "、".join(
        str(shot.get("onscreen_text")) for shot in shots if shot.get("onscreen_text")
    )
    style = str(storyboard.get("visual_style") or "真实生活方式商业广告")
    duration = storyboard.get("total_duration_seconds", 20)
    values = (
        shot_types or "中近景平视连续镜头",
        subjects or "年轻消费者与演示商品",
        scenes or "干净明亮的真实生活场景",
        actions or "主体自然完成产品体验并看向镜头",
        "从略显困扰逐渐转为放松笃定，眼神自然聚焦",
        "自然呼吸，视线随手部操作轻微移动，手指准确触碰商品",
        "身体移动时衣袖与衣摆自然滞后、轻摆并缓慢回落",
        str(copywriting.get("voiceover") or "无口播"),
        str(copywriting.get("tone") or "符合年轻消费者身份的自然可信语气"),
        movements or "稳定轻推，结尾固定",
        "明亮柔和自然光，光线方向与色温连续",
        style,
        f"商品外观跨镜头一致；屏幕文字：{onscreen_text or '无'}",
        f"{duration} 秒",
    )
    labels = (
        "镜头类型",
        "主体",
        "场景",
        "连续动作",
        "微表情",
        "符合场景的微动作",
        "服饰因动作产生的物理反应",
        "口播",
        "符合人物身份、场景细节的语气",
        "镜头运动",
        "光线氛围",
        "风格",
        "细节",
        "时长",
    )
    return "\n".join(
        f"[{label}] {' '.join(str(value).split())}"
        for label, value in zip(labels, values, strict=True)
    )


def _production_package_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    production_plan = _production_coordinator_payload(input_data)
    allowed_ids = set(production_plan["allowed_reference_ids"])
    references = [
        reference
        for reference in input_data.get("references", [])
        if isinstance(reference, dict) and reference.get("id") in allowed_ids
    ]
    copywriting_input = {
        **input_data,
        "production_plan": production_plan,
        "references": references,
    }
    copywriting = _copywriting_payload(copywriting_input)
    storyboard = _storyboard_payload({**copywriting_input, "copywriting": copywriting})
    video_prompt = _video_prompt_payload(
        {**copywriting_input, "copywriting": copywriting, "storyboard": storyboard}
    )
    return {
        "production_plan": production_plan,
        "copywriting": copywriting,
        "storyboard": storyboard,
        "video_prompt": video_prompt,
    }


def _review_payload(input_data: dict[str, Any], scenario: str) -> dict[str, Any]:
    video_prompt = input_data.get("video_prompt", {})
    parameters = video_prompt.get("provider_parameters", {})
    force_fail = bool(parameters.get("force_review_fail")) or scenario in {
        "fail",
        "review_fail",
    }
    if force_fail:
        return {
            "status": "fail",
            "score": 58,
            "issues": [
                {
                    "issue_id": "review-issue-1",
                    "severity": "error",
                    "category": "demo_control",
                    "message": "Mock 控制参数要求本次审核失败",
                    "node": "video_prompt",
                    "field_path": "provider_parameters.force_review_fail",
                    "suggested_fix": "移除强制失败参数后重新审核",
                }
            ],
            "return_to": "video_prompt",
            "required_changes": ["移除强制失败参数并重新生成视频提示词"],
        }
    return {
        "status": "pass",
        "score": 92,
        "issues": [],
        "return_to": None,
        "required_changes": [],
    }


def _video_clone_mapping_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    analysis = input_data.get("analysis", {})
    replacements = [
        reference
        for reference in input_data.get("replacement_references", [])
        if isinstance(reference, dict) and isinstance(reference.get("id"), str)
    ]
    replacement_ids = [reference["id"] for reference in replacements][:10]
    request_text = str(input_data.get("request_text", ""))
    clone_level = next(
        (level for level in ("结构借鉴", "平衡复刻", "高还原") if level in request_text),
        "平衡复刻",
    )
    mappings = []
    for index, shot in enumerate(analysis.get("shots", [])):
        replacement = replacements[index % len(replacements)]
        mappings.append(
            {
                "shot_id": shot["shot_id"],
                "replacement_reference_ids": [replacement["id"]],
                "retained_structure": [
                    shot.get("purpose", "other"),
                    shot.get("reusable_pattern", "镜头功能"),
                ],
                "rewritten_subject": f"使用 {replacement.get('label', '替换素材')} 作为新主体",
                "rewritten_action": f"围绕用户目标重做：{shot.get('action', '完成核心演示')}",
                "rewritten_dialogue_or_text": "使用用户品牌与产品信息重写表达",
                "compliance_changes": ["替换原人物、商标和可识别布景", "不沿用原片独特台词"],
            }
        )
    return {
        "strategy": "保留参考片的钩子功能、节奏和镜头逻辑，全面替换主体、场景与表达。",
        "clone_level": clone_level,
        "source_reference_id": analysis.get("reference_id", "reference-video"),
        "replacement_reference_ids": replacement_ids,
        "mappings": mappings,
        "continuity_rules": [
            "替换主体外观跨镜头一致",
            "商品结构和品牌文字保持准确",
            "动作点与切镜节奏连续",
        ],
        "compliance_notes": ["不复用原片人物肖像、商标、独特台词或可识别布景"],
    }


def _video_clone_prompt_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    mapping = input_data.get("mapping", {})
    analysis = input_data.get("analysis", {})
    reference_ids = [
        reference["id"]
        for reference in input_data.get("references", [])
        if isinstance(reference, dict) and isinstance(reference.get("id"), str)
    ][:10]
    shots_by_id = {
        shot["shot_id"]: shot
        for shot in analysis.get("shots", [])
        if isinstance(shot, dict) and isinstance(shot.get("shot_id"), str)
    }
    shot_prompts = []
    timeline = []
    for item in mapping.get("mappings", []):
        shot = shots_by_id.get(item.get("shot_id"), {})
        prompt = (
            f"{shot.get('start_seconds', 0)}-{shot.get('end_seconds', 3)} 秒；"
            f"{item.get('rewritten_subject')}；{item.get('rewritten_action')}；"
            f"{shot.get('shot_size', '近景')}，{shot.get('camera_movement', '稳定运镜')}；"
            f"{item.get('rewritten_dialogue_or_text', '')}；{shot.get('transition', '自然切镜')}。"
        )
        item_ids = item.get("replacement_reference_ids", [])
        shot_prompts.append(
            {
                "shot_id": item["shot_id"],
                "prompt": prompt,
                "negative_prompt": "主体漂移，商品变形，错误文字，水印，原片人物或商标复现",
                "reference_ids": item_ids,
            }
        )
        timeline.append(prompt)
    duration = input_data.get("duration_seconds", 10)
    aspect_ratio = input_data.get("aspect_ratio", "9:16")
    return {
        "optimization_summary": (
            "已把视频 DNA、素材绑定、时间轴和连续性约束合并为逐镜头生成提示词。"
        ),
        "shot_prompts": shot_prompts,
        "generation": {
            "prompt": "\n".join(timeline),
            "negative_prompt": (
                "主体漂移，商品结构变化，文字乱码，错误品牌，水印，"
                "原片人物、商标或独特布景复现"
            ),
            "duration_seconds": duration,
            "aspect_ratio": aspect_ratio,
            "reference_ids": reference_ids,
            "provider_parameters": {"motion_strength": 0.65},
        },
    }


def _fixture_for(
    output_model: type[BaseModel], input_data: dict[str, Any], scenario: str
) -> dict[str, Any]:
    fixture_builders = {
        IntentDecision: _intent_payload,
        DirectorOutput: _creative_brief_payload,
        ResearchOutput: _research_payload,
        ResearchStrategyOutput: _research_strategy_payload,
        StrategyOutput: _strategy_payload,
        ProductionCoordinatorOutput: _production_coordinator_payload,
        ProductionPackageOutput: _production_package_payload,
        BrandPackagingOutput: _brand_packaging_payload,
        CopywritingOutput: _copywriting_payload,
        StoryboardOutput: _storyboard_payload,
        VideoPromptOutput: _video_prompt_payload,
        VideoCloneMappingOutput: _video_clone_mapping_payload,
        VideoClonePromptOutput: _video_clone_prompt_payload,
    }
    if output_model is ReviewerOutput:
        return _review_payload(input_data, scenario)
    builder = fixture_builders.get(output_model)
    if builder is None:
        raise ValueError(f"No mock fixture registered for {output_model.__name__}")
    return builder(input_data)


class DeterministicMockAgentModelProvider:
    provider_name = "mock"
    is_mock = True

    def __init__(self, control: MockProviderControl | None = None) -> None:
        self.control = control or MockProviderControl()

    async def generate_structured[OutputT: BaseModel](
        self,
        *,
        system_prompt: str,
        input_data: dict[str, Any],
        output_model: type[OutputT],
        model: str | None = None,
        timeout_seconds: int = 60,
        metadata: dict[str, Any] | None = None,
    ) -> StructuredGenerationResult[OutputT]:
        del system_prompt, timeout_seconds, metadata
        started = perf_counter()
        await asyncio.sleep(self.control.latency_ms / 1000)
        if self.control.scenario == "provider_error":
            raise RuntimeError("Mock model provider error requested by control scenario")
        if self.control.scenario == "coordinator_error" and output_model in {
            ProductionCoordinatorOutput,
            ProductionPackageOutput,
        }:
            raise RuntimeError("Mock coordinator provider error requested by control scenario")
        specialist_errors = {
            "copywriter_error": CopywritingOutput,
            "storyboard_error": StoryboardOutput,
            "video_prompt_error": VideoPromptOutput,
        }
        if specialist_errors.get(self.control.scenario) is output_model or (
            self.control.scenario in specialist_errors and output_model is ProductionPackageOutput
        ):
            raise RuntimeError(f"Mock {self.control.scenario} requested by control scenario")
        payload = (
            {}
            if self.control.scenario == "validation_error"
            else _fixture_for(output_model, input_data, self.control.scenario)
        )
        if self.control.scenario == "coordinator_invalid_reference" and output_model in {
            ProductionCoordinatorOutput,
            ProductionPackageOutput,
        }:
            plan = payload.get("production_plan", payload)
            plan["allowed_reference_ids"] = ["unknown-reference-id"]
        output = output_model.model_validate(payload)
        raw_output = json.dumps(output.model_dump(mode="json"), ensure_ascii=False)
        return StructuredGenerationResult[OutputT](
            output=output,
            raw_output=raw_output,
            provider=self.provider_name,
            model=model or "mock-structured-v1",
            input_tokens=0,
            output_tokens=0,
            duration_ms=max(0, round((perf_counter() - started) * 1000)),
        )


class DeterministicMockResearchProvider:
    provider_name = "mock"
    is_mock = True

    def __init__(self, control: MockProviderControl | None = None) -> None:
        self.control = control or MockProviderControl()

    async def search(self, *, queries: list[ResearchQuery]) -> ResearchProviderResult:
        await asyncio.sleep(self.control.latency_ms / 1000)
        if self.control.scenario == "provider_error":
            raise RuntimeError("Mock research provider error requested by control scenario")
        sources = [
            ResearchSource(
                source_id=f"mock-source-{index}",
                title=f"Demo 研究样本 {index}",
                evidence_type=EvidenceType.DEMO_SOURCE,
                url=f"https://mock.local/research/{index}",
                summary=f"围绕“{query.query}”的结构化 Demo 研究结论。",
                retrieved_at=datetime.now(UTC),
            )
            for index, query in enumerate(queries, start=1)
        ]
        return ResearchProviderResult(provider=self.provider_name, is_mock=True, sources=sources)


class DeterministicMockVideoProvider:
    provider_name = "mock"
    is_mock = True

    def __init__(self, control: MockProviderControl | None = None) -> None:
        self.control = control or MockProviderControl()
        self._tasks: dict[str, VideoTask] = {}
        self._lock = asyncio.Lock()

    async def submit(self, *, request: VideoGenerationRequest) -> VideoTask:
        del request
        await asyncio.sleep(self.control.latency_ms / 1000)
        if self.control.scenario == "provider_error":
            raise RuntimeError("Mock video provider error requested by control scenario")
        task = VideoTask(
            task_id=f"mock-video-{uuid4().hex}",
            provider=self.provider_name,
            is_mock=True,
            status=VideoTaskStatus.QUEUED,
            progress=0,
        )
        async with self._lock:
            self._tasks[task.task_id] = task
        return task.model_copy(deep=True)

    async def get_status(self, *, task_id: str) -> VideoTask:
        await asyncio.sleep(self.control.latency_ms / 1000)
        if self.control.scenario == "provider_error":
            raise RuntimeError("Mock video provider error requested by control scenario")
        async with self._lock:
            current = self._tasks.get(task_id)
            if current is None:
                raise KeyError(f"Unknown mock video task: {task_id}")
            if current.status is VideoTaskStatus.QUEUED:
                updated = current.model_copy(
                    update={"status": VideoTaskStatus.PROCESSING, "progress": 0.5}
                )
            elif current.status is VideoTaskStatus.PROCESSING:
                if self.control.scenario == "video_fail":
                    updated = current.model_copy(
                        update={
                            "status": VideoTaskStatus.FAILED,
                            "progress": 1,
                            "error_code": "MOCK_VIDEO_FAILED",
                            "error_message": "Mock video failure requested by control scenario",
                        }
                    )
                else:
                    updated = current.model_copy(
                        update={
                            "status": VideoTaskStatus.COMPLETED,
                            "progress": 1,
                            "result_url": f"https://mock.local/videos/{task_id}.mp4",
                        }
                    )
            else:
                updated = current
            self._tasks[task_id] = updated
            return updated.model_copy(deep=True)
