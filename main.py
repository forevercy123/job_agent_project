import streamlit as st
from agent.scheduler_agent import SchedulerAgent
from tools.memory_tool import (
    save_user_info,
    get_all_memory_count,
    get_all_memory_text,
    reset_vector_db,
)
from tools.pdf_loader import load_resume_pdf

st.set_page_config(page_title="校园求职规划多Agent系统", layout="wide")
st.title("🎓 校园求职规划智能多Agent助手")

# 初始化调度Agent（只在会话首次加载时创建）
if "scheduler" not in st.session_state:
    st.session_state.scheduler = SchedulerAgent()

# 面试专用状态管理（多轮面试）
if "current_interview_q" not in st.session_state:
    st.session_state.current_interview_q = ""
if "interview_feedback" not in st.session_state:
    st.session_state.interview_feedback = ""
if "interview_round" not in st.session_state:
    st.session_state.interview_round = 0


# ==================== 侧边栏：用户基础信息 ====================
with st.sidebar:
    st.header("👤 个人求职信息")
    major = st.text_input("专业", value="计算机科学与技术")
    target_job = st.text_input("意向实习岗位", value="AI Agent开发实习")
    city = st.text_input("意向城市", value="武汉")
    skills = st.text_area("掌握技能", value="Python, LangChain, 大模型应用开发")

    # 保存按钮（追加模式，保留历史）
    if st.button("💾 保存个人信息至长期记忆", key="btn_save"):
        info_str = f"专业:{major},意向岗位:{target_job},城市:{city},技能:{skills}"
        ok = save_user_info(info_str)
        if ok:
            count = get_all_memory_count()
            st.success(f"✅ 已保存！当前记忆库共 {count} 条历史记录")
        else:
            st.warning("⚠️ 保存失败，请检查网络连接")

    # 查看所有记忆
    if st.button("📋 查看所有历史记忆", key="btn_view"):
        all_memory = get_all_memory_text()
        st.info("📦 记忆库内容：\n\n" + all_memory)

    # 清空长期记忆
    if st.button("🗑️ 清空所有长期记忆", key="btn_reset"):
        reset_vector_db()
        st.warning("⚠️ 所有长期记忆已清空")

    # 清空对话短期记忆
    if st.button("🔄 清空对话短期记忆", key="btn_clear_mem"):
        st.session_state.scheduler.clear_memory()
        st.success("对话上下文记忆已清空")


# ==================== Tab 切换 ====================
tab1, tab2, tab3 = st.tabs(["🔍 岗位智能匹配", "📄 简历诊断优化", "🎯 面试模拟"])


# ==================== Tab1 岗位检索 ====================
# Tab1 岗位检索
with tab1:
    st.subheader("🔍 岗位智能匹配与推荐")
    user_demand = st.text_input(
        "补充求职需求描述（可选）",
        placeholder="如：想找薪资 150-200 元/天、提供食宿的实习",
    )

    # 初始化状态
    if "search_batch" not in st.session_state:
        st.session_state.search_batch = 0
    if "job_result" not in st.session_state:
        st.session_state.job_result = ""  # 当前批次结果
    if "job_history" not in st.session_state:
        st.session_state.job_history = []  # 历史批次结果列表

    # ========== 两个按钮 ==========
    col1, col2 = st.columns([3, 1])

    with col1:
        if st.button("🚀 启动岗位检索Agent", key="btn_search", type="primary"):
            st.session_state.search_batch = 0  # 重置为第1批
            st.session_state.job_history = []  # 清空历史
            with st.spinner(
                f"🔎 正在搜索第 {st.session_state.search_batch + 1} 批岗位... 请稍候"
            ):
                full_info = f"专业{major},岗位{target_job},城市{city},技能{skills}"
                demand_with_batch = (
                    f"{user_demand} batch:{st.session_state.search_batch}"
                )
                res = st.session_state.scheduler.dispatch_task(
                    demand_with_batch, full_info, task_type="search"
                )
            # 保存到状态中，下面统一渲染
            st.session_state.job_result = res

    with col2:
        if st.button("🔄 换一批推荐", key="btn_next_batch"):
            st.session_state.search_batch += 1  # 批次+1
            with st.spinner(
                f"🔎 正在搜索第 {st.session_state.search_batch + 1} 批岗位... 请稍候"
            ):
                full_info = f"专业{major},岗位{target_job},城市{city},技能{skills}"
                demand_with_batch = (
                    f"{user_demand} batch:{st.session_state.search_batch}"
                )
                res = st.session_state.scheduler.dispatch_task(
                    demand_with_batch, full_info, task_type="search"
                )
            # 保存到状态中，下面统一渲染
            st.session_state.job_result = res

    # ========== 统一渲染：当前批次结果（两个按钮下方） ==========
    st.markdown("---")
    if st.session_state.job_result:
        # 当前批次标题显示在当前结果上方
        st.markdown(f"**📌 当前第 {st.session_state.search_batch + 1} 批推荐**")
        st.markdown(st.session_state.job_result)
    else:
        st.info("👆 请点击上方“启动岗位检索Agent”开始搜索岗位")


# ==================== Tab2 简历优化 ====================
with tab2:
    st.subheader("📄 简历 JD 匹配与优化建议")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### 📎 上传简历")
        upload_file = st.file_uploader("选择简历 PDF 文件", type="pdf")
        resume_content = ""

        if upload_file:
            with st.spinner("正在解析简历 PDF..."):
                # 保存到本地并解析
                with open("./docs/resume.pdf", "wb") as f:
                    f.write(upload_file.read())
                resume_content = load_resume_pdf("./docs/resume.pdf")

            # 展示预览（可折叠）
            with st.expander("📄 点击查看简历解析内容预览", expanded=False):
                st.text_area(
                    "简历内容", value=resume_content, height=300, key="resume_preview"
                )
            st.success(f"✅ 简历解析成功，共 {len(resume_content)} 字")

    with col_b:
        st.markdown("### 📋 目标岗位 JD")
        jd_input = st.text_area(
            "粘贴目标岗位 JD（岗位职责 + 任职要求）",
            placeholder="岗位职责：\n1. 负责 AI Agent 相关产品开发...\n\n任职要求：\n1. 熟练掌握 Python...",
            height=300,
            key="jd_input",
        )

    run_resume = st.button("🎯 启动简历诊断优化Agent", key="btn_resume", type="primary")
    if run_resume:
        with st.spinner("📝 正在分析简历与 JD 匹配度... 请稍候"):
            demand = f"简历内容:{resume_content}\n岗位JD:{jd_input}"
            res = st.session_state.scheduler.dispatch_task(
                demand, "", task_type="resume"
            )
        st.markdown("---")
        st.markdown(res)


# ==================== Tab3 多轮连续面试模拟 ====================
with tab3:
    st.subheader("🎯 多轮交互式面试模拟")

    # 难度选择
    diff = st.radio("选择面试难度", ["简单", "中等", "困难"], horizontal=True)

    # 复用简历和 JD 内容（如果在 Tab2 填写过）
    resume_for_interview = (
        resume_content
        if "resume_content" in dir() and resume_content
        else "暂无上传简历"
    )
    jd_for_interview = jd_input if "jd_input" in dir() and jd_input else "暂无JD"

    # 展示当前上下文
    with st.expander("📝 当前面试上下文（简历+JD）", expanded=False):
        st.markdown("**简历内容：**")
        st.text(
            resume_for_interview[:500]
            + ("..." if len(resume_for_interview) > 500 else "")
        )
        st.markdown("**目标岗位 JD：**")
        st.text(jd_for_interview[:500] + ("..." if len(jd_for_interview) > 500 else ""))

    # 面试进度条
    if st.session_state.interview_round > 0:
        st.markdown(f"**📍 当前进度：第 {st.session_state.interview_round} 轮面试**")
    st.divider()

    # 1. 生成第一道面试题
    start_col, reset_col = st.columns([3, 1])
    with start_col:
        if st.button(
            "🚀 开始面试，生成第一道问题", key="btn_start_interview", type="primary"
        ):
            with st.spinner("面试官正在准备第一题..."):
                first_q = st.session_state.scheduler.interview_agent.gen_first_question(
                    resume=resume_for_interview, jd=jd_for_interview, diff=diff
                )
                st.session_state.current_interview_q = first_q
                st.session_state.interview_feedback = ""
                st.session_state.interview_round = 1
                st.success("面试官提问：")
                st.markdown(f"**{first_q}**")

    with reset_col:
        if st.button("🔄 重新开始本场面试", key="btn_restart_interview"):
            st.session_state.scheduler.interview_agent.clear_interview_record()
            st.session_state.current_interview_q = ""
            st.session_state.interview_feedback = ""
            st.session_state.interview_round = 0
            st.info("已清空面试记录，请点击左侧按钮重新开始")

    # 2. 有当前问题时：答题区、点评、追问、复盘报告
    if st.session_state.current_interview_q:
        st.divider()
        st.markdown(f"### 💬 面试官第 {st.session_state.interview_round} 问：")
        st.markdown(f"**{st.session_state.current_interview_q}**")

        user_answer = st.text_area("✍️ 输入你的回答", height=180, key="answer_area")

        col1, col2, col3 = st.columns(3)

        # 点评回答
        with col1:
            if st.button("📝 AI 点评本次回答", key="btn_review"):
                if user_answer.strip():
                    with st.spinner("AI 正在分析你的回答..."):
                        feedback = (
                            st.session_state.scheduler.interview_agent.review_answer(
                                question=st.session_state.current_interview_q,
                                answer=user_answer,
                            )
                        )
                        st.session_state.interview_feedback = feedback
                else:
                    st.warning("请先输入你的回答再点击点评")

        # 展示点评结果
        if st.session_state.interview_feedback:
            st.markdown("#### 📊 回答点评反馈")
            st.markdown(st.session_state.interview_feedback)

        # 生成追问
        with col2:
            if st.button("➡️ 获取下一道追问", key="btn_follow"):
                if user_answer.strip():
                    with st.spinner("面试官正在基于你的回答生成下一题..."):
                        next_q = st.session_state.scheduler.interview_agent.gen_follow_question(
                            last_answer=user_answer
                        )
                        st.session_state.current_interview_q = next_q
                        st.session_state.interview_feedback = ""
                        st.session_state.interview_round += 1
                        st.rerun()  # 刷新页面展示新问题
                else:
                    st.warning("请先输入你的回答再点击追问")

        # 生成完整复盘报告
        with col3:
            if st.button("📈 生成整场面试复盘", key="btn_report"):
                with st.spinner("AI 正在整理整场面试复盘报告..."):
                    full_report = (
                        st.session_state.scheduler.interview_agent.generate_full_review()
                    )
                    st.divider()
                    st.markdown("## 📑 整场面试复盘报告")
                    st.markdown(full_report)

    # 底部操作区
    st.divider()
    st.caption("💡 提示：完成多轮面试后，点击'生成整场面试复盘'可以获得全面的改进建议")
