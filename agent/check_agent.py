from agent.base_agent import BaseAgent


class CheckAgent(BaseAgent):
    def check_job_result(self, raw_search_result):
        prompt = f"""
校验下面岗位搜索结果，过滤3类内容：1.3年以上社招岗位 2.培训机构广告 3.过期招聘信息
只保留应届生可投实习，输出清洗后的结构化岗位清单，剔除所有无效内容：
原始搜索内容：{raw_search_result}
"""
        # ✅ 用 stateless，不需要对话历史
        return self.run_stateless(prompt)

    def check_resume_content(self, origin_resume, optimized_resume):
        prompt = f"""
校验优化后的简历，对比原始简历，若出现原始简历没有的技能、项目、实习经历，直接删除并标注风险；保证内容完全真实。
原始简历：{origin_resume}
优化后简历：{optimized_resume}
输出修正后无幻觉简历。
"""
        # ✅ 用 stateless，不需要对话历史
        return self.run_stateless(prompt)
