from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

class ActionHumanHandoff(Action):
    def name(self) -> Text:
        return "action_human_handoff"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
    
        
        html_message = """
        <div style="background-color: #fff; border: 1px solid #e0e0e0; border-radius: 10px; padding: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); font-family: sans-serif;">
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                <span style="font-size: 24px; margin-right: 10px;">💁‍♀️</span>
                <h3 style="color: #d32f2f; margin: 0; font-size: 16px; font-weight: bold;">Hỗ Trợ Trực Tiếp</h3>
            </div>
            <p style="font-size: 14px; color: #333; line-height: 1.5; margin-bottom: 12px;">
                Dạ, em đã ghi nhận yêu cầu. Hiện tại các bạn nhân viên đang bận, anh/chị vui lòng liên hệ qua:
            </p>
            <div style="background-color: #f9fafb; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                <div style="margin-bottom: 8px; display: flex; align-items: center;">
                    <span style="margin-right: 8px;">📞</span>
                    <span style="font-weight: 600; font-size: 14px;">Hotline:</span>
                    <a href="tel:19001234" style="color: #d32f2f; text-decoration: none; margin-left: 5px; font-weight: bold;">1900 1234</a>
                </div>
                <div style="margin-bottom: 8px; display: flex; align-items: center;">
                    <span style="margin-right: 8px;">📧</span>
                    <span style="font-weight: 600; font-size: 14px;">Email:</span>
                    <a href="mailto:support@techshop.com" style="color: #1976d2; text-decoration: none; margin-left: 5px;">support@techshop.com</a>
                </div>
                <div style="display: flex; align-items: flex-start;">
                    <span style="margin-right: 8px;">🏠</span>
                    <span style="font-size: 14px;">Ghé trực tiếp cửa hàng gần nhất.</span>
                </div>
            </div>
            <p style="font-size: 13px; color: #666; margin: 0; font-style: italic; text-align: center;">
                Em xin lỗi vì sự bất tiện này ạ! ❤️
            </p>
        </div>
        """
        
        dispatcher.utter_message(text=html_message)
        return []
