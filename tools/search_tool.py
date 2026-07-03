import os
import time
from dotenv import load_dotenv
from langchain_community.tools import TavilySearchResults

load_dotenv()


def get_search_tool(max_results=7):
    """
    初始化搜索工具
    max_results: 每次搜索返回的条目数，默认7条（确保5条有效岗位）
    """
    try:
        search_tool = TavilySearchResults(
            api_key=os.getenv("TAVILY_API_KEY"),
            max_results=max_results,
            search_depth="basic",
            include_answer=True,
        )
        return search_tool
    except Exception as e:
        print(f"⚠️  搜索工具初始化失败: {str(e)[:80]}")

        class EmptySearchTool:
            def run(self, query):
                return "（搜索服务暂时不可用，请检查网络连接或 API Key）"

        return EmptySearchTool()


def get_search_queries(major, target_job, city, skills, batch=0):
    """
    根据当前批次生成不同的搜索关键词组合，实现"下一批"换一批效果
    batch=0：常规搜索
    batch=1：换平台 + 加"内推"
    batch=2：加"校招/实习"关键词 + 薪资
    batch>=3：随机组合
    """
    base_queries = [
        # 第1批：常规匹配
        f"{city} {target_job} 实习 {major} 招聘",
        f"{target_job} {city} 应届生实习 岗位职责",
        # 第2批：换平台关键词
        f"{city} {target_job} 实习 内推 招聘信息",
        f"{target_job} {city} 校招实习 招聘网站",
        # 第3批：加技能和薪资
        f"{city} {target_job} 实习 要求 {skills}",
        f"{target_job} 实习 {city} 薪资 200/天",
    ]
    # 不同批次选不同关键词
    if batch % 3 == 0:
        return base_queries[0], base_queries[1]
    elif batch % 3 == 1:
        return base_queries[2], base_queries[3]
    else:
        return base_queries[4], base_queries[5]
