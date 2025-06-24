# === IMPORTS ===
import streamlit as st
import json
import random
from datetime import datetime, timedelta, timezone
import os
import requests
import base64

# === CONSTANTS ===
SKILLS = ['html', 'css', 'javascript', 'react', 'github']

# === FUNCTIONS ===
def save_to_github(account, final_result, history, failed):
    now_utc = datetime.now(timezone.utc)
    hanoi_time = now_utc.astimezone(timezone(timedelta(hours=7)))
    filename = f"{account}_{hanoi_time.strftime('%Y%m%d_%H%M%S')}.json"
    file_path = f"results/{filename}"

    file_content = {
        "account": account,
        "final_result": final_result,
        "failed": failed,
        "history": history,
        "timestamp": datetime.now().isoformat()
    }

    content_str = json.dumps(file_content, indent=2, ensure_ascii=False)
    content_b64 = base64.b64encode(content_str.encode()).decode()

    url = f"https://api.github.com/repos/{st.secrets.github_username}/{st.secrets.github_repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {st.secrets.github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "message": f"Add result for {account}",
        "content": content_b64
    }
    res = requests.put(url, headers=headers, json=payload)
    if res.status_code in [200, 201]:
        st.success(f"💾 Đã lưu kết quả tại results/{filename}")
    else:
        st.error(f"❌ Không thể lưu kết quả lên GitHub. Chi tiết: {res.text}")

def save_result_to_file(account: str, result: dict):
    os.makedirs("results", exist_ok=True)
    clean_account = account.strip().replace(" ", "_").lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{clean_account}_{timestamp}.json"
    filepath = os.path.join("results", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return filepath

# === CORE ENGINE ===
class AdaptiveTestingEngine:
    def __init__(self, questions_data):
        self.questions_data = questions_data
        self.seniority_map = {'F': 'fresher', 'J': 'junior', 'M': 'middle', 'S': 'senior'}
        self.reverse_map = {v: k for k, v in self.seniority_map.items()}
        self.questions_by_level = {}
        for q in questions_data:
            key = f"{q['skill']}_{q['seniority']}_{q['level']}"
            self.questions_by_level.setdefault(key, []).append(q)

    def get_question(self, skill, seniority, level):
        key = f"{skill}_{seniority}_{level}"
        return random.choice(self.questions_by_level.get(key, [])) if self.questions_by_level.get(key) else None

    def format_level_string(self, seniority, level):
        return f"{self.reverse_map.get(seniority, '?')}{level}"


class AdaptiveTestSession:
    def __init__(self, engine, skill, start_seniority='middle'):
        self.engine = engine
        self.skill = skill
        self.starting_seniority = start_seniority
        self.current_seniority = start_seniority
        self.current_level = 3
        self.answer_history = []
        self.question_history = []
        self.is_finished = False
        self.final_result = None
        self.path_state = "initial"
        self.failed = False

    def get_next_question(self):
        if self.is_finished:
            return None
        q = self.engine.get_question(self.skill, self.current_seniority, self.current_level)
        if q:
            shuffled_q = q.copy()
            shuffled_options = q["options"].copy()
            random.shuffle(shuffled_options)
            shuffled_q["options"] = shuffled_options

            self.question_history.append(shuffled_q)
            return shuffled_q
        return None

    def submit_answer(self, selected_index):
        if self.is_finished or not self.question_history:
            return {"error": "No question"}

        question = self.question_history[-1]
        is_correct = question['options'][selected_index]['isAnswerKey']

        self.answer_history.append({
            'question_id': question['id'],
            'selected_index': selected_index,
            'is_correct': is_correct
        })

        # Select appropriate method
        level = self.starting_seniority
        if level == 'fresher':
            return self._update_state_after_answer_fresher(is_correct)
        elif level == 'junior':
            return self._update_state_after_answer_junior(is_correct)
        elif level == 'middle':
            return self._update_state_after_answer_middle(is_correct)
        elif level == 'senior':
            return self._update_state_after_answer_senior(is_correct)
        else:
            return {"error": "Invalid seniority"}

    def _finish_test(self, label, failed=False):
        self.is_finished = True
        self.final_result = label
        self.failed = failed

    def _get_result(self):
        return {
            "is_finished": self.is_finished,
            "final_result": self.final_result,
            "failed": self.failed,
            "answer_history": self.answer_history[-1] if self.answer_history else {}
        }

    def _update_state_after_answer_middle(self, is_correct):

        if len(self.answer_history) == 1:
            if is_correct:
                self.current_seniority = 'middle'
                self.current_level = 5
                self.path_state = 'M5'
            else:
                self.current_seniority = 'middle'
                self.current_level = 1
                self.path_state = 'M1'

        # Q2 – M5 hoặc M1
        elif len(self.answer_history) == 2:
            if self.path_state == 'M5':
                if is_correct:
                    self.current_seniority = 'senior'
                    self.current_level = 3
                    self.path_state = 'S3'
                else:
                    self.current_seniority = 'middle'
                    self.current_level = 4
                    self.path_state = 'M4'
            elif self.path_state == 'M1':
                if is_correct:
                    self.current_seniority = 'middle'
                    self.current_level = 2
                    self.path_state = 'M2'
                else:
                    self.current_seniority = 'junior'
                    self.current_level = 3
                    self.path_state = 'J3'

        # Q3 – M2 / M4 / S3 / J3
        elif len(self.answer_history) == 3:
            if self.path_state == 'M2':
                if is_correct:
                    self._finish_test("LEVELM2")
                else:
                    self._finish_test("LEVELM1")
                return self._get_result()
            elif self.path_state == 'M4':
                if is_correct:
                    self._finish_test("LEVELM4")
                else:
                    self._finish_test("LEVELM3")
                return self._get_result()
            elif self.path_state == 'S3':
                if is_correct:
                    self.current_seniority = 'senior'
                    self.current_level = 5
                    self.path_state = 'S5'
                else:
                    self.current_seniority = 'senior'
                    self.current_level = 1
                    self.path_state = 'S1'
            elif self.path_state == 'J3':
                if is_correct:
                    self.current_seniority = 'junior'
                    self.current_level = 5
                    self.path_state = 'J5'
                else:
                    self.current_seniority = 'junior'
                    self.current_level = 1
                    self.path_state = 'J1'

        # Q4 – S5 / S1 / J5 / J1
        elif len(self.answer_history) == 4:
            if self.path_state == 'S5':
                if is_correct:
                    self._finish_test("LEVELS5")
                else:
                    self.current_seniority = 'senior'
                    self.current_level = 4
                    self.path_state = 'S4'
            elif self.path_state == 'S1':
                if is_correct:
                    self.current_seniority = 'senior'
                    self.current_level = 2
                    self.path_state = 'S2'
                else:
                    self._finish_test("LEVELM5")
                return self._get_result()
            elif self.path_state == 'J5':
                if is_correct:
                    self._finish_test("LEVELJ5")
                else:
                    self.current_seniority = 'junior'
                    self.current_level = 4
                    self.path_state = 'J4'
            elif self.path_state == 'J1':
                if is_correct:
                    self.current_seniority = 'junior'
                    self.current_level = 2
                    self.path_state = 'J2'
                else:
                    self._finish_test("LEVELJ0", failed=True)
                return self._get_result()

        # Q5 – S4 / S2 / J4 / J2
        elif len(self.answer_history) == 5:
            if self.path_state == 'S4':
                if is_correct:
                    self._finish_test("LEVELS4")
                else:
                    self._finish_test("LEVELS3")
            elif self.path_state == 'S2':
                if is_correct:
                    self._finish_test("LEVELS2")
                else:
                    self._finish_test("LEVELS1")
            elif self.path_state == 'J4':
                if is_correct:
                    self._finish_test("LEVELJ4")
                else:
                    self._finish_test("LEVELJ3")
            elif self.path_state == 'J2':
                if is_correct:
                    self._finish_test("LEVELJ2")
                else:
                    self._finish_test("LEVELJ1")

        return self._get_result()


    def _update_state_after_answer_senior(self, is_correct):
        """
        Cập nhật trạng thái bài test sau mỗi câu trả lời,
        theo cây nhánh: bắt đầu từ S3, rồi xuống S1, rồi M3 nếu cần.
        """
        if len(self.answer_history) == 1:  # Q1: S3
            if is_correct:
                self.current_seniority = 'senior'
                self.current_level = 5
                self.path_state = 'S5'
            else:
                self.current_seniority = 'senior'
                self.current_level = 1
                self.path_state = 'S1'

        elif len(self.answer_history) == 2:
            if self.path_state == 'S5':
                if is_correct:
                    self._finish_test("LEVELS5")
                else:
                    self.current_seniority = 'senior'
                    self.current_level = 4
                    self.path_state = 'S4'
            elif self.path_state == 'S1':
                if is_correct:
                    self.current_seniority = 'senior'
                    self.current_level = 2
                    self.path_state = 'S2'
                else:
                    self.current_seniority = 'middle'
                    self.current_level = 3
                    self.path_state = 'M3'

        elif len(self.answer_history) == 3:
            if self.path_state == 'S4':
                if is_correct:
                    self._finish_test("LEVELS4")
                else:
                    self._finish_test("LEVELS3")
                return self._get_result()
            elif self.path_state == 'S2':
                if is_correct:
                    self._finish_test("LEVELS2")
                else:
                    self._finish_test("LEVELS1")
                return self._get_result()
            elif self.path_state == 'M3':
                if is_correct:
                    self.current_seniority = 'middle'
                    self.current_level = 5
                    self.path_state = 'M5'
                else:
                    self.current_seniority = 'middle'
                    self.current_level = 1
                    self.path_state = 'M1'

        elif len(self.answer_history) == 4:
            if self.path_state == 'M5':
                if is_correct:
                    self._finish_test("LEVELM5")
                else:
                    self.current_seniority = 'middle'
                    self.current_level = 4
                    self.path_state = 'M4'
            elif self.path_state == 'M1':
                if is_correct:
                    self.current_seniority = 'middle'
                    self.current_level = 2
                    self.path_state = 'M2'
                else:
                    self._finish_test("LEVELM0", failed=True)

        elif len(self.answer_history) == 5:
            if self.path_state == 'M4':
                if is_correct:
                    self._finish_test("LEVELM4")
                else:
                    self._finish_test("LEVELM3")
            elif self.path_state == 'M2':
                if is_correct:
                    self._finish_test("LEVELM2")
                else:
                    self._finish_test("LEVELM1")

        return self._get_result()


    def _update_state_after_answer_fresher(self, is_correct):
        if len(self.answer_history) == 1:  # Q1: F3
            if is_correct:
                self.current_seniority = 'fresher'
                self.current_level = 5
                self.path_state = 'F5'
            else:
                self.current_seniority = 'fresher'
                self.current_level = 1
                self.path_state = 'F1'

        elif len(self.answer_history) == 2:
            if self.path_state == 'F5':
                if is_correct:
                    self.current_seniority = 'junior'
                    self.current_level = 3
                    self.path_state = 'J3'
                else:
                    self.current_seniority = 'fresher'
                    self.current_level = 4
                    self.path_state = 'F4'
            elif self.path_state == 'F1':
                if is_correct:
                    self.current_seniority = 'fresher'
                    self.current_level = 2
                    self.path_state = 'F2'
                else:
                    self._finish_test("LEVELF0", failed=True)
                    return self._get_result()

        elif len(self.answer_history) == 3:
            if self.path_state == 'F4':
                if is_correct:
                    self._finish_test("LEVELF4")
                else:
                    self._finish_test("LEVELF3")
                return self._get_result()
            elif self.path_state == 'F2':
                if is_correct:
                    self._finish_test("LEVELF2")
                else:
                    self._finish_test("LEVELF1")
                return self._get_result()
            elif self.path_state == 'J3':
                if is_correct:
                    self.current_seniority = 'junior'
                    self.current_level = 5
                    self.path_state = 'J5'
                else:
                    self.current_seniority = 'junior'
                    self.current_level = 1
                    self.path_state = 'J1'

        elif len(self.answer_history) == 4:
            if self.path_state == 'J5':
                if is_correct:
                    self._finish_test("LEVELJ5")
                else:
                    self.current_seniority = 'junior'
                    self.current_level = 4
                    self.path_state = 'J4'
            elif self.path_state == 'J1':
                if is_correct:
                    self.current_seniority = 'junior'
                    self.current_level = 2
                    self.path_state = 'J2'
                else:
                    self._finish_test("LEVELF5")

        elif len(self.answer_history) == 5:
            if self.path_state == 'J4':
                if is_correct:
                    self._finish_test("LEVELJ4")
                else:
                    self._finish_test("LEVELJ3")
            elif self.path_state == 'J2':
                if is_correct:
                    self._finish_test("LEVELJ2")
                else:
                    self._finish_test("LEVELJ1")

        return self._get_result()



    def _update_state_after_answer_junior(self, is_correct):
        if len(self.answer_history) == 1:
            if is_correct:
                self.current_seniority = 'junior'
                self.current_level = 5
                self.path_state = 'J5'
            else:
                self.current_seniority = 'junior'
                self.current_level = 1
                self.path_state = 'J1'

        elif len(self.answer_history) == 2:
            if self.path_state == 'J5':
                if is_correct:
                    self.current_seniority = 'middle'
                    self.current_level = 3
                    self.path_state = 'M3'
                else:
                    self.current_seniority = 'junior'
                    self.current_level = 4
                    self.path_state = 'J4'
            elif self.path_state == 'J1':
                if is_correct:
                    self.current_seniority = 'junior'
                    self.current_level = 2
                    self.path_state = 'J2'
                else:
                    self.current_seniority = 'fresher'
                    self.current_level = 3
                    self.path_state = 'F3'

        elif len(self.answer_history) == 3:
            if self.path_state == 'J2':
                if is_correct:
                    self._finish_test("LEVELJ2")
                else:
                    self._finish_test("LEVELJ1")
                return self._get_result()
            elif self.path_state == 'J4':
                if is_correct:
                    self._finish_test("LEVELJ4")
                else:
                    self._finish_test("LEVELJ3")
                return self._get_result()
            elif self.path_state == 'M3':
                if is_correct:
                    self.current_seniority = 'middle'
                    self.current_level = 5
                    self.path_state = 'M5'
                else:
                    self.current_seniority = 'middle'
                    self.current_level = 1
                    self.path_state = 'M1'
            elif self.path_state == 'F3':
                if is_correct:
                    self.current_seniority = 'fresher'
                    self.current_level = 5
                    self.path_state = 'F5'
                else:
                    self.current_seniority = 'fresher'
                    self.current_level = 1
                    self.path_state = 'F1'

        elif len(self.answer_history) == 4:
            if self.path_state == 'M5':
                if is_correct:
                    self._finish_test("LEVELM5")
                else:
                    self.current_seniority = 'middle'
                    self.current_level = 4
                    self.path_state = 'M4'
            elif self.path_state == 'M1':
                if is_correct:
                    self.current_seniority = 'middle'
                    self.current_level = 2
                    self.path_state = 'M2'
                else:
                    self._finish_test("LEVELJ5")
                return self._get_result()
            elif self.path_state == 'F5':
                if is_correct:
                    self._finish_test("LEVELF5")
                else:
                    self.current_seniority = 'fresher'
                    self.current_level = 4
                    self.path_state = 'F4'
            elif self.path_state == 'F1':
                if is_correct:
                    self.current_seniority = 'fresher'
                    self.current_level = 2
                    self.path_state = 'F2'
                else:
                    self._finish_test("LEVELF0", failed=True)
                return self._get_result()

        elif len(self.answer_history) == 5:
            if self.path_state == 'M4':
                if is_correct:
                    self._finish_test("LEVELM4")
                else:
                    self._finish_test("LEVELM3")
            elif self.path_state == 'M2':
                if is_correct:
                    self._finish_test("LEVELM2")
                else:
                    self._finish_test("LEVELM1")
            elif self.path_state == 'F4':
                if is_correct:
                    self._finish_test("LEVELF4")
                else:
                    self._finish_test("LEVELF3")
            elif self.path_state == 'F2':
                if is_correct:
                    self._finish_test("LEVELF2")
                else:
                    self._finish_test("LEVELF1")

        return self._get_result()


# === LOAD DATA ===
@st.cache_data
def load_questions():
    with open("merged_file.json", "r", encoding="utf-8") as f:
        return json.load(f)

# === STREAMLIT STATE ===
if "skills_queue" not in st.session_state:
    st.session_state["skills_queue"] = SKILLS.copy()
    st.session_state["current_skill"] = st.session_state["skills_queue"].pop(0)
    st.session_state["results_per_skill"] = {}
    st.session_state["session"] = None
    st.session_state["question"] = None
    st.session_state["account"] = ""

questions_data_all = load_questions()

# === UI HEADER ===
st.set_page_config(page_title="Adaptive Multi-Skill Quiz", layout="centered")
st.title("🎯 Adaptive Skill Testing - Multi Skill")
st.markdown("**💡 Skills to be tested:** html, css, javascript, react, github")

current_skill = st.session_state["current_skill"]
st.subheader(f"🔧 Đang kiểm tra kỹ năng: {current_skill.upper()}")

questions_data = [q for q in questions_data_all if q['skill'] == current_skill]

# === ACCOUNT INPUT ===
if st.session_state["session"] is None:
    st.subheader("👤 Nhập tên hoặc email của bạn:")
    account = st.text_input("Account:", value=st.session_state.get("account", ""), key="account_input")
    st.subheader("Chọn cấp độ bắt đầu:")
    seniority = st.selectbox("👉 Chọn:", ['fresher', 'junior', 'middle', 'senior'])

    if st.button("🚀 Bắt đầu kiểm tra"):
        if not account.strip():
            st.warning("❌ Vui lòng nhập tên hoặc email của bạn.")
        else:
            st.session_state["account"] = account
            engine = AdaptiveTestingEngine(questions_data)
            session = AdaptiveTestSession(engine, start_seniority=seniority)
            st.session_state["session"] = session
            st.session_state["question"] = session.get_next_question()
            st.rerun()

# === SHOW QUESTION ===
elif not st.session_state["session"].is_finished:
    session = st.session_state["session"]
    question = st.session_state["question"]

    level = session.engine.format_level_string(session.current_seniority, session.current_level)
    st.subheader(f"📌 Câu hỏi mức độ: {level}")
    st.markdown(f"**❓ {question['question']}**")

    for i, option in enumerate(question["options"]):
        if st.button(option["description"], key=f"opt_{i}"):
            result = session.submit_answer(i)
            if result.get("answer_history"):
                st.success("✅ ĐÚNG") if result['answer_history']['is_correct'] else st.error("❌ SAI")

            if not result["is_finished"]:
                st.session_state["question"] = session.get_next_question()
                st.rerun()
            else:
                st.rerun()

# === SHOW RESULT AND MOVE TO NEXT SKILL ===
elif st.session_state["session"].is_finished:
    result = st.session_state["session"].final_result
    failed = st.session_state["session"].failed
    account = st.session_state["account"]

    st.success("🎉 Hoàn thành kỹ năng!")
    st.write(f"🏁 Kết quả kỹ năng {current_skill.upper()}: **{result}**")

    st.session_state["results_per_skill"][current_skill] = result

    if "result_saved" not in st.session_state:
        final_result = {
            "account": account,
            "skill": current_skill,
            "final_result": result,
            "failed": failed,
            "answer_history": st.session_state["session"].answer_history,
            "datetime": datetime.now().isoformat()
        }

        try:
            filepath = save_result_to_file(account, final_result)
            st.info(f"💾 Đã lưu cục bộ tại: {filepath}")
        except Exception as e:
            st.error(f"❌ Lỗi khi lưu file cục bộ: {e}")

        try:
            save_to_github(account, result, st.session_state["session"].answer_history, failed)
        except Exception as e:
            st.error(f"❌ Lỗi khi lưu GitHub: {e}")

        st.session_state["result_saved"] = True

    # Tiếp tục skill kế
    if st.button("➡️ Tiếp tục kỹ năng tiếp theo"):
        if st.session_state["skills_queue"]:
            st.session_state["current_skill"] = st.session_state["skills_queue"].pop(0)
            st.session_state["session"] = None
            st.session_state["question"] = None
            st.session_state.pop("result_saved", None)
            st.rerun()
        else:
            st.session_state["finished_all"] = True
            st.rerun()

# === FINAL SUMMARY ===
if st.session_state.get("finished_all"):
    st.title("📊 TỔNG KẾT TOÀN BỘ KỸ NĂNG")
    for skill, level in st.session_state["results_per_skill"].items():
        st.write(f"✅ {skill.upper()}: {level}")

    if st.button("🔁 Làm lại toàn bộ"):
        st.session_state.clear()
        st.rerun()
