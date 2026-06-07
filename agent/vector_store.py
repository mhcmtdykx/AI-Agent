"""
公共向量检索模块 - 基于 TF-IDF 的文本相似度检索
供 RAG 和长期记忆系统共用，避免重复实现
"""
import math
import re
from typing import List, Dict, Tuple, Optional
from collections import Counter


class TFIDFIndex:
    """TF-IDF 向量索引，支持增量添加和批量添加"""

    def __init__(self):
        self.texts: List[str] = []
        self.idf_scores: Dict[str, float] = {}
        self.doc_vectors: List[Dict[str, float]] = []
        self._dirty = False  # 标记是否有新文档未重建 IDF

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """分词：中文按字符，英文按单词"""
        tokens = []
        tokens.extend(re.findall(r'[\u4e00-\u9fff]', text))
        tokens.extend(re.findall(r'[a-zA-Z]+', text.lower()))
        return tokens

    @staticmethod
    def _compute_tf(tokens: List[str]) -> Dict[str, float]:
        """计算词频"""
        counter = Counter(tokens)
        total = len(tokens)
        if total == 0:
            return {}
        return {word: count / total for word, count in counter.items()}

    def _rebuild_idf(self):
        """重建 IDF（仅在有新文档时调用）"""
        doc_count = len(self.texts)
        if doc_count == 0:
            self.idf_scores = {}
            return
        word_doc_count: Counter = Counter()
        for text in self.texts:
            for token in set(self.tokenize(text)):
                word_doc_count[token] += 1
        self.idf_scores = {
            word: math.log(doc_count / (count + 1)) + 1
            for word, count in word_doc_count.items()
        }
        self._dirty = False

    def _text_to_vector(self, text: str) -> Dict[str, float]:
        """将文本转为 TF-IDF 向量"""
        tokens = self.tokenize(text)
        tf = self._compute_tf(tokens)
        return {
            word: tf_val * self.idf_scores.get(word, 1.0)
            for word, tf_val in tf.items()
        }

    def add(self, text: str):
        """添加单条文本（延迟重建 IDF）"""
        self.texts.append(text)
        self._dirty = True

    def add_batch(self, texts: List[str]):
        """批量添加文本（只重建一次 IDF）"""
        self.texts.extend(texts)
        self._dirty = True
        self._rebuild_idf()
        # 为所有新增文档计算向量
        for text in texts:
            self.doc_vectors.append(self._text_to_vector(text))

    def _ensure_built(self):
        """确保 IDF 和向量已构建"""
        if self._dirty:
            self._rebuild_idf()
            # 为尚未计算向量的文档补充向量
            while len(self.doc_vectors) < len(self.texts):
                idx = len(self.doc_vectors)
                self.doc_vectors.append(self._text_to_vector(self.texts[idx]))

    @staticmethod
    def _cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """计算余弦相似度"""
        common_words = set(vec1.keys()) & set(vec2.keys())
        if not common_words:
            return 0.0
        dot_product = sum(vec1[w] * vec2[w] for w in common_words)
        norm1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        norm2 = math.sqrt(sum(v ** 2 for v in vec2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def search(self, query: str, top_k: int = 3) -> List[Tuple[int, float]]:
        """
        搜索最相似的文本

        Returns:
            [(index, score), ...] 按相似度降序
        """
        self._ensure_built()
        if not self.texts:
            return []

        query_vector = self._text_to_vector(query)
        similarities = [
            (i, self._cosine_similarity(query_vector, doc_vec))
            for i, doc_vec in enumerate(self.doc_vectors)
        ]
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [(idx, score) for idx, score in similarities[:top_k] if score > 0]

    def clear(self):
        """清空索引"""
        self.texts.clear()
        self.doc_vectors.clear()
        self.idf_scores.clear()
        self._dirty = False
