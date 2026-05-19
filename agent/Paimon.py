from agent.BasicRole import BasicRole
from dotenv import load_dotenv
from pathlib import Path
import yaml
from tool.xng.langgraph_search_tool import get_xng_tools

# 加载 .env，让 BasicRole 默认模型配置可直接生效
load_dotenv()

# 从 YAML 读取派蒙系统提示词（包含人设、风格与安全约束）
prompt_path = Path(__file__).with_name("PaimonPrompt.yaml")
with prompt_path.open("r", encoding="utf-8") as f:
    prompt_config = yaml.safe_load(f)
system_prompt = prompt_config["system_prompt"]

# 派蒙角色的开场用户提示词：作为首次对话的默认输入
user_prompt = "你好派蒙，我们开始聊天吧。"
role_data_dir = Path(__file__).resolve().parent.parent / "data" / "role" / "role_json"
role_tools = get_xng_tools()

Paimon = BasicRole(
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    role="派蒙",
    tools=role_tools,
    vector_collections=["genshin_world_bg","genshin_story"],
    user_id="paimon_default_user",
)


Paimon.multi_round_chat()
