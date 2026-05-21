from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
        role: 角色文件名（不含 .json）。
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
    输出角色基础信息（模板：角色）。字段包括：名称、称号、全名、英文名称、稀有度、所属、
    种族、介绍、元素属性、武器类型、命之座、特殊料理、性别、TAG、限定、实装日期、实装版本。

    Args:
        role: 角色文件名（不含 .json）。

    输出示例:
        ```json
        {
          "角色": "神里绫华",
          "数据": {
            "名称": "神里绫华",
            "称号": "白鹭霜华",
            "英文名称": "Kamisato Ayaka",
            "稀有度": "5星",
            "所属": "稻妻",
            "元素属性": "冰",
            "武器类型": "单手剑"
          }
        }
        ```
    """
    return {"角色": role, "数据": q_role(role)}


@tool
def role_attr(role: str) -> dict[str, Any]:
    """
    输出角色属性数据（模板：角色/属性数据）。字段包括：
    生命上限及各等级/突破（生命上限、20生命上限、20+生命上限、40生命上限、40+生命上限、
    50生命上限、50+生命上限、60生命上限、60+生命上限、70生命上限、70+生命上限、
    80生命上限、80+生命上限、90生命上限）；
    攻击力及各等级/突破（攻击力、20攻击力、20+攻击力、40攻击力、40+攻击力、50攻击力、
    50+攻击力、60攻击力、60+攻击力、70攻击力、70+攻击力、80攻击力、80+攻击力、90攻击力）；
    防御力及各等级/突破（防御力、20防御力、20+防御力、40防御力、40+防御力、50防御力、
    50+防御力、60防御力、60+防御力、70防御力、70+防御力、80防御力、80+防御力、90防御力）；
    突破加成属性；突破加成数值（突破20、未破40、突破40、未破50、突破50、未破60、突破60、
    未破70、突破70、未破80、突破80、未破90、突破90）。

    Args:
        role: 角色文件名（不含 .json）。

    输出示例:
        ```json
        {
          "角色": "神里绫华",
          "属性数据": {
            "生命上限": "1001",
            "20生命上限": "2597",
            "攻击力": "27",
            "防御力": "61",
            "突破加成属性": "暴击伤害",
            "突破40": "9.6%"
          }
        }
        ```
    """
    return {"角色": role, "属性数据": q_attr(role)}


@tool
def role_break(role: str) -> dict[str, Any]:
    """
    输出角色突破材料简介表（模板：角色/突破简）。字段包括：突破特产材料、突破晶石材料序列、
    突破BOSS材料、突破普通材料序列、20级新天赋、60级新天赋。
    信息中缺少材料的数量，请你联网搜索各材料需要的数量再整理给用户。

    Args:
        role: 角色文件名（不含 .json）。

    输出示例:
        ```json
        {
          "角色": "神里绫华",
          "突破简": {
            "突破特产材料": "绯樱绣球",
            "突破晶石材料序列": "哀叙冰玉",
            "突破BOSS材料": "恒常机关之心",
            "突破普通材料序列": "刀镡",
            "20级新天赋": "天罪国罪镇词",
            "60级新天赋": "寒天宣命祝词"
          }
        }
        ```
    """
    return {"角色": role, "突破简": q_break(role)}


@tool
def role_info(role: str) -> dict[str, Any]:
    """
    输出角色信息（模板：角色/信息）。字段包括：昵称/外号、中文CV、日文CV、英文CV、韩文CV、
    生日、体型、卡池名、个人任务、角色属性、衣装名称、归属、职业、名片名称、名片描述。

    Args:
        role: 角色文件名（不含 .json）。

    输出示例:
        ```json
        {
          "角色": "神里绫华",
          "信息": {
            "昵称/外号": "白鹭公主",
            "中文CV": "小N",
            "生日": "9月28日",
            "体型": "少女",
            "归属": "社奉行",
            "名片名称": "神里绫华·扇子"
          }
        }
        ```
    """
    return {"角色": role, "信息": q_info(role)}


@tool
def role_con(role: str) -> dict[str, Any]:
    """
    输出角色命之座（模板：角色/命之座）。字段包括：
    命之座1、命之座1效果、命之座2、命之座2效果、命之座3、命之座3效果、
    命之座4、命之座4效果、命之座5、命之座5效果、命之座6、命之座6效果。

    Args:
        role: 角色文件名（不含 .json）。

    输出示例:
        ```json
        {
          "角色": "神里绫华",
          "命之座": {
            "命之座1": "霜杀墨染樱",
            "命之座1效果": "普通攻击或重击造成冰元素伤害时，有概率缩短技能冷却。"
          }
        }
        ```
    """
    return {"角色": role, "命之座": q_con(role)}


@tool
def role_skill(role: str) -> dict[str, Any]:
    """
    输出角色技能列表（模板：角色技能/*），按数据中出现顺序返回序号与技能名称。
    字段包括：序号、技能名。

    Args:
        role: 角色文件名（不含 .json）。

    输出示例:
        ```json
        {
          "角色": "神里绫华",
          "技能列表": [
            {"序号": "1", "技能名": "普通攻击·神里流·倾"},
            {"序号": "2", "技能名": "神里流·冰华"}
          ]
        }
        ```
    """
    return {"角色": role, "技能列表": q_skill(role)}


@tool
def role_talent(role: str) -> dict[str, Any]:
    """
    输出天赋技能详情（模板：天赋技能），每条天赋包含序号与原始字段。
    字段包括：序号、GIF、技能名、描述、属性1..属性N，以及各属性的 LV1..LV15 数值
    （如 属性1LV1..属性1LV15、属性2LV1..属性2LV15）。

    Args:
        role: 角色文件名（不含 .json）。

    输出示例:
        ```json
        {
          "角色": "神里绫华",
          "天赋技能": [
            {
              "序号": "1",
              "GIF": "1",
              "技能名": "神里流·倾",
              "描述": "普通攻击\n\n进行至多五段的连续剑击。",
              "属性1": "一段伤害",
              "属性1LV1": "45.7%"
            }
          ]
        }
        ```
    """
    return {"角色": role, "天赋技能": q_talent(role)}