"""
RAG模块 - 检索增强生成
支持文档加载、文本分割、向量检索
"""
import os
import re
from typing import List, Dict, Tuple, Literal
from collections import Counter

from .vector_store import TFIDFIndex


class Document:
    """文档类"""
    def __init__(self, content: str, metadata: Dict = None):
        self.content = content
        self.metadata = metadata or {}

    def __repr__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Document(content={preview}, metadata={self.metadata})"


class TextSplitter:
    """文本分割器，支持多种切分策略"""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        strategy: Literal["paragraph", "markdown", "semantic"] = "paragraph"
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy

    def split_text(self, text: str) -> List[str]:
        """根据策略分割文本"""
        if self.strategy == "markdown":
            return self._split_by_markdown(text)
        elif self.strategy == "semantic":
            return self._split_by_semantic(text)
        else:
            return self._split_by_paragraph(text)

    def _split_by_paragraph(self, text: str) -> List[str]:
        """按段落分割（原有策略）"""
        paragraphs = re.split(r'\n\s*\n', text)

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                if self.chunk_overlap > 0 and current_chunk:
                    current_chunk = current_chunk[-self.chunk_overlap:] + "\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk += "\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return self._split_long_chunks(chunks) if chunks else [text]

    def _split_by_markdown(self, text: str) -> List[str]:
        """按Markdown标题层级切分

        策略：
        1. 按一级标题(# )分割为大块
        2. 每个大块内按二级标题(## )分割为中块
        3. 如果中块仍超长，继续按三级标题(### )分割
        4. 最后按句子兜底分割超长块
        """
        # 按一级标题分割
        sections = re.split(r'(?=^# )', text, flags=re.MULTILINE)
        sections = [s.strip() for s in sections if s.strip()]

        chunks = []
        for section in sections:
            if len(section) <= self.chunk_size:
                chunks.append(section)
                continue

            # 按二级标题分割
            sub_sections = re.split(r'(?=^## )', section, flags=re.MULTILINE)
            sub_sections = [s.strip() for s in sub_sections if s.strip()]

            current_chunk = ""
            for sub in sub_sections:
                if len(sub) <= self.chunk_size:
                    if len(current_chunk) + len(sub) > self.chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sub
                    else:
                        current_chunk += "\n\n" + sub if current_chunk else sub
                else:
                    # 按三级标题分割
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = ""
                    sub_sub_sections = re.split(r'(?=^### )', sub, flags=re.MULTILINE)
                    for sss in sub_sub_sections:
                        sss = sss.strip()
                        if not sss:
                            continue
                        if len(sss) <= self.chunk_size:
                            chunks.append(sss)
                        else:
                            # 按四级标题或段落分割
                            sub4 = re.split(r'(?=^#### )', sss, flags=re.MULTILINE)
                            for s in sub4:
                                s = s.strip()
                                if s:
                                    if len(s) <= self.chunk_size:
                                        chunks.append(s)
                                    else:
                                        # 兜底：按段落分割
                                        para_chunks = self._split_by_paragraph(s)
                                        chunks.extend(para_chunks)

            if current_chunk.strip():
                chunks.append(current_chunk.strip())

        return chunks if chunks else [text]

    def _split_by_semantic(self, text: str) -> List[str]:
        """基于语义相似度的切分

        策略：
        1. 先按句子分割
        2. 计算相邻句子的词袋相似度
        3. 在相似度低的位置切分（语义转折点）
        4. 合并小块直到达到chunk_size
        """
        # 按句子分割
        sentences = re.split(r'(?<=[。！？.!?])\s*', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            return [text]

        # 计算相邻句子的相似度
        similarities = []
        for i in range(len(sentences) - 1):
            sim = self._compute_similarity(sentences[i], sentences[i + 1])
            similarities.append(sim)

        # 计算切分阈值（低于平均值 - 标准差的位置）
        if similarities:
            avg_sim = sum(similarities) / len(similarities)
            std_sim = (sum((s - avg_sim) ** 2 for s in similarities) / len(similarities)) ** 0.5
            threshold = max(avg_sim - std_sim, 0.1)  # 最低阈值0.1
        else:
            threshold = 0.3

        # 在低相似度位置切分
        split_points = [0]
        for i, sim in enumerate(similarities):
            if sim < threshold:
                split_points.append(i + 1)
        split_points.append(len(sentences))

        # 生成初始块
        raw_chunks = []
        for i in range(len(split_points) - 1):
            start = split_points[i]
            end = split_points[i + 1]
            chunk = " ".join(sentences[start:end])
            if chunk.strip():
                raw_chunks.append(chunk.strip())

        # 合并小块，分割大块
        return self._merge_small_chunks(raw_chunks)

    @staticmethod
    def _compute_similarity(text1: str, text2: str) -> float:
        """计算两段文本的词袋余弦相似度"""
        def tokenize(text: str) -> List[str]:
            tokens = []
            tokens.extend(re.findall(r'[\u4e00-\u9fff]', text))
            tokens.extend(re.findall(r'[a-zA-Z]+', text.lower()))
            return tokens

        tokens1 = tokenize(text1)
        tokens2 = tokenize(text2)

        if not tokens1 or not tokens2:
            return 0.0

        counter1 = Counter(tokens1)
        counter2 = Counter(tokens2)

        all_words = set(counter1.keys()) | set(counter2.keys())
        dot_product = sum(counter1.get(w, 0) * counter2.get(w, 0) for w in all_words)
        norm1 = sum(v ** 2 for v in counter1.values()) ** 0.5
        norm2 = sum(v ** 2 for v in counter2.values()) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """合并小块，分割大块"""
        if not chunks:
            return []

        result = []
        current_chunk = ""

        for chunk in chunks:
            if len(chunk) > self.chunk_size:
                # 先保存当前累积的块
                if current_chunk:
                    result.append(current_chunk.strip())
                    current_chunk = ""
                # 大块按句子分割
                result.extend(self._split_long_chunks([chunk]))
            elif len(current_chunk) + len(chunk) + 1 > self.chunk_size:
                result.append(current_chunk.strip())
                current_chunk = chunk
            else:
                current_chunk += " " + chunk if current_chunk else chunk

        if current_chunk.strip():
            result.append(current_chunk.strip())

        return result if result else [" ".join(chunks)]

    def _split_long_chunks(self, chunks: List[str]) -> List[str]:
        """将超长块按句子分割"""
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= self.chunk_size:
                final_chunks.append(chunk)
                continue

            sentences = re.split(r'([。！？.!?])', chunk)
            sub_chunk = ""
            for i in range(0, len(sentences), 2):
                sentence = sentences[i]
                if i + 1 < len(sentences):
                    sentence += sentences[i + 1]
                if len(sub_chunk) + len(sentence) > self.chunk_size:
                    if sub_chunk:
                        final_chunks.append(sub_chunk.strip())
                    sub_chunk = sentence
                else:
                    sub_chunk += sentence
            if sub_chunk.strip():
                final_chunks.append(sub_chunk.strip())

        return final_chunks

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """分割文档列表"""
        split_docs = []
        for doc in documents:
            chunks = self.split_text(doc.content)
            for i, chunk in enumerate(chunks):
                metadata = doc.metadata.copy()
                metadata["chunk_index"] = i
                metadata["split_strategy"] = self.strategy
                split_docs.append(Document(chunk, metadata))
        return split_docs


class SimpleVectorStore:
    """基于 TFIDFIndex 的文档向量存储"""

    def __init__(self):
        self.documents: List[Document] = []
        self._index = TFIDFIndex()

    def add_documents(self, documents: List[Document]):
        """批量添加文档（使用批量 IDF 计算，性能更优）"""
        self.documents.extend(documents)
        self._index.add_batch([doc.content for doc in documents])

    def search(self, query: str, top_k: int = 3) -> List[Tuple[Document, float]]:
        """搜索最相关的文档"""
        results = self._index.search(query, top_k)
        return [(self.documents[idx], score) for idx, score in results]

    def clear(self):
        """清空存储"""
        self.documents.clear()
        self._index.clear()


class DocumentLoader:
    """文档加载器"""

    @staticmethod
    def load_text(file_path: str) -> Document:
        """加载文本文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        metadata = {"source": file_path, "filename": os.path.basename(file_path)}
        return Document(content, metadata)

    @staticmethod
    def load_from_string(content: str, metadata: Dict = None) -> Document:
        """从字符串加载"""
        return Document(content, metadata or {})

    @staticmethod
    def load_directory(directory: str, extensions: List[str] = None) -> List[Document]:
        """加载目录下的所有文本文件"""
        if extensions is None:
            extensions = ['.txt', '.md']

        documents = []
        for filename in os.listdir(directory):
            if any(filename.endswith(ext) for ext in extensions):
                file_path = os.path.join(directory, filename)
                try:
                    doc = DocumentLoader.load_text(file_path)
                    documents.append(doc)
                except Exception as e:
                    print(f"加载文件失败 {file_path}: {e}")

        return documents


class RAGSystem:
    """RAG系统"""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        strategy: Literal["paragraph", "markdown", "semantic"] = "paragraph"
    ):
        self.vector_store = SimpleVectorStore()
        self.text_splitter = TextSplitter(chunk_size, chunk_overlap, strategy)
        self.is_loaded = False

    def load_documents(self, documents: List[Document]):
        """加载文档"""
        split_docs = self.text_splitter.split_documents(documents)
        self.vector_store.add_documents(split_docs)
        self.is_loaded = True
        return len(split_docs)

    def load_text(self, text: str, metadata: Dict = None):
        """加载文本"""
        doc = DocumentLoader.load_from_string(text, metadata)
        return self.load_documents([doc])

    def load_file(self, file_path: str):
        """加载文件"""
        doc = DocumentLoader.load_text(file_path)
        return self.load_documents([doc])

    def load_directory(self, directory: str):
        """加载目录"""
        docs = DocumentLoader.load_directory(directory)
        if docs:
            return self.load_documents(docs)
        return 0

    def search(self, query: str, top_k: int = 3) -> List[Tuple[Document, float]]:
        """搜索相关文档"""
        return self.vector_store.search(query, top_k)

    def get_context(self, query: str, top_k: int = 3) -> str:
        """获取相关上下文"""
        results = self.search(query, top_k)
        if not results:
            return ""
        return "\n\n---\n\n".join(doc.content for doc, _ in results)

    def clear(self):
        """清空知识库"""
        self.vector_store.clear()
        self.is_loaded = False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "document_count": len(self.vector_store.documents),
            "is_loaded": self.is_loaded
        }


# 全局RAG实例
rag_system = RAGSystem()
