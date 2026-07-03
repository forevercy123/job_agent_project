import streamlit as st
from agent.scheduler_agent import SchedulerAgent
from tools.memory_tool import (
    save_user_info,
    get_all_memory_count,
    get_all_memory_text,
    reset_vector_db,
)
from tools.pdf_loader import load_resume_pdf
from tools.auth_tool import (
    init_db,
    register_user,
    login_user,
    get_user_count,
    check_and_increment_quota,
    get_user_usage,
    get_all_users,
    admin_update_user_status,
    admin_delete_user,
    get_pending_user_count,
    admin_set_password,
    admin_needs_password,
    ADMIN_USERNAME,
)

# 页面配置（必须放在最前面）
st.set_page_config(page_title="校园求职规划多Agent系统", layout="wide")

# 初始化用户数据库
init_db()

st.title("🎓 校园求职规划智能多Agent助手")


# ========== 登录状态 session 初始化 ==========
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None


# ========== 登录/注册页面 ==========
def show_auth_page():
    """未登录时展示：左侧登录 + 右侧注册"""
    left_col, right_col = st.columns([1, 1])

    # ===== 左侧：登录 =====
    with left_col:
        st.subheader("🔑 用户登录")
        login_username = st.text_input("用户名", key="login_username")
        login_password = st.text_input("密码", type="password", key="login_password")

        if st.button("🚀 登录", type="primary", key="btn_login"):
            ok, msg, user_data = login_user(login_username, login_password)
            if ok:
                st.session_state.logged_in = True
                st.session_state.current_user = user_data
                st.success(msg)
                st.rerun()
            else:
                st.error(f"❌ {msg}")

        st.caption("💡 新用户？请在右侧注册账号")
        total_users = get_user_count()
        st.caption(f"📊 当前平台注册用户：{total_users} 人")

        # Admin 首次设置密码入口
        if admin_needs_password():
            st.divider()
            st.warning("🛠️ 系统首次运行，请在这里设置管理员密码：")
            admin_pw = st.text_input(
                "管理员密码（至少8位）", type="password", key="admin_pw_1"
            )
            admin_pw2 = st.text_input(
                "确认管理员密码", type="password", key="admin_pw_2"
            )
            if st.button("✅ 设置管理员密码", key="btn_set_admin_pw"):
                if admin_pw != admin_pw2:
                    st.error("两次密码不一致")
                else:
                    ok, msg = admin_set_password(admin_pw)
                    if ok:
                        st.success(f"{msg}，请用 admin + 新设密码登录")
                    else:
                        st.error(msg)

    # ===== 右侧：注册 =====
    with right_col:
        st.subheader("📝 新用户注册")
        reg_username = st.text_input("用户名（2 字符以上）", key="reg_username")
        reg_email = st.text_input("邮箱（可选）", key="reg_email")
        reg_password = st.text_input(
            "密码（6 字符以上）", type="password", key="reg_password"
        )
        reg_password2 = st.text_input("确认密码", type="password", key="reg_password2")

        if st.button("✅ 注册新账号", key="btn_register"):
            if reg_password != reg_password2:
                st.error("❌ 两次输入的密码不一致")
            else:
                ok, msg = register_user(reg_username, reg_password, reg_email)
                if ok:
                    st.success(msg)
                    st.info("⏳ 注册成功！请等待管理员审批后再登录")
                else:
                    st.error(f"❌ {msg}")

        st.caption("🔒 密码加密存储，我们无法查看明文密码")
        st.caption("⏳ 新用户需管理员审批后才能使用功能")


# ========== 如果未登录 ==========
if not st.session_state.get("logged_in", False):
    show_auth_page()
    st.stop()

# ========== 以下为已登录后的主功能 ==========

# 初始化调度 Agent
if "scheduler" not in st.session_state:
    st.session_state.scheduler = SchedulerAgent()

# 面试状态
if "current_interview_q" not in st.session_state:
    st.session_state.current_interview_q = ""
if "interview_feedback" not in st.session_state:
    st.session_state.interview_feedback = ""
if "interview_round" not in st.session_state:
    st.session_state.interview_round = 0

# 当前登录用户信息
user_info = st.session_state.get("current_user", {})
user_id = user_info.get("id", 0)
is_admin = user_info.get("is_admin", False)
username = user_info.get("username", "用户")


# ==================== 侧边栏 ====================
with st.sidebar:
    st.subheader(f"👋 欢迎，{username}")
    if is_admin:
        st.success("🛠️ 您是管理员")
    if user_info.get("email"):
        st.caption(f"📧 {user_info['email']}")
    st.caption(f"🕐 注册时间: {user_info.get('created_at', '-')}")
    st.caption(f"🔓 最近登录: {user_info.get('last_login', '-')}")

    # 今日使用配额（普通用户可见）
    if not is_admin:
        st.divider()
        st.markdown("**📊 今日使用情况**")
        usage = get_user_usage(user_id)
        feature_names = {
            "search": "岗位检索",
            "resume": "简历优化",
            "interview": "面试模拟",
        }
        for feat, name in feature_names.items():
            info = usage.get(feat, {"used": 0, "max": 10, "remaining": 10})
            st.caption(
                f"{name}: {info['used']}/{info['max']}（剩{info['remaining']}次）"
            )
    else:
        # 管理员看待审批提醒
        pending = get_pending_user_count()
        if pending > 0:
            st.warning(f"⏳ 有 {pending} 个用户等待审批")

    st.divider()

    # 退出登录按钮
    if st.button("🚪 退出登录", key="btn_logout"):
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.success("已安全退出")
        st.rerun()

    # 普通用户功能区
    st.divider()
    st.header("👤 个人求职信息")
    major = st.text_input("专业", value="计算机科学与技术")
    target_job = st.text_input("意向实习岗位", value="AI Agent开发实习")
    city = st.text_input("意向城市", value="武汉")
    skills = st.text_area("掌握技能", value="Python, LangChain, 大模型应用开发")

    if st.button("💾 保存个人信息至长期记忆", key="btn_save"):
        info_str = f"专业:{major},意向岗位:{target_job},城市:{city},技能:{skills}"
        ok = save_user_info(info_str, user_id)
        if ok:
            count = get_all_memory_count(user_id)
            st.success(f"✅ 已保存！当前记忆库共 {count} 条历史记录")
        else:
            st.warning("⚠️ 保存失败")

    if st.button("📋 查看所有历史记忆", key="btn_view"):
        all_memory = get_all_memory_text(user_id)
        st.info("📦 记忆库内容：\n\n" + all_memory)

    if st.button("🗑️ 清空所有长期记忆", key="btn_reset"):
        reset_vector_db(user_id)
        st.warning("⚠️ 所有长期记忆已清空")

    if st.button("🔄 清空对话短期记忆", key="btn_clear_mem"):
        st.session_state.scheduler.clear_memory()
        st.success("对话上下文记忆已清空")


# ==================== Tab 切换 ====================
if is_admin:
    # 管理员：多一个管理后台 Tab
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🔍 岗位智能匹配", "📄 简历诊断优化", "🎯 面试模拟", "🛠️ 管理后台"]
    )
else:
    tab1, tab2, tab3 = st.tabs(["🔍 岗位智能匹配", "📄 简历诊断优化", "🎯 面试模拟"])


# ==================== Tab1 岗位检索 ====================
with tab1:
    st.subheader("🔍 岗位智能匹配与推荐")

    # 先检查配额
    quota_ok, quota_msg = (
        check_and_increment_quota(user_id, "search") if False else (True, "")
    )

    user_demand = st.text_input(
        "补充求职需求描述（可选）",
        placeholder="如：想找薪资 150-200 元/天、提供食宿的实习",
    )

    if "search_batch" not in st.session_state:
        st.session_state.search_batch = 0
    if "job_result" not in st.session_state:
        st.session_state.job_result = ""
    if "job_history" not in st.session_state:
        st.session_state.job_history = []

    col1, col2 = st.columns([3, 1])

    with col1:
        if st.button("🚀 启动岗位检索Agent", key="btn_search", type="primary"):
            # 调用前检查配额
            ok, msg = check_and_increment_quota(user_id, "search")
            if not ok and not is_admin:  # 管理员不限额
                st.error(msg)
            else:
                if not is_admin:
                    st.info(msg)
                st.session_state.search_batch = 0
                st.session_state.job_history = []
                with st.spinner(
                    f"🔎 正在搜索第 {st.session_state.search_batch + 1} 批岗位..."
                ):
                    full_info = f"专业{major},岗位{target_job},城市{city},技能{skills}"
                    demand_with_batch = (
                        f"{user_demand} batch:{st.session_state.search_batch}"
                    )
                    res = st.session_state.scheduler.dispatch_task(
                        demand_with_batch, full_info, task_type="search"
                    )
                st.session_state.job_result = res

    with col2:
        if st.button("🔄 换一批推荐", key="btn_next_batch"):
            # 换一批也消耗配额（但比首次搜索稍松）
            ok, msg = check_and_increment_quota(user_id, "search")
            if not ok and not is_admin:
                st.error(msg)
            else:
                if not is_admin:
                    st.info(msg)
                st.session_state.search_batch += 1
                with st.spinner(
                    f"🔎 正在搜索第 {st.session_state.search_batch + 1} 批岗位..."
                ):
                    full_info = f"专业{major},岗位{target_job},城市{city},技能{skills}"
                    demand_with_batch = (
                        f"{user_demand} batch:{st.session_state.search_batch}"
                    )
                    res = st.session_state.scheduler.dispatch_task(
                        demand_with_batch, full_info, user_id, task_type="search"
                    )
                st.session_state.job_result = res

    st.markdown("---")
    if st.session_state.job_result:
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
                with open("./docs/resume.pdf", "wb") as f:
                    f.write(upload_file.read())
                resume_content = load_resume_pdf("./docs/resume.pdf")
            with st.expander("📄 点击查看简历解析内容预览", expanded=False):
                st.text_area(
                    "简历内容",
                    value=resume_content,
                    height=300,
                    key="resume_preview",
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

    if st.button("🎯 启动简历诊断优化Agent", key="btn_resume", type="primary"):
        # 调用前检查配额
        ok, msg = check_and_increment_quota(user_id, "resume")
        if not ok and not is_admin:
            st.error(msg)
        else:
            if not is_admin:
                st.info(msg)
            with st.spinner("📝 正在分析简历与 JD 匹配度... 请稍候"):
                demand = f"简历内容:{resume_content}\n岗位JD:{jd_input}"
                res = st.session_state.scheduler.dispatch_task(
                    demand, "", task_type="resume"
                )
            st.markdown("---")
            st.markdown(res)


# ==================== Tab3 面试模拟 ====================
with tab3:
    st.subheader("🎯 多轮交互式面试模拟")

    diff = st.radio("选择面试难度", ["简单", "中等", "困难"], horizontal=True)

    resume_for_interview = (
        resume_content
        if "resume_content" in dir() and resume_content
        else "暂无上传简历"
    )
    jd_for_interview = jd_input if "jd_input" in dir() and jd_input else "暂无JD"

    with st.expander("📝 当前面试上下文（简历+JD）", expanded=False):
        st.markdown("**简历内容：**")
        st.text(
            resume_for_interview[:500]
            + ("..." if len(resume_for_interview) > 500 else "")
        )
        st.markdown("**目标岗位 JD：**")
        st.text(jd_for_interview[:500] + ("..." if len(jd_for_interview) > 500 else ""))

    if st.session_state.interview_round > 0:
        st.markdown(f"**📍 当前进度：第 {st.session_state.interview_round} 轮面试**")
    st.divider()

    start_col, reset_col = st.columns([3, 1])
    with start_col:
        if st.button(
            "🚀 开始面试，生成第一道问题", key="btn_start_interview", type="primary"
        ):
            # 调用前检查配额
            ok, msg = check_and_increment_quota(user_id, "interview")
            if not ok and not is_admin:
                st.error(msg)
            else:
                if not is_admin:
                    st.info(msg)
                with st.spinner("面试官正在准备第一题..."):
                    first_q = (
                        st.session_state.scheduler.interview_agent.gen_first_question(
                            resume=resume_for_interview,
                            jd=jd_for_interview,
                            diff=diff,
                            session_key=f"user_{user_id}",  # ✅ 用 user_id 隔离
                        )
                    )
                    st.session_state.current_interview_q = first_q
                    st.session_state.interview_feedback = ""
                    st.session_state.interview_round = 1
                    st.success("面试官提问：")
                    st.markdown(f"**{first_q}**")

    with reset_col:
        if st.button("🔄 重新开始本场面试", key="btn_restart_interview"):
            st.session_state.scheduler.interview_agent.clear_interview_record(
                session_key=f"user_{user_id}"  # ✅ 用 user_id 隔离
            )
            st.session_state.current_interview_q = ""
            st.session_state.interview_feedback = ""
            st.session_state.interview_round = 0
            st.info("已清空面试记录，请点击左侧按钮重新开始")

    if st.session_state.current_interview_q:
        st.divider()
        st.markdown(f"### 💬 面试官第 {st.session_state.interview_round} 问：")
        st.markdown(f"**{st.session_state.current_interview_q}**")

        user_answer = st.text_area("✍️ 输入你的回答", height=180, key="answer_area")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📝 AI 点评本次回答", key="btn_review"):
                if user_answer.strip():
                    with st.spinner("AI 正在分析你的回答..."):
                        feedback = (
                            st.session_state.scheduler.interview_agent.review_answer(
                                question=st.session_state.current_interview_q,
                                answer=user_answer,
                                session_key=f"user_{user_id}",  # ✅ 用 user_id 隔离
                            )
                        )
                        st.session_state.interview_feedback = feedback
                else:
                    st.warning("请先输入你的回答再点击点评")

        if st.session_state.interview_feedback:
            st.markdown("#### 📊 回答点评反馈")
            st.markdown(st.session_state.interview_feedback)

        with col2:
            if st.button("➡️ 获取下一道追问", key="btn_follow"):
                if user_answer.strip():
                    with st.spinner("面试官正在基于你的回答生成下一题..."):
                        next_q = st.session_state.scheduler.interview_agent.gen_follow_question(
                            last_answer=user_answer,
                            session_key=f"user_{user_id}",  # ✅ 用 user_id 隔离
                        )
                        st.session_state.current_interview_q = next_q
                        st.session_state.interview_feedback = ""
                        st.session_state.interview_round += 1
                        st.rerun()
                else:
                    st.warning("请先输入你的回答再点击追问")

        with col3:
            if st.button("📈 生成整场面试复盘", key="btn_report"):
                with st.spinner("AI 正在整理整场面试复盘报告..."):
                    full_report = (
                        st.session_state.scheduler.interview_agent.generate_full_review(
                            session_key=f"user_{user_id}"  # ✅ 用 user_id 隔离
                        )
                    )
                    st.divider()
                    st.markdown("## 📑 整场面试复盘报告")
                    st.markdown(full_report)

    st.divider()
    st.caption("💡 提示：完成多轮面试后，点击“生成整场面试复盘”可以获得全面的改进建议")


# ==================== Tab4 管理员后台（仅管理员可见） ====================
if is_admin:
    with tab4:
        st.subheader("🛠️ 管理员后台")

        # 概览统计
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        all_users = get_all_users()
        active_count = sum(1 for u in all_users if u["status"] == "active")
        pending_count = sum(1 for u in all_users if u["status"] == "pending")
        blocked_count = sum(1 for u in all_users if u["status"] == "blocked")

        col_stat1.metric("总用户数", len(all_users))
        col_stat2.metric("已激活用户", active_count)
        col_stat3.metric("待审批/已禁用", f"{pending_count} / {blocked_count}")

        st.divider()
        st.markdown("### 👥 用户管理")

        # 用户列表表格
        if not all_users:
            st.info("暂无用户数据")
        else:
            # 构造表格数据
            table_rows = []
            for u in all_users:
                status_text = {
                    "pending": "⏳ 待审批",
                    "active": "✅ 已激活",
                    "blocked": "🚫 已禁用",
                }.get(u["status"], u["status"])

                role = "🛠️ 管理员" if u["is_admin"] else "普通用户"
                table_rows.append(
                    {
                        "ID": u["id"],
                        "用户名": u["username"],
                        "邮箱": u["email"],
                        "角色": role,
                        "状态": status_text,
                        "总使用次数": u["total_usage"],
                        "注册时间": u["created_at"],
                        "最近登录": u["last_login"],
                    }
                )

            # 渲染表格
            st.dataframe(table_rows, width="stretch")

            # ---- 操作区 ----
            st.divider()
            st.markdown("#### 🎛️ 用户操作")

            # 选一个用户
            user_options = {
                f"[{u['id']}] {u['username']} ({u['status']})": u["id"]
                for u in all_users
                if not u["is_admin"]
            }

            if user_options:
                selected_label = st.selectbox(
                    "选择要操作的用户",
                    list(user_options.keys()),
                    key="admin_user_select",
                )
                selected_id = user_options[selected_label]

                # 三个操作按钮
                col_op1, col_op2, col_op3 = st.columns(3)
                with col_op1:
                    if st.button("✅ 激活 / 批准", key="btn_approve"):
                        ok, msg = admin_update_user_status(selected_id, "active")
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                with col_op2:
                    if st.button("🚫 禁用账号", key="btn_block"):
                        ok, msg = admin_update_user_status(selected_id, "blocked")
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                with col_op3:
                    if st.button("🗑️ 删除用户", key="btn_delete_user"):
                        confirm = st.checkbox(
                            "⚠️ 我确认要删除此用户（此操作不可恢复）",
                            key="admin_confirm_delete",
                        )
                        if confirm:
                            ok, msg = admin_delete_user(selected_id)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.info("请先勾选确认框再点击删除")
            else:
                st.info("暂无可管理的普通用户")

        # ---- 配额说明 ----
        st.divider()
        st.markdown("#### 📋 当前每日配额配置")
        st.caption("• 岗位检索：10 次/天")
        st.caption("• 简历优化：5 次/天")
        st.caption("• 面试模拟：3 次/天")
        st.caption("• 管理员账号不限额")
        st.info(
            "💡 如需调整每日配额，修改 tools/auth_tool.py 中的 DAILY_QUOTA 字典，然后重启服务"
        )
