from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import (
    Restarted, 
    AllSlotsReset,
    ActiveLoop  
)

class ActionCustomRestart(Action):
    def name(self) -> Text:
        return "action_restart_slot"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        print("Restarting the conversation and resetting all slots.")
        
        return [
            ActiveLoop(None),  # Deactivate form hiện tại
            AllSlotsReset(),   # Reset tất cả slots
            Restarted()        # Restart conversation
        ]