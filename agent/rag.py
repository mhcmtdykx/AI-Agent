"""
RAG模块 - 检索增强生成
支持文档加载、文本分割、向量检索
"""
import os
import re
import json
import math
from typing import List, Dict, Tuple, Optional
from collections import Counter


class Document:
    """文档类"""
    def __init__(self, content: str, metadata: Dict = None):
        self.content = content
        self.metadata = metadata or {}
    
    def __repr__(self):
        return "Document(content={}, metadata={})".format(
            self.content[:50] + "..." if len(self.content) > 50 else self.content,
            self.metadata
        )


class TextSplitter:
    """文本分割器"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        初始化文本分割器
        
        Args:
            chunk_size: 每个块的最大字符数
            chunk_overlap: 块之间的重叠字符数
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split_text(self, text: str) -> List[str]:
        """分割文本"""
        # 先按段落分割
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 如果当前块加上新段落超过限制，保存当前块并开始新块
            if len(current_chunk) + len(para) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # 保留重叠部分
                if self.chunk_overlap > 0 and current_chunk:
                    current_chunk = current_chunk[-self.chunk_overlap:] + "\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk += "\n" + para if current_chunk else para
        
        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # 如果单个段落太长，进一步分割
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > self.chunk_size:
                # 按句子分割
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
    """简单的向量存储（基于TF-IDF）"""
    
    def __init__(self):
        self.documents: List[Document] = []
        self.idf_scores: Dict[str, float] = {}
        self.doc_vectors: List[Dict[str, float]] = []
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词（支持中文）"""
        # 中文按字符分词，英文按单词分词
        tokens = []
        # 提取中文字符
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.extend(chinese_chars)
        # 提取英文单词
        english_words = re.findall(r'[a-zA-Z]+', text.lower())
        tokens.extend(english_words)
        return tokens
    
    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """计算词频"""
        counter = Counter(tokens)
        total = len(tokens)
        return {word: count / total for word, count in counter.items()}
    
    def _compute_idf(self):
        """计算逆文档频率"""
        doc_count = len(self.documents)
        word_doc_count = Counter()
        
        for doc in self.documents:
            tokens = set(self._tokenize(doc.content))
            for token in tokens:
                word_doc_count[token] += 1
        
        self.idf_scores = {
            word: math.log(doc_count / (count + 1)) + 1
            for word, count in word_doc_count.items()
        }
    
    def add_documents(self, documents: List[Document]):
        """添加文档"""
        self.documents.extend(documents)
        self._compute_idf()
        
        # 计算每个文档的TF-IDF向量
        self.doc_vectors = []
        for doc in self.documents:
            tokens = self._tokenize(doc.content)
            tf = self._compute_tf(tokens)
            vector = {
                word: tf_val * self.idf_scores.get(word, 1.0)
                for word, tf_val in tf.items()
            }
            self.doc_vectors.append(vector)
    
    def search(self, query: str, top_k: int = 3) -> List[Tuple[Document, float]]:
        """搜索最相关的文档"""
        if not self.documents:
            return []
        
        # 计算查询的TF-IDF向量
        query_tokens = self._tokenize(query)
        query_tf = self._compute_tf(query_tokens)
        query_vector = {
            word: tf_val * self.idf_scores.get(word, 1.0)
            for word, tf_val in query_tf.items()
        }
        
        # 计算余弦相似度
        similarities = []
        for doc_vector in self.doc_vectors:
            similarity = self._cosine_similarity(query_vector, doc_vector)
            similarities.append(similarity)
        
        # 排序并返回top_k
        indexed_similarities = list(enumerate(similarities))
        indexed_similarities.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for idx, score in indexed_similarities[:top_k]:
            if score > 0:  # 只返回相关度大于0的结果
                results.append((self.documents[idx], score))
        
        return results
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """计算余弦相似度"""
        # 获取共同的词
        common_words = set(vec1.keys()) & set(vec2.keys())
        
        if not common_words:
            return 0.0
        
        # 计算点积
        dot_product = sum(vec1[word] * vec2[word] for word in common_words)
        
        # 计算向量长度
        norm1 = math.sqrt(sum(val ** 2 for val in vec1.values()))
        norm2 = math.sqrt(sum(val ** 2 for val in vec2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def clear(self):
        """清空存储"""
        self.documents.clear()
        self.doc_vectors.clear()
        self.idf_scores.clear()


class DocumentLoader:
    """文档加载器"""
    
    @staticmethod
    def load_text(file_path: str) -> Document:
        """加载文本文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        metadata = {
            "source": file_path,
            "filename": os.path.basename(file_path)
        }
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
                    print("加载文件失败 {}: {}".format(file_path, e))
        
        return documents


class RAGSystem:
    """RAG系统"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        初始化RAG系统
        
        Args:
            chunk_size: 文本块大小
            chunk_overlap: 块重叠大小
        """
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
        
        context_parts = []
        for doc, score in results:
            context_parts.append(doc.content)
        
        return "\n\n---\n\n".join(context_parts)
    
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
