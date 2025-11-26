import re
import unicodedata
from typing import Any, Dict, List, Text, Union

from rasa.engine.graph import GraphComponent, ExecutionContext
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.training_data.message import Message
from rasa.shared.nlu.constants import TEXT
from rasa.shared.nlu.training_data.training_data import TrainingData


@DefaultV1Recipe.register(
    DefaultV1Recipe.ComponentType.MESSAGE_FEATURIZER, is_trainable=False
)
class VietnameseTextNormalizer(GraphComponent):
    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "VietnameseTextNormalizer":
        return cls(config, resource)

    def __init__(self, config: Dict[Text, Any], resource: Resource) -> None:
        self.config = config
        self._resource = resource
        self.spell_corrections = self._load_spell_corrections()
    
    def _load_spell_corrections(self) -> Dict[str, Union[str, List[str]]]:
        import json
        import os
        json_path = os.path.join(
            os.path.dirname(__file__),  
            "vi-nsw-dict-ecommerce.json"
        )
        
        corrections = {}
        
        try:
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    corrections = json.load(f)
                
                print(f"Loaded {len(corrections)} entries from vi-nsw-dict.json")
            else:
                corrections = self._get_fallback_corrections()
        except Exception as e:
            print(f"Error loading vi-nsw-dict.json: {e}, using fallback")
            corrections = self._get_fallback_corrections()
        
        return corrections

    def normalize_unicode(self, text: str) -> str:
        """Chuẩn hóa unicode về dạng NFC."""
        return unicodedata.normalize('NFC', text)

    def clean_text(self, text: str) -> str:
        """Làm sạch văn bản - loại bỏ khoảng trắng thừa."""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def correct_spelling(self, text: str) -> str:
        words = text.split()
        corrected_words = []
        
        for word in words:
            word_lower = word.lower()
            
            if word_lower in self.spell_corrections:
                correction = self.spell_corrections[word_lower]
                
                # Support both string and array format
                if isinstance(correction, list):
                    # Nếu là array, lấy phần tử đầu tiên
                    corrected_words.append(correction[0] if correction else word)
                else:
                    # Nếu là string, dùng trực tiếp
                    corrected_words.append(correction)
            else:
                corrected_words.append(word)
                
        return ' '.join(corrected_words)

    def normalize_text(self, text: str) -> str:
        """Chuẩn hóa văn bản hoàn chỉnh."""
        if not text:
            return ""
        text = self.normalize_unicode(text)
        text = self.clean_text(text)
        text = self.correct_spelling(text)
        return text

    def process(self, messages: List[Message]) -> List[Message]:
        """
        Chỉ chạy khi nhận tin nhắn từ người dùng (Inference).
        Giúp đưa input 'teencode' về dạng chuẩn để khớp với Training Data.
        """
        for message in messages:
            original_text = message.get(TEXT)
            if original_text:
                normalized_text = self.normalize_text(original_text)
                message.set(TEXT, normalized_text)
        return messages

    def process_training_data(self, training_data: TrainingData) -> TrainingData:
        """
        Process training data - required by Rasa.
        KHÔNG can thiệp vào training data để tránh lỗi lệch Entity offsets.
        """
        return training_data

    def train(self, training_data: TrainingData) -> Resource:
        """
        Train component - không cần train gì.
        Giả định dữ liệu trong nlu.yml đã được viết chuẩn.
        """
        return self._resource