import numpy as np
import warnings
from typing import Any, Dict, List,  Text
from sentence_transformers import SentenceTransformer

from rasa.engine.graph import GraphComponent, ExecutionContext
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.training_data.message import Message
from rasa.shared.nlu.training_data.training_data import TrainingData
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.shared.nlu.training_data.features import Features
from rasa.shared.nlu.constants import TEXT, FEATURE_TYPE_SENTENCE

# Ẩn cảnh báo không cần thiết
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


@DefaultV1Recipe.register(
    component_types=["feature_extractor"], is_trainable=False
)
class SentenceTransformerFeaturizer(GraphComponent):
    """
    Custom featurizer sử dụng SentenceTransformers để tạo embedding vector.
    
    Tương thích với Rasa 3.x và hoạt động với DIETClassifier.
    Hỗ trợ batch processing để tăng tốc độ xử lý.
    """

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Cấu hình mặc định của component."""
        return {
            "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
            "batch_size": 32,  # Số lượng messages xử lý cùng lúc
            "cache_dir": None,  # Thư mục cache model (None = dùng mặc định)
            "show_progress_bar": False,  # Hiển thị progress bar khi encode
        }

    def __init__(self, config: Dict[str, Any]) -> None:
        """Khởi tạo component với cấu hình."""
        self.config = config
        self.model_name = self.config.get("model_name")
        self.batch_size = self.config.get("batch_size", 32)
        self.cache_dir = self.config.get("cache_dir")
        self.show_progress_bar = self.config.get("show_progress_bar", False)
        
        print(f"[SentenceTransformerFeaturizer] Initializing model: {self.model_name}")
        
        try:
            self.model = SentenceTransformer(
                self.model_name,
                cache_folder=self.cache_dir
            )
            print(f"[SentenceTransformerFeaturizer] Model loaded successfully. Embedding dimension: {self.model.get_sentence_embedding_dimension()}")
        except Exception as e:
            raise RuntimeError(f"Failed to load SentenceTransformer model '{self.model_name}': {e}")

    @classmethod
    def create(
        cls,
        config: Dict[str, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "SentenceTransformerFeaturizer":
        """Factory method để tạo instance của component."""
        return cls(config)

    def process(self, messages: List[Message]) -> List[Message]:
        """
        Xử lý danh sách messages trong quá trình inference.
        Sử dụng batch processing để tối ưu hiệu suất.
        """
        # Lọc messages có text
        messages_with_text = [msg for msg in messages if msg.get(TEXT)]
        
        if not messages_with_text:
            return messages
        
        # Batch processing: encode nhiều texts cùng lúc
        texts = [msg.get(TEXT) for msg in messages_with_text]
        
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=self.show_progress_bar,
                convert_to_numpy=True
            )
            
            # Gán features cho từng message
            for msg, embedding in zip(messages_with_text, embeddings):
                self._add_features_to_message(msg, embedding)
                
        except Exception as e:
            print(f"[SentenceTransformerFeaturizer] Error during encoding: {e}")
            # Fallback: xử lý từng message riêng lẻ
            for msg in messages_with_text:
                self._set_features_single(msg)
        
        return messages

    def process_training_data(self, training_data: TrainingData) -> TrainingData:
        """
        Xử lý training data trong quá trình training.
        Sử dụng batch processing để tăng tốc.
        """
        training_examples = training_data.training_examples
        messages_with_text = [msg for msg in training_examples if msg.get(TEXT)]
        
        if not messages_with_text:
            return training_data
        
        print(f"[SentenceTransformerFeaturizer] Processing {len(messages_with_text)} training examples...")
        
        # Batch processing cho training data
        texts = [msg.get(TEXT) for msg in messages_with_text]
        
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=True,  # Luôn hiển thị progress khi training
                convert_to_numpy=True
            )
            
            # Gán features cho từng message
            for msg, embedding in zip(messages_with_text, embeddings):
                self._add_features_to_message(msg, embedding)
            
            print(f"[SentenceTransformerFeaturizer] Successfully encoded {len(messages_with_text)} examples")
            
        except Exception as e:
            print(f"[SentenceTransformerFeaturizer] Error during training encoding: {e}")
            # Fallback
            for msg in messages_with_text:
                self._set_features_single(msg)
        
        return training_data

    def _add_features_to_message(self, message: Message, embedding: np.ndarray) -> None:
        """
        Thêm features vào message theo đúng chuẩn Rasa 3.x.
        
        Args:
            message: Message object cần thêm features
            embedding: Vector embedding (1D array)
        """
        features_array = embedding.reshape(1, -1)
        
        # Tạo Features object với các tham số chuẩn
        features = Features(
            features_array,
            FEATURE_TYPE_SENTENCE,  # Đánh dấu đây là sentence-level features
            TEXT,                   # Attribute name
            self.__class__.__name__ # Origin: tên của component tạo ra features
        )
        
        # Thêm features vào message
        message.add_features(features)

    def _set_features_single(self, message: Message) -> None:
        """
        Xử lý từng message riêng lẻ (fallback method).
        Dùng khi batch processing gặp lỗi.
        """
        text = message.get(TEXT)
        if not text:
            return
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            self._add_features_to_message(message, embedding)
        except Exception as e:
            print(f"[SentenceTransformerFeaturizer] Error encoding text '{text[:50]}...': {e}")

    @classmethod
    def validate_config(cls, config: Dict[Text, Any]) -> None:
        """
        Validate cấu hình của component.
        """
        required_keys = ["model_name"]
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required config key: {key}")