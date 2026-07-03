import os
import time
from dotenv import load_dotenv
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

load_dotenv()


class BaseAgent:
    def __init__(self):
        self.llm = ChatTongyi(
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
            model="qwen-turbo",
            temperature=0.1,
        )
        # 用字典存储多个独立的记忆空间，key为 session_id
        self.history_stores = {}

    def _get_or_create_history(self, session_id):
        """获取或创建指定 session_id 的对话历史"""
        if session_id not in self.history_stores:
            self.history_stores[session_id] = InMemoryChatMessageHistory()
        return self.history_stores[session_id]

    def run(self, prompt: str, session_id="default", max_retries=2) -> str:
        """
        带记忆的调用，相同 session_id 共享对话历史
        增加异常处理和自动重试，避免网络波动导致崩溃
        """
        for attempt in range(max_retries + 1):
            try:
                llm_with_history = RunnableWithMessageHistory(
                    self.llm, lambda sid: self._get_or_create_history(sid)
                )
                response = llm_with_history.invoke(
                    [HumanMessage(content=prompt)], config={"session_id": session_id}
                )
                return response.content
            except Exception as e:
                if attempt < max_retries:
                    # 网络波动，等待 1 秒后重试
                    print(f"⚠️  LLM 调用失败，第 {attempt + 1} 次重试: {str(e)[:80]}")
                    time.sleep(1)
                else:
                    # 重试失败，返回友好提示
                    return f"⚠️  AI服务暂时不可用（{str(e)[:80]}），请稍后重试"
        return "⚠️ AI服务暂时不可用，请稍后重试"

    def run_stateless(self, prompt: str, max_retries=2) -> str:
        """
        无状态调用：每次调用都是全新会话，不带任何历史记忆
        增加异常处理和自动重试
        """
        for attempt in range(max_retries + 1):
            try:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                return response.content
            except Exception as e:
                if attempt < max_retries:
                    print(f"⚠️  LLM 调用失败，第 {attempt + 1} 次重试: {str(e)[:80]}")
                    time.sleep(1)
                else:
                    return f"⚠️  AI服务暂时不可用（{str(e)[:80]}），请稍后重试"
        return "⚠️ AI服务暂时不可用，请稍后重试"

    def clear_memory(self, session_id="default"):
        """清空指定 session 的记忆（不传则清空 default）"""
        if session_id in self.history_stores:
            self.history_stores[session_id].clear()

    def clear_all_memory(self):
        """清空所有 session 的记忆"""
        self.history_stores.clear()
