from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
import sys

from langchain_core.tools import tool

# 角色数据文件目录
ROLE_DIR = Path(__file__).resolve().parents[2] / "data" / "role" / "role_json"


def read_role(role: str) -> dict[str, Any]:
    """
    读取角色 JSON 原始数据。

    Args:
        role: 角色文件名（不含 .json）。
    """
    role_path = ROLE_DIR / f"{role}.json"
    with role_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def miss(role: str, err: FileNotFoundError) -> dict[str, Any]:
    """找不到角色文件时，返回可直接给模型的错误信息。"""
    # 记录错误日志，避免工具调用直接崩溃
    print(f"[角色工具] 找不到角色数据文件：{role}", file=sys.stderr, flush=True)
    return {
        "角色": role,
        "错误": str(err),
        "可能原因": "角色数据文件名为中文，请使用角色中文名（例如：胡桃），不要使用英文名或拼音。",
    }


def run(role: str, label: str, fn: Callable[[str], Any]) -> dict[str, Any]:
    """
    统一封装工具调用，捕获所有异常并返回结构化错误信息。

    Args:
        role: 角色中文名。
        label: 返回数据的标签（如 "数据"、"属性数据"）。
        fn: 实际查询函数。
    """
    print(f"[角色工具] 调用 {fn.__name__}，角色：{role}", file=sys.stderr, flush=True)
    try:
        return {"角色": role, label: fn(role)}
    except FileNotFoundError as err:
        return miss(role, err)
    except StopIteration:
        print(f"[角色工具] 角色 {role} 缺少必要模板块：{fn.__name__}", file=sys.stderr, flush=True)
        return {
            "角色": role,
            "错误": f"角色数据中缺少 {label} 对应的模板块",
            "提示": "该角色数据可能不完整，请尝试查询其他信息。",
        }
    except Exception as err:
        print(f"[角色工具] {fn.__name__} 调用异常：{type(err).__name__}: {err}", file=sys.stderr, flush=True)
        return {
            "角色": role,
            "错误": f"查询 {label} 时发生异常：{type(err).__name__}",
            "提示": "请换一种方式提问，或查询该角色的其他信息。",
        }


def pick(blocks: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """
    从模板块中取出指定 name 的条目。

    Args:
        blocks: JSON 中的 blocks 列表。
        name: 模板名称（如 角色/属性数据）。
    """
    return next(
        block for block in blocks if block["type"] == "template" and block["name"] == name
    )


def q_role(role: str) -> dict[str, Any]:
    """
    查询角色基础信息（模板：角色）。

    Args:
        role: 角色中文名（不含 .json）。
    """
    raw = read_role(role)
    return pick(raw["blocks"], "角色")["data"]


def q_attr(role: str) -> dict[str, Any]:
    """
    查询角色属性数据（模板：角色/属性数据）。

    Args:
        role: 角色文件名（不含 .json）。
    """
    raw = read_role(role)
    return pick(raw["blocks"], "角色/属性数据")["data"]


def q_break(role: str) -> dict[str, Any]:
    """
    查询角色突破简表（模板：角色/突破简）。

    Args:
        role: 角色文件名（不含 .json）。
    """
    raw = read_role(role)
    return pick(raw["blocks"], "角色/突破简")["data"]


def q_info(role: str) -> dict[str, Any]:
    """
    查询角色信息（模板：角色/信息）。

    Args:
        role: 角色文件名（不含 .json）。
    """
    raw = read_role(role)
    return pick(raw["blocks"], "角色/信息")["data"]


def q_con(role: str) -> dict[str, Any]:
    """
    查询角色命之座（模板：角色/命之座）。

    Args:
        role: 角色文件名（不含 .json）。
    """
    raw = read_role(role)
    return pick(raw["blocks"], "角色/命之座")["data"]


def q_skill(role: str) -> list[dict[str, Any]]:
    """
    查询角色技能列表（模板：角色技能/*）。

    Args:
        role: 角色文件名（不含 .json）。
    """
    raw = read_role(role)
    skills: list[dict[str, Any]] = []
    for block in raw["blocks"]:
        if block["type"] != "template":
            continue
        if not block["name"].startswith("角色技能/"):
            continue
        # 角色技能条目按出现顺序输出
        kind = block["name"].split("/", 1)[1]
        skills.append({"序号": kind, "技能名": block["args"][0]})
    return skills


def q_talent(role: str) -> list[dict[str, Any]]:
    """
    查询天赋技能详情（模板：天赋技能）。

    Args:
        role: 角色文件名（不含 .json）。
    """
    raw = read_role(role)
    talents: list[dict[str, Any]] = []
    for block in raw["blocks"]:
        if block["type"] != "template" or block["name"] != "天赋技能":
            continue
        # 天赋技能完整保留 data，并补上序号
        info = dict(block["data"])
        info["序号"] = block["args"][0]
        talents.append(info)
    return talents


@tool
def role_base(role: str) -> dict[str, Any]:
    """
    查询角色的基础信息，返回角色的核心档案数据。

    可获取的信息包括：
    - 身份标识：名称（中文名）、称号（如"白鹭霜华"）、全名、英文名称
    - 稀有度与属性：稀有度（4星/5星）、元素属性（火/水/风/雷/冰/岩/草）、武器类型（单手剑/双手剑/长柄武器/法器/弓）
    - 归属信息：所属国家/地区（蒙德/璃月/稻妻/须弥/枫丹/纳塔/至冬等）、种族
    - 角色特征：性别（男/女）、命之座名称、特殊料理名称、TAG标签
    - 版本信息：是否为限定角色、实装日期、首次实装的游戏版本号
    - 角色介绍：官方背景介绍文本

    适用场景：用户询问角色的基本信息、身份、稀有度、元素、武器、所属国家等。

    Args:
        role: 角色中文名（例如：胡桃、神里绫华、钟离）。
    """
    return run(role, "数据", q_role)


@tool
def role_attr(role: str) -> dict[str, Any]:
    """
    查询角色的属性数值数据，包含基础属性及其在各等级/突破阶段的具体数值。

    可获取的信息包括：
    - 基础属性初始值：生命上限、攻击力、防御力
    - 各等级/突破阶段的属性数值：包含 20级、20级突破、40级、40级突破、50级、50级突破、
      60级、60级突破、70级、70级突破、80级、80级突破、90级 共13个阶段的生命上限/攻击力/防御力数值
    - 突破加成属性：角色突破时额外提升的属性类型（如暴击率、暴击伤害、元素充能效率等）
    - 突破加成数值：各突破阶段（突破20、未破40、突破40、未破50、突破50、未破60、突破60、
      未破70、突破70、未破80、突破80、未破90、突破90）对应的加成属性百分比数值

    注意：所有数值均为角色基础白值，不包含武器、圣遗物等外部加成。

    适用场景：用户询问角色各等级属性数值、突破属性加成、角色基础面板数据。

    Args:
        role: 角色中文名（例如：胡桃、神里绫华、钟离）。
    """
    return run(role, "属性数据", q_attr)


@tool
def role_break(role: str) -> dict[str, Any]:
    """
    查询角色突破所需的材料概览，列出每种材料的名称但不包含具体数量。

    可获取的信息包括：
    - 突破特产材料：角色所在地区的特产采集物名称（如绯樱绣球、琉璃袋、劫波莲等）
    - 突破晶石材料序列：对应元素属性的晶石/晶块系列名称（如哀叙冰玉、坚牢黄玉等）
    - 突破BOSS材料：需要击败的世界BOSS掉落的专属材料名称（如常燃火种、飓风之种等）
    - 突破普通材料序列：需要刷取的普通怪物掉落材料名称（如刀镡、史莱姆凝液等）
    - 20级新天赋：角色20级突破后解锁的固有天赋名称
    - 60级新天赋：角色60级突破后解锁的固有天赋名称

    重要提示：本工具仅列出材料名称，不包含每个突破等级所需的具体数量。如需完整的突破材料
    数量表，请结合本工具返回的材料名称，使用联网搜索功能查询各等级的具体需求量。

    适用场景：用户询问角色突破需要什么材料、突破材料清单、角色培养材料。

    Args:
        role: 角色中文名（例如：胡桃、神里绫华、钟离）。
    """
    return run(role, "突破简", q_break)


@tool
def role_info(role: str) -> dict[str, Any]:
    """
    查询角色的详细背景信息，包含配音演员、角色设定、社交关系等非战斗数据。

    可获取的信息包括：
    - 配音演员：中文CV、日文CV、英文CV、韩文CV（四种语言的配音演员姓名）
    - 角色设定：昵称/外号（玩家社区常用的称呼）、生日（月日格式）、体型（成男/成女/少年/少女/幼女）
    - 角色身份：归属（所属组织或势力，如社奉行、骑士团等）、职业、角色属性（如神之眼持有者等）
    - 卡池信息：卡池名（角色UP时的卡池命名）
    - 任务相关：个人任务/传说任务名称
    - 衣装信息：衣装名称（角色皮肤/衣装名称）
    - 名片信息：名片名称、名片描述（角色好感度满级后解锁的名片详情）

    适用场景：用户询问角色配音演员（CV）、生日、体型、所属组织、名片、外号/昵称等背景信息。

    Args:
        role: 角色中文名（例如：胡桃、神里绫华、钟离）。
    """
    return run(role, "信息", q_info)


@tool
def role_con(role: str) -> dict[str, Any]:
    """
    查询角色的命之座（命座/星座/Constellation）信息，返回全部6层命之座的名称与效果。

    可获取的信息包括：
    - 命之座1-6层：每层命之座的名称和具体效果描述
    - 命之座1：第1层命之座名称及效果
    - 命之座2：第2层命之座名称及效果
    - 命之座3：第3层命之座名称及效果
    - 命之座4：第4层命之座名称及效果
    - 命之座5：第5层命之座名称及效果
    - 命之座6：第6层命之座名称及效果（满命效果，通常质变）

    说明：命之座是角色的重复获取强化系统，每获取一个相同角色可激活一层命之座，提升角色
    战斗能力。玩家社区中"几命""多少命"即指命之座层数。

    适用场景：用户询问角色命之座/命座/星座效果、几命质变、满命效果等。

    Args:
        role: 角色中文名（例如：胡桃、神里绫华、钟离）。
    """
    return run(role, "命之座", q_con)


@tool
def role_skill(role: str) -> dict[str, Any]:
    """
    查询角色的技能列表，返回角色拥有的所有技能/天赋的序号与名称汇总。

    可获取的信息包括：
    - 技能序号：技能在角色数据中的排列顺序编号
    - 技能名：技能的中文全称（如"普通攻击·神里流·倾""神里流·冰华""神里流·霜灭"等）

    说明：此工具返回技能概览（名称列表），如需查看某个技能在各等级下的详细数值
    （如伤害倍率、冷却时间、持续时长等），请使用 role_talent 工具查询具体的技能数值详情。

    适用场景：用户询问角色有哪些技能、技能名称是什么；需要先了解技能列表再进一步查询具体技能详情时。

    Args:
        role: 角色中文名（例如：胡桃、神里绫华、钟离）。
    """
    return run(role, "技能列表", q_skill)


@tool
def role_talent(role: str) -> dict[str, Any]:
    """
    查询角色的天赋技能详细数值，返回每个技能在各等级（1-15级）下的具体倍率或效果数据。

    每个天赋技能条目包含以下信息：
    - 序号：天赋在角色数据中的排列编号，与 role_skill 工具返回的序号对应
    - GIF：关联的展示动画编号
    - 技能名：技能的完整中文名称
    - 描述：技能的官方文本描述，说明技能的功能和使用方式
    - 属性列表及等级数值：每个属性维度（如"一段伤害""二段伤害""技能伤害""持续时长"
      "冷却时间"等）在 LV1 到 LV15 共15个等级下的具体数值。属性维度数量和名称因技能
      而异，取决于该技能的设计复杂度。

    说明：此工具返回的是角色详细的技能倍率数据，包含普通攻击的每一段伤害、元素战技和
    元素爆发的各级倍率、冷却时间、持续时长等精确数值。如需先了解角色有哪些技能，
    可使用 role_skill 工具查看技能名称列表。

    适用场景：用户询问技能伤害倍率、技能各等级数值对比、技能冷却时间、技能具体效果等
    详细的战斗数据。

    Args:
        role: 角色中文名（例如：胡桃、神里绫华、钟离）。
    """
    return run(role, "天赋技能", q_talent)