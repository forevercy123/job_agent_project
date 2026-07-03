from tools.memory_tool import get_memory_vector_store
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


def calculate_jd_resume_score(resume_text, jd_text):
    vdb = get_memory_vector_store()
    embed = vdb._embedding_function
    # 向量化
    resume_vec = np.array(embed.embed_query(resume_text)).reshape(1, -1)
    jd_vec = np.array(embed.embed_query(jd_text)).reshape(1, -1)
    # 余弦相似度 0~1 → 转0~100分
    score = cosine_similarity(resume_vec, jd_vec)[0][0] * 100
    return round(score, 2)
