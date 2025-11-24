import unicodedata
from typing import Any, Dict, List, Text

from rasa.engine.graph import GraphComponent, ExecutionContext
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.training_data.training_data import TrainingData
from rasa.shared.nlu.training_data.message import Message
from rasa.shared.nlu.constants import TEXT

@DefaultV1Recipe.register(
    DefaultV1Recipe.ComponentType.MESSAGE_FEATURIZER, is_trainable=True
)
class AccentAugmenter(GraphComponent):
    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "AccentAugmenter":
        return cls(config, model_storage, resource)

    def __init__(
        self,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
    ) -> None:
        self.config = config
        self._resource = resource
        self.augment_enabled = config.get("augment_enabled", True)

    @staticmethod
    def remove_vietnamese_accents(text: str) -> str:
        nfd = unicodedata.normalize('NFD', text)
        output = []
        for char in nfd:
            if unicodedata.category(char) != 'Mn':
                output.append(char)
        text_without_accents = ''.join(output)
        text_without_accents = text_without_accents.replace('đ', 'd').replace('Đ', 'D')
        return unicodedata.normalize('NFC', text_without_accents)

    def has_vietnamese_accents(self, text: str) -> bool:
        return text != self.remove_vietnamese_accents(text)

    def process_training_data(self, training_data: TrainingData) -> TrainingData:
        """
        Required by Rasa - augment training data here.
        """
        if not self.augment_enabled:
            return training_data
        
        new_examples = []
        
        for example in training_data.training_examples:
            text = example.get(TEXT)
            if not text:
                continue
            
            # Chỉ augment nếu text có dấu
            if self.has_vietnamese_accents(text):
                text_without_accents = self.remove_vietnamese_accents(text)
                
                # Tạo message mới
                augmented_message = Message(data={TEXT: text_without_accents})
                
                # Copy Intent
                if example.data.get("intent"):
                    augmented_message.set("intent", example.data.get("intent"))
                
                if example.data.get("entities"):
                    augmented_entities = []
                    for entity in example.data.get("entities"):
                        aug_entity = entity.copy()
                        aug_entity["value"] = self.remove_vietnamese_accents(aug_entity["value"])
                        augmented_entities.append(aug_entity)
                    augmented_message.set("entities", augmented_entities)
                
                new_examples.append(augmented_message)
        
        # Thêm tất cả ví dụ mới vào training data
        training_data.training_examples.extend(new_examples)
        print(f"✓ AccentAugmenter: Added {len(new_examples)} accent-free examples")
        
        return training_data

    def train(self, training_data: TrainingData) -> Resource:
        """Train method - augmentation already done in process_training_data."""
        return self._resource

    def process(self, messages: List[Message]) -> List[Message]:
        """Inference không làm gì cả."""
        return messages