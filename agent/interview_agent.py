from agent.base_agent import BaseAgent


class InterviewAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        # 存储完整面试对话记录
        self.interview_history = []
        # 缓存当前简历、JD，用于持续追问
        self.cur_resume = ""
        self.cur_jd = ""
        self.cur_diff = "中等"

    # 生成第一轮开场面试题
    def gen_first_question(self, resume, jd, diff="中等"):
        self.cur_resume = resume
        self.cur_jd = jd
        self.cur_diff = diff
        prompt = f"""
你是大厂AI/Agent方向面试官，进行{diff}难度应届生技术面试。
只输出1道开场问题，不要多余解释。
候选人简历：{resume}
目标岗位JD：{jd}
"""
        q = self.run(prompt).strip()
        self.interview_history.append({"question": q, "answer": ""})
        return q

    # 根据上一轮回答生成针对性追问
    def gen_follow_question(self, last_answer):
        if not self.interview_history:
            return "请先生成第一轮面试问题"
        last_q = self.interview_history[-1]["question"]
        prompt = f"""
面试上下文：
面试官：{last_q}
候选人回答：{last_answer}
基于回答深挖技术细节、项目难点，只输出1道追问，不要多余文字。
岗位JD：{self.cur_jd}
候选人简历：{self.cur_resume}
"""
        follow_q = self.run(prompt).strip()
        self.interview_history.append({"question": follow_q, "answer": ""})
        return follow_q

    # 单轮回答点评
    def review_answer(self, question, answer):
        # 把回答存入历史记录
        self.interview_history[-1]["answer"] = answer
        prompt = f"""
简短点评候选人本次回答：指出短板、补充标准答案、给出优化话术，简洁清晰。
面试问题：{question}
候选人回答：{answer}
"""
        feedback = self.run(prompt)
        return feedback

    # 整场面试完整复盘报告
    def generate_full_review(self):
        if len(self.interview_history) == 0:
            return "暂无面试对话记录，请先完成面试问答"
        history_text = "\n".join(
            [
                f"【面试官】{item['question']}\n【我】{item['answer']}"
                for item in self.interview_history
            ]
        )
        prompt = f"""
生成整场面试完整复盘报告，分4块输出：
1. 综合面试得分（0-100）
2. 回答亮点
3. 薄弱知识点（分技术/项目表达/软实力）
4. 针对性提升学习路线
完整对话记录：
{history_text}
岗位JD：{self.cur_jd}
候选人简历：{self.cur_resume}
"""
        full_report = self.run(prompt)
        return full_report

    # 清空本场面试所有记录，重新开始面试
    def clear_interview_record(self):
        self.interview_history = []
        self.cur_resume = ""
        self.cur_jd = ""

    # 兼容调度器批量一次性生成5道面试题的接口
    def gen_question(self, resume, jd, diff="中等"):
        prompt = f"""
生成{diff}难度的岗位面试题，包含基础技术八股、项目深挖题、HR行为题，一次性输出5道完整题目，不要多余描述。
候选人简历：{resume}
目标岗位JD：{jd}
"""
        return self.run(prompt)
