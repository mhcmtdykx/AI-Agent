"""
RAG模块 - 检索增强生成
支持文档加载、文本分割、向量检索
"""
import os
import re
from typing import List, Dict, Tuple

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
    """文本分割器"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        """分割文本"""
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

        # 如果单个段落太长，进一步按句子分割
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > self.chunk_size:
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
            else:
                final_chunks.append(chunk)

        return final_chunks if final_chunks else [text]

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """分割文档列表"""
        split_docs = []
        for doc in documents:
            chunks = self.split_text(doc.content)
            for i, chunk in enumerate(chunks):
                metadata = doc.metadata.copy()
                metadata["chunk_index"] = i
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

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.vector_store = SimpleVectorStore()
        self.text_splitter = TextSplitter(chunk_size, chunk_overlap)
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


# 全局RAG实例缓存
_rag_instances = {}


def get_rag_system(user_id: str = None) -> RAGSystem:
    """获取RAG系统实例（支持用户隔离）"""
    if user_id:
        if user_id not in _rag_instances:
            _rag_instances[user_id] = RAGSystem()
        return _rag_instances[user_id]
    # 无 user_id 时返回全局实例（向后兼容）
    if "_global" not in _rag_instances:
        _rag_instances["_global"] = RAGSystem()
    return _rag_instances["_global"]


# 保持向后兼容
rag_system = get_rag_system()
