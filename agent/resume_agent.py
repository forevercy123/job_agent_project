from agent.base_agent import BaseAgent
from agent.check_agent import CheckAgent
from tools.similarity_tool import calculate_jd_resume_score


class ResumeAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.checker = CheckAgent()  # 简历内容校验Agent（防幻觉）

    # 在 optimize_resume 函数内开头加入打分逻辑
    def optimize_resume(self, resume_text, jd_text):
        # 1. 计算简历与JD的语义匹配分数
        match_score = calculate_jd_resume_score(resume_text, jd_text)

        # 2. LLM生成优化草稿
        draft_prompt = f"""
你是专业简历优化师，简历与该岗位JD语义匹配度为 {match_score}/100分。
分数越低代表简历越不匹配岗位，优化时重点补齐缺失技能关键词。
【用户原始简历】
{resume_text}
【目标岗位JD】
{jd_text}
输出结构：
1. 简历岗位匹配总分：{match_score} 分
2. 简历短板诊断（逐条列出缺失技能、表述问题）
3. 逐段STAR法则修改建议
4. 完整优化后简历
要求：不编造虚假项目与技能，贴合应届生求职场景。
        """
        raw_optimized = self.run(draft_prompt)

        # 3. CheckAgent 校验：对比原始简历，删除编造内容，保证真实
        final_optimized = self.checker.check_resume_content(resume_text, raw_optimized)
        return final_optimized
