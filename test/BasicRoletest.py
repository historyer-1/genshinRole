from agent.BasicRole import BasicRole
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from agent.Paimon import chat

load_dotenv()


def test_api():
    """
    测试api是否正常工作
    """
    llm = ChatOpenAI(
        model=os.getenv("model"),
        api_key=os.getenv("api_key"),
        base_url=os.getenv("base_url"),
        temperature=1.0,          # 降低随机性，减少“脑补”     
    )
    # 传入一条标准对话消息
    result = llm.invoke([
        {"role": "user", "content": "你好，你是什么模型，请说中文"}
    ])
    print("llm.invoke result:", getattr(result, "content", result))



def test_role_work() -> None:
    
    role_default = BasicRole(system_prompt="你是助手", user_prompt="请开始对话")


    dummy_llm = ChatOpenAI(
            model=os.getenv("model"),
            api_key=os.getenv("api_key"),
            base_url=os.getenv("base_url"),
            max_tokens=50000,
        )
    role = BasicRole(system_prompt="你是助手", user_prompt="请开始对话", llm=dummy_llm)
    role.multi_round_chat()




chat()

