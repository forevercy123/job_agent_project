from agent.base_agent import BaseAgent
from agent.check_agent import CheckAgent
from tools.search_tool import get_search_tool, get_search_queries
import time


class SearchAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.search = get_search_tool(max_results=7)  # 每次搜7条（确保5条有效）
        self.checker = CheckAgent()

    def search_job(self, major, target_job, city, skills, batch=0):
        """
        搜索岗位
        batch: 当前批次号（0=第1批，1=第2批，2=第3批...）
        每批返回至少5个岗位，包含来源平台和投递链接
        """
        # 1. 根据批次选择不同的关键词组合搜索
        query1, query2 = get_search_queries(major, target_job, city, skills, batch)

        results_1 = self.search.run(query1)
        time.sleep(1)  # 避免 API 频限
        results_2 = self.search.run(query2)

        # 合并搜索结果
        combined_raw = f"=== 搜索批次 {batch + 1} ===\n\n【搜索词1】{query1}\n结果：{results_1}\n\n【搜索词2】{query2}\n结果：{results_2}"

        # 2. CheckAgent 过滤无效信息（剔除社招/过期/培训机构广告）
        cleaned_result = self.checker.check_job_result(combined_raw)

        # 3. LLM 整理成结构化输出（要求：每个岗位含来源平台+投递链接）
        prompt = f"""
你是专业的岗位推荐专家。根据以下搜索结果，整理适配应届生的实习岗位。

【用户信息】
专业：{major}
意向岗位：{target_job}
意向城市：{city}
掌握技能：{skills}
当前批次：第 {batch + 1} 批推荐

【已清洗的搜索结果】
{cleaned_result}

【输出格式要求】
严格按照以下 Markdown 格式输出，每个岗位占一个独立块，至少推荐 5 个岗位：

---

### 🎯 岗位推荐 1
**岗位名称**：xxx
**公司名称**：xxx
**所在城市**：xxx
**实习/兼职**：xxx
**岗位来源**：Boss直聘 / 实习僧 / 拉勾网 / 猎聘 / LinkedIn / 公司官网 / 其他
**投递链接**：🔗 [点击投递简历](这里填搜索结果中找到的真实URL，如果没找到就写"需自行搜索公司官网投递")
**薪资范围**：xxx 元/天 或 xxx 元/月
**核心要求**：
- 要求1
- 要求2
**岗位亮点**：简短描述（如：大厂背书、有转正机会、提供食宿、导师制等）

---

### 🎯 岗位推荐 2
（同上格式...）

---

【重要规则】
1. 必须输出至少 5 个岗位推荐，优先选择近期发布、明确为"实习/校招"的岗位
2. 每个岗位必须标注【岗位来源】和【投递链接】字段
3. 如果搜索结果中没有明确的投递链接，写"需自行搜索公司官网投递"
4. 如果没找到明确的公司名，根据搜索内容推断
5. 只保留应届生可投的实习岗位，剔除要求3年以上经验的社招岗位
6. 剔除培训机构、付费实习、培训招生的虚假信息
7. 岗位按匹配度从高到低排序，最匹配的放在最前面
8. "岗位来源"从搜索结果的 URL 域名推断（如 linkedin.com→领英，zhipin.com→Boss直聘）
        """
        return self.run_stateless(prompt)
