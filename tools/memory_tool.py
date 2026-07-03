import chromadb
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
DB_PATH = "./vector_db"


def get_memory_vector_store():
    """获取或初始化向量库（不删除现有数据），增加异常处理"""
    try:
        embedding = DashScopeEmbeddings(
            model="text-embedding-v1", dashscope_api_key=os.getenv("DASHSCOPE_API_KEY")
        )
        vdb = Chroma(
            persist_directory=DB_PATH,
            embedding_function=embedding,
            client=chromadb.PersistentClient(path=DB_PATH),
        )
        return vdb
    except Exception as e:
        print(f"⚠️  向量库初始化失败: {str(e)[:80]}")

        # 返回一个简单的空包装对象，避免上游崩溃
        class EmptyVectorStore:
            def similarity_search(self, query, k=2):
                return []

            @property
            def _collection(self):
                class EmptyColl:
                    def count(self):
                        return 0

                    def get(self, **kwargs):
                        return {"ids": [], "documents": [], "metadatas": []}

                    def delete(self, ids=None):
                        pass

                return EmptyColl()

            def add_texts(self, texts, metadatas=None):
                print("⚠️  向量库不可用，数据未持久化保存")

        return EmptyVectorStore()


def reset_vector_db():
    """
    清空向量库中的所有数据（不删除文件，避免 Windows 文件锁定问题）
    通过 Chroma collection 的 delete 接口实现
    """
    try:
        vdb = get_memory_vector_store()
        collection = vdb._collection
        if collection.count() > 0:
            all_ids = collection.get()["ids"]
            collection.delete(ids=all_ids)
        return vdb
    except Exception as e:
        print(f"⚠️  清空向量库失败: {str(e)[:80]}")
        return None


def save_user_info(user_info: str):
    """保存用户求职信息到向量库（追加模式），增加异常处理"""
    try:
        vdb = get_memory_vector_store()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        info_with_timestamp = f"[{timestamp}] {user_info}"
        vdb.add_texts(
            [info_with_timestamp],
            metadatas=[{"type": "user_base_info", "timestamp": timestamp}],
        )
        return True
    except Exception as e:
        print(f"⚠️  保存记忆失败: {str(e)[:80]}")
        return False


def recall_user_info(query: str, top_k=5):
    """从向量库中检索相关的历史用户信息，增加异常处理"""
    try:
        vdb = get_memory_vector_store()
        collection = vdb._collection
        if collection.count() == 0:
            return "（暂无历史记忆，请先保存个人信息）"
        res = vdb.similarity_search(query, k=top_k)
        formatted = []
        for i, doc in enumerate(res, 1):
            formatted.append(f"记录{i}: {doc.page_content}")
        return "\n".join(formatted)
    except Exception as e:
        return f"（记忆检索失败: {str(e)[:80]}）"


def get_all_memory_count():
    """返回当前向量库中的记录总数"""
    try:
        vdb = get_memory_vector_store()
        collection = vdb._collection
        return collection.count()
    except Exception as e:
        print(f"⚠️  查询记忆数量失败: {str(e)[:80]}")
        return 0


def get_all_memory_text():
    """返回向量库中所有记忆文本"""
    try:
        vdb = get_memory_vector_store()
        collection = vdb._collection
        if collection.count() == 0:
            return "（向量库为空）"
        all_docs = collection.get(include=["documents", "metadatas"])
        formatted = []
        for i, (doc, meta) in enumerate(
            zip(all_docs["documents"], all_docs["metadatas"]), 1
        ):
            ts = meta.get("timestamp", "未知时间") if meta else "未知时间"
            formatted.append(f"[{ts}] 记录{i}: {doc}")
        return "\n".join(formatted)
    except Exception as e:
        return f"（读取记忆失败: {str(e)[:80]}）"
