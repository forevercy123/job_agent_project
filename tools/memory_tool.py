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
            def similarity_search(self, query, k=2, filter=None):
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


def reset_vector_db(user_id: int = None):
    """
    清空向量库数据（指定 user_id 时只清空该用户，不影响其他用户）
    通过 Chroma collection 的 delete 接口实现，避免 Windows 文件锁定问题
    """
    try:
        vdb = get_memory_vector_store()
        collection = vdb._collection
        if collection.count() == 0:
            return vdb
        if user_id is None:
            # 全量清空（保留给管理员或调试场景）
            all_ids = collection.get()["ids"]
            collection.delete(ids=all_ids)
            print("[memory] 已清空向量库全部数据")
        else:
            # 只清空当前用户的数据
            user_docs = collection.get(
                where={"user_id": int(user_id)},
                include=[],
            )
            user_ids = user_docs.get("ids", [])
            if user_ids:
                collection.delete(ids=user_ids)
                print(f"[memory] 已清空用户 {user_id} 的 {len(user_ids)} 条记录")
        return vdb
    except Exception as e:
        print(f"⚠️  清空向量库失败: {str(e)[:80]}")
        return None


def save_user_info(user_info: str, user_id: int):
    """保存用户求职信息到向量库（按 user_id 隔离，追加模式）"""
    if user_id is None:
        print("⚠️  save_user_info: user_id 不能为空")
        return False
    try:
        vdb = get_memory_vector_store()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        info_with_timestamp = f"[{timestamp}] {user_info}"
        vdb.add_texts(
            [info_with_timestamp],
            metadatas=[
                {
                    "type": "user_base_info",
                    "timestamp": timestamp,
                    "user_id": int(user_id),
                }
            ],
        )
        return True
    except Exception as e:
        print(f"⚠️  保存记忆失败: {str(e)[:80]}")
        return False


def recall_user_info(query: str, user_id: int, top_k=5):
    """从向量库中检索**当前用户**的历史信息（按 user_id 过滤，避免跨用户数据泄漏）"""
    if user_id is None:
        return "（用户未登录，无法访问记忆）"
    try:
        vdb = get_memory_vector_store()
        collection = vdb._collection
        if collection.count() == 0:
            return "（暂无历史记忆，请先保存个人信息）"
        # 按 user_id 过滤后再做相似度检索
        res = vdb.similarity_search(
            query,
            k=top_k,
            filter={"user_id": int(user_id)},
        )
        if not res:
            return "（您暂未保存任何个人信息，请先在左侧填写并保存）"
        formatted = []
        for i, doc in enumerate(res, 1):
            formatted.append(f"记录{i}: {doc.page_content}")
        return "\n".join(formatted)
    except Exception as e:
        return f"（记忆检索失败: {str(e)[:80]}）"


def get_all_memory_count(user_id: int = None):
    """返回向量库中的记录总数（指定 user_id 时只统计该用户）"""
    try:
        vdb = get_memory_vector_store()
        collection = vdb._collection
        if user_id is None:
            return collection.count()
        # 按 user_id 过滤统计
        result = collection.get(
            where={"user_id": int(user_id)},
            include=[],
        )
        return len(result.get("ids", []))
    except Exception as e:
        print(f"⚠️  查询记忆数量失败: {str(e)[:80]}")
        return 0


def get_all_memory_text(user_id: int = None):
    """返回向量库中的记忆文本（指定 user_id 时只返回该用户的数据）"""
    try:
        vdb = get_memory_vector_store()
        collection = vdb._collection
        if collection.count() == 0:
            return "（向量库为空）"
        # 按 user_id 过滤
        if user_id is not None:
            all_docs = collection.get(
                where={"user_id": int(user_id)},
                include=["documents", "metadatas"],
            )
        else:
            all_docs = collection.get(include=["documents", "metadatas"])
        if not all_docs.get("ids"):
            return "（您暂未保存任何信息）"
        formatted = []
        for i, (doc, meta) in enumerate(
            zip(all_docs["documents"], all_docs["metadatas"]), 1
        ):
            ts = meta.get("timestamp", "未知时间") if meta else "未知时间"
            formatted.append(f"[{ts}] 记录{i}: {doc}")
        return "\n".join(formatted)
    except Exception as e:
        return f"（读取记忆失败: {str(e)[:80]}）"
