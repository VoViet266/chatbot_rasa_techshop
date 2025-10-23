# actions/actions.py

from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import Restarted, SessionStarted, ActionExecuted

class ActionCustomRestart(Action):
    def name(self) -> Text:
    
        return "action_restart_slot"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        print("làm mới!!!!")
        return [Restarted()]