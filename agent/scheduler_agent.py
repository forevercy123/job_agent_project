from agent.base_agent import BaseAgent
from agent.search_agent import SearchAgent
from agent.resume_agent import ResumeAgent
from agent.interview_agent import InterviewAgent
from tools.memory_tool import recall_user_info
import json


class SchedulerAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.search_agent = SearchAgent()
        self.resume_agent = ResumeAgent()
        self.interview_agent = InterviewAgent()

    def dispatch_task(self, user_requirement, user_info, user_id=None, task_type=None):
        """
        参数 task_type: 可选 "search" / "resume" / "interview" / None(自动判断)
        如果指定了 task_type，直接执行对应任务，不再依赖LLM调度判断
        user_id: 当前登录用户 ID，用于向量记忆的用户隔离
        """
        # 读取长期向量记忆里的历史用户信息（按 user_id 隔离，避免跨用户数据泄漏）
        memory_info = recall_user_info("用户求职背景", user_id)
        full_user_info = f"{user_info}\n历史记忆信息:{memory_info}"

        final_result = ""

        # ============== 新增：如果显式指定了任务类型，直接执行 ==============
        if task_type == "search":
            # 只执行岗位检索（支持 batch 参数）
            major, job, city, skill = self._parse_user_info(full_user_info)

            # 从 user_requirement 中解析批次号（格式："batch:X"）
            batch = 0
            try:
                if "batch:" in user_requirement:
                    import re

                    match = re.search(r"batch:(\d+)", user_requirement)
                    if match:
                        batch = int(match.group(1))
            except Exception:
                pass

            job_res = self.search_agent.search_job(major, job, city, skill, batch)
            final_result = f"=== 岗位匹配结果（第 {batch + 1} 批） ===\n" + job_res
            return final_result

        if task_type == "resume":
            # 只执行简历优化
            resume_text = self._extract_resume_text(user_requirement)
            jd_text = self._extract_jd_text(user_requirement)
            resume_res = self.resume_agent.optimize_resume(resume_text, jd_text)
            final_result = "===简历优化诊断报告===\n" + resume_res
            return final_result

        if task_type == "interview":
            # 只执行面试题库生成
            resume_text = self._extract_resume_text(user_requirement)
            jd_text = self._extract_jd_text(user_requirement)
            interview_q = self.interview_agent.gen_question(
                resume_text, jd_text, "中等"
            )
            final_result = "===批量面试题库===\n" + interview_q
            return final_result

        # ============== 原有自动判断逻辑（作为兜底） ==============
        # 调度判断：识别需要调用哪些子Agent（无状态调用，不受历史对话影响）
        dispatch_prompt = f"""
你是求职多智能体调度总指挥，根据用户需求判断需要启用哪些子Agent，仅输出名称，逗号分隔：
可选子Agent：岗位检索Agent、简历优化Agent、面试模拟Agent
用户基础信息：{full_user_info}
用户当前需求：{user_requirement}
输出示例：岗位检索Agent,简历优化Agent
        """
        need_agents = self.run_stateless(dispatch_prompt).strip()

        # 1. 岗位检索分支
        if "岗位检索" in need_agents:
            major, job, city, skill = self._parse_user_info(full_user_info)
            job_res = self.search_agent.search_job(major, job, city, skill)
            final_result += "===岗位匹配结果===\n" + job_res + "\n\n"

        # 2. 简历优化分支
        if "简历优化" in need_agents:
            resume_text = self._extract_resume_text(user_requirement)
            jd_text = self._extract_jd_text(user_requirement)
            resume_res = self.resume_agent.optimize_resume(resume_text, jd_text)
            final_result += "===简历优化诊断报告===\n" + resume_res + "\n\n"

        # 3. 批量面试题库分支
        if "面试模拟" in need_agents:
            resume_text = self._extract_resume_text(user_requirement)
            jd_text = self._extract_jd_text(user_requirement)
            interview_q = self.interview_agent.gen_question(
                resume_text, jd_text, "中等"
            )
            final_result += "===批量面试题库===\n" + interview_q + "\n\n"

        # 无匹配任务时，直接大模型回答通用求职问题
        if not final_result:
            final_result = self.run_stateless(
                f"用户求职信息：{full_user_info}\n用户问题：{user_requirement}"
            )
        return final_result

    # 通过大模型抽取专业/岗位/城市/技能
    def _parse_user_info(self, info_text):
        extract_prompt = f"""
从下面求职信息中提取4个字段，严格仅输出JSON，无多余文字：
字段说明：
major：学历专业
target_job：意向实习岗位
city：意向工作城市
skill：掌握的技术栈、技能
用户信息：{info_text}
输出示例：{{"major":"计算机科学与技术","target_job":"AI Agent开发实习","city":"杭州","skill":"Python, LangChain, 大模型应用"}}
        """
        extract_res = self.run_stateless(extract_prompt).strip()
        try:
            data = json.loads(extract_res)
            major = data.get("major", "计算机相关专业")
            target_job = data.get("target_job", "大模型应用实习")
            city = data.get("city", "全国不限")
            skill = data.get("skill", "Python、大模型开发")
        except Exception:
            major, target_job, city, skill = "计算机", "AI开发实习", "不限", "Python"
        return major, target_job, city, skill

    # 从用户输入文本自动提取简历原文
    def _extract_resume_text(self, text):
        extract_prompt = f"""
判断下面文本中属于用户简历的内容，只输出简历原文，没有简历则返回空字符串：
{text}
        """
        content = self.run_stateless(extract_prompt).strip()
        return content if content else ""

    # 从用户输入文本自动提取岗位JD
    def _extract_jd_text(self, text):
        extract_prompt = f"""
判断下面文本中属于招聘岗位JD的内容，只输出JD原文，没有JD则返回空字符串：
{text}
        """
        content = self.run_stateless(extract_prompt).strip()
        return content if content else ""
