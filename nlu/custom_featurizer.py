# nlu/custom_featurizer.py

import numpy as np
import warnings
from typing import Any, Dict
from sentence_transformers import SentenceTransformer

from rasa.engine.graph import GraphComponent, ExecutionContext
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.training_data.message import Message
from rasa.engine.recipes.default_recipe import DefaultV1Recipe

# Ẩn cảnh báo không quan trọng từ PyTorch
warnings.filterwarnings("ignore", category=FutureWarning)


@DefaultV1Recipe.register(
    component_types=["feature_extractor"], is_trainable=False
)
class SentenceTransformerFeaturizer(GraphComponent):
    """Custom featurizer sử dụng SentenceTransformers để tạo embedding."""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Cấu hình mặc định."""
        return {"model_name": "paraphrase-multilingual-MiniLM-L12-v2"}

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        model_name = self.config.get("model_name")
        print(f"[CustomFeaturizer] Loading SentenceTransformer model: {model_name}")
        self.model = SentenceTransformer(model_name)

    @classmethod
    def create(
        cls,
        config: Dict[str, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "SentenceTransformerFeaturizer":
        return cls(config)

    def process(self, message: Message, **kwargs: Any) -> None:
        text = message.get("text")
        if not text:
            return

        embedding = self.model.encode([text])[0]
        message.set("text_features", np.array(embedding).reshape(1, -1))
        print(f"[CustomFeaturizer] Embedded '{text[:40]}...' -> vector size {embedding.shape[0]}")
