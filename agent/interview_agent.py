from agent.base_agent import BaseAgent


class InterviewAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        # ✅ 改为按 session_key 隔离，避免多用户时互相覆盖
        self.interview_histories = (
            {}
        )  # {session_key: [{"question":..., "answer":...}, ...]}
        self.cur_resumes = {}  # {session_key: resume_text}
        self.cur_jds = {}  # {session_key: jd_text}
        self.cur_diffs = {}  # {session_key: difficulty}

    def _get_history(self, session_key):
        """获取指定会话的面试历史，不存在则新建"""
        if session_key not in self.interview_histories:
            self.interview_histories[session_key] = []
        return self.interview_histories[session_key]

    # 生成第一轮开场面试题
    def gen_first_question(self, resume, jd, diff="中等", session_key="default"):
        self.cur_resumes[session_key] = resume
        self.cur_jds[session_key] = jd
        self.cur_diffs[session_key] = diff
        prompt = f"""
你是大厂AI/Agent方向面试官，进行{diff}难度应届生技术面试。
只输出1道开场问题，不要多余解释。
候选人简历：{resume}
目标岗位JD：{jd}
"""
        q = self.run_stateless(prompt).strip()
        # ✅ 按 session_key 保存历史
        history = self._get_history(session_key)
        history.append({"question": q, "answer": ""})
        print(
            f"[interview] session {session_key}: 第1问已生成, 历史长度={len(history)}"
        )
        return q

    # 根据上一轮回答生成针对性追问
    def gen_follow_question(self, last_answer, session_key="default"):
        history = self._get_history(session_key)
        if not history:
            return "请先生成第一轮面试问题"
        last_q = history[-1]["question"]
        resume = self.cur_resumes.get(session_key, "")
        jd = self.cur_jds.get(session_key, "")
        prompt = f"""
面试上下文：
面试官：{last_q}
候选人回答：{last_answer}
基于回答深挖技术细节、项目难点，只输出1道追问，不要多余文字。
岗位JD：{jd}
候选人简历：{resume}
"""
        follow_q = self.run_stateless(prompt).strip()
        history.append({"question": follow_q, "answer": ""})
        print(f"[interview] session {session_key}: 生成追问, 历史长度={len(history)}")
        return follow_q

    # 单轮回答点评
    def review_answer(self, question, answer, session_key="default"):
        # 把回答存入对应会话的历史记录
        history = self._get_history(session_key)
        if history and history[-1]["question"] == question:
            history[-1]["answer"] = answer
        prompt = f"""
简短点评候选人本次回答：指出短板、补充标准答案、给出优化话术，简洁清晰。
面试问题：{question}
候选人回答：{answer}
"""
        feedback = self.run_stateless(prompt)
        return feedback

    # 整场面试完整复盘报告
    def generate_full_review(self, session_key="default"):
        history = self._get_history(session_key)
        if len(history) == 0:
            return "暂无面试对话记录，请先完成面试问答"
        history_text = "\n".join(
            [
                f"【面试官】{item['question']}\n【我】{item['answer']}"
                for item in history
            ]
        )
        resume = self.cur_resumes.get(session_key, "")
        jd = self.cur_jds.get(session_key, "")
        prompt = f"""
生成整场面试完整复盘报告，分4块输出：
1. 综合面试得分（0-100）
2. 回答亮点
3. 薄弱知识点（分技术/项目表达/软实力）
4. 针对性提升学习路线
完整对话记录：
{history_text}
岗位JD：{jd}
候选人简历：{resume}
"""
        full_report = self.run_stateless(prompt)
        return full_report

    # 清空本场面试所有记录（按会话）
    def clear_interview_record(self, session_key="default"):
        if session_key in self.interview_histories:
            del self.interview_histories[session_key]
        if session_key in self.cur_resumes:
            del self.cur_resumes[session_key]
        if session_key in self.cur_jds:
            del self.cur_jds[session_key]
        if session_key in self.cur_diffs:
            del self.cur_diffs[session_key]
        print(f"[interview] session {session_key}: 已清空面试记录")

    # 兼容调度器批量一次性生成5道面试题的接口
    def gen_question(self, resume, jd, diff="中等"):
        prompt = f"""
生成{diff}难度的岗位面试题，包含基础技术八股、项目深挖题、HR行为题，一次性输出5道完整题目，不要多余描述。
候选人简历：{resume}
目标岗位JD：{jd}
"""
        return self.run_stateless(prompt)
